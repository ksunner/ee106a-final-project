"""
Modernized ArUco ROS2 Node
Compatible with OpenCV >= 4.7 (tested on 4.12.0)
Original functionality preserved.
"""

import rclpy
import rclpy.node
from rclpy.qos import qos_profile_sensor_data
from cv_bridge import CvBridge
import numpy as np
import cv2
import math
from sensor_msgs.msg import CameraInfo, Image
from geometry_msgs.msg import PoseArray, Pose, TransformStamped
from ros2_aruco_interfaces.msg import ArucoMarkers
from rcl_interfaces.msg import ParameterDescriptor, ParameterType
from tf2_ros import TransformBroadcaster


def quaternion_from_matrix(matrix):
    """Convert a rotation matrix to quaternion."""
    q = np.empty((4,), dtype=np.float64)
    M = np.array(matrix, dtype=np.float64, copy=False)[:4, :4]
    t = np.trace(M)
    if t > M[3, 3]:
        q[3] = t
        q[2] = M[1, 0] - M[0, 1]
        q[1] = M[0, 2] - M[2, 0]
        q[0] = M[2, 1] - M[1, 2]
    else:
        i, j, k = 0, 1, 2
        if M[1, 1] > M[0, 0]:
            i, j, k = 1, 2, 0
        if M[2, 2] > M[i, i]:
            i, j, k = 2, 0, 1
        t = M[i, i] - (M[j, j] + M[k, k]) + M[3, 3]
        q[i] = t
        q[j] = M[i, j] + M[j, i]
        q[k] = M[k, i] + M[i, k]
        q[3] = M[k, j] - M[j, k]
    q *= 0.5 / math.sqrt(t * M[3, 3])
    return q


class ArucoNode(rclpy.node.Node):
    def __init__(self):
        super().__init__("aruco_node")

        # Declare parameters
        self.declare_parameter(
            name="marker_size",
            value=0.0625,
            descriptor=ParameterDescriptor(
                type=ParameterType.PARAMETER_DOUBLE,
                description="Default marker size (m).",
            ),
        )

        self.declare_parameter(
            name="aruco_dictionary_id",
            value="DICT_5X5_250",
            descriptor=ParameterDescriptor(
                type=ParameterType.PARAMETER_STRING,
                description="Aruco dictionary type.",
            ),
        )

        self.declare_parameter(
            name="image_topic",
            value="/camera/image_raw",
            descriptor=ParameterDescriptor(
                type=ParameterType.PARAMETER_STRING,
                description="Image topic to subscribe.",
            ),
        )

        self.declare_parameter(
            name="camera_info_topic",
            value="/camera/camera_info",
            descriptor=ParameterDescriptor(
                type=ParameterType.PARAMETER_STRING,
                description="Camera info topic to subscribe.",
            ),
        )

        self.declare_parameter(
            name="camera_frame",
            value="",
            descriptor=ParameterDescriptor(
                type=ParameterType.PARAMETER_STRING,
                description="Camera optical frame.",
            ),
        )

        # Load parameters
        self.marker_size = self.get_parameter("marker_size").value
        dictionary_name = self.get_parameter("aruco_dictionary_id").value
        image_topic = self.get_parameter("image_topic").value
        info_topic = self.get_parameter("camera_info_topic").value
        self.camera_frame = self.get_parameter("camera_frame").value

        # Logging
        self.get_logger().info(f"Default marker size: {self.marker_size}")
        self.get_logger().info(f"Aruco dictionary: {dictionary_name}")
        self.get_logger().info(f"Image topic: {image_topic}")
        self.get_logger().info(f"Camera info topic: {info_topic}")
        self.get_logger().info(f"Camera frame: {self.camera_frame}")

        # Marker sizes for your tags
        self.marker_size_map = {
            1: 0.15,  2: 0.15,  3: 0.15,  4: 0.15,
            5: 0.05,
            6: 0.15, 7: 0.15, 8: 0.09, 9: 0.15,  # ID 8 is 90mm for chess board
            10: 0.15, 11: 0.15,
            20: 0.05, 21: 0.05, 22: 0.05
        }

        self.get_logger().info(f"Marker size map: {self.marker_size_map}")

        # Validate dictionary ID
        try:
            dictionary_id = cv2.aruco.__getattribute__(dictionary_name)
        except AttributeError:
            self.get_logger().error(f"Invalid dictionary id: {dictionary_name}")
            raise

        # Modern ArUco API (OpenCV >= 4.7)
        self.aruco_dictionary = cv2.aruco.getPredefinedDictionary(dictionary_id)
        self.aruco_parameters = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(
            self.aruco_dictionary, self.aruco_parameters
        )

        # Subscribers
        self.info_sub = self.create_subscription(
            CameraInfo, info_topic, self.info_callback, qos_profile_sensor_data
        )

        self.create_subscription(
            Image, image_topic, self.image_callback, qos_profile_sensor_data
        )

        # Publishers
        self.poses_pub = self.create_publisher(PoseArray, "aruco_poses", 10)
        self.markers_pub = self.create_publisher(ArucoMarkers, "aruco_markers", 10)

        # TF Broadcaster
        self.tf_broadcaster = TransformBroadcaster(self)

        self.bridge = CvBridge()
        self.info_msg = None
        self.intrinsic_mat = None
        self.distortion = None

    def info_callback(self, info_msg):
        self.info_msg = info_msg
        self.intrinsic_mat = np.reshape(np.array(info_msg.k), (3, 3))
        self.distortion = np.array(info_msg.d)
        self.destroy_subscription(self.info_sub)

    def solve_pnp_pose(self, corners, marker_size):
        """Estimate pose using solvePnP (modern replacement for old estimatePoseSingleMarkers)."""

        half = marker_size / 2.0

        # Marker 3D corner points
        obj_points = np.array([
            [-half,  half, 0],
            [ half,  half, 0],
            [ half, -half, 0],
            [-half, -half, 0],
        ], dtype=np.float32)

        # 2D image points
        img_points = corners.reshape(4, 2).astype(np.float32)

        ok, rvec, tvec = cv2.solvePnP(
            obj_points,
            img_points,
            self.intrinsic_mat,
            self.distortion,
            flags=cv2.SOLVEPNP_IPPE_SQUARE
        )

        return ok, rvec, tvec

    def image_callback(self, img_msg):
        if self.info_msg is None:
            return

        # Convert image
        cv_image = self.bridge.imgmsg_to_cv2(img_msg, desired_encoding="mono8")

        markers_msg = ArucoMarkers()
        pose_array = PoseArray()

        frame = self.camera_frame if self.camera_frame else self.info_msg.header.frame_id
        markers_msg.header.frame_id = frame
        pose_array.header.frame_id = frame
        markers_msg.header.stamp = img_msg.header.stamp
        pose_array.header.stamp = img_msg.header.stamp

        # Modern detection
        corners, marker_ids, rejected = self.detector.detectMarkers(cv_image)

        if marker_ids is None:
            return

        for i, marker_id in enumerate(marker_ids):
            marker_id_val = marker_id[0]

            # Determine marker size
            marker_size = self.marker_size_map.get(marker_id_val, self.marker_size)
            detected_corners = corners[i]

            # ---- New pose estimation method ----
            ok, rvec, tvec = self.solve_pnp_pose(detected_corners, marker_size)
            if not ok:
                continue

            pose = Pose()
            pose.position.x = tvec[0][0]
            pose.position.y = tvec[1][0]
            pose.position.z = tvec[2][0]

            rot_matrix = np.eye(4)
            rot_matrix[0:3, 0:3] = cv2.Rodrigues(rvec)[0]
            quat = quaternion_from_matrix(rot_matrix)

            pose.orientation.x = quat[0]
            pose.orientation.y = quat[1]
            pose.orientation.z = quat[2]
            pose.orientation.w = quat[3]

            # Publish TF
            transform = TransformStamped()
            transform.header.stamp = img_msg.header.stamp
            transform.header.frame_id = frame
            transform.child_frame_id = f"ar_marker_{marker_id_val}"

            transform.transform.translation.x = pose.position.x
            transform.transform.translation.y = pose.position.y
            transform.transform.translation.z = pose.position.z

            transform.transform.rotation.x = quat[0]
            transform.transform.rotation.y = quat[1]
            transform.transform.rotation.z = quat[2]
            transform.transform.rotation.w = quat[3]

            self.tf_broadcaster.sendTransform(transform)

            pose_array.poses.append(pose)
            markers_msg.poses.append(pose)
            markers_msg.marker_ids.append(marker_id_val)

        self.poses_pub.publish(pose_array)
        self.markers_pub.publish(markers_msg)


def main():
    rclpy.init()
    node = ArucoNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
