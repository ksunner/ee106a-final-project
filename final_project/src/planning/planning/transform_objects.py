import rclpy
from rclpy.node import Node
from tf2_ros import Buffer, TransformListener
from visualization_msgs.msg import Marker, MarkerArray
import numpy as np
from scipy.spatial.transform import Rotation as R

class TransformObjects(Node):
    def __init__(self):
        super().__init__('transform_objects')

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.objects_sub = self.create_subscription(
            MarkerArray,
            '/detected_objects',
            self.objects_callback,
            10
        )

        self.objects_pub = self.create_publisher(MarkerArray, '/detected_objects_base_link', 10)

        rclpy.spin_once(self, timeout_sec=2)
        self.get_logger().info("Transform Objects node initialized")

    def objects_callback(self, msg: MarkerArray):
        """Transform all detected objects from camera frame to base_link frame"""
        try:
            # Lookup transform from base_link to camera frame
            transform = self.tf_buffer.lookup_transform(
                'base_link',
                "camera_depth_optical_frame",
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=1.0)
            )

            # Extract rotation and translation
            t = transform.transform.translation
            translation = np.array([t.x, t.y, t.z])
            q = transform.transform.rotation
            quat = np.array([q.x, q.y, q.z, q.w])
            r = R.from_quat(quat)
            R_base_camera = r.as_matrix()

            # Build 4x4 transformation matrix
            T = np.eye(4)
            T[:3, :3] = R_base_camera
            T[:3, 3] = translation

            # Transform all markers
            transformed_markers = MarkerArray()

            for marker in msg.markers:
                # Only transform position markers (not text labels)
                if marker.ns == "detected_objects":
                    transformed_marker = Marker()
                    transformed_marker.header.stamp = self.get_clock().now().to_msg()
                    transformed_marker.header.frame_id = 'base_link'
                    transformed_marker.ns = marker.ns
                    transformed_marker.id = marker.id
                    transformed_marker.type = marker.type
                    transformed_marker.action = marker.action

                    # Transform position
                    p_cam = np.array([
                        marker.pose.position.x,
                        marker.pose.position.y,
                        marker.pose.position.z,
                        1.0
                    ])
                    p_base = T @ p_cam

                    transformed_marker.pose.position.x = float(p_base[0])
                    transformed_marker.pose.position.y = float(p_base[1])
                    transformed_marker.pose.position.z = float(p_base[2])
                    transformed_marker.pose.orientation.w = 1.0

                    # Copy other properties
                    transformed_marker.scale = marker.scale
                    transformed_marker.color = marker.color

                    transformed_markers.markers.append(transformed_marker)

                    # Also transform text label
                    text_marker = Marker()
                    text_marker.header.stamp = self.get_clock().now().to_msg()
                    text_marker.header.frame_id = 'base_link'
                    text_marker.ns = "object_labels_base"
                    text_marker.id = marker.id + 1000
                    text_marker.type = Marker.TEXT_VIEW_FACING
                    text_marker.action = Marker.ADD

                    text_marker.pose.position.x = float(p_base[0])
                    text_marker.pose.position.y = float(p_base[1])
                    text_marker.pose.position.z = float(p_base[2] + 0.05)
                    text_marker.pose.orientation.w = 1.0

                    # Find corresponding text from original markers
                    for orig_marker in msg.markers:
                        if orig_marker.ns == "object_labels" and orig_marker.id == marker.id + 1000:
                            text_marker.text = orig_marker.text
                            break

                    text_marker.scale.z = 0.02
                    text_marker.color.r = 1.0
                    text_marker.color.g = 1.0
                    text_marker.color.b = 1.0
                    text_marker.color.a = 1.0

                    transformed_markers.markers.append(text_marker)

            self.objects_pub.publish(transformed_markers)
            self.get_logger().info(f"Transformed {len(transformed_markers.markers)//2} objects to base_link frame")

        except Exception as e:
            self.get_logger().error(f"Failed to transform objects: {str(e)}")

def main(args=None):
    rclpy.init(args=args)
    node = TransformObjects()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
