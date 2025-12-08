#!/usr/bin/env python3
"""
ArUco Detection Checker

This script helps debug ArUco marker detection issues by:
1. Subscribing to camera topics and checking if images are being published
2. Subscribing to ArUco marker topics and displaying detected markers
3. Checking TF transforms for detected markers

Usage:
    ros2 run planning check_aruco_detection
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from ros2_aruco_interfaces.msg import ArucoMarkers
from geometry_msgs.msg import PoseArray
from tf2_ros import Buffer, TransformListener
import rclpy.time


class ArucoDetectionChecker(Node):
    """Debugging node for ArUco detection."""

    def __init__(self):
        super().__init__('aruco_detection_checker')

        self.get_logger().info("=== ArUco Detection Checker ===")

        # Track what we've received
        self.image_received = False
        self.camera_info_received = False
        self.markers_received = False
        self.detected_marker_ids = set()

        # TF listener
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # Subscribe to camera topics
        self.image_sub = self.create_subscription(
            Image,
            '/camera1/image_raw',
            self.image_callback,
            10
        )

        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            '/camera1/camera_info',
            self.camera_info_callback,
            10
        )

        # Subscribe to ArUco topics
        self.markers_sub = self.create_subscription(
            ArucoMarkers,
            '/aruco_markers',
            self.markers_callback,
            10
        )

        self.poses_sub = self.create_subscription(
            PoseArray,
            '/aruco_poses',
            self.poses_callback,
            10
        )

        # Timer to print status
        self.create_timer(2.0, self.print_status)

        # Timer to check TF
        self.create_timer(1.0, self.check_tf)

        self.get_logger().info("Waiting for topics...")

    def image_callback(self, msg):
        """Callback for image topic."""
        if not self.image_received:
            self.image_received = True
            self.get_logger().info(f"✓ Camera image received: {msg.width}x{msg.height}, encoding={msg.encoding}")

    def camera_info_callback(self, msg):
        """Callback for camera info topic."""
        if not self.camera_info_received:
            self.camera_info_received = True
            self.get_logger().info(f"✓ Camera info received: frame_id={msg.header.frame_id}")
            self.get_logger().info(f"  Camera matrix K: {msg.k}")

    def markers_callback(self, msg):
        """Callback for ArUco markers."""
        if not self.markers_received:
            self.markers_received = True
            self.get_logger().info("✓ ArUco markers topic is publishing")

        if len(msg.marker_ids) > 0:
            new_ids = set(msg.marker_ids) - self.detected_marker_ids
            if new_ids:
                self.detected_marker_ids.update(new_ids)
                self.get_logger().info(f"✓ NEW MARKERS DETECTED: {sorted(new_ids)}")
                self.get_logger().info(f"  Total markers seen: {sorted(self.detected_marker_ids)}")

    def poses_callback(self, msg):
        """Callback for ArUco poses."""
        if len(msg.poses) > 0:
            self.get_logger().info(f"Received {len(msg.poses)} marker poses")

    def check_tf(self):
        """Check TF transforms for chess markers."""
        chess_marker_ids = [100, 101, 102, 103]
        base_frame = "base_link"

        for marker_id in chess_marker_ids:
            marker_frame = f"aruco_marker_{marker_id}"

            try:
                t = self.tf_buffer.lookup_transform(
                    base_frame,
                    marker_frame,
                    rclpy.time.Time(),
                    timeout=rclpy.duration.Duration(seconds=0.1)
                )

                # Only log once per marker
                if marker_id not in self.detected_marker_ids:
                    self.detected_marker_ids.add(marker_id)
                    pos = t.transform.translation
                    self.get_logger().info(
                        f"✓ TF transform found for marker {marker_id}: "
                        f"[{pos.x:.3f}, {pos.y:.3f}, {pos.z:.3f}]"
                    )

            except Exception:
                # Marker not visible - don't spam logs
                pass

    def print_status(self):
        """Print periodic status update."""
        self.get_logger().info("--- Status ---")
        self.get_logger().info(f"Camera image:     {'✓ OK' if self.image_received else '✗ NOT RECEIVED'}")
        self.get_logger().info(f"Camera info:      {'✓ OK' if self.camera_info_received else '✗ NOT RECEIVED'}")
        self.get_logger().info(f"ArUco topic:      {'✓ OK' if self.markers_received else '✗ NOT RECEIVED'}")
        self.get_logger().info(f"Detected markers: {sorted(self.detected_marker_ids) if self.detected_marker_ids else 'None'}")

        # Provide helpful suggestions
        if not self.image_received:
            self.get_logger().warn("Camera not publishing! Check:")
            self.get_logger().warn("  1. Is camera connected? (ls /dev/video*)")
            self.get_logger().warn("  2. Is camera node running? (ros2 node list | grep camera)")
            self.get_logger().warn("  3. Check topic: ros2 topic echo /camera1/image_raw")

        if not self.markers_received:
            self.get_logger().warn("ArUco node not publishing! Check:")
            self.get_logger().warn("  1. Is aruco_node running? (ros2 node list | grep aruco)")
            self.get_logger().warn("  2. Check parameters: ros2 param list /aruco_node")
            self.get_logger().warn("  3. Check image topic matches camera")

        if self.image_received and self.markers_received and not self.detected_marker_ids:
            self.get_logger().warn("Camera OK, ArUco node OK, but no markers detected!")
            self.get_logger().warn("  1. Are markers visible in camera view?")
            self.get_logger().warn("  2. Are markers printed clearly?")
            self.get_logger().warn("  3. Check marker size parameter (should be 0.05 for 50mm)")
            self.get_logger().warn("  4. Check dictionary (should be DICT_5X5_250)")
            self.get_logger().warn("  5. View camera: ros2 run rqt_image_view rqt_image_view")

        # Check for chess markers specifically
        chess_markers = {100, 101, 102, 103}
        detected_chess = self.detected_marker_ids.intersection(chess_markers)
        missing_chess = chess_markers - self.detected_marker_ids

        if detected_chess:
            self.get_logger().info(f"Chess markers detected: {sorted(detected_chess)}")
        if missing_chess and self.detected_marker_ids:
            self.get_logger().warn(f"Missing chess markers: {sorted(missing_chess)}")

        self.get_logger().info("-" * 40)


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    node = ArucoDetectionChecker()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
