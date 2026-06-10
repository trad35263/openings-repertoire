# lichess_api.py
# 5 June 2026

# import modules
import requests
import chess
import chess.pgn
from dotenv import load_dotenv
import os

# import Colours class
from utils import Colours

# Inputs class
class Inputs:

    # Lichess API token
    load_dotenv()
    API_TOKEN = os.environ.get("MY_API_KEY")

    # input PGN text file
    filename = "root.txt"

    # default parameters
    frequency_threshold = 0.0005

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
    if not moves:

        # current line is a leaf, return it
        return [line]

    # create empty list to store extended lines
    result = []

    # loop for all possible responses
    for move in moves:

        # recursively call function to extend line
        new_line = line + [move["san"]]
        result.extend(extend_line(new_line, player_colour))

    return result

def save_pgn(all_branches: list[list[str]], output_file: str = "repertoire.pgn", event_name: str = "Repertoire"):
    """Saves the given lines as a PGN file containing the full repertoire."""
    # create game object
    game = chess.pgn.Game()
    game.headers["Event"] = event_name

    # loop for each branch in extended move tree
    for branch in all_branches:

        # create a board to track the position
        node = game
        board = chess.Board()

        # loop for each move in the branch
        for san in branch:

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

    print(f"PGN saved to {output_file}")

# main function
def main():

    # calculate total number of games in database
    params = {**Inputs.params_base}
    response = requests.get(Inputs.url, params = params, headers = Inputs.headers)
    data = response.json()
    total_moves = data["white"] + data["draws"] + data["black"]
    Inputs.move_threshold = int(Inputs.frequency_threshold * total_moves)

    # user feedback
    print(f"Total games in database: {total_moves}. Setting pruning threshold to {Inputs.move_threshold} games!")

    # open input file
    with open(Inputs.filename) as f:
        game = chess.pgn.read_game(f)

    # create empty list to store branches of extended move tree
    branches = []

    # loop for unique line in the input tree
    for i, line in enumerate(walk_lines(game)):

        # extend lines
        branches.extend(extend_line(line, chess.WHITE))

    # save new repertoire as pgn file
    save_pgn(branches, "repertoire.pgn")

# upon script execution
if __name__ == "__main__":

    # run main
    main()
