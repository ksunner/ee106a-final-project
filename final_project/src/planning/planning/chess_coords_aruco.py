#!/usr/bin/env python3
"""
Chess Board Calibration and Coordinate System using ArUco Markers

This module provides board calibration using 4 ArUco markers placed at the corners:
- ar_marker_100 at a1 (bottom-left, white's perspective)
- ar_marker_101 at h1 (bottom-right)
- ar_marker_102 at h8 (top-right)
- ar_marker_103 at a8 (top-left)

The calibration calculates the center position of all 64 squares.
Calibration data is saved to ~/.ros/chess_calibration.yaml and auto-loaded on startup.
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PointStamped
from tf2_ros import Buffer, TransformListener
import rclpy.time
import numpy as np
from std_srvs.srv import Trigger
import yaml
import os
from pathlib import Path


class ChessBoardCalibrator(Node):
    """
    Calibrates chess board using ArUco markers at corners.

    Markers are placed at:
    - 100: a1 (bottom-left)
    - 101: h1 (bottom-right)
    - 102: h8 (top-right)
    - 103: a8 (top-left)
    """

    def __init__(self):
        super().__init__('chess_board_calibrator')

        # ArUco marker IDs at corners
        self.marker_ids = {
            'a1': 100,
            'h1': 101,
            'h8': 102,
            'a8': 103
        }

        # Store detected marker positions
        self.marker_positions = {}
        self.calibrated = False
        self.square_centers = {}  # Dict mapping square notation to (x, y, z)

        # Calibration file path
        self.calibration_file = Path.home() / '.ros' / 'chess_calibration.yaml'
        self.calibration_file.parent.mkdir(parents=True, exist_ok=True)

        # TF listener
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # Publisher for board center
        self.board_center_pub = self.create_publisher(
            PointStamped,
            '/chess_board_center',
            10
        )

        # Dictionary to store publishers for each square
        self.square_pubs = {}

        # Service to trigger calibration
        self.calibration_service = self.create_service(
            Trigger,
            '/calibrate_chess_board',
            self.calibrate_callback
        )

        # Timer to continuously lookup markers
        self.timer = self.create_timer(0.1, self.lookup_markers)

        self.get_logger().info("Chess Board Calibrator initialized")

        # Try to load previous calibration
        if self.load_calibration():
            self.get_logger().info("✓ Loaded previous calibration from file")
            self.get_logger().info(f"  File: {self.calibration_file}")
            self.get_logger().info("  To recalibrate, call service '/calibrate_chess_board'")

            # Start publishing loaded positions
            self.create_timer(0.1, self.publish_all_squares)
            self.publish_board_center()
        else:
            self.get_logger().info("No previous calibration found")
            self.get_logger().info("Place ArUco markers at: a1(100), h1(101), h8(102), a8(103)")
            self.get_logger().info("Call service '/calibrate_chess_board' when ready")

    def lookup_markers(self):
        """Continuously lookup marker positions via TF."""
        if self.calibrated:
            return  # Stop looking once calibrated

        base_frame = "base_link"

        for square, marker_id in self.marker_ids.items():
            ar_frame = f"ar_marker_{marker_id}"

            try:
                t = self.tf_buffer.lookup_transform(
                    base_frame,
                    ar_frame,
                    rclpy.time.Time(),
                    timeout=rclpy.duration.Duration(seconds=1.0)
                )

                # Store position
                pos = np.array([
                    t.transform.translation.x,
                    t.transform.translation.y,
                    t.transform.translation.z
                ])
                self.marker_positions[square] = pos

                # Log when we successfully detect a marker (only once)
                if not hasattr(self, f'_logged_{square}'):
                    self.get_logger().info(f"Detected marker {marker_id} at {square}: ({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f})")
                    setattr(self, f'_logged_{square}', True)

            except Exception as e:
                # Log the actual error for debugging
                if not hasattr(self, f'_error_logged_{square}'):
                    self.get_logger().warn(f"Cannot find transform for {ar_frame}: {str(e)}")
                    setattr(self, f'_error_logged_{square}', True)
                continue

    def calibrate_callback(self, request, response):
        """Service callback to perform calibration."""
        self.get_logger().info("Calibration service called - looking for markers...")

        # Force fresh marker lookup even if previously calibrated
        self.calibrated = False
        self.marker_positions.clear()

        # Clear logging flags to allow fresh detection messages
        for square in self.marker_ids.keys():
            if hasattr(self, f'_logged_{square}'):
                delattr(self, f'_logged_{square}')
            if hasattr(self, f'_error_logged_{square}'):
                delattr(self, f'_error_logged_{square}')

        # Directly call lookup_markers multiple times to detect markers
        # Don't rely on the timer callback
        import time
        max_attempts = 10
        attempt = 0

        while attempt < max_attempts and len(self.marker_positions) < 4:
            self.lookup_markers()  # Directly call lookup
            attempt += 1
            if len(self.marker_positions) < 4:
                time.sleep(0.2)  # Brief pause between attempts
                self.get_logger().info(f"Searching for markers... ({len(self.marker_positions)}/4 detected, attempt {attempt}/{max_attempts})")

        # Check if all 4 markers are detected
        if len(self.marker_positions) < 4:
            detected = list(self.marker_positions.keys())
            response.success = False
            response.message = f"Only {len(detected)} markers detected: {detected}. Need all 4 corners."
            self.get_logger().error(response.message)
            return response

        # Perform calibration
        success = self.calibrate_board()

        if success:
            # Save calibration to file
            if self.save_calibration():
                self.get_logger().info(f"✓ Calibration saved to {self.calibration_file}")

            response.success = True
            response.message = f"Board calibrated successfully! {len(self.square_centers)} squares computed and saved."
            self.get_logger().info(response.message)

            # Publish board center
            self.publish_board_center()

            # Log some sample squares
            self.log_sample_squares()

            # Start publishing all square positions (only if not already started)
            if not hasattr(self, '_publish_timer'):
                self._publish_timer = self.create_timer(0.1, self.publish_all_squares)
        else:
            response.success = False
            response.message = "Calibration failed. Check marker positions."
            self.get_logger().error(response.message)

        return response

    def calibrate_board(self):
        """
        Calibrate the board using the 4 corner markers.

        Assumes:
        - 8 squares between diagonal corners
        - Square centers align with marker centers
        - Board is roughly planar

        Returns:
            bool: True if calibration successful
        """
        try:
            # Get corner positions
            a1 = self.marker_positions['a1']
            h1 = self.marker_positions['h1']
            h8 = self.marker_positions['h8']
            a8 = self.marker_positions['a8']

            self.get_logger().info("Corner marker positions:")
            self.get_logger().info(f"  a1: [{a1[0]:.3f}, {a1[1]:.3f}, {a1[2]:.3f}]")
            self.get_logger().info(f"  h1: [{h1[0]:.3f}, {h1[1]:.3f}, {h1[2]:.3f}]")
            self.get_logger().info(f"  h8: [{h8[0]:.3f}, {h8[1]:.3f}, {h8[2]:.3f}]")
            self.get_logger().info(f"  a8: [{a8[0]:.3f}, {a8[1]:.3f}, {a8[2]:.3f}]")

            # Calculate all 64 square centers using bilinear interpolation
            # Files: a-h (0-7), Ranks: 1-8 (0-7)
            files = 'abcdefgh'
            ranks = '12345678'

            for file_idx, file_char in enumerate(files):
                for rank_idx, rank_char in enumerate(ranks):
                    # Bilinear interpolation between corners
                    # file_idx: 0 (a) to 7 (h)
                    # rank_idx: 0 (1) to 7 (8)

                    # Interpolation parameters
                    u = file_idx / 7.0  # 0 at file 'a', 1 at file 'h'
                    v = rank_idx / 7.0  # 0 at rank 1, 1 at rank 8

                    # Bilinear interpolation formula:
                    # P(u,v) = (1-u)(1-v)*a1 + u(1-v)*h1 + u*v*h8 + (1-u)*v*a8
                    pos = (
                        (1-u) * (1-v) * a1 +  # a1 corner
                        u * (1-v) * h1 +      # h1 corner
                        u * v * h8 +          # h8 corner
                        (1-u) * v * a8        # a8 corner
                    )

                    square = f"{file_char}{rank_char}"
                    self.square_centers[square] = pos

            self.calibrated = True
            self.get_logger().info(f"Calibrated {len(self.square_centers)} square centers")

            return True

        except Exception as e:
            self.get_logger().error(f"Calibration error: {str(e)}")
            return False

    def publish_board_center(self):
        """Publish the center of the board (between d4, d5, e4, e5)."""
        if not self.calibrated:
            return

        # Board center is average of the 4 center squares
        center_squares = ['d4', 'd5', 'e4', 'e5']
        center_pos = np.mean([self.square_centers[sq] for sq in center_squares], axis=0)

        msg = PointStamped()
        msg.header.frame_id = "base_link"
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.point.x = float(center_pos[0])
        msg.point.y = float(center_pos[1])
        msg.point.z = float(center_pos[2])

        self.board_center_pub.publish(msg)
        self.get_logger().info(
            f"Board center: [{center_pos[0]:.3f}, {center_pos[1]:.3f}, {center_pos[2]:.3f}]"
        )

    def log_sample_squares(self):
        """Log positions of some sample squares."""
        samples = ['a1', 'a8', 'h1', 'h8', 'd4', 'e4', 'e2']

        self.get_logger().info("Sample square positions:")
        for sq in samples:
            if sq in self.square_centers:
                pos = self.square_centers[sq]
                self.get_logger().info(
                    f"  {sq}: [{pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f}]"
                )

    def get_square_position(self, square):
        """
        Get the 3D position of a chess square center.

        Args:
            square: Chess notation (e.g., 'e4')

        Returns:
            numpy.array: [x, y, z] position or None if not calibrated
        """
        if not self.calibrated:
            self.get_logger().warn("Board not calibrated yet")
            return None

        if square not in self.square_centers:
            self.get_logger().error(f"Invalid square: {square}")
            return None

        return self.square_centers[square]

    def save_calibration(self):
        """
        Save calibration data to YAML file.

        Returns:
            bool: True if save successful
        """
        try:
            # Convert numpy arrays to lists for YAML serialization
            data = {
                'square_centers': {
                    square: pos.tolist()
                    for square, pos in self.square_centers.items()
                }
            }

            with open(self.calibration_file, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)

            return True

        except Exception as e:
            self.get_logger().error(f"Failed to save calibration: {str(e)}")
            return False

    def load_calibration(self):
        """
        Load calibration data from YAML file.

        Returns:
            bool: True if load successful
        """
        try:
            if not self.calibration_file.exists():
                return False

            with open(self.calibration_file, 'r') as f:
                data = yaml.safe_load(f)

            if not data or 'square_centers' not in data:
                return False

            # Convert lists back to numpy arrays
            self.square_centers = {
                square: np.array(pos)
                for square, pos in data['square_centers'].items()
            }

            self.calibrated = True
            self.get_logger().info(f"Loaded {len(self.square_centers)} square positions")

            return True

        except Exception as e:
            self.get_logger().error(f"Failed to load calibration: {str(e)}")
            return False

    def publish_all_squares(self):
        """Publish all square positions continuously."""
        if not self.calibrated:
            return

        for square, pos in self.square_centers.items():
            # Create publisher for this square if it doesn't exist
            if square not in self.square_pubs:
                topic_name = f'/chess_square/{square}'
                self.square_pubs[square] = self.create_publisher(
                    PointStamped,
                    topic_name,
                    10
                )

            # Publish position
            msg = PointStamped()
            msg.header.frame_id = "base_link"
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.point.x = float(pos[0])
            msg.point.y = float(pos[1])
            msg.point.z = float(pos[2])

            self.square_pubs[square].publish(msg)


def main_calibrator(args=None):
    """Main entry point for calibrator node."""
    rclpy.init(args=args)
    node = ChessBoardCalibrator()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    # Run calibrator by default
    main_calibrator()
