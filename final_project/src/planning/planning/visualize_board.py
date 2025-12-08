#!/usr/bin/env python3
"""
Chess Board Visualization Tool

Subscribes to all chess square positions and prints them in a grid format.
Useful for debugging and verifying calibration.

Usage:
    ros2 run planning visualize_board
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PointStamped
import numpy as np


class BoardVisualizer(Node):
    """Visualizes chess board square positions."""

    def __init__(self):
        super().__init__('board_visualizer')

        # Storage for square positions
        self.square_positions = {}
        self.subscribers = {}

        # Create subscribers for all 64 squares
        files = 'abcdefgh'
        ranks = '12345678'

        for file_char in files:
            for rank_char in ranks:
                square = f"{file_char}{rank_char}"
                topic = f'/chess_square/{square}'

                self.subscribers[square] = self.create_subscription(
                    PointStamped,
                    topic,
                    lambda msg, sq=square: self.square_callback(msg, sq),
                    10
                )

        # Timer to print board periodically
        self.create_timer(2.0, self.print_board)

        self.get_logger().info("Board Visualizer started")
        self.get_logger().info("Waiting for square positions from calibrator...")

    def square_callback(self, msg, square):
        """Store received square position."""
        self.square_positions[square] = np.array([
            msg.point.x,
            msg.point.y,
            msg.point.z
        ])

    def print_board(self):
        """Print board in a nice grid format."""
        if len(self.square_positions) == 0:
            self.get_logger().info("No square positions received yet. Is the calibrator running?")
            return

        if len(self.square_positions) < 64:
            self.get_logger().info(f"Received {len(self.square_positions)}/64 squares")
            return

        print("\n" + "="*80)
        print("CHESS BOARD CALIBRATION - Square Positions")
        print("="*80)

        files = 'abcdefgh'
        ranks = '87654321'  # Print from top to bottom

        # Print board with coordinates
        print("\nBoard layout (z-heights in mm above base_link):\n")
        print("     a      b      c      d      e      f      g      h")
        print("  " + "-"*64)

        for rank in ranks:
            row = f"{rank} |"
            for file_char in files:
                square = f"{file_char}{rank}"
                if square in self.square_positions:
                    pos = self.square_positions[square]
                    z_mm = pos[2] * 1000  # Convert to mm
                    row += f" {z_mm:5.0f} "
                else:
                    row += "   -   "
            row += f"| {rank}"
            print(row)

        print("  " + "-"*64)
        print("     a      b      c      d      e      f      g      h")

        # Print detailed corner positions
        print("\nCorner positions (in meters, base_link frame):")
        corners = ['a1', 'h1', 'h8', 'a8']
        for corner in corners:
            if corner in self.square_positions:
                pos = self.square_positions[corner]
                print(f"  {corner}: x={pos[0]:7.4f}, y={pos[1]:7.4f}, z={pos[2]:7.4f}")

        # Calculate and print board statistics
        print("\nBoard Statistics:")

        # Calculate board dimensions
        if all(c in self.square_positions for c in ['a1', 'h1', 'a8', 'h8']):
            a1 = self.square_positions['a1']
            h1 = self.square_positions['h1']
            a8 = self.square_positions['a8']
            h8 = self.square_positions['h8']

            width_bottom = np.linalg.norm(h1 - a1)
            width_top = np.linalg.norm(h8 - a8)
            height_left = np.linalg.norm(a8 - a1)
            height_right = np.linalg.norm(h8 - h1)

            print(f"  Bottom width (a1-h1): {width_bottom*1000:.1f} mm")
            print(f"  Top width (a8-h8):    {width_top*1000:.1f} mm")
            print(f"  Left height (a1-a8):  {height_left*1000:.1f} mm")
            print(f"  Right height (h1-h8): {height_right*1000:.1f} mm")

            # Calculate average square size
            avg_square_width = (width_bottom + width_top) / 2 / 7
            avg_square_height = (height_left + height_right) / 2 / 7

            print(f"  Average square width:  {avg_square_width*1000:.1f} mm")
            print(f"  Average square height: {avg_square_height*1000:.1f} mm")

            # Check if board is square
            square_deviation = abs(avg_square_width - avg_square_height) / avg_square_width * 100
            print(f"  Square deviation: {square_deviation:.1f}%")

            if square_deviation > 5:
                print("  WARNING: Board appears distorted (>5% deviation from square)")

        # Calculate board center
        center_squares = ['d4', 'd5', 'e4', 'e5']
        if all(sq in self.square_positions for sq in center_squares):
            center = np.mean([self.square_positions[sq] for sq in center_squares], axis=0)
            print(f"  Board center: x={center[0]:7.4f}, y={center[1]:7.4f}, z={center[2]:7.4f}")

        print("="*80 + "\n")


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    node = BoardVisualizer()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
