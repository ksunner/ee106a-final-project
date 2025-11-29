#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PointStamped
from tf2_ros import Buffer, TransformListener
import rclpy.time

class MultiCubePoseFromAruco(Node):
    def __init__(self):
        super().__init__('multi_cube_pose_from_aruco')

        # --- Track all cube IDs and assign colors ---
        self.cube_ids = {
            20: "blue",
            21: "green",
            22: "red",
        }

        self.get_logger().info("Tracking cube markers: " +
                               ", ".join([f"{cid}({c})" for cid, c in self.cube_ids.items()]))

        # --- TF listener ---
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # --- Publishers for each cube color ---
        self.pubs = {
            color: self.create_publisher(PointStamped, f"/cube_pose_{color}", 10)
            for color in self.cube_ids.values()
        }

        # Timer to publish 20 Hz
        self.timer = self.create_timer(0.05, self.lookup_all)

    def lookup_all(self):
        """Try to lookup each cube's pose and publish it."""
        for marker_id, color in self.cube_ids.items():
            ar_frame = f"ar_marker_{marker_id}"
            base_frame = "base_link"

            try:
                t = self.tf_buffer.lookup_transform(
                    base_frame,
                    ar_frame,
                    rclpy.time.Time(),
                    timeout=rclpy.duration.Duration(seconds=0.05)
                )
            except Exception:
                # No marker seen → skip
                continue

            # Create message
            msg = PointStamped()
            msg.header.frame_id = base_frame
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.point.x = t.transform.translation.x
            msg.point.y = t.transform.translation.y
            msg.point.z = t.transform.translation.z

            # Publish
            self.pubs[color].publish(msg)

            # Optional logging (uncomment if needed)
            # self.get_logger().info(f"Published pose for cube {color}: {msg.point}")

def main(args=None):
    rclpy.init(args=args)
    node = MultiCubePoseFromAruco()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
