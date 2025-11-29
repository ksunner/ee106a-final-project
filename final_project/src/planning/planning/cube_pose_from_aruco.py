#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PointStamped
from tf2_ros import Buffer, TransformListener
import rclpy.time

class CubePoseFromAruco(Node):
    def __init__(self):
        super().__init__('cube_pose_from_aruco')

        # Declare configurable parameter for cube marker ID
        self.declare_parameter('cube_marker_id', 20)
        self.cube_marker_id = (
            self.get_parameter('cube_marker_id').get_parameter_value().integer_value
        )

        self.get_logger().info(f"Tracking cube at ar_marker_{self.cube_marker_id}")

        # TF Buffer + Listener
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # Publisher for cube pose in base_link frame
        self.pub = self.create_publisher(PointStamped, '/cube_pose_base_link', 10)
        # Timer to attempt TF lookup at 20 Hz
        self.timer = self.create_timer(0.05, self.lookup_and_publish)

    def lookup_and_publish(self):
        cube_frame = f'ar_marker_{self.cube_marker_id}'
        target_frame = 'base_link'

        try:
            t = self.tf_buffer.lookup_transform(
                target_frame,
                cube_frame,
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=0.1)
            )
        except Exception as e:
            # No marker yet → do nothing
            return

        # Create PointStamped with cube position
        msg = PointStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = target_frame

        msg.point.x = t.transform.translation.x
        msg.point.y = t.transform.translation.y
        msg.point.z = t.transform.translation.z

        self.pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = CubePoseFromAruco()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
