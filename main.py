import argparse
import chess
import chess.uci
import lichess
import json
import logging


def is_bot_account(token):
    li = lichess.Lichess(token)
    user_profile = li.get_profile()
    return user_profile.get("bot") is not None


def upgrade_account(li):
    if li.upgrade_to_bot_account() is None:
        return False

    print("Succesfully upgraded {} to Bot Account!".format(username))
    return True


def start(li, game_id, engine, weights=None):
    # init
    user_profile = li.get_profile()
    username = user_profile.get("username")
    print("Welcome {}!".format(username))

    stream = li.get_stream(game_id)
    updates = stream.iter_lines()

    #Initial response of stream will be the full game info. Store it
    game_info = json.loads(next(updates).decode('utf-8'))
    board = setup_board(game_info)
    engine = setup_engine(engine, board, weights)

    # need to do this to check if its playing against SF.
    # If Lichess Stockfish is playing response will contain:
    # 'white':{'aiLevel': 6} or 'black':{'aiLevel': 6}
    # instead of user info
    is_white = False
    if game_info.get("white").get("name"):
        is_white = (game_info.get("white")["name"] == username)

    print(game_info)
    board = play_first_move(game_info, game_id, is_white, engine, board, li)

    for update in updates:
        if update:
            #board = process_update(board, engine, update, movetime, is_white)
            upd = json.loads(update.decode('utf-8'))
            print(upd)
            wtime, btime, winc, binc = get_time_controls(upd)
            moves = upd.get("moves").split()
            board = update_board(board, moves[-1])

            if is_engine_move(is_white, moves):
                engine.position(board)
                best_move, ponder = engine.go(wtime=wtime, btime=btime, winc=winc, binc=binc)
                print(best_move)
                li.make_move(game_id, best_move)

    print("Game over!")


def play_first_move(game_info, game_id, is_white, engine, board, li):
    wtime, btime, winc, binc = get_time_controls(game_info["state"])
    moves = game_info["state"]["moves"].split()
    print("First move! It begins...")
    if is_engine_move(is_white, moves):
        engine.position(board)
        # need to hardcode first movetime since Lichess has 30 sec limit.
        best_move, ponder = engine.go(movetime=2000)
        print(best_move)
        li.make_move(game_id, best_move)

    return board


def setup_board(game_info):
    board = chess.Board()
    moves = game_info["state"]["moves"].split()
    for move in moves:
        board = update_board(board, move)

    return board


def setup_engine(engine, board, weights=None):
    print("Loading Engine!")
    if weights:
        engine = chess.uci.popen_engine([engine, "-w", weights])
    else:
        engine = chess.uci.popen_engine(engine)

    engine.uci()
    engine.position(board)
    return engine


def is_white_to_move(moves):
    return (len(moves) % 2) == 0


def update_board(board, move):
    print(move)
    uci_move = chess.Move.from_uci(move)
    board.push(uci_move)
    return board


def is_engine_move(is_white, moves):
    is_w = (is_white and is_white_to_move(moves))
    is_b = (is_white is False and is_white_to_move(moves) is False)

    return (is_w or is_b)


def get_time_controls(data):
    wtime = data.get("wtime")
    btime = data.get("btime")
    winc = data.get("winc")
    binc = data.get("binc")

    return wtime, btime, winc, binc


if __name__ == "__main__":
    logger = logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description='Play on Lichess with a bot')
    parser.add_argument('token', type=str, help='OAuth token')
    parser.add_argument('-g', '--gameid', type=str, help='Lichess Game Id')
    parser.add_argument('-e', '--engine', type=str, help='path to engine binary')
    parser.add_argument('-w', '--weights', type=str, help='path to training data (weights) file')
    parser.add_argument('-u', action='store_true', help='Add this flag to upgrade your account to a bot account.')
    args = parser.parse_args()

    li = lichess.Lichess(args.token)

    is_bot = is_user_bot(li)
    if args.u is True and is_bot is False:
        is_bot = upgrade_account(li)

    if is_bot:
        start(li, args.gameid, args.engine, args.weights)
    else:
        print("This is not a bot account. Please upgrade your Lichess account to a bot account!")
