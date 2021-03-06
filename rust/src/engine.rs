use super::arrayboard::{is_piece_white, ArrayBoard, BitMove};
use std::cmp;
use std::io;
use std::sync::atomic::{AtomicBool, AtomicU8, Ordering};

// PeSTO piece evaluation tables
#[rustfmt::skip]
const MG_PAWN_TABLE: [i16;64] = [
    0,   0,   0,   0,   0,   0,  0,   0,
    98, 134,  61,  95,  68, 126, 34, -11,
    -6,   7,  26,  31,  65,  56, 25, -20,
    -14,  13,   6,  21,  23,  12, 17, -23,
    -27,  -2,  -5,  12,  17,   6, 10, -25,
    -26,  -4,  -4, -10,   3,   3, 33, -12,
    -35,  -1, -20, -23, -15,  24, 38, -22,
    0,   0,   0,   0,   0,   0,  0,   0,
];

#[rustfmt::skip]
const EG_PAWN_TABLE: [i16;64] = [
      0,   0,   0,   0,   0,   0,   0,   0,
    178, 173, 158, 134, 147, 132, 165, 187,
     94, 100,  85,  67,  56,  53,  82,  84,
     32,  24,  13,   5,  -2,   4,  17,  17,
     13,   9,  -3,  -7,  -7,  -8,   3,  -1,
      4,   7,  -6,   1,   0,  -5,  -1,  -8,
     13,   8,   8,  10,  13,   0,   2,  -7,
      0,   0,   0,   0,   0,   0,   0,   0,
];

#[rustfmt::skip]
const MG_KNIGHT_TABLE: [i16;64] = [
    0,   0,   0,   0,   0,   0,   0,   0,
    178, 173, 158, 134, 147, 132, 165, 187,
    94, 100,  85,  67,  56,  53,  82,  84,
    32,  24,  13,   5,  -2,   4,  17,  17,
    13,   9,  -3,  -7,  -7,  -8,   3,  -1,
    4,   7,  -6,   1,   0,  -5,  -1,  -8,
    13,   8,   8,  10,  13,   0,   2,  -7,
    0,   0,   0,   0,   0,   0,   0,   0,
];

#[rustfmt::skip]
const EG_KNIGHT_TABLE: [i16;64] = [
    -58, -38, -13, -28, -31, -27, -63, -99,
    -25,  -8, -25,  -2,  -9, -25, -24, -52,
    -24, -20,  10,   9,  -1,  -9, -19, -41,
    -17,   3,  22,  22,  22,  11,   8, -18,
    -18,  -6,  16,  25,  16,  17,   4, -18,
    -23,  -3,  -1,  15,  10,  -3, -20, -22,
    -42, -20, -10,  -5,  -2, -20, -23, -44,
    -29, -51, -23, -15, -22, -18, -50, -64,
];

#[rustfmt::skip]
const MG_BISHOP_TABLE: [i16;64] = [
    -29,   4, -82, -37, -25, -42,   7,  -8,
    -26,  16, -18, -13,  30,  59,  18, -47,
    -16,  37,  43,  40,  35,  50,  37,  -2,
     -4,   5,  19,  50,  37,  37,   7,  -2,
     -6,  13,  13,  26,  34,  12,  10,   4,
      0,  15,  15,  15,  14,  27,  18,  10,
      4,  15,  16,   0,   7,  21,  33,   1,
    -33,  -3, -14, -21, -13, -12, -39, -21,
];

#[rustfmt::skip]
const EG_BISHOP_TABLE: [i16;64] = [
    -14, -21, -11,  -8, -7,  -9, -17, -24,
     -8,  -4,   7, -12, -3, -13,  -4, -14,
      2,  -8,   0,  -1, -2,   6,   0,   4,
     -3,   9,  12,   9, 14,  10,   3,   2,
     -6,   3,  13,  19,  7,  10,  -3,  -9,
    -12,  -3,   8,  10, 13,   3,  -7, -15,
    -14, -18,  -7,  -1,  4,  -9, -15, -27,
    -23,  -9, -23,  -5, -9, -16,  -5, -17,
];

#[rustfmt::skip]
const MG_ROOK_TABLE: [i16;64] = [
     32,  42,  32,  51, 63,  9,  31,  43,
     27,  32,  58,  62, 80, 67,  26,  44,
     -5,  19,  26,  36, 17, 45,  61,  16,
    -24, -11,   7,  26, 24, 35,  -8, -20,
    -36, -26, -12,  -1,  9, -7,   6, -23,
    -45, -25, -16, -17,  3,  0,  -5, -33,
    -44, -16, -20,  -9, -1, 11,  -6, -71,
    -19, -13,   1,  17, 16,  7, -37, -26,
];

#[rustfmt::skip]
const EG_ROOK_TABLE: [i16;64] = [
    13, 10, 18, 15, 12,  12,   8,   5,
    11, 13, 13, 11, -3,   3,   8,   3,
     7,  7,  7,  5,  4,  -3,  -5,  -3,
     4,  3, 13,  1,  2,   1,  -1,   2,
     3,  5,  8,  4, -5,  -6,  -8, -11,
    -4,  0, -5, -1, -7, -12,  -8, -16,
    -6, -6,  0,  2, -9,  -9, -11,  -3,
    -9,  2,  3, -1, -5, -13,   4, -20,
];

#[rustfmt::skip]
const MG_QUEEN_TABLE: [i16;64] = [
    -28,   0,  29,  12,  59,  44,  43,  45,
    -24, -39,  -5,   1, -16,  57,  28,  54,
    -13, -17,   7,   8,  29,  56,  47,  57,
    -27, -27, -16, -16,  -1,  17,  -2,   1,
     -9, -26,  -9, -10,  -2,  -4,   3,  -3,
    -14,   2, -11,  -2,  -5,   2,  14,   5,
    -35,  -8,  11,   2,   8,  15,  -3,   1,
     -1, -18,  -9,  10, -15, -25, -31, -50,
];

#[rustfmt::skip]
const EG_QUEEN_TABLE: [i16;64] = [
     -9,  22,  22,  27,  27,  19,  10,  20,
    -17,  20,  32,  41,  58,  25,  30,   0,
    -20,   6,   9,  49,  47,  35,  19,   9,
      3,  22,  24,  45,  57,  40,  57,  36,
    -18,  28,  19,  47,  31,  34,  39,  23,
    -16, -27,  15,   6,   9,  17,  10,   5,
    -22, -23, -30, -16, -16, -23, -36, -32,
    -33, -28, -22, -43,  -5, -32, -20, -41,
];

#[rustfmt::skip]
const MG_KING_TABLE: [i16;64] = [
    -65,  23,  16, -15, -56, -34,   2,  13,
     29,  -1, -20,  -7,  -8,  -4, -38, -29,
     -9,  24,   2, -16, -20,   6,  22, -22,
    -17, -20, -12, -27, -30, -25, -14, -36,
    -49,  -1, -27, -39, -46, -44, -33, -51,
    -14, -14, -22, -46, -44, -30, -15, -27,
      1,   7,  -8, -64, -43, -16,   9,   8,
    -15,  36,  12, -54,   8, -28,  24,  14,
];

#[rustfmt::skip]
const EG_KING_TABLE: [i16;64] = [
    -74, -35, -18, -18, -11,  15,   4, -17,
    -12,  17,  14,  17,  17,  38,  23,  11,
     10,  17,  23,  15,  20,  45,  44,  13,
     -8,  22,  24,  27,  26,  33,  26,   3,
    -18,  -4,  21,  24,  27,  23,   9, -11,
    -19,  -3,  11,  21,  23,  16,   7,  -9,
    -27, -11,   4,  13,  14,   4,  -5, -17,
    -53, -34, -21, -11, -28, -14, -24, -43
];

const MG_PIECE_VALUES: [i16; 6] = [
    82,   // Pawns
    337,  // Knights
    365,  // Bishops
    477,  // Rooks
    1025, // Queens
    0,    // Kings
];
const EG_PIECE_VALUES: [i16; 6] = [
    94,  // Pawns
    281, // Knights
    297, // Bishops
    512, // Rooks
    936, // Queens
    0,   // Kings
];

const MG_PESTO: [[i16; 64]; 6] = [
    MG_PAWN_TABLE,
    MG_KNIGHT_TABLE,
    MG_BISHOP_TABLE,
    MG_ROOK_TABLE,
    MG_QUEEN_TABLE,
    MG_KING_TABLE,
];
const EG_PESTO: [[i16; 64]; 6] = [
    EG_PAWN_TABLE,
    EG_KNIGHT_TABLE,
    EG_BISHOP_TABLE,
    EG_ROOK_TABLE,
    EG_QUEEN_TABLE,
    EG_KING_TABLE,
];

const GAMEPHASE_INCREMENTAL: [i16; 12] = [0, 0, 1, 1, 1, 1, 2, 2, 4, 4, 0, 0];
const MG_TABLE: [[i16; 64]; 12] = initialize_tables(MG_PIECE_VALUES, MG_PESTO);
const EG_TABLE: [[i16; 64]; 12] = initialize_tables(EG_PIECE_VALUES, EG_PESTO);
const CHECKMATE: i64 = 100000000;

pub static MAX_DEPTH: AtomicU8 = AtomicU8::new(6);
const DEBUG: bool = true;

pub const fn initialize_tables(piece_vals: [i16; 6], pesto: [[i16; 64]; 6]) -> [[i16; 64]; 12] {
    let mut table = [[0; 64]; 12];
    let mut ptype = 0;
    while ptype < 6 {
        let mut sq = 0;
        while sq < 64 {
            table[ptype * 2 + 1][sq] = piece_vals[ptype] + pesto[ptype][sq];
            table[ptype * 2][sq] = piece_vals[ptype] + pesto[ptype][sq ^ 0b111000];
            sq += 1;
        }
        ptype += 1;
    }
    table
}

fn eval(board: ArrayBoard) -> i64 {
    let mut game_phase = 0;
    let mut w_mg = 0;
    let mut b_mg = 0;
    let mut w_eg = 0;
    let mut b_eg = 0;
    for sq in 0..64 {
        let piece = board.get_piece(sq) as usize;
        if piece == 0 {
            continue;
        }
        let piece_f = piece - 2;
        if is_piece_white(piece as u32) {
            w_mg += MG_TABLE[piece_f][sq] as i64;
            w_eg += EG_TABLE[piece_f][sq] as i64;
        } else {
            b_mg += MG_TABLE[piece_f][sq] as i64;
            b_eg += EG_TABLE[piece_f][sq] as i64;
        }
        game_phase += GAMEPHASE_INCREMENTAL[piece_f] as i64;
    }
    let (mg_score, eg_score) = if board.white_to_move() {
        (w_mg - b_mg, w_eg - b_eg)
    } else {
        (b_mg - w_mg, b_eg - w_eg)
    };
    // Tapered eval: as the game approaches endgame, weigh the end game evaluation more heavily.
    // Endgame is decided based on number of minor pieces remaining.
    let mg_phase = cmp::max(game_phase, 24);
    let eg_phase = 24 - mg_phase;
    (mg_phase * mg_score + eg_phase * eg_score) / 24
}

fn print_info(score: i64, mate_in: Option<i8>, nodes: u64, pv: &str) {
    if !DEBUG {
        return;
    }
    match mate_in {
        Some(m) => println!(
            "info depth {MAX_DEPTH:?} score mate {mi} nodes {nodes} pv {pv}",
            mi = (m + 1) / 2 * ((score / CHECKMATE) as i8)
        ),
        None => println!("info depth {MAX_DEPTH:?} score cp {score} nodes {nodes} pv {pv}"),
    }
}

pub fn search(
    board: ArrayBoard,
    mut alpha: i64,
    beta: i64,
    depth: u8,
) -> (String, i64, Option<i8>, u64) {
    if depth == MAX_DEPTH.load(Ordering::Relaxed) {
        return ("".to_string(), eval(board), None, /* nodes */ 1);
    }
    let moves = board.generate_moves();
    if moves.len() == 0 {
        if board.is_king_checked() {
            return ("".to_string(), -CHECKMATE, Some(1), 1);
        }
        return ("".to_string(), 0, None, 1);
    }

    let mut nodes = 0;
    let mut best_mate_in: Option<i8> = None;
    let mut best_pv: String = String::from("");

    for (i, mv) in moves.into_iter().enumerate() {
        if depth == 0 {
            println!("info currmove {} currmovenumber {i}", mv.to_string());
        }
        let new_board = board.make_move(&mv);
        let (pv, score, mate_in, child_nodes) = search(new_board, -beta, -alpha, depth + 1);
        nodes += child_nodes;

        if -score >= beta {
            return (
                mv.to_string() + " " + &pv,
                beta,
                match best_mate_in {
                    None => None,
                    Some(m) => Some(m + 1),
                },
                nodes,
            );
        }
        if -score > alpha {
            alpha = -score;
            best_mate_in = mate_in;
            best_pv = mv.to_string() + " " + &pv.to_string();
            if depth == 0 {
                print_info(-score, mate_in, nodes, &best_pv);
            }
        } else if score == -CHECKMATE &&
                let Some(bm) = best_mate_in &&
                let Some(m) = mate_in &&
                m < bm {
            println!("{}{} Found a better CHECKMATE best_mate_in {best_mate_in:?}  mate_in: {m}  score: {score} {:?}",
            "  ".repeat(depth as usize), if board.white_to_move() { "W" } else {"B"}, mate_in);
            let mut buffer = String::new();
            io::stdin().read_line(&mut buffer).ok();
            alpha = -score;
            best_mate_in = mate_in;
            best_pv = mv.to_string() + " " + &pv.to_string();
            if depth == 0 {
                print_info(-score, mate_in, nodes, &best_pv);
            }
        }
    }
    (
        best_pv,
        alpha,
        match best_mate_in {
            None => None,
            Some(m) => Some(m + 1),
        },
        nodes,
    )
}
