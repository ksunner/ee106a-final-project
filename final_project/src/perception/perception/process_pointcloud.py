import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from geometry_msgs.msg import PointStamped
import numpy as np
import sensor_msgs_py.point_cloud2 as pc2
from std_msgs.msg import Header

class RealSensePCSubscriber(Node):
    def __init__(self):
        super().__init__('realsense_pc_subscriber')

        # Plane coefficients and max distance (meters)
        self.declare_parameter('plane.a', 0.0)
        self.declare_parameter('plane.b', 0.0)
        self.declare_parameter('plane.c', 0.0)
        self.declare_parameter('plane.d', 0.0)
        self.declare_parameter('max_distance', 0.3)
        self.declare_parameter('object_color', 'blue')

        self.a = self.get_parameter('plane.a').value
        self.b = self.get_parameter('plane.b').value
        self.c = self.get_parameter('plane.c').value
        self.d = self.get_parameter('plane.d').value
        self.max_distance = self.get_parameter('max_distance').value
        self.object_color = self.get_parameter('object_color').value

        # Subscribers
        self.pc_sub = self.create_subscription(
            PointCloud2,
            '/camera/camera/depth/color/points',
            self.pointcloud_callback,
            10
        )

        # Publishers
        self.cube_pose_pub = self.create_publisher(PointStamped, '/cube_pose', 1)
        self.filtered_points_pub = self.create_publisher(PointCloud2, '/filtered_points', 1)

        self.get_logger().info("Subscribed to PointCloud2 topic and marker publisher ready")

    def pointcloud_callback(self, msg: PointCloud2):
        # Convert PointCloud2 to Nx3 array with RGB color information
        points = []
        colors = []
        for p in pc2.read_points(msg, field_names=('x','y','z','rgb'), skip_nans=True):
            points.append([p[0], p[1], p[2]])
            # Extract RGB from the packed float
            rgb = p[3]
            # Convert float32 to uint32 to extract RGB bytes
            rgb_int = int.from_bytes(np.float32(rgb).tobytes(), byteorder='little')
            r = (rgb_int >> 16) & 0xFF
            g = (rgb_int >> 8) & 0xFF
            b = rgb_int & 0xFF
            colors.append([r, g, b])

        points = np.array(points)
        colors = np.array(colors)

        # ------------------------
        #TODO: Add your code here!
        # ------------------------

        # Apply max distance filter
        a, b, c, d = self.a, self.b, self.c, self.d
        denom = np.sqrt(a**2 + b**2 + c**2)
        signed_distances = (a*points[:,0] + b*points[:,1] + c*points[:,2] + d) / denom
        valid_mask = (signed_distances <= 0) & (points[:, 2] < self.max_distance)

        # Apply plane filtering
        filtered_points = points[valid_mask]
        filtered_colors = colors[valid_mask]

        # Filter for desired color based on object_color parameter
        if self.object_color == 'blue':
            color_mask = self.filter_blue_color(filtered_colors)
        elif self.object_color == 'red':
            color_mask = self.filter_red_color(filtered_colors)
        else:
            self.get_logger().error(f"Unknown object_color: {self.object_color}. Must be 'blue' or 'red'.")
            return

        # Get only points of the desired color
        colored_points = filtered_points[color_mask]

        if len(colored_points) == 0:
            self.get_logger().warn(f"No {self.object_color} points detected!")
            return

        # Compute position of the cube via colored points only
        cube_x, cube_y, cube_z = np.mean(colored_points, axis=0)

        self.get_logger().info(f"Filtered points: {filtered_points.shape[0]}, {self.object_color.capitalize()} points: {colored_points.shape[0]}")

        cube_pose = PointStamped()
        # Fill in message
        cube_pose.header = msg.header
        cube_pose.point.x = float(cube_x)
        cube_pose.point.y = float(cube_y)
        cube_pose.point.z = float(cube_z)

        self.cube_pose_pub.publish(cube_pose)

        self.publish_filtered_points(colored_points, msg.header)

    def filter_blue_color(self, colors: np.ndarray) -> np.ndarray:
        """
        Filter for blue colors using HSV color space.
        Returns a boolean mask indicating which points are blue.
        """
        if len(colors) == 0:
            return np.array([], dtype=bool)

        # Normalize RGB to [0, 1]
        colors_normalized = colors / 255.0

        # Convert RGB to HSV
        r, g, b = colors_normalized[:, 0], colors_normalized[:, 1], colors_normalized[:, 2]

        max_c = np.maximum(np.maximum(r, g), b)
        min_c = np.minimum(np.minimum(r, g), b)
        diff = max_c - min_c

        # Calculate Hue
        h = np.zeros_like(max_c)
        mask_r = (max_c == r) & (diff > 0)
        mask_g = (max_c == g) & (diff > 0)
        mask_b = (max_c == b) & (diff > 0)

        h[mask_r] = 60 * (((g[mask_r] - b[mask_r]) / diff[mask_r]) % 6)
        h[mask_g] = 60 * (((b[mask_g] - r[mask_g]) / diff[mask_g]) + 2)
        h[mask_b] = 60 * (((r[mask_b] - g[mask_b]) / diff[mask_b]) + 4)

        # Calculate Saturation
        s = np.where(max_c > 0, diff / max_c, 0)

        # Calculate Value
        v = max_c

        # Blue hue range: approximately 200-260 degrees in HSV
        # Adjust these thresholds based on your specific blue object
        hue_lower = 180
        hue_upper = 260
        saturation_min = 0.3  # Minimum saturation to avoid grayish colors
        value_min = 0.2  # Minimum brightness

        blue_mask = (h >= hue_lower) & (h <= hue_upper) & (s >= saturation_min) & (v >= value_min)

        return blue_mask

    def filter_red_color(self, colors: np.ndarray) -> np.ndarray:
        """
        Filter for red colors using HSV color space.
        Returns a boolean mask indicating which points are red.
        Red hue wraps around 0 degrees, so we need two ranges.
        """
        if len(colors) == 0:
            return np.array([], dtype=bool)

        # Normalize RGB to [0, 1]
        colors_normalized = colors / 255.0

        # Convert RGB to HSV
        r, g, b = colors_normalized[:, 0], colors_normalized[:, 1], colors_normalized[:, 2]

        max_c = np.maximum(np.maximum(r, g), b)
        min_c = np.minimum(np.minimum(r, g), b)
        diff = max_c - min_c

        # Calculate Hue
        h = np.zeros_like(max_c)
        mask_r = (max_c == r) & (diff > 0)
        mask_g = (max_c == g) & (diff > 0)
        mask_b = (max_c == b) & (diff > 0)

        h[mask_r] = 60 * (((g[mask_r] - b[mask_r]) / diff[mask_r]) % 6)
        h[mask_g] = 60 * (((b[mask_g] - r[mask_g]) / diff[mask_g]) + 2)
        h[mask_b] = 60 * (((r[mask_b] - g[mask_b]) / diff[mask_b]) + 4)

        # Calculate Saturation
        s = np.where(max_c > 0, diff / max_c, 0)

        # Calculate Value
        v = max_c

        # Red hue wraps around 0 degrees in HSV
        # Red range 1: 0-20 degrees (main red)
        # Red range 2: 340-360 degrees (magenta-red)
        # Adjust these thresholds based on your specific red object
        hue_lower1 = 0
        hue_upper1 = 20
        hue_lower2 = 340
        hue_upper2 = 360
        saturation_min = 0.3  # Minimum saturation to avoid grayish colors
        value_min = 0.2  # Minimum brightness

        red_mask = (((h >= hue_lower1) & (h <= hue_upper1)) | ((h >= hue_lower2) & (h <= hue_upper2))) & (s >= saturation_min) & (v >= value_min)

        return red_mask

    def publish_filtered_points(self, filtered_points: np.ndarray, header: Header):
        # Create PointCloud2 message from filtered Nx3 array
        filtered_msg = pc2.create_cloud_xyz32(header, filtered_points.tolist())
        self.filtered_points_pub.publish(filtered_msg)


def main(args=None):
    rclpy.init(args=args)
    node = RealSensePCSubscriber()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()