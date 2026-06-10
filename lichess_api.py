# lichess_api.py
# 5 June 2026

# import modules
import matplotlib.pyplot as plt
import requests
import chess
import chess.pgn
from dotenv import load_dotenv
import os

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

    # default parameters for Lichess API requests
    url = "https://explorer.lichess.ovh/lichess"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}"
    }
    params_base = {
        "speeds": "blitz,rapid",
        "ratings": "2000,2200,2500",
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
    params = {**Inputs.params_base, "play": ",".join(m.uci() for m in board.move_stack)}
    response = requests.get(Inputs.url, params = params, headers = Inputs.headers)
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

    # there are no responses that meet the threshold
    """if not moves:

        # current line is a leaf, return it
        result = [{
            "line": line,
            "games": data["white"] + data["draws"] + data["black"]
        }]
        return result"""

    # create empty list to store extended lines
    result = []

    # loop for all possible responses
    for move in moves:

        # append to result
        result.extend([{
            "line": line + [move["san"]],
            "games": move["white"] + move["draws"] + move["black"]
        }])

        # recursively call function to extend line
        new_line = line + [move["san"]]
        result.extend(
            extend_line(new_line, player_colour)
        )

    return result

def save_pgn(branches: list[list[str]], output_file: str = "repertoire.pgn", event_name: str = "Repertoire"):
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

    with open(output_file, "w") as f:
        exporter = chess.pgn.FileExporter(f)
        game.accept(exporter)

    print(f"Repertoire saved as {Colours.GREEN}{output_file}{Colours.END}!")

    return game

def sankey_diagram(input, output):
    """Creates a Sankey diagram of a tree of branches."""
    # create empty nodes and links dictionaries
    nodes = {
        "labels": [],
        "x": [],
        "display_names": []
    }
    links = {
        "sources": [],
        "targets": [],
        "values": []
    }

    # loop for all positions including input
    for position in [input] + output:

        # convert line to string and store
        position["string"] = ",".join(position["line"])

        # append to nodes dictionary
        nodes["labels"].append(position["string"])
        nodes["x"].append(len(position["line"]))
        nodes["display_names"].append(position["line"][-1])

    # loop for each output position
    for position in output:

        # append to links dictionary
        links["sources"].append(",".join(position["line"][:-1]))
        links["targets"].append(",".join(position["line"]))
        links["values"].append(position["games"])

    # create Sankey object
    sankey = Sankey(nodes, links)

    # re-retrieve nodes and links dictionaries
    nodes = sankey.nodes
    links = sankey.links

    # loop for each node
    for i in range(len(nodes["labels"])):

        # calculate number of unaccounted for positions
        diff = (
            next(d for d in [input] + output if d["string"] == nodes["labels"][i])["games"]
            - nodes["outflows"][i]
        )

        # check value is more than zero
        if diff > 0:

            # create leaf node
            nodes["labels"].append(nodes["labels"][i] + "-")
            nodes["x"].append(nodes["x"][i] + 1)
            nodes["display_names"].append("")

            # create link between nodes
            links["sources"].append(nodes["labels"][i])
            links["targets"].append(nodes["labels"][i] + "-")
            links["values"].append(diff)

    # trim nodes and links dictionaries to prevent array length mismatches
    nodes = {key: value for key, value in nodes.items() if key in {"labels", "x", "display_names"}}
    links = {key: value for key, value in links.items() if key in {"sources", "targets", "values"}}

    # create NEW Sankey object
    sankey = Sankey(nodes, links)

    # create plot
    fig, ax = plt.subplots()
    sankey.plot(fig, ax)

# main function
def main():

    # calculate total number of games in database
    params = {**Inputs.params_base}
    response = requests.get(Inputs.url, params = params, headers = Inputs.headers)
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
    for i, line in enumerate(walk_lines(game)):

        # build board from current line
        board = chess.Board()
        for move in line:
            board.push_san(move)

        # fetch lichess API for current position
        params = {**Inputs.params_base, "play": ",".join(m.uci() for m in board.move_stack)}
        response = requests.get(Inputs.url, params = params, headers = Inputs.headers)
        response.raise_for_status()
        data = response.json()

        # store as input
        inputs.append({"line": line, "games": data["white"] + data["draws"] + data["black"]})

        # extend lines
        branches = extend_line(line, chess.WHITE)
        outputs.extend(branches)

        # create sankey diagram
        sankey_diagram(inputs[-1], branches)

    # count games in input
    input_games = sum([branch["games"] for branch in inputs])
    output_games = sum([branch["games"] for branch in branches])
    percent = 100 * output_games / input_games
    print(
        f"Repertoire covers {Colours.GREEN}{output_games}{Colours.END} of "
        f"{Colours.GREEN}{input_games} ({percent:.4g}%){Colours.END} games in the input file."
    )

    # save new repertoire as pgn file
    save_pgn(branches, "repertoire.pgn")

# upon script execution
if __name__ == "__main__":

    # run main and show all plots
    main()
    plt.show()
