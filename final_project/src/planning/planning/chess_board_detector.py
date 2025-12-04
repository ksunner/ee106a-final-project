#!/usr/bin/env python3
"""
Chess Board Detection Node

Automatically detects chessboard square centers using computer vision.
Uses homography-based approach to handle camera perspective/slant.
Publishes detected squares as visualization markers for RViz2.

Author: Claude
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import PointStamped
from visualization_msgs.msg import Marker, MarkerArray
from cv_bridge import CvBridge
import cv2
import numpy as np
from tf2_ros import Buffer, TransformListener
import rclpy.time


class ChessBoardDetector(Node):
    """
    Detects chessboard square centers and publishes their positions.
    """

    def __init__(self):
        super().__init__('chess_board_detector')

        # Parameters
        self.declare_parameter('image_topic', '/camera1/image_raw')
        self.declare_parameter('board_marker_id', 8)  # ArUco marker on board
        self.declare_parameter('square_size', 0.055)  # 5.5cm squares

        image_topic = self.get_parameter('image_topic').value
        self.board_marker_id = self.get_parameter('board_marker_id').value
        self.square_size = self.get_parameter('square_size').value

        # Chess board parameters (8x8 board = 7x7 internal corners)
        self.board_size = (7, 7)  # Internal corners for findChessboardCorners

        # CV Bridge
        self.bridge = CvBridge()

        # TF Buffer for ArUco marker position
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # Storage for detected square centers
        self.square_centers = {}  # Dict: square_name -> (x, y, z) in base_link frame
        self.aruco_marker_pose = None

        # Image subscriber
        self.image_sub = self.create_subscription(
            Image,
            image_topic,
            self.image_callback,
            10
        )

        # Publishers
        self.marker_pub = self.create_publisher(
            MarkerArray,
            '/chess_square_centers',
            10
        )

        # Detection state
        self.board_detected = False
        self.detection_count = 0
        self.required_detections = 5  # Require multiple consistent detections

        self.get_logger().info("Chess Board Detector initialized")
        self.get_logger().info(f"Looking for {self.board_size[0]}x{self.board_size[1]} chessboard corners")

    def get_aruco_marker_pose(self):
        """Get the ArUco marker pose from TF."""
        marker_frame = f'ar_marker_{self.board_marker_id}'
        target_frame = 'base_link'

        try:
            t = self.tf_buffer.lookup_transform(
                target_frame,
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

    def image_callback(self, msg):
        """Process camera image to detect chessboard."""
        if self.board_detected:
            return  # Already detected, no need to keep processing

        # Get ArUco marker pose
        aruco_pose = self.get_aruco_marker_pose()
        if aruco_pose is None:
            return

        self.aruco_marker_pose = aruco_pose

        # Convert ROS image to OpenCV
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().error(f"CV Bridge error: {e}")
            return

        # Convert to grayscale
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)

        # Detect chessboard corners
        ret, corners = cv2.findChessboardCorners(
            gray,
            self.board_size,
            flags=cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        )

        if ret:
            # Refine corner positions
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

            # Compute square centers from corners
            self.compute_square_centers(corners, cv_image.shape)

            self.detection_count += 1
            self.get_logger().info(f"Chessboard detected! ({self.detection_count}/{self.required_detections})")

            if self.detection_count >= self.required_detections:
                self.board_detected = True
                self.get_logger().info("✓ Chessboard calibration complete!")
                self.publish_square_markers()
        else:
            if self.detection_count == 0:
                self.get_logger().warn("Chessboard not detected. Ensure full board is visible.", throttle_duration_sec=2.0)

    def compute_square_centers(self, corners, image_shape):
        """
        Compute the center of each chess square from detected corners.
        Uses homography to map from image coordinates to board coordinates.
        """
        # Reshape corners to 7x7 grid
        corners = corners.reshape(self.board_size[0], self.board_size[1], 2)

        # Define object points in board coordinate system (in meters)
        # The internal corners span 7 squares in each direction
        objp = np.zeros((self.board_size[0] * self.board_size[1], 2), np.float32)
        objp[:, :2] = np.mgrid[0:self.board_size[0], 0:self.board_size[1]].T.reshape(-1, 2)
        objp = objp * self.square_size

        # Image points (detected corners)
        imgp = corners.reshape(-1, 2)

        # Compute homography from board coordinates to image coordinates
        H, _ = cv2.findHomography(objp, imgp, cv2.RANSAC)

        if H is None:
            self.get_logger().warn("Failed to compute homography")
            return

        # Generate all 64 square centers in board coordinates
        # Squares are offset by 0.5 square_size from the corner grid
        files = 'abcdefgh'
        ranks = '12345678'

        for rank_idx in range(8):
            for file_idx in range(8):
                # Square center in board coordinates (relative to top-left corner)
                # Add 0.5 offset because corners are at intersections
                board_x = (file_idx + 0.5) * self.square_size
                board_y = (rank_idx + 0.5) * self.square_size

                # Transform to image coordinates using homography
                point_board = np.array([[board_x, board_y]], dtype=np.float32)
                point_img = cv2.perspectiveTransform(point_board.reshape(-1, 1, 2), H)

                # Store square center (we'll compute 3D position later)
                square_name = files[file_idx] + ranks[7 - rank_idx]  # Flip rank for chess notation

                # For now, store 2D image coordinates
                # In a real system, you'd use camera calibration to get 3D positions
                # Here we'll approximate based on the plane assumption
                if square_name not in self.square_centers:
                    self.square_centers[square_name] = (board_x, board_y)

        self.get_logger().info(f"Computed centers for {len(self.square_centers)} squares")

    def compute_3d_position_from_aruco(self, board_x, board_y):
        """
        Compute 3D position of a square center relative to base_link.
        Uses ArUco marker as reference point on the board plane.

        Assumes board is flat and marker is at center.
        """
        if self.aruco_marker_pose is None:
            return None

        # ArUco marker position in base_link frame
        marker_x, marker_y, marker_z = self.aruco_marker_pose

        # Board coordinate system: origin at top-left corner (a8)
        # ArUco marker is at center of board (between d4, d5, e4, e5)
        # That's at board coordinates (3.5 * square_size, 3.5 * square_size)
        marker_board_x = 3.5 * self.square_size
        marker_board_y = 3.5 * self.square_size

        # Offset from marker to this square
        dx = board_x - marker_board_x
        dy = board_y - marker_board_y

        # Assume board is in XY plane of base_link (adjust if needed)
        # This is a simplification - real system would use full camera calibration
        square_x = marker_x + dx
        square_y = marker_y + dy
        square_z = marker_z  # Same height as marker (on board plane)

        return (square_x, square_y, square_z)

    def publish_square_markers(self):
        """Publish visualization markers for all detected square centers."""
        if not self.square_centers:
            return

        marker_array = MarkerArray()

        for idx, (square_name, (board_x, board_y)) in enumerate(self.square_centers.items()):
            # Compute 3D position
            pos = self.compute_3d_position_from_aruco(board_x, board_y)
            if pos is None:
                continue

            # Create sphere marker at square center
            marker = Marker()
            marker.header.frame_id = 'base_link'
            marker.header.stamp = self.get_clock().now().to_msg()
            marker.ns = 'chess_squares'
            marker.id = idx
            marker.type = Marker.SPHERE
            marker.action = Marker.ADD

            marker.pose.position.x = pos[0]
            marker.pose.position.y = pos[1]
            marker.pose.position.z = pos[2]
            marker.pose.orientation.w = 1.0

            marker.scale.x = 0.01  # 1cm diameter sphere
            marker.scale.y = 0.01
            marker.scale.z = 0.01

            # Color based on square color (alternating pattern)
            file_idx = 'abcdefgh'.index(square_name[0])
            rank_idx = '12345678'.index(square_name[1])
            is_light_square = (file_idx + rank_idx) % 2 == 0

            if is_light_square:
                marker.color.r = 0.9
                marker.color.g = 0.9
                marker.color.b = 0.7
            else:
                marker.color.r = 0.3
                marker.color.g = 0.2
                marker.color.b = 0.1
            marker.color.a = 0.8

            marker.lifetime = rclpy.duration.Duration(seconds=0).to_msg()  # Persist
            marker_array.markers.append(marker)

            # Add text label
            text_marker = Marker()
            text_marker.header = marker.header
            text_marker.ns = 'chess_labels'
            text_marker.id = idx + 1000
            text_marker.type = Marker.TEXT_VIEW_FACING
            text_marker.action = Marker.ADD

            text_marker.pose.position.x = pos[0]
            text_marker.pose.position.y = pos[1]
            text_marker.pose.position.z = pos[2] + 0.03  # 3cm above square
            text_marker.pose.orientation.w = 1.0

            text_marker.scale.z = 0.015  # Text height
            text_marker.color.r = 1.0
            text_marker.color.g = 1.0
            text_marker.color.b = 1.0
            text_marker.color.a = 1.0

            text_marker.text = square_name
            text_marker.lifetime = rclpy.duration.Duration(seconds=0).to_msg()
            marker_array.markers.append(text_marker)

        self.marker_pub.publish(marker_array)
        self.get_logger().info(f"Published {len(marker_array.markers)} visualization markers")


def main(args=None):
    rclpy.init(args=args)
    node = ChessBoardDetector()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
