#!/usr/bin/env python3
"""
Chess Game Parser

Parses chess game files in various notations and converts to move sequences.
Supports:
- Standard Algebraic Notation (SAN): e4, Nf3, Qxd5+
- Simple notation: e2-e4, g1-f3
- PGN format games
"""

import re
from typing import List, Tuple, Optional


class ChessGameParser:
    """Parse chess game files into move sequences."""

    def __init__(self):
        self.files = 'abcdefgh'
        self.ranks = '12345678'

        # Current board state (simplified - just track piece positions)
        self.reset_board()

    def reset_board(self):
        """Reset to initial board position."""
        # Format: piece positions as {square: piece_type}
        self.board = {
            # White pieces
            'a1': 'R', 'b1': 'N', 'c1': 'B', 'd1': 'Q',
            'e1': 'K', 'f1': 'B', 'g1': 'N', 'h1': 'R',
            'a2': 'P', 'b2': 'P', 'c2': 'P', 'd2': 'P',
            'e2': 'P', 'f2': 'P', 'g2': 'P', 'h2': 'P',
            # Black pieces
            'a8': 'r', 'b8': 'n', 'c8': 'b', 'd8': 'q',
            'e8': 'k', 'f8': 'b', 'g8': 'n', 'h8': 'r',
            'a7': 'p', 'b7': 'p', 'c7': 'p', 'd7': 'p',
            'e7': 'p', 'f7': 'p', 'g7': 'p', 'h7': 'p',
        }

    def parse_game_file(self, filename: str) -> List[Tuple[str, str]]:
        """
        Parse a game file and return list of (from_square, to_square) moves.

        Supports multiple formats:
        - Simple: e2-e4 or e2 e4
        - SAN: e4, Nf3, Qxd5+
        - PGN: with move numbers like 1. e4 e5 2. Nf3

        Args:
            filename: Path to game file

        Returns:
            List of (from_square, to_square) tuples
        """
        with open(filename, 'r') as f:
            content = f.read()

        # Try different parsers
        moves = self.parse_simple_notation(content)
        if not moves:
            moves = self.parse_san_notation(content)
        if not moves:
            moves = self.parse_pgn_notation(content)

        return moves

    def parse_simple_notation(self, content: str) -> List[Tuple[str, str]]:
        """
        Parse simple notation: e2-e4, e2 e4, or just e2e4.

        Format:
            e2-e4
            g1-f3
            # Comments start with #
        """
        moves = []
        lines = content.split('\n')

        for line in lines:
            # Remove comments
            line = line.split('#')[0].strip()
            if not line:
                continue

            # Match patterns: e2-e4, e2 e4, or e2e4
            match = re.match(r'([a-h][1-8])[\s-]*([a-h][1-8])', line)
            if match:
                from_sq, to_sq = match.groups()
                moves.append((from_sq, to_sq))

        return moves if moves else None

    def parse_san_notation(self, content: str) -> List[Tuple[str, str]]:
        """
        Parse Standard Algebraic Notation.

        Examples: e4, Nf3, Bxc4, O-O, Qd8+, Ra8#
        """
        moves = []

        # Extract all SAN moves
        # Pattern matches: piece moves, pawn moves, captures, checks, checkmates
        pattern = r'([NBRQK]?[a-h]?[1-8]?x?[a-h][1-8][+#]?|O-O(?:-O)?)'
        san_moves = re.findall(pattern, content)

        for san in san_moves:
            try:
                from_to = self.san_to_squares(san)
                if from_to:
                    moves.append(from_to)
            except Exception as e:
                print(f"Warning: Could not parse '{san}': {e}")
                continue

        return moves if moves else None

    def parse_pgn_notation(self, content: str) -> List[Tuple[str, str]]:
        """
        Parse PGN (Portable Game Notation) format.

        Example:
            1. e4 e5
            2. Nf3 Nc6
            3. Bb5 a6
        """
        # Remove PGN headers [...]
        content = re.sub(r'\[.*?\]', '', content)

        # Remove move numbers
        content = re.sub(r'\d+\.+', '', content)

        # Now parse as SAN
        return self.parse_san_notation(content)

    def san_to_squares(self, san: str) -> Optional[Tuple[str, str]]:
        """
        Convert SAN notation to (from_square, to_square).

        This is a simplified implementation that works for common cases.
        """
        # Remove check/checkmate symbols
        san = san.replace('+', '').replace('#', '').replace('!', '').replace('?', '')

        # Handle castling
        if san == 'O-O' or san == 'O-O-O':
            # Determine whose turn (simplified - assume alternating)
            # This needs board state tracking for full implementation
            return None  # Skip castling for now

        # Extract destination square (always last 2 characters)
        dest = san[-2:]
        if not self.is_valid_square(dest):
            return None

        # Determine piece type
        if san[0].isupper():
            piece = san[0]
            san = san[1:]
        else:
            piece = 'P'  # Pawn

        # Find the piece's current position
        from_square = self.find_piece_square(piece, dest, san)

        if from_square:
            # Update board state
            self.move_piece(from_square, dest)
            return (from_square, dest)

        return None

    def find_piece_square(self, piece: str, dest: str, hint: str = '') -> Optional[str]:
        """
        Find which square the piece is moving from.

        Args:
            piece: Piece type (K, Q, R, B, N, P)
            dest: Destination square
            hint: Additional info (file or rank hint)
        """
        # Search board for pieces of this type
        candidates = []

        for square, p in self.board.items():
            if p.upper() == piece:
                # Check if this piece can move to dest
                # (Simplified - just check it's a different square)
                if square != dest:
                    # Apply hint filters
                    if 'x' in hint:
                        # Capture - check file hint before 'x'
                        file_hint = hint.split('x')[0]
                        if file_hint and square[0] != file_hint:
                            continue
                    elif len(hint) > 2:
                        # File or rank hint
                        if hint[0] in self.files and square[0] != hint[0]:
                            continue
                        elif hint[0] in self.ranks and square[1] != hint[0]:
                            continue

                    candidates.append(square)

        # Return best candidate (for simplicity, return first)
        return candidates[0] if candidates else None

    def move_piece(self, from_sq: str, to_sq: str):
        """Update board state with a move."""
        if from_sq in self.board:
            piece = self.board[from_sq]
            del self.board[from_sq]
            self.board[to_sq] = piece

    def is_valid_square(self, square: str) -> bool:
        """Check if square notation is valid."""
        return (len(square) == 2 and
                square[0] in self.files and
                square[1] in self.ranks)


def main():
    """Test the parser."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python chess_game_parser.py <game_file>")
        sys.exit(1)

    parser = ChessGameParser()
    moves = parser.parse_game_file(sys.argv[1])

    print(f"Parsed {len(moves)} moves:")
    for i, (from_sq, to_sq) in enumerate(moves, 1):
        print(f"{i}. {from_sq} -> {to_sq}")


if __name__ == "__main__":
    main()
