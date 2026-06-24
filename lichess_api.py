# lichess_api.py
# 5 June 2026

# import modules
import matplotlib.pyplot as plt
import requests
import chess
import chess.pgn
from time import perf_counter as timer
import matplotlib.colors as mcolors
import numpy as np
from collections import defaultdict

# system modules
from dotenv import load_dotenv
import os
import sys

# import Colours class
from utils import Colours

# import Sankey class
from sankey import Sankey

# Inputs class
class Inputs:

    # Lichess API token
    load_dotenv()
    API_TOKEN = os.environ.get("API_TOKEN")

    # input PGN text file
    filename = "root.txt"

    # default parameters
    frequency_threshold = 1e-3

    # default parameters for Lichess opening explorer API requests
    lichess = {
        "url": "https://explorer.lichess.ovh/lichess",
        "headers": {
            "Authorization": f"Bearer {API_TOKEN}"
        },
        "params_base": {
            "speeds": "blitz,rapid",
            "ratings": "2000,2200,2500",
        }
    }
    masters = {
        "url": "https://explorer.lichess.ovh/lichess",
        "headers": {
            "Authorization": f"Bearer {API_TOKEN}"
        }
    }

def walk_lines(node, line = []):
    """Recursively yield every unique root-to-leaf path in the game tree."""
    # if no more moves, this is a leaf — yield the complete line
    if not node.variations:
        yield line
        return

    # recurse into every variation at this node
    for variation in node.variations:
        move_san = node.board().san(variation.move)
        yield from walk_lines(variation, line + [move_san])

def extend_line(line: list[str], player_colour: chess.Color):
    """Recursively extends a chess line by fetching Lichess API explorer data."""
    # build board from current line
    board = chess.Board()
    for move in line:
        board.push_san(move)

    # fetch lichess API for current position
    params = {**Inputs.lichess["params_base"], "play": ",".join(m.uci() for m in board.move_stack)}
    response = requests.get(Inputs.lichess["url"], params = params, headers = Inputs.lichess["headers"])
    response.raise_for_status()
    data = response.json()

    # player's turn
    if board.turn == player_colour:

        # get only the single most popular move
        moves = [data["moves"][0]]

    # opponent's turn
    else:

        # get all moves filtered by the popularity threshold
        moves = [move for move in data["moves"] if (move["white"] + move["draws"] + move["black"]) > Inputs.move_threshold]

    # create empty list to store extended lines
    result = []

    # loop for all possible responses
    for move in moves:

        # append to result
        result.extend([{
            "line": line + [move["san"]],
            "games": move["white"] + move["draws"] + move["black"],
            "opening": move["opening"]["eco"] if move["opening"] else None
        }])

        # recursively call function to extend line
        new_line = line + [move["san"]]
        result.extend(
            extend_line(new_line, player_colour)
        )

    return result

def save_pgn(branches: list[list[str]], event_name: str = "Repertoire"):
    """Saves the given lines as a PGN file containing the full repertoire."""
    # create game object
    game = chess.pgn.Game()
    game.headers["Event"] = event_name

    # loop for each branch in extended move tree
    for branch in branches:

        # separate line from branch
        line = branch["line"]

        # create a board to track the position
        node = game
        board = chess.Board()

        # loop for each move in the line
        for san in line:

            # store move object
            move = board.parse_san(san)

            # check if this move already exists as a child of the current node
            existing = next((child for child in node.variations if child.move == move), None)
            if existing:

                # traverse existing node
                node = existing

            # move is new
            else:

                # add new variation
                node = node.add_variation(move)

            # make move and update board position
            board.push(move)

    # construct output filename
    output_filename = Inputs.filename.replace(".txt", "_repertoire.pgn")

    # save file as .pgn
    with open(output_filename, "w") as f:
        exporter = chess.pgn.FileExporter(f)
        game.accept(exporter)

    print(f"Repertoire saved as {Colours.GREEN}{output_filename}{Colours.END}!")

    return game

def sankey_diagram(input, output):
    """Creates a Sankey diagram of a tree of branches."""
    # create empty nodes and links dictionaries
    nodes = {
        "labels": [],
        "x": [],
        "display_names": [],
        "colours": []
    }
    links = {
        "sources": [],
        "targets": [],
        "values": []
    }

    # get all eco codes in the output
    eco_codes = set([line["opening"] for line in output])
    eco_colours = assign_eco_colours(eco_codes)

    # loop for all positions including input
    for position in input + output:

        # convert line to string and store
        position["string"] = ",".join(position["line"])

        # append to nodes dictionary
        nodes["labels"].append(position["string"])
        nodes["x"].append(len(position["line"]))
        nodes["display_names"].append(f'{position["line"][-1]}\n{position["games"]}')

        # position dictionary contains any ECO codes
        if "opening" in position.keys():

            # position has an associated ECO code
            if position["opening"]:

                # colour nodes according to opening
                nodes["colours"].append(eco_colours[position["opening"]])

            # position has no ECO code
            else:

                # untagged openings are white
                nodes["colours"].append("white")

        # position dictionary contains no ECO codes
        else:

            # all nodes are white
            nodes["colours"].append("white")

    # loop for each output position
    for position in output:

        # append to links dictionary
        links["sources"].append(",".join(position["line"][:-1]))
        links["targets"].append(",".join(position["line"]))
        links["values"].append(position["games"])

    # create Sankey object
    sankey = Sankey(nodes, links)

    leaves = [node for node in sankey.nodes if node.leaves]

    for leaf in leaves:

        # get all upstream nodes
        link_indices = [index for index, target in enumerate(sankey.links["targets"]) if target == leaf.index]
        sources = [sankey.links["sources"][index] for index in link_indices]

    # loop for each node
    for i in range(len(sankey.nodes)):

        # calculate number of unaccounted for positions
        diff = (
            next(d for d in input + output if d["string"] == sankey.nodes[i].labels)["games"]
            - sankey.nodes[i].outflows
        )

        # for white's moves
        if sankey.nodes[i].columns % 2 == 1:

            pass

            #print(f"diff: {diff}")

        # for black's moves
        else:

            # check value is more than zero
            if diff > 0:

                # create leaf node
                nodes["labels"].append(sankey.nodes[i].labels + "-")
                nodes["x"].append(sankey.nodes[i].x + 1)
                nodes["display_names"].append("")
                nodes["colours"].append("gray")

                # create link between nodes
                links["sources"].append(sankey.nodes[i].labels)
                links["targets"].append(sankey.nodes[i].labels + "-")
                links["values"].append(diff)

    # trim nodes and links dictionaries to prevent array length mismatches
    nodes = {key: value for key, value in nodes.items() if key in {"labels", "x", "display_names", "colours"}}
    links = {key: value for key, value in links.items() if key in {"sources", "targets", "values"}}

    print(f"nodes: {nodes}")
    print(f"links: {links}")

    # create NEW Sankey object
    sankey = Sankey(nodes, links)

    # create plot
    fig, ax = plt.subplots()
    sankey.plot(fig, ax)

def assign_eco_colours(eco_codes):
    """Determines a dictionary of colours based on the input opening ECO codes."""
    # parse ECO codes
    parsed = {code: (code[0], int(code[1:])) for code in eco_codes if code is not None}

    # loop for each input ECO code
    letter_groups = defaultdict(list)
    for code, (letter, number) in parsed.items():

        # append the ECO code letter and number separately
        letter_groups[letter].append((number, code))

    # loop for each letter group
    for letter in letter_groups:

        # sort letters alphabetically
        letter_groups[letter].sort(key=lambda x: x[0])

    # get default colour cycle
    default_colours = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    colours = {"": "white"}

    # case 1: all ECO codes share the same letter
    if len(letter_groups) == 1:

        # loop for each unique ECO code
        for i, (number, code) in enumerate(list(letter_groups.values())[0]):

            # assign a colour from the matplotlib default colours
            colours[code] = default_colours[i % len(default_colours)]

    # case 2: ECO codes correspond to multiple letters
    else:

        # loop for each unique letter
        for i, (letter, members) in enumerate(sorted(letter_groups.items())):

            # determine base colour
            base_colour = default_colours[i % len(default_colours)]

            # convert base colour to HLS to manipulate lightness
            base_rgb = mcolors.to_rgb(base_colour)
            h, l, s = mcolors.rgb_to_hsv(base_rgb)

            # there is only one ECO code with this letter
            if len(members) == 1:

                # use solid base colour
                colours[members[0][1]] = base_colour

            # there are multiple ECO codes with this letter
            else:

                # vary lightness across a range by rank, not by number value
                lightness_values = np.linspace(1.0, 0.4, len(members))

                # loop for each number corresponding to that letter in the ECO code
                for rank, (number, code) in enumerate(members):

                    # convert to RGB and store colour
                    rgb = mcolors.hsv_to_rgb((h, s, lightness_values[rank]))
                    colours[code] = mcolors.to_hex(rgb)

    return colours

# main function
def main():

    # calculate total number of games in database
    params = {**Inputs.lichess["params_base"]}
    response = requests.get(Inputs.lichess["url"], params = params, headers = Inputs.lichess["headers"])
    data = response.json()
    total_moves = data["white"] + data["draws"] + data["black"]
    Inputs.move_threshold = int(Inputs.frequency_threshold * total_moves)

    # user feedback
    print(
        f"Total games in database: {Colours.GREEN}{total_moves}{Colours.END}. "
        f"Setting pruning threshold to {Colours.GREEN}{Inputs.move_threshold}{Colours.END} games!"
    )

    # open input file
    with open(Inputs.filename) as f:
        game = chess.pgn.read_game(f)

    # create empty lists to store inputs and outputs to move tree
    inputs = []
    outputs = []

    # loop for unique line in the input tree
    for line in walk_lines(game):

        # build board from current line
        board = chess.Board()
        for move in line:
            board.push_san(move)

        # fetch lichess API for current position
        params = {**Inputs.lichess["params_base"], "play": ",".join(m.uci() for m in board.move_stack)}
        response = requests.get(Inputs.lichess["url"], params = params, headers = Inputs.lichess["headers"])
        response.raise_for_status()
        data = response.json()

        # store as input
        inputs.append({"line": line, "games": data["white"] + data["draws"] + data["black"]})

        # extend lines
        branches = extend_line(line, chess.WHITE)
        outputs.extend(branches)

    # count games in input
    """input_games = sum([branch["games"] for branch in inputs])
    output_games = sum([branch["games"] for branch in branches])
    percent = 100 * output_games / input_games
    print(
        f"Repertoire covers {Colours.GREEN}{output_games}{Colours.END} of "
        f"{Colours.GREEN}{input_games} ({percent:.4g}%){Colours.END} games in the input file."
    )"""

    # save new repertoire as pgn file
    save_pgn(outputs)

    # create sankey diagram
    sankey_diagram(inputs, outputs)

# upon script execution
if __name__ == "__main__":

    # user has given an input file
    if len(sys.argv) > 1:

        # take user argument as input filename
        Inputs.filename = sys.argv[1]

    # run main and show all plots
    main()
    plt.show()
