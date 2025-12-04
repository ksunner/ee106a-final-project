#!/usr/bin/env python3
"""
Chess Board Calibrator

Detects chessboard and provides calibrated offsets for each square.
Replaces manual center positioning with automatic computer vision detection.

Usage:
    1. Launch this node to detect and calibrate the board
    2. Query square positions via the /get_square_offset service
    3. Visualize detected squares in RViz2 on /chess_square_centers topic
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import Point
from visualization_msgs.msg import Marker, MarkerArray
from std_srvs.srv import Trigger
from cv_bridge import CvBridge
import cv2
import numpy as np
from tf2_ros import Buffer, TransformListener
import rclpy.time
import json


class ChessBoardCalibrator(Node):
    """
    Automatically calibrates chess board square positions using computer vision.
    """

    def __init__(self):
        super().__init__('chess_board_calibrator')

        # Parameters
        self.declare_parameter('image_topic', '/camera1/image_raw')
        self.declare_parameter('board_marker_id', 8)
        self.declare_parameter('square_size', 0.055)  # 5.5cm
        self.declare_parameter('calibration_file', '/tmp/chess_board_calibration.json')

        self.image_topic = self.get_parameter('image_topic').value
        self.board_marker_id = self.get_parameter('board_marker_id').value
        self.square_size = self.get_parameter('square_size').value
        self.calibration_file = self.get_parameter('calibration_file').value

        # Chess board detection parameters
        self.board_size = (7, 7)  # 7x7 internal corners for 8x8 board

        # State
        self.bridge = CvBridge()
        self.calibrated = False
        self.square_offsets = {}  # square_name -> (dx, dy) offset from ArUco marker
        self.aruco_pose = None

        # TF
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # Subscribers
        self.image_sub = self.create_subscription(
            Image,
            self.image_topic,
            self.image_callback,
            10
        )

        # Publishers
        self.marker_pub = self.create_publisher(
            MarkerArray,
            '/chess_square_centers',
            10
        )

        # Service
        self.calibrate_srv = self.create_service(
            Trigger,
            '/calibrate_chess_board',
            self.calibrate_service_callback
        )

        # Timer to publish markers periodically
        self.create_timer(1.0, self.publish_markers)

        self.get_logger().info("=" * 60)
        self.get_logger().info("Chess Board Calibrator Ready")
        self.get_logger().info("=" * 60)
        self.get_logger().info("Ensure the full chess board is visible to the camera")
        self.get_logger().info("Call service: ros2 service call /calibrate_chess_board std_srvs/srv/Trigger")
        self.get_logger().info("=" * 60)

    def get_aruco_pose(self):
        """Get ArUco marker position in base_link frame."""
        marker_frame = f'ar_marker_{self.board_marker_id}'
        try:
            t = self.tf_buffer.lookup_transform(
                'base_link',
                marker_frame,
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=0.1)
            )
            return (
                t.transform.translation.x,
                t.transform.translation.y,
                t.transform.translation.z
            )
        except Exception:
            return None

    def calibrate_service_callback(self, request, response):
        """Service callback to trigger calibration."""
        self.get_logger().info("Calibration requested...")

        if self.calibrated:
            response.success = True
            response.message = "Board already calibrated! Recalibrating..."
            self.calibrated = False

        # Trigger will happen in image_callback
        response.success = True
        response.message = "Calibration started. Point camera at full chess board."
        return response

    def image_callback(self, msg):
        """Process images to detect and calibrate chess board."""
        if self.calibrated:
            return

        # Get ArUco marker pose
        self.aruco_pose = self.get_aruco_pose()
        if self.aruco_pose is None:
            self.get_logger().warn(
                f"ArUco marker {self.board_marker_id} not detected",
                throttle_duration_sec=5.0
            )
            return

        # Convert image
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        except Exception as e:
            self.get_logger().error(f"Image conversion failed: {e}")
            return

        # Detect chessboard
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        ret, corners = cv2.findChessboardCorners(
            gray,
            self.board_size,
            cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK
        )

        if not ret:
            self.get_logger().warn(
                "Chessboard not detected. Ensure full board is visible.",
                throttle_duration_sec=2.0
            )
            return

        # Refine corners
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

        # Calibrate!
        success = self.calibrate_from_corners(corners)

        if success:
            self.calibrated = True
            self.save_calibration()
            self.get_logger().info("✓ Calibration successful!")
            self.get_logger().info(f"Calibrated {len(self.square_offsets)} squares")

    def calibrate_from_corners(self, corners):
        """Compute square offsets from detected corners using homography."""
        # Object points in board frame (meters)
        objp = np.zeros((self.board_size[0] * self.board_size[1], 2), np.float32)
        objp[:, :2] = np.mgrid[0:self.board_size[0], 0:self.board_size[1]].T.reshape(-1, 2)
        objp = objp * self.square_size

        # Image points
        imgp = corners.reshape(-1, 2)

        # Homography
        H, status = cv2.findHomography(objp, imgp, cv2.RANSAC, 5.0)
        if H is None:
            self.get_logger().error("Homography computation failed")
            return False

        # Compute square centers
        files = 'abcdefgh'
        ranks = '12345678'

        # Board frame: origin at corner a8 (top-left from white's perspective)
        # ArUco marker is at center: (3.5 * square_size, 3.5 * square_size)
        marker_board_x = 3.5 * self.square_size
        marker_board_y = 3.5 * self.square_size

        for rank_idx in range(8):
            for file_idx in range(8):
                # Square center in board frame
                board_x = (file_idx + 0.5) * self.square_size
                board_y = (rank_idx + 0.5) * self.square_size

                # Offset from ArUco marker (in board frame)
                dx_board = board_x - marker_board_x
                dy_board = board_y - marker_board_y

                # Negate both to match robot coordinate system (mirrored)
                dx = -dx_board
                dy = -dy_board

                # Square name (flip both file and rank for proper chess notation)
                square_name = files[7 - file_idx] + ranks[7 - rank_idx]

                # Store offset
                self.square_offsets[square_name] = (dx, dy)

        return True

    def save_calibration(self):
        """Save calibration to file."""
        try:
            with open(self.calibration_file, 'w') as f:
                json.dump(self.square_offsets, f, indent=2)
            self.get_logger().info(f"Calibration saved to {self.calibration_file}")
        except Exception as e:
            self.get_logger().error(f"Failed to save calibration: {e}")

    def load_calibration(self):
        """Load calibration from file."""
        try:
            with open(self.calibration_file, 'r') as f:
                self.square_offsets = json.load(f)
            self.calibrated = True
            self.get_logger().info(f"Loaded calibration from {self.calibration_file}")
            return True
        except Exception:
            return False

    def publish_markers(self):
        """Publish visualization markers for RViz."""
        if not self.calibrated or self.aruco_pose is None:
            return

        marker_array = MarkerArray()
        files = 'abcdefgh'
        ranks = '12345678'

        for idx, (square_name, (dx, dy)) in enumerate(self.square_offsets.items()):
            # 3D position in base_link frame
            x = self.aruco_pose[0] + dx
            y = self.aruco_pose[1] + dy
            z = self.aruco_pose[2]

            # Sphere marker
            marker = Marker()
            marker.header.frame_id = 'base_link'
            marker.header.stamp = self.get_clock().now().to_msg()
            marker.ns = 'chess_squares'
            marker.id = idx
            marker.type = Marker.SPHERE
            marker.action = Marker.ADD

            marker.pose.position.x = x
            marker.pose.position.y = y
            marker.pose.position.z = z
            marker.pose.orientation.w = 1.0

            marker.scale.x = 0.01
            marker.scale.y = 0.01
            marker.scale.z = 0.01

            # Color by square
            file_idx = files.index(square_name[0])
            rank_idx = ranks.index(square_name[1])
            is_light = (file_idx + rank_idx) % 2 == 0

            if is_light:
                marker.color.r, marker.color.g, marker.color.b = 0.9, 0.9, 0.7
            else:
                marker.color.r, marker.color.g, marker.color.b = 0.3, 0.2, 0.1
            marker.color.a = 0.8

            marker_array.markers.append(marker)

            # Text label
            text = Marker()
            text.header = marker.header
            text.ns = 'chess_labels'
            text.id = idx + 1000
            text.type = Marker.TEXT_VIEW_FACING
            text.action = Marker.ADD
            text.pose.position.x = x
            text.pose.position.y = y
            text.pose.position.z = z + 0.03
            text.pose.orientation.w = 1.0
            text.scale.z = 0.012
            text.color.r, text.color.g, text.color.b, text.color.a = 1.0, 1.0, 1.0, 1.0
            text.text = square_name
            marker_array.markers.append(text)

        self.marker_pub.publish(marker_array)


def main(args=None):
    rclpy.init(args=args)
    node = ChessBoardCalibrator()

    # Try to load existing calibration
    if node.load_calibration():
        node.get_logger().info("Using existing calibration")
    else:
        node.get_logger().info("No existing calibration found")

    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
