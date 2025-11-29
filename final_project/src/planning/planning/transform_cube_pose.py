import rclpy
from rclpy.node import Node
from tf2_ros import Buffer, TransformListener
from geometry_msgs.msg import PointStamped
import numpy as np
from scipy.spatial.transform import Rotation as R

class TransformCubePose(Node):
    def __init__(self):
        super().__init__('transform_cube_pose')

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.cube_pose_sub = self.create_subscription(
            PointStamped,
            '/cube_pose',
            self.cube_pose_callback,
            10
        )

        self.cube_pose_pub = self.create_publisher(PointStamped, '/cube_pose_base_link', 1) # Please ensure this is filled

        # self.timer = self.create_timer(0.1, self.publish_transformed_pose)

        rclpy.spin_once(self, timeout_sec=2)
        self.cube_pose = None

    def cube_pose_callback(self, msg: PointStamped):
        if self.cube_pose is None:
            self.cube_pose = self.transform_cube_pose(msg)
        self.cube_pose_pub.publish(self.cube_pose)

    def transform_cube_pose(self, msg: PointStamped):
        """ 
        Transform point into base_link frame
        Args: 
            - msg: PointStamped - The message from /cube_pose, of the position of the cube in camera_depth_optical_frame
        Returns:
            Point: point in base_link_frame in form [x, y, z]
        """

        transform = self.tf_buffer.lookup_transform('base_link', "camera_depth_optical_frame", rclpy.time.Time(), timeout=rclpy.duration.Duration(seconds=5.0))
        
        t = transform.transform.translation
        translation = np.array([t.x, t.y, t.z])
        q = transform.transform.rotation
        quat = np.array([q.x, q.y, q.z, q.w])
        r = R.from_quat(quat)
        R_base_camera = r.as_matrix()
        T = np.eye(4)
        T[:3, :3] = R_base_camera
        T[:3, 3] = translation

        p_cam = np.array([msg.point.x, msg.point.y, msg.point.z, 1.0])
        p_base = T @ p_cam

        point_base = PointStamped()
        point_base.header.stamp = self.get_clock().now().to_msg()
        point_base.header.frame_id = 'base_link'
        point_base.point.x = float(p_base[0])
        point_base.point.y = float(p_base[1])
        point_base.point.z = float(p_base[2])
        return point_base
    def publish_transformed_pose(self):
        if self.cube_pose is None:
            return

        transformed = self.transform_cube_pose(self.cube_pose)
        if transformed is not None:
            self.cube_pose_pub.publish(transformed)

def main(args=None):
    rclpy.init(args=args)
    node = TransformCubePose()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
