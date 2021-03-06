"""
Implementation of a Chess board using a 267-length bitmap to store all the data
about the chess board state.

Benchmarks:
 - PC (Ryzen 5 3600 @ 3.6 GHz, 16GB RAM)
    boardInitialization: 15.895µs
    startposMoves(50):    0.465ms
    startposMoves(100):   0.933ms
    computeLegalMoves():  3.800µs

 - Lenovo P1G4 (i7-11850H, 32GB RAM)
    boardInitialization: 13.400900003034621µs
    startposMoves(50): 0.3792362999993202ms
    startposMoves(100): 0.7665094999974826ms
"""
STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
TEST_FEN = "rn2k3/2pp1pp1/2b1pn2/1BB5/P3P3/1PN2Q1r/2PP1P1P/R3K1NR w KQq - 0 15"
# TEST_FEN = "3R1q1k/pp4b1/6Q1/8/1P4n1/P6K/6P1/2r5 w - - 4 40"
TRICKY_FEN = "r3k2r/pPppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"

EMPTY = 0
PAWN = 1
KNIGHT = 2
BISHOP = 3
ROOK = 4
QUEEN = 5
KING = 6

BOARD_SIZE = 8
NUM_SQUARES = 64
MAX_INDEX = 255
PIECE_SIZE = 4  # 4 bits for piece. piece[3] is side, and piece[0:3] is the piece
PIECE_MASK = 15 # 0b1111
CASTLES_MASK = 15 # 0b1111
ENPASSANT_MASK = 63 # 0b111111

# BITMAP INDEXES
BOARD_START = 0
SIDE_TO_MOVE_START = 256
CASTLES_START = 257
ENPASSANT_START = 261

# LOGICAL CONSTANTS, MAPS AND LISTS
PIECE_MAP = {"r":ROOK, "b":BISHOP, "n":KNIGHT, "q":QUEEN}
PIECE_STRING = " pnbrqk"
# PIECE_STRING = " prbnqk"
# CASTLE_MOVES = {"e1g1":(7,7), "e8g8":(0,7), "e1c1":(7,0), "e8c8":(0,0)}
CASTLE_MOVES = {0o20060604: 0o07,  # e8g8 / k / black king-side
                0o20060204: 0o00,  # e8c8 / q / black queen-side
                0o20067674: 0o77,  # e1g1 / K / white king-side
                0o20067274: 0o70}  # e1c3 / Q / white queen-side
ROOK_DIRS = [(-1,0),(1,0),(0,-1),(0,1)]
BISHOP_DIRS = [(-1,-1),(-1,1),(1,-1),(1,1)]
KNIGHT_DIRS = [(-2,-1),(-2,1),(2,-1),(2,1),(-1,-2),(-1,2),(1,-2),(1,2)]
ROYAL_DIRS = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
DIR_MAP= {ROOK: ROOK_DIRS, BISHOP: BISHOP_DIRS, QUEEN: ROYAL_DIRS, \
            KNIGHT: KNIGHT_DIRS, KING: ROYAL_DIRS}

# MOVE BIT MAPS
# | meta (4) | promotion (3) | dest piece (3) | src piece (3) | dest sq (6) | src sq (6) |
DEST_SQ      = 6
SRC_PIECE    = 12
DEST_PIECE   = 15
PROMO_PIECE  = 18
MOVE_META    = 21

MOVE_SQ_MASK    = 0b111111
MOVE_PIECE_MASK = 0b111
MOVE_META_MASK = 0b1111

CAPTURE      = 0b00001
CASTLE       = 0b00010
CHECK        = 0b00100
PROMOTION    = 0b01000

class BitBoard():
    """
    The paper said we need 768 bits? 2 x 6 x 64
    But we don't need a different bit for each piece... there are 6 possible
    pieces, so we only need 3 bits, plus one bit to represent side.

    total: 267 bits
    |  en passant (6 bits)  | castles (4 bits) | side to move (1 bit) | board (4x64=256 bits) |
    |266                 261|260            257|256                256|255                   0|
    """
    # TODO: move the board to the lowest bits to get rid of all the unnecessary shifts.
    def __init__(self, bits):
        assert(isinstance(bits, int))
        self._bits = bits
        self._legalMoves = None
        self._castles = None
        self._whiteToMove = None
        self._sideToMove = None
        self._enpassant = None

    """ ====================== Static helper methods ======================= """
    def coordToAddress(coord):
        return PIECE_SIZE * (BOARD_SIZE * coord[0] + coord[1])

    def indexToCoord(index):
        return (int(index / BOARD_SIZE), index % BOARD_SIZE)

    def indexToAlgebraic(index):
        file = "abcdefgh"[index % BOARD_SIZE]
        return file + str(8 - int(index / BOARD_SIZE))

    def indexToAddress(index):
        return PIECE_SIZE * index

    def algebraicToIndex(algebraic):
        return (BOARD_SIZE*(8-int(algebraic[1]))) + ord(algebraic[0])-ord('a')

    def algebraicToAddress(algebraic):
        row = 8 - int(algebraic[1])
        col = ord(algebraic[0]) - ord('a')
        return PIECE_SIZE * (BOARD_SIZE * row + col)

    def algebraicToCoord(algebraic):
        return (8 - int(algebraic[1]), ord(algebraic[0]) - ord('a'))

    # Also returns an outOfBounds bool if the addition would be out of bounds
    # on a normal chess board.
    def indexPlusCoord(index, coord):
        result = index + (coord[0] * BOARD_SIZE) + coord[1]
        if result < 0 or result > 63:
            return -1, True
        col = (index % BOARD_SIZE) + coord[1]
        return result, (col < 0 or col > 7)

    # Basically only for en passant logic. Returns a 6 bit int, where the
    # higher 3 bits are for the row, and the lower 3 bits are for the col.
    def algebraicToBits(algebraic):
        return ((8 - int(algebraic[1])) << 3) + (ord(algebraic[0]) - ord('a'))

    def indexToBits(index):
        return ((8 - int(algebraic[1])) << 3) + (ord(algebraic[0]) - ord('a'))

    def pieceAtAlgebraic(bits, algebraic):
        i = BitBoard.algebraicToAddress(algebraic[0:2])
        return (bits & (PIECE_MASK << i)) >> i

    def getPiece(bits, index):
        shift = PIECE_SIZE * index
        return (bits & (PIECE_MASK << shift)) >> shift

    def removePiece(bits, address):
        return bits & ~(PIECE_MASK << address)

    def addPiece(bits, address, piece):
        # Need to remove piece, if there is already a piece there
        bits = BitBoard.removePiece(bits, address)
        return bits | (piece << address)

    def pieceType(piece):
        return piece & 7

    def pieceSide(piece):
        return (piece & 8) >> 3

    def areEnemies(p1, p2):
        return BitBoard.pieceSide(p1) != BitBoard.pieceSide(p2)

    def isBackRank(index):
        return index < 8 or index >= 56

    def moveCaptureValue(move):
        srcPiece = (move & (MOVE_PIECE_MASK << SRC_PIECE)) >> SRC_PIECE
        destPiece = (move & (MOVE_PIECE_MASK << DEST_PIECE)) >> DEST_PIECE
        return destPiece - srcPiece

    def createFromFen(fenstring):
        fenArr = fenstring.split(" ")
        rows = fenArr[0].split("/")
        pieceMap = {"p": PAWN, "r": ROOK, "b": BISHOP, "n": KNIGHT, "q": QUEEN, "k": KING}
        bits = 0
        address = BOARD_START
        for r in range(len(rows)):
            empties = 0
            for c in range(len(rows[r])):
                if rows[r][c].isdigit():   # Empty squares
                    address += PIECE_SIZE * int(rows[r][c])
                    continue
                # Black = 0, White = 1
                player = 0 if rows[r][c].islower() else 1
                piece = (player << 3) | pieceMap[rows[r][c].lower()]
                bits |= piece << address
                address += PIECE_SIZE

        # SIDE TO MOVE: 0 is black, 1 is white
        if fenArr[1] == "w":
            bits |= 1 << SIDE_TO_MOVE_START

        # CASTLES:
        #   k (black king-side):  0  (0b00)
        #   q (black queen-side): 1  (0b01)
        #   K (white king-side):  2  (0b10)
        #   Q (white queen-side): 3  (0b11)
        castles = 0
        for castle in fenArr[2]:
            tmp = 0b0001 if castle.islower() else 0b0100
            if castle.lower() == "k":
                castles |= tmp
            elif castle.lower() == "q":
                castles |= tmp << 1
        bits |= castles << CASTLES_START

        # EN PASSANT:
        #  | index (0-64, 6 bits) |
        if (fenArr[3] != "-"):
            bits |= BitBoard.algebraicToIndex(fenArr[3]) << ENPASSANT_START

        return BitBoard(bits)

    """ Getters """
    def getCastles(self):
        if self._castles is not None:
            return self._castles
        self._castles = (self._bits & (CASTLES_MASK << CASTLES_START)) >> CASTLES_START
        return self._castles

    # This is more useful as syntactic sugar for if statements.
    def whiteToMove(self):
        if self._whiteToMove is not None:
            return self._whiteToMove
        self._whiteToMove = (self._bits & (1 << SIDE_TO_MOVE_START)) >> SIDE_TO_MOVE_START
        return self._whiteToMove

    # This is more useful when creating a piece.
    def sideToMove(self):
        if self._sideToMove is not None:
            return self._sideToMove
        # 256 (SIDE_TO_MOVE_START) - 3 (PIECE BITS)
        self._sideToMove = (self._bits & (1 << SIDE_TO_MOVE_START)) >> 253
        return self._sideToMove

    def getEnpassant(self):
        if self._enpassant is not None:
            return self._enpassant
        self._enpassant = (self._bits & (ENPASSANT_MASK << ENPASSANT_START)) >> ENPASSANT_START
        return self._enpassant

    def getLegalMoves(self):
        if self._legalMoves is None:
            self.computeLegalMoves()
        return self._legalMoves

    def isOpponentPiece(self, piece):
        """ Returns true if the piece is against the side to play. """
        isWhitePiece = (piece & 8) >> 3
        return isWhitePiece != self.whiteToMove()

    """ ============= Class methods ======================================== """
    def activePieces(self):
        whitePieces = []
        blackPieces = []
        for i in range(NUM_SQUARES):
            address = i * PIECE_SIZE
            piece = (self._bits & (PIECE_MASK << address)) >> address
            if piece == 0:
                continue
            if (8 & piece) == 0:
                blackPieces.append((BitBoard.pieceType(piece), i))
                continue
            whitePieces.append((BitBoard.pieceType(piece), i))
        return (whitePieces, blackPieces)

    def castleLogic(self, move, piece, bits):
        newCastles = self.getCastles()
        if BitBoard.pieceType(piece) == KING:
            if move in CASTLE_MOVES:
                rookIndex = CASTLE_MOVES[move]
                bits = BitBoard.removePiece(bits, rookIndex * PIECE_SIZE)
                newCol = 5 if ((rookIndex & 0b111) == 7) else 3
                rookDest = (rookIndex & (0b111 << 3)) | newCol
                # BitBoard.coordToAddress((rook[0], newFile))
                bits = BitBoard.addPiece(bits, \
                    rookDest * PIECE_SIZE, ROOK | self.sideToMove())
            # Even if not castling, moving king cancels all castle possibility.
            newCastles &= ~(0b11 << (2 if self.whiteToMove() else 0))

        # If our rook moves, remove that castle possibility
        if BitBoard.pieceType(piece) == ROOK:
            shift = (2 if self.whiteToMove() else 0) + \
                    (0 if (move & 0b111) == 7 else 1)
            newCastles &= ~(0b1 << shift)

        # If we just took on a starting rook square, remove opponent's castle possibility
        oppRow = 7 if self.whiteToMove() else 0
        destRow = (move & (0b111 << 9)) >> 9
        if destRow == oppRow:
            shift = (0 if self.whiteToMove() else 2) + \
                    (0 if (move & 0b111) == 7 else 1)
            newCastles &= ~(0b1 << shift)
        bits &= ((newCastles << CASTLES_START) | ~(CASTLES_MASK << CASTLES_START))
        return bits

    def makeMove(self, move):
        """
        |move| should be a string of length 4 or 5 representing the piece to be
        moved and its end location.
            <init file><init rank><dest file><dest rank>
        """
        newBits = 0
        if isinstance(move, str):
            src = BitBoard.algebraicToIndex(move[0:2])
            dest = BitBoard.algebraicToIndex(move[2:4])
            promo = 0 if len(move) < 5 else PIECE_MAP[move[4]]
            move = dest << DEST_SQ | src
        else:
            assert(isinstance(move, int)), type(move)
            src = MOVE_SQ_MASK & move
            dest = ((MOVE_SQ_MASK << DEST_SQ) & move) >> DEST_SQ
            promo = ((MOVE_PIECE_MASK << PROMO_PIECE) & move) >> PROMO_PIECE

        srcAddr = src * PIECE_SIZE
        srcPiece = BitBoard.getPiece(self._bits, src)
        endPiece = srcPiece

        # Right now, keep the legality checks simple and just trust in the GUI
        # to send us legal moves only.
        if srcPiece == 0 or self.isOpponentPiece(srcPiece):
            # self.prettyPrint()
            self.prettyPrintVerbose()
            print("Illegal move: " + oct(move))

        newBits = BitBoard.removePiece(self._bits, srcAddr)
        newBits = self.castleLogic(move, srcPiece, newBits)

        # Pawn promotion logic
        if BitBoard.pieceType(srcPiece) == PAWN and (dest <= 0o07 or dest >= 0o70):
            endPiece = (QUEEN if promo > 0 else promo) | self.sideToMove()

        # En passant logic
        if BitBoard.pieceType(srcPiece) == PAWN and dest == self.getEnpassant():
            # captured piece is on same row as src, and same col as dest.
            capturedAddr = ((src & (0b111 << 3)) | (dest & 0b111)) * PIECE_SIZE
            newBits = BitBoard.removePiece(newBits, capturedAddr)

        newBits &= ~(ENPASSANT_MASK << ENPASSANT_START)
        doubleAdvance = abs(src - dest) == 0o20
        if BitBoard.pieceType(srcPiece) == PAWN and doubleAdvance:
            epRow = 0o50 if self.whiteToMove() else 0o20
            newBits |= (epRow | (src & 0b111)) << ENPASSANT_START

        destAddr = dest * PIECE_SIZE
        newBits = BitBoard.addPiece(newBits, destAddr, endPiece)

        # Flip whose turn it is.
        newBits ^= (1 << SIDE_TO_MOVE_START)

        return BitBoard(newBits)


    """ ============== Legal Moves calculation ===================== """
    def findPiece(self, piece):
        shift = BOARD_START
        while shift < MAX_INDEX:
            if piece == ((self._bits & (PIECE_MASK << shift)) >> shift):
                return int(shift / PIECE_SIZE)
            shift += PIECE_SIZE
        self.prettyPrintVerbose()
        raise Exception("Piece not found: " + bin(piece))

    def constructMove(srcSq, destSq, srcPiece, destPiece = 0, meta = 0, promoPiece = 0):
        srcPiece = BitBoard.pieceType(srcPiece)
        destPiece = BitBoard.pieceType(destPiece)
        return meta << MOVE_META | promoPiece << PROMO_PIECE | \
                destPiece << DEST_PIECE | srcPiece << SRC_PIECE | \
                destSq << DEST_SQ | srcSq

    def legalMovesForNonPawns(self, piece, index, directions):
        multiStep = PIECE_STRING[BitBoard.pieceType(piece)] in "rbq"
        moves = []
        for d in directions:
            destSq, outOfBounds = BitBoard.indexPlusCoord(index, d)
            while multiStep and not outOfBounds \
                    and BitBoard.getPiece(self._bits, destSq) == 0:
                # cMove = BitBoard.constructMove(index, destSq, piece)
                # print("{} {} -> {}: {}".format(bin(piece), oct(index), oct(destSq), oct(cMove)))
                moves.append(BitBoard.constructMove(index, destSq, piece))
                destSq, outOfBounds = BitBoard.indexPlusCoord(destSq, d)
            if outOfBounds:
                continue
            destPiece = BitBoard.getPiece(self._bits, destSq)
            if destPiece != 0 and BitBoard.areEnemies(piece, destPiece):
                # cMove = BitBoard.constructMove(index, destSq, piece, destPiece, CAPTURE)
                # print("{} {} -> {}: {}".format(bin(piece), oct(index), oct(destSq), oct(cMove)))
                moves.append(BitBoard.constructMove(index, destSq, piece, destPiece, CAPTURE))
                continue
            if (not multiStep and destPiece == 0):
                # cMove = BitBoard.constructMove(index, destSq, piece)
                # print("{} {} -> {}: {}".format(bin(piece), oct(index), oct(destSq), oct(cMove)))
                moves.append(BitBoard.constructMove(index, destSq, piece, destPiece))
        return moves

    def legalMovesForPawn(self, pawn, index):
        moves = []
        forward = -1 if self.whiteToMove() else 1
        diagonals = [(forward, -1), (forward, 1)]
        # Pawn take logic
        for diag in diagonals:
            destSq, outOfBounds = BitBoard.indexPlusCoord(index, diag)
            if outOfBounds:
                continue
            destPiece = BitBoard.getPiece(self._bits, destSq)
            if destPiece != 0 and BitBoard.areEnemies(pawn, destPiece):
                if BitBoard.isBackRank(destSq):
                    for promo in [QUEEN, ROOK, BISHOP, KNIGHT]:
                        moves.append(BitBoard.constructMove(index, destSq, pawn, destPiece, CAPTURE | PROMOTION, promo))
                    continue
                moves.append(BitBoard.constructMove(index, destSq, pawn, destPiece, CAPTURE))
                continue
            if destSq == self.getEnpassant() and destSq > 0:
                moves.append(BitBoard.constructMove(index, destSq, pawn, PAWN, CAPTURE))

        # Pawn advance logic
        destSq, outOfBounds = BitBoard.indexPlusCoord(index, (forward, 0))
        if outOfBounds or BitBoard.getPiece(self._bits, destSq) != 0:
            return moves
        if BitBoard.isBackRank(destSq):
            for promo in [QUEEN, ROOK, BISHOP, KNIGHT]:
                moves.append(BitBoard.constructMove(index, destSq, pawn, destPiece, 0, promo))
        else:
            moves.append(BitBoard.constructMove(index, destSq, pawn))

        # Pawn double advance logic
        if int(index / BOARD_SIZE) != (6 if self.whiteToMove() else 1):
            return moves
        double = index + (2 * BOARD_SIZE * forward)
        if BitBoard.getPiece(self._bits, double) == 0:
            moves.append(BitBoard.constructMove(index, double, pawn))

        return moves

    def legalMovesForPiece(self, piece, index):
        if BitBoard.pieceType(piece) == PAWN:
            return self.legalMovesForPawn(piece, index)
        return self.legalMovesForNonPawns(piece, index, \
            DIR_MAP[BitBoard.pieceType(piece)])

    def legalCastleMoves(self):
        castleMap = {1: 0o20060604,  # e8g8 / k / black king-side
                     2: 0o20060204,  # e8c8 / q / black queen-side
                     4: 0o20067674,  # e1g1 / K / white king-side
                     8: 0o20067274}  # e1c3 / Q / white queen-side
        moves = []
        for shift in range(2):
            mask = 1 << (shift + (2 if self.whiteToMove() else 0))
            castle = self.getCastles() & mask
            if castle == 0:
                continue
            isKingside = (shift == 0)
            # Check squares between king and rook
            emptyMask = 255 if isKingside else 4095
            shift = (56 * PIECE_SIZE if self.whiteToMove() else 0) \
                    + (20 if isKingside else 4)
            if (self._bits & (emptyMask << shift)) != 0:
                continue

            # Check that all transit squares are not attacked
            transits = [4,5,6] if isKingside else [2,3,4]
            row = 56 if self.whiteToMove() else 0
            if any([self.isSquareAttacked(t + row, (self.sideToMove() | KING)) \
                    for t in transits]):
                continue
            moves.append(castleMap[castle])
        return moves

    def isSquareAttackedByPiece(self, index, target, directions, pieces):
        multiStep = any([p in pieces for p in "rbq"])
        for d in directions:
            tmp, outOfBounds = BitBoard.indexPlusCoord(index, d)
            while multiStep and not outOfBounds \
                    and BitBoard.getPiece(self._bits, tmp) == 0:
                tmp, outOfBounds = BitBoard.indexPlusCoord(tmp, d)
            if outOfBounds:
                continue
            piece = BitBoard.getPiece(self._bits, tmp)
            pieceStr = PIECE_STRING[BitBoard.pieceType(piece)]
            if pieceStr in pieces and BitBoard.areEnemies(piece, target):
                return True
        return False

    def isSquareAttacked(self, index, target = None):
        """
        If target is None, will use whatever piece is at the index.
        """
        directionals = [(KNIGHT_DIRS, "n"), (ROOK_DIRS, "rq"), \
                        (BISHOP_DIRS, "bq"), (ROYAL_DIRS, "k")]
        if target is None:
            target = BitBoard.getPiece(self._bits, index)
        if any([self.isSquareAttackedByPiece(index, target, dir, ps) \
                for (dir, ps) in directionals]):
            return True
        # Pawn logic is special
        forward = 1 if self.whiteToMove() else -1
        diagonals = [(forward, 1), (forward, -1)]
        for diag in diagonals:
            tmp, outOfBounds = BitBoard.indexPlusCoord(index, diag)
            if outOfBounds:
                continue
            piece = BitBoard.getPiece(self._bits, tmp)
            if BitBoard.pieceType(piece) == PAWN and BitBoard.areEnemies(piece, target):
                return True
        return False

    def isKingSafeAfterMove(self, move):
        postMoveBoard = self.makeMove(move)
        king = self.sideToMove() | KING

        kingIndex = postMoveBoard.findPiece(king)
        return not postMoveBoard.isSquareAttacked(kingIndex, king)

    def kingCheckAnalysis(self, moves):
        newMoves = []
        for move in moves:
            postMoveBoard = self.makeMove(move)
            ourKing = KING | self.sideToMove()
            ourKingIndex = postMoveBoard.findPiece(ourKing)
            if postMoveBoard.isSquareAttacked(ourKingIndex, ourKing):
                # Get rid of moves that leave our king in check
                continue
            otherKing = KING | (0 if self.whiteToMove() else 8)
            otherKingIndex = postMoveBoard.findPiece(otherKing)
            if postMoveBoard.isSquareAttacked(otherKingIndex, otherKing):
                newMoves.append(move | (CHECK << MOVE_META))
                continue
            newMoves.append(move)
        return newMoves


    # Only for if the active player's king is in check mate, since it can't be
    # checkmate when it's not your turn.
    def isCheckMate(self):
        # try:
        kingIndex = self.findPiece(self.sideToMove() | KING)
        return len(self.getLegalMoves()) == 0 and self.isSquareAttacked(kingIndex)
        # except:
        #     self.prettyPrintVerbose()
        #     return True

    def computeLegalMoves(self):
        if self._legalMoves is not None:
            return
        moves = []
        for i in range(NUM_SQUARES):
            piece = BitBoard.getPiece(self._bits, i)
            if piece == 0 or self.isOpponentPiece(piece):
                continue
            moves += self.legalMovesForPiece(piece, i)
        moves += self.legalCastleMoves()
        moves = self.kingCheckAnalysis(moves)
        moves.sort(key=(lambda m: m & (MOVE_META_MASK << MOVE_META)), reverse=True)
        # self._legalMoves = [m[0] for m in moves]
        self._legalMoves = moves

    """ ============== Debugging and Printing ===================== """
    def moveToDebugString(move):
        src = BitBoard.indexToAlgebraic(move & MOVE_SQ_MASK)
        dest = BitBoard.indexToAlgebraic((move & (MOVE_SQ_MASK << DEST_SQ)) >> DEST_SQ)
        srcPiece = (move & (MOVE_PIECE_MASK << SRC_PIECE)) >> SRC_PIECE
        destPiece = (move & (MOVE_PIECE_MASK << DEST_PIECE)) >> DEST_PIECE
        meta = (move & (MOVE_META_MASK << MOVE_META)) >> MOVE_META
        pieces = ["", "p", "R", "B", "N", "Q", "K"]
        return "{}{}->{}{}{}".format(pieces[srcPiece], src, pieces[destPiece], dest, \
            " " + bin(meta)[2:] if meta > 0 else "")

    def moveStr(move):
        src = BitBoard.indexToAlgebraic(move & MOVE_SQ_MASK)
        dest = BitBoard.indexToAlgebraic((move & (MOVE_SQ_MASK << DEST_SQ)) >> DEST_SQ)
        promo = (move & (MOVE_PIECE_MASK << PROMO_PIECE)) >> PROMO_PIECE
        pieces = ["", "", "r", "b", "n", "q", ""]
        return "{}{}{}".format(src, dest, pieces[promo])

    def printLegalMoves(self):
        print([BitBoard.moveToDebugString(m) for m in self.getLegalMoves()])

    def prettyPrint(self):
        for i in range(NUM_SQUARES):
            if i % BOARD_SIZE == 0:
                print("|", end='')
            bitmask = 15 << (i * PIECE_SIZE)
            pieceBits = (self._bits & bitmask) >> (i * PIECE_SIZE)
            piece = PIECE_STRING[pieceBits & 7]
            whiteToPlay = pieceBits & 8
            piece = piece.upper() if whiteToPlay else piece
            if i % BOARD_SIZE != 0:
                print(piece.rjust(2), end='')
            else:
                print(piece, end='')
            if i % BOARD_SIZE == 7:
                print("|")

    def prettyPrintVerbose(self):
        print("PRETTY PRINT ==================")
        print("Board bits as int: {}".format(self._bits))
        binary = format(self._bits, '#0269b')
        print("Board bits binary: " + binary)
        strStart = 2
        print("  En Passant[261:266]: {}".format(binary[strStart:strStart + 6]))

        castles = strStart + 6
        print("  Castles[257:261]:    {}".format(binary[castles:castles+4]))
        print("  Side to move[256]:   {}".format(binary[castles+4]))
        print("  Board [0:256]: (is reflected across y=-x compared to normal board)")
        board = castles + 5
        for i in range(BOARD_SIZE):
            start = board + i * PIECE_SIZE * BOARD_SIZE
            end = board + (i + 1) * PIECE_SIZE * BOARD_SIZE
            print("    {}".format(binary[start:end]))
        print("  Board (fancy):")
        self.prettyPrint()
        print()

if __name__ == "__main__":
    board = BitBoard.createFromFen(TEST_FEN)
    # perft(board, 0, 4)
    # for move in moves.split():
    # board = board.makeMove("e2e4")
    board.prettyPrintVerbose()
    # board.printLegalMoves()
    # board = board.makeMove("e7e5")
    # board.prettyPrintVerbose()
    # print(board.getLegalMoves())
