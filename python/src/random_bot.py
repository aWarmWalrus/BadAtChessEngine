import random
from collections import defaultdict
from bitboard import BitBoard

ENGINE_NAME = "RANDOM"
STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
TEST_FEN = "r1b1k1nr/p2p1pNp/n1B5/1p1NPR1P/6P1/3P1Q2/P1P1K3/qR4b1 b KQkq - 1 2"
TEST2_FEN = "rnbqk2r/pppp1pp1/5n1p/1Bb1p3/4P2N/5P2/PPPP2PP/RNBQK2R b KQkq - 0 5"
ENPASSANT_FEN = "rnbqkbnr/1p1p1ppp/8/1Bp1p3/p3P3/5N1P/PPPP1PP1/RNBQK2R w KQkq c6 0 5"
KING_CHECK_BLACK = "3k4/8/3P4/8/8/8/8/K7 b - - 1 2"
KING_CHECK_WHITE = "3k4/8/8/8/8/3p4/8/3K4 w - - 1 2"

class Engine:
    def __init__(self):
        self.options = defaultdict(str)
        self.board = BitBoard(0)

    def inputUCI(self):
        print("id name " + ENGINE_NAME)
        print("id author Walrus")
        print("uciok")

    def setOptions(self, line):
        print("unimplemented")

    def isReady(self):
        print("readyok")

    def newGame(self):
        pass  # nothing to do

    def position(self, line):
        words = line.split()
        assert(words[0] == "position")

        if words[1] == "startpos":
            self.board = BitBoard.createFromFen(STARTING_FEN)
            if len(words) > 2 and words[2] == "moves":
                for move in words[3:]:
                    self.board = self.board.makeMove(move)
        else:
            print("weird " + words.join())

    def go(self):
        moves = self.board.getLegalMoves()
        if self.board.isCheckMate():
            print("CHECK MATED SON")
            return
        elif len(moves) == 0:
            print("stale mate...??")
            return
        print("bestmove " + random.choice(moves))

    def run(self):
        while True:
            line = input()
            if line == "uci":
                self.inputUCI()
            elif line.startswith("setoption"):
                self.setOptions(line)
            elif line.startswith("isready"):
                self.isReady()
            elif line.startswith("ucinewgame"):
                self.newGame()
            elif line.startswith("position"):
                self.position(line)
            elif line.startswith("go"):
                self.go()
            elif line.startswith("print"):
                self.board.prettyPrint()
                print(self.board.getLegalMoves())
            elif line.startswith("end") or line.startswith("quit"):
                print("goodbye")
                break

if __name__ == "__main__":
    engine = Engine()
    engine.run()
