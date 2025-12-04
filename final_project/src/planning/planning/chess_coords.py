"""
Chess Board Coordinate System
Maps chess square notation (a1-h8) to offset coordinates from the ArUco marker center
"""


class ChessCoords:
    """
    Manages chess board coordinate transformations.

    The ArUco marker is placed at the center of the board (intersection of e4, e5, d4, d5).
    Each square is 5.5cm x 5.5cm.

    Coordinate system:
    - a1 is bottom-left (white's perspective)
    - h8 is top-right
    - ArUco marker at board center
    """

    def __init__(self, square_size=0.055):
        """
        Initialize chess coordinate system.

        Args:
            square_size: Size of each chess square in meters (default 0.055m = 5.5cm)
        """
        self.square_size = square_size

        # Files (columns) and ranks (rows)
        self.files = 'abcdefgh'
        self.ranks = '12345678'

        # The ArUco marker is at the center of the board
        # This is the intersection point of the four center squares (d4, d5, e4, e5)
        # Center of board in file/rank coordinates is at (3.5, 3.5)
        # where files go 0-7 (a-h) and ranks go 0-7 (1-8)
        # Adjusted: was off by +1 rank (e3 instead of e2), so shift center up by 1
        self.center_file = 3.5  # Between d and e
        self.center_rank = 4.5  # Adjusted to fix +1 rank offset (between rank 5 and 6)

    def square_to_offset(self, square):
        """
        Convert chess square notation to offset from ArUco marker center.

        Args:
            square: Chess square in algebraic notation (e.g., 'e4', 'a1')

        Returns:
            (dx, dy): Offset from ArUco marker in meters
        """
        if len(square) != 2:
            raise ValueError(f"Invalid square notation: {square}")

        file_char = square[0].lower()
        rank_char = square[1]

        if file_char not in self.files or rank_char not in self.ranks:
            raise ValueError(f"Invalid square notation: {square}")

        # Get file index (0-7 for a-h)
        file_idx = self.files.index(file_char)
        # Get rank index (0-7 for 1-8)
        rank_idx = self.ranks.index(rank_char)

        # Calculate offset from center
        # Based on observations:
        # - e2->e4 went to d8->d6, suggesting both axes are inverted
        # Robot coordinate system (relative to ArUco marker at board center):
        #   -X (dx): increases with file letter (file a -> file h)
        #   -Y (dy): increases with rank number (rank 1 -> rank 8)
        #
        # Negating both axes to correct for inversion
        dx = -(file_idx - self.center_file) * self.square_size
        dy = -(rank_idx - self.center_rank) * self.square_size

        return (dx, dy)

    def validate_square(self, square):
        """
        Validate if a square notation is valid.

        Args:
            square: Chess square notation

        Returns:
            bool: True if valid, False otherwise
        """
        if len(square) != 2:
            return False
        return square[0].lower() in self.files and square[1] in self.ranks


if __name__ == "__main__":
    # Test the chess coordinate system
    chess = ChessCoords()

    print("Chess Board Coordinate System Test")
    print("=" * 60)
    print(f"Square size: {chess.square_size * 100:.1f} cm")
    print(f"ArUco marker at board center (between d4-d5-e4-e5)")
    print()

    # Test corner squares
    test_squares = ['a1', 'a8', 'h1', 'h8', 'd4', 'd5', 'e4', 'e5']

    print("Square -> Offset from ArUco Center")
    print("-" * 60)
    for square in test_squares:
        dx, dy = chess.square_to_offset(square)
        print(f"{square:4s} -> dx={dx:+.4f}m ({dx*100:+.1f}cm), "
              f"dy={dy:+.4f}m ({dy*100:+.1f}cm)")

    print()
    print("The four center squares (around ArUco marker):")
    for sq in ['d4', 'd5', 'e4', 'e5']:
        dx, dy = chess.square_to_offset(sq)
        print(f"  {sq}: dx={dx*100:+.2f}cm, dy={dy*100:+.2f}cm")
