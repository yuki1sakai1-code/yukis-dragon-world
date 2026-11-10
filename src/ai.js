// Wizard's Chess AI Engine for 7x7 Draconic Sanctum
// (Minimax + Alpha-Beta Pruning + Positional Piece-Square Tables)

const PIECE_VALUES = {
  p: 100,
  n: 320,
  b: 330,
  r: 500,
  q: 900,
  k: 20000
};

// 7x7 Positional tables from White's perspective (7 rows x 7 cols = 49 cells)
// r=0: Rank 7 (enemy baseline), r=6: Rank 1 (white baseline)
const PST = {
  p: [
      0,  0,  0,  0,  0,  0,  0, // Rank 7 (Promoted)
     45, 50, 55, 60, 55, 50, 45, // Rank 6 (Near promotion)
     10, 15, 25, 30, 25, 15, 10, // Rank 5 (Attacking)
      5, 10, 20, 25, 20, 10,  5, // Rank 4 (Center dispute)
      0,  0, 10, 15, 10,  0,  0, // Rank 3
      0,  0,  0,  0,  0,  0,  0, // Rank 2 (Starting rank)
      0,  0,  0,  0,  0,  0,  0  // Rank 1
  ],
  n: [
    -35,-20,-10,-10,-10,-20,-35,
    -20,  0, 10, 15, 10,  0,-20,
    -10, 10, 20, 25, 20, 10,-10,
    -10, 15, 25, 30, 25, 15,-10,
    -10, 10, 20, 25, 20, 10,-10,
    -20,  0, 10, 15, 10,  0,-20,
    -35,-20,-10,-10,-10,-20,-35
  ],
  b: [
    -15,-10, -5, -5, -5,-10,-15,
    -10,  5,  5,  5,  5,  5,-10,
     -5,  5, 15, 15, 15,  5, -5,
     -5, 10, 15, 20, 15, 10, -5,
     -5,  5, 15, 15, 15,  5, -5,
    -10,  5,  5,  5,  5,  5,-10,
    -15,-10, -5, -5, -5,-10,-15
  ],
  r: [
      5, 10, 12, 15, 12, 10,  5, // Infiltration rank
     10, 15, 15, 18, 15, 15, 10,
     -5,  0,  0,  5,  0,  0, -5,
     -5,  0,  0,  5,  0,  0, -5,
     -5,  0,  0,  5,  0,  0, -5,
      0,  0,  0,  5,  0,  0,  0,
      0,  5,  5,  8,  5,  5,  0
  ],
  q: [
    -15, -8, -5,  0, -5, -8,-15,
     -8,  0,  5,  8,  5,  0, -8,
     -5,  5, 10, 12, 10,  5, -5,
      0,  8, 12, 16, 12,  8,  0,
     -5,  5, 10, 12, 10,  5, -5,
     -8,  0,  5,  8,  5,  0, -8,
    -15, -8, -5,  0, -5, -8,-15
  ],
  k: [
    -30,-30,-30,-30,-30,-30,-30,
    -30,-30,-30,-30,-30,-30,-30,
    -20,-20,-20,-20,-20,-20,-20,
    -10,-10,-15,-15,-15,-10,-10,
      0,  0, -5,-10, -5,  0,  0,
     10, 15,  0, -5,  0, 15, 10,
     15, 20, 10,  5, 10, 20, 15
  ]
};

export function evaluateBoard(chess) {
  if (chess.isCheckmate()) {
    return chess.turn() === 'w' ? -99999 : 99999;
  }
  // ステイルメイト（手詰まり）は動けなくなった手番側の敗北（包囲勝利: SANCTUM SURROUNDED）
  if (chess.isStalemate()) {
    return chess.turn() === 'w' ? -99999 : 99999;
  }
  if (chess.isDraw() || chess.isThreefoldRepetition()) {
    return 0;
  }

  const board = chess.board();
  let score = 0;

  for (let r = 0; r < 7; r++) {
    for (let c = 0; c < 7; c++) {
      const cell = board[r][c];
      if (!cell) continue;
      const base = PIECE_VALUES[cell.type] || 0;
      const table = PST[cell.type];
      const idx = cell.color === 'w' ? r * 7 + c : (6 - r) * 7 + c;
      const bonus = table ? table[idx] : 0;

      if (cell.color === 'w') {
        score += base + bonus;
      } else {
        score -= base + bonus;
      }
    }
  }
  return score;
}

function orderMoves(moves) {
  return moves.sort((a, b) => {
    const scoreA = (a.captured ? (PIECE_VALUES[a.captured] || 100) * 10 - (PIECE_VALUES[a.piece] || 100) : 0) + (a.promotion ? 800 : 0);
    const scoreB = (b.captured ? (PIECE_VALUES[b.captured] || 100) * 10 - (PIECE_VALUES[b.piece] || 100) : 0) + (b.promotion ? 800 : 0);
    return scoreB - scoreA;
  });
}

function minimax(chess, depth, alpha, beta, maximizingPlayer) {
  if (depth === 0 || chess.isGameOver()) {
    return evaluateBoard(chess);
  }

  const moves = orderMoves(chess.moves({ verbose: true }));
  if (maximizingPlayer) {
    let maxEval = -Infinity;
    for (const move of moves) {
      chess.move(move);
      const ev = minimax(chess, depth - 1, alpha, beta, false);
      chess.undo();
      if (ev > maxEval) maxEval = ev;
      if (ev > alpha) alpha = ev;
      if (beta <= alpha) break;
    }
    return maxEval;
  } else {
    let minEval = Infinity;
    for (const move of moves) {
      chess.move(move);
      const ev = minimax(chess, depth - 1, alpha, beta, true);
      chess.undo();
      if (ev < minEval) minEval = ev;
      if (ev < beta) beta = ev;
      if (beta <= alpha) break;
    }
    return minEval;
  }
}

export function chooseBestMove(chess, depth = 2, isMoveForbidden = null) {
  let moves = orderMoves(chess.moves({ verbose: true }));
  if (isMoveForbidden) {
    const validMoves = moves.filter((m) => !isMoveForbidden(m));
    if (validMoves.length > 0) {
      moves = validMoves;
    }
  }
  if (moves.length === 0) return null;

  const isWhite = chess.turn() === 'w';
  let bestMove = moves[0];

  if (isWhite) {
    let maxVal = -Infinity;
    for (const move of moves) {
      chess.move(move);
      const val = minimax(chess, Math.max(0, depth - 1), -Infinity, Infinity, false);
      chess.undo();
      if (val > maxVal) {
        maxVal = val;
        bestMove = move;
      }
    }
  } else {
    let minVal = Infinity;
    for (const move of moves) {
      chess.move(move);
      const val = minimax(chess, Math.max(0, depth - 1), -Infinity, Infinity, true);
      chess.undo();
      if (val < minVal) {
        minVal = val;
        bestMove = move;
      }
    }
  }

  return bestMove;
}
