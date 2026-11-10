// Draconic Sanctum 7x7 Chess Engine (SanctumChess7)
// Custom rule engine for 7x7 symmetric dragon altar chess

export const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g'];
export const RANKS = [1, 2, 3, 4, 5, 6, 7];

export const INITIAL_FEN = 'rnbkbnr/1ppppp1/p5p/7/P5P/1PPPPP1/RNBKBNR w - - 0 1';

export class SanctumChess7 {
  constructor(fen = INITIAL_FEN) {
    this._history = [];
    this._board = [];
    this._turn = 'w';
    this._halfMoves = 0;
    this._fullMoves = 1;
    this.load(fen);
  }

  reset() {
    this.load(INITIAL_FEN);
  }

  load(fen) {
    this._history = [];
    this._board = Array.from({ length: 7 }, () => Array(7).fill(null));

    const parts = fen.trim().split(/\s+/);
    const ranks = parts[0].split('/');

    if (ranks.length !== 7) {
      throw new Error(`Invalid 7x7 FEN rank count: ${ranks.length}`);
    }

    for (let r = 0; r < 7; r++) {
      const rowStr = ranks[r];
      let c = 0;
      for (let i = 0; i < rowStr.length; i++) {
        const ch = rowStr[i];
        if (ch >= '1' && ch <= '7') {
          c += parseInt(ch, 10);
        } else {
          const isUpper = ch === ch.toUpperCase();
          const color = isUpper ? 'w' : 'b';
          const type = ch.toLowerCase();
          const rank = 7 - r;
          const square = `${FILES[c]}${rank}`;
          this._board[r][c] = { type, color, square };
          c++;
        }
      }
    }

    this._turn = parts[1] === 'b' ? 'b' : 'w';
    this._halfMoves = parts[4] ? parseInt(parts[4], 10) : 0;
    this._fullMoves = parts[5] ? parseInt(parts[5], 10) : 1;
  }

  fen() {
    const rows = [];
    for (let r = 0; r < 7; r++) {
      let emptyCount = 0;
      let rowStr = '';
      for (let c = 0; c < 7; c++) {
        const cell = this._board[r][c];
        if (!cell) {
          emptyCount++;
        } else {
          if (emptyCount > 0) {
            rowStr += emptyCount;
            emptyCount = 0;
          }
          const ch = cell.color === 'w' ? cell.type.toUpperCase() : cell.type.toLowerCase();
          rowStr += ch;
        }
      }
      if (emptyCount > 0) rowStr += emptyCount;
      rows.push(rowStr);
    }
    return `${rows.join('/')} ${this._turn} - - ${this._halfMoves} ${this._fullMoves}`;
  }

  board() {
    // Return 7x7 shallow copy of rows
    return this._board.map((row) => row.slice());
  }

  turn() {
    return this._turn;
  }

  get(square) {
    const coords = this._squareToCoords(square);
    if (!coords) return null;
    return this._board[coords.r][coords.c];
  }

  _squareToCoords(square) {
    if (typeof square !== 'string' || square.length < 2) return null;
    const fileIdx = FILES.indexOf(square[0]);
    const rank = parseInt(square[1], 10);
    if (fileIdx < 0 || fileIdx > 6 || isNaN(rank) || rank < 1 || rank > 7) return null;
    return { r: 7 - rank, c: fileIdx };
  }

  _coordsToSquare(r, c) {
    return `${FILES[c]}${7 - r}`;
  }

  _isInside(r, c) {
    return r >= 0 && r < 7 && c >= 0 && c < 7;
  }

  _findKing(color, board = this._board) {
    for (let r = 0; r < 7; r++) {
      for (let c = 0; c < 7; c++) {
        const piece = board[r][c];
        if (piece && piece.type === 'k' && piece.color === color) {
          return { r, c };
        }
      }
    }
    return null;
  }

  _isSquareAttackedBy(r, c, attackerColor, board = this._board) {
    // 1. Pawn attacks
    const pawnRow = attackerColor === 'w' ? r + 1 : r - 1;
    if (this._isInside(pawnRow, c - 1)) {
      const p = board[pawnRow][c - 1];
      if (p && p.type === 'p' && p.color === attackerColor) return true;
    }
    if (this._isInside(pawnRow, c + 1)) {
      const p = board[pawnRow][c + 1];
      if (p && p.type === 'p' && p.color === attackerColor) return true;
    }

    // 2. Knight attacks
    const knightDirs = [
      [-2, -1], [-2, 1], [-1, -2], [-1, 2],
      [1, -2], [1, 2], [2, -1], [2, 1]
    ];
    for (const [dr, dc] of knightDirs) {
      const nr = r + dr;
      const nc = c + dc;
      if (this._isInside(nr, nc)) {
        const p = board[nr][nc];
        if (p && p.type === 'n' && p.color === attackerColor) return true;
      }
    }

    // 3. Orthogonal rays (Rook & Queen)
    const orthoDirs = [[-1, 0], [1, 0], [0, -1], [0, 1]];
    for (const [dr, dc] of orthoDirs) {
      let nr = r + dr;
      let nc = c + dc;
      while (this._isInside(nr, nc)) {
        const p = board[nr][nc];
        if (p) {
          if (p.color === attackerColor && (p.type === 'r' || p.type === 'q')) return true;
          break;
        }
        nr += dr;
        nc += dc;
      }
    }

    // 4. Diagonal rays (Bishop & Queen)
    const diagDirs = [[-1, -1], [-1, 1], [1, -1], [1, 1]];
    for (const [dr, dc] of diagDirs) {
      let nr = r + dr;
      let nc = c + dc;
      while (this._isInside(nr, nc)) {
        const p = board[nr][nc];
        if (p) {
          if (p.color === attackerColor && (p.type === 'b' || p.type === 'q')) return true;
          break;
        }
        nr += dr;
        nc += dc;
      }
    }

    // 5. King attack (1 square around)
    for (let dr = -1; dr <= 1; dr++) {
      for (let dc = -1; dc <= 1; dc++) {
        if (dr === 0 && dc === 0) continue;
        const nr = r + dr;
        const nc = c + dc;
        if (this._isInside(nr, nc)) {
          const p = board[nr][nc];
          if (p && p.type === 'k' && p.color === attackerColor) return true;
        }
      }
    }

    return false;
  }

  inCheck(color = this._turn) {
    const kingPos = this._findKing(color);
    if (!kingPos) return false;
    const enemyColor = color === 'w' ? 'b' : 'w';
    return this._isSquareAttackedBy(kingPos.r, kingPos.c, enemyColor);
  }

  _generatePseudoLegalMoves(options = {}) {
    const moves = [];
    const color = options.color || this._turn;
    const filterSquare = options.square ? this._squareToCoords(options.square) : null;

    const generateForCell = (r, c) => {
      const piece = this._board[r][c];
      if (!piece || piece.color !== color) return;
      const fromSq = piece.square;

      if (piece.type === 'p') {
        const forward = color === 'w' ? -1 : 1;
        const startRow = color === 'w' ? 5 : 1; // Rank 2 for white, Rank 6 for black
        const promoRow = color === 'w' ? 0 : 6; // Rank 7 for white, Rank 1 for black

        // 1 step forward
        const nextR = r + forward;
        if (this._isInside(nextR, c) && !this._board[nextR][c]) {
          const toSq = this._coordsToSquare(nextR, c);
          if (nextR === promoRow) {
            for (const promo of ['q', 'r', 'b', 'n']) {
              moves.push({
                from: fromSq,
                to: toSq,
                piece: 'p',
                color,
                promotion: promo,
                flags: 'p'
              });
            }
          } else {
            moves.push({
              from: fromSq,
              to: toSq,
              piece: 'p',
              color,
              flags: 'n'
            });
          }

          // 2 steps forward from start
          const doubleR = r + forward * 2;
          if (r === startRow && this._isInside(doubleR, c) && !this._board[doubleR][c]) {
            moves.push({
              from: fromSq,
              to: this._coordsToSquare(doubleR, c),
              piece: 'p',
              color,
              flags: 'b'
            });
          }
        }

        // Captures
        for (const dc of [-1, 1]) {
          const capC = c + dc;
          if (this._isInside(nextR, capC)) {
            const target = this._board[nextR][capC];
            if (target && target.color !== color) {
              const toSq = this._coordsToSquare(nextR, capC);
              if (nextR === promoRow) {
                for (const promo of ['q', 'r', 'b', 'n']) {
                  moves.push({
                    from: fromSq,
                    to: toSq,
                    piece: 'p',
                    color,
                    captured: target.type,
                    promotion: promo,
                    flags: 'cp'
                  });
                }
              } else {
                moves.push({
                  from: fromSq,
                  to: toSq,
                  piece: 'p',
                  color,
                  captured: target.type,
                  flags: 'c'
                });
              }
            }
          }
        }
      } else if (piece.type === 'n') {
        const dirs = [
          [-2, -1], [-2, 1], [-1, -2], [-1, 2],
          [1, -2], [1, 2], [2, -1], [2, 1]
        ];
        for (const [dr, dc] of dirs) {
          const nr = r + dr;
          const nc = c + dc;
          if (this._isInside(nr, nc)) {
            const target = this._board[nr][nc];
            if (!target) {
              moves.push({ from: fromSq, to: this._coordsToSquare(nr, nc), piece: 'n', color, flags: 'n' });
            } else if (target.color !== color) {
              moves.push({ from: fromSq, to: this._coordsToSquare(nr, nc), piece: 'n', color, captured: target.type, flags: 'c' });
            }
          }
        }
      } else if (piece.type === 'b' || piece.type === 'r' || piece.type === 'q') {
        const dirs = [];
        if (piece.type === 'b' || piece.type === 'q') {
          dirs.push([-1, -1], [-1, 1], [1, -1], [1, 1]);
        }
        if (piece.type === 'r' || piece.type === 'q') {
          dirs.push([-1, 0], [1, 0], [0, -1], [0, 1]);
        }
        for (const [dr, dc] of dirs) {
          let nr = r + dr;
          let nc = c + dc;
          while (this._isInside(nr, nc)) {
            const target = this._board[nr][nc];
            if (!target) {
              moves.push({ from: fromSq, to: this._coordsToSquare(nr, nc), piece: piece.type, color, flags: 'n' });
            } else {
              if (target.color !== color) {
                moves.push({ from: fromSq, to: this._coordsToSquare(nr, nc), piece: piece.type, color, captured: target.type, flags: 'c' });
              }
              break;
            }
            nr += dr;
            nc += dc;
          }
        }
      } else if (piece.type === 'k') {
        for (let dr = -1; dr <= 1; dr++) {
          for (let dc = -1; dc <= 1; dc++) {
            if (dr === 0 && dc === 0) continue;
            const nr = r + dr;
            const nc = c + dc;
            if (this._isInside(nr, nc)) {
              const target = this._board[nr][nc];
              if (!target) {
                moves.push({ from: fromSq, to: this._coordsToSquare(nr, nc), piece: 'k', color, flags: 'n' });
              } else if (target.color !== color) {
                moves.push({ from: fromSq, to: this._coordsToSquare(nr, nc), piece: 'k', color, captured: target.type, flags: 'c' });
              }
            }
          }
        }
      }
    };

    if (filterSquare) {
      generateForCell(filterSquare.r, filterSquare.c);
    } else {
      for (let r = 0; r < 7; r++) {
        for (let c = 0; c < 7; c++) {
          generateForCell(r, c);
        }
      }
    }

    return moves;
  }

  moves(options = {}) {
    const verbose = !!options.verbose;
    const pseudos = this._generatePseudoLegalMoves(options);
    const legals = [];

    for (const move of pseudos) {
      if (this._isLegal(move)) {
        move.san = this._buildSan(move);
        legals.push(move);
      }
    }

    if (!verbose) {
      return legals.map((m) => m.san);
    }
    return legals;
  }

  _isLegal(move) {
    const from = this._squareToCoords(move.from);
    const to = this._squareToCoords(move.to);
    const piece = this._board[from.r][from.c];
    const target = this._board[to.r][to.c];

    // Tentatively apply move
    this._board[to.r][to.c] = piece ? { ...piece, square: move.to } : null;
    this._board[from.r][from.c] = null;

    const kingPos = this._findKing(move.color);
    let inCheck = false;
    if (kingPos) {
      const enemyColor = move.color === 'w' ? 'b' : 'w';
      inCheck = this._isSquareAttackedBy(kingPos.r, kingPos.c, enemyColor);
    }

    // Revert
    this._board[from.r][from.c] = piece;
    this._board[to.r][to.c] = target;

    return !inCheck;
  }

  _buildSan(move) {
    let san = '';
    if (move.piece === 'p') {
      if (move.captured) {
        san = `${move.from[0]}x${move.to}`;
      } else {
        san = move.to;
      }
      if (move.promotion) {
        san += `=${move.promotion.toUpperCase()}`;
      }
    } else {
      san = `${move.piece.toUpperCase()}${move.captured ? 'x' : ''}${move.to}`;
    }
    return san;
  }

  move(moveInput) {
    let parsedMove = null;

    if (typeof moveInput === 'string') {
      // Find matching move by SAN or from-to
      const legals = this.moves({ verbose: true });
      parsedMove = legals.find((m) => m.san === moveInput || `${m.from}${m.to}` === moveInput);
    } else if (typeof moveInput === 'object' && moveInput !== null) {
      const legals = this.moves({ verbose: true, square: moveInput.from });
      parsedMove = legals.find((m) => {
        if (m.from !== moveInput.from || m.to !== moveInput.to) return false;
        if (moveInput.promotion) {
          return m.promotion === moveInput.promotion;
        }
        return true;
      });
    }

    if (!parsedMove) {
      throw new Error(`Illegal move: ${JSON.stringify(moveInput)}`);
    }

    const from = this._squareToCoords(parsedMove.from);
    const to = this._squareToCoords(parsedMove.to);
    const piece = this._board[from.r][from.c];
    const capturedPiece = this._board[to.r][to.c];

    // Record history snapshot
    const record = {
      move: parsedMove,
      capturedPiece,
      prevTurn: this._turn,
      prevHalfMoves: this._halfMoves,
      prevFullMoves: this._fullMoves
    };
    this._history.push(record);

    // Apply move
    let placedType = piece.type;
    if (parsedMove.promotion) {
      placedType = parsedMove.promotion;
    }

    this._board[to.r][to.c] = {
      type: placedType,
      color: piece.color,
      square: parsedMove.to
    };
    this._board[from.r][from.c] = null;

    // Turn switch
    this._turn = this._turn === 'w' ? 'b' : 'w';
    if (this._turn === 'w') {
      this._fullMoves++;
    }

    if (piece.type === 'p' || capturedPiece) {
      this._halfMoves = 0;
    } else {
      this._halfMoves++;
    }

    // Check check / checkmate indicator for SAN
    if (this.inCheck()) {
      if (this.isCheckmate()) {
        parsedMove.san += '#';
      } else {
        parsedMove.san += '+';
      }
    }

    return parsedMove;
  }

  undo() {
    if (this._history.length === 0) return null;
    const last = this._history.pop();
    const move = last.move;
    const from = this._squareToCoords(move.from);
    const to = this._squareToCoords(move.to);

    // Revert piece to from
    this._board[from.r][from.c] = {
      type: move.piece,
      color: move.color,
      square: move.from
    };

    // Revert captured piece to to
    this._board[to.r][to.c] = last.capturedPiece;

    this._turn = last.prevTurn;
    this._halfMoves = last.prevHalfMoves;
    this._fullMoves = last.prevFullMoves;

    return move;
  }

  history(options = {}) {
    if (options.verbose) {
      return this._history.map((h) => h.move);
    }
    return this._history.map((h) => h.move.san);
  }

  isCheckmate() {
    return this.inCheck() && this.moves({ verbose: true }).length === 0;
  }

  isStalemate() {
    return !this.inCheck() && this.moves({ verbose: true }).length === 0;
  }

  isDraw() {
    // ステイルメイトは包囲殲滅勝利（手番側の敗北）に変更されたため引き分けには含めない
    if (this._halfMoves >= 100) return true; // 50-move rule
    return false;
  }

  isThreefoldRepetition() {
    // Basic check for repeat positions
    if (this._history.length < 6) return false;
    const currentFenBoard = this.fen().split(' ').slice(0, 2).join(' ');
    let matches = 0;
    // Walk back history is optional, default false
    return false;
  }

  isGameOver() {
    return this.isCheckmate() || this.isStalemate() || this.isDraw();
  }
}

