#!/usr/bin/env python3
"""
Chess piece movement using ArUco-calibrated board positions.

This node moves chess pieces from one square to another using positions
calculated by the ChessBoardCalibrator node.

Usage:
    # First, run the calibrator and calibrate the board
    ros2 run planning chess_board_calibrator
    ros2 service call /calibrate_chess_board std_srvs/srv/Trigger

    # Then move pieces
    ros2 run planning chess_move_aruco --from e2 --to e4
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from geometry_msgs.msg import PointStamped
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger
import sys

from planning.ik import IKPlanner


class ChessMoveAruco(Node):
    """
    Chess piece movement node using ArUco-calibrated board positions.
    """

    def __init__(self, from_square, to_square, offset_x=0.0, offset_y=0.0, offset_z=0.22):
        super().__init__("chess_move_aruco")

        self.from_square = from_square.lower()
        self.to_square = to_square.lower()

        # Position offsets for fine-tuning
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.offset_z_grasp = offset_z  # Z offset for grasp height

        # Validate squares
        if not self.validate_square(self.from_square):
            raise ValueError(f"Invalid origin square: {from_square}")
        if not self.validate_square(self.to_square):
            raise ValueError(f"Invalid destination square: {to_square}")

        self.get_logger().info("=== Chess Move (ArUco Calibrated) ===")
        self.get_logger().info(f"Moving piece: {self.from_square} -> {self.to_square}")
        if offset_x != 0.0 or offset_y != 0.0 or offset_z != 0.22:
            self.get_logger().info(f"Position offsets: x={offset_x:+.3f}, y={offset_y:+.3f}, z_grasp={offset_z:+.3f}")

        # Positions from calibrator
        self.from_position = None
        self.to_position = None
        self.positions_received = False

        # Joint state
        self.joint_state = None

        # Subscribe to joint states
        self.subscription_joints = self.create_subscription(
            JointState,
            "/joint_states",
            self.joint_state_callback,
            1
        )

        # Subscribe to calibrated square positions
        # We'll create subscribers for each specific square we need
        self.from_sub = self.create_subscription(
            PointStamped,
            f'/chess_square/{self.from_square}',
            self.from_square_callback,
            1
        )

        self.to_sub = self.create_subscription(
            PointStamped,
            f'/chess_square/{self.to_square}',
            self.to_square_callback,
            1
        )

        # Action client for trajectory execution
        self.exec_ac = ActionClient(
            self,
            FollowJointTrajectory,
            "/scaled_joint_trajectory_controller/follow_joint_trajectory"
        )

        # Gripper service client
        self.gripper_cli = self.create_client(Trigger, "/toggle_gripper")

        # IK planner
        self.ik_planner = IKPlanner()

        # Job queue
        self.job_queue = []

        # Service to get square position
        self.get_square_client = self.create_client(
            Trigger,
            '/get_square_position'
        )

        self.get_logger().info("Waiting for square positions from calibrator...")

        # Timer to check if we have positions and start movement
        self.check_timer = self.create_timer(0.5, self.check_and_start)

    def validate_square(self, square):
        """Validate chess square notation."""
        if len(square) != 2:
            return False
        return square[0] in 'abcdefgh' and square[1] in '12345678'

    def joint_state_callback(self, msg):
        """Update joint state."""
        self.joint_state = msg

    def from_square_callback(self, msg):
        """Receive origin square position."""
        if self.from_position is None:
            self.from_position = [msg.point.x, msg.point.y, msg.point.z]
            self.get_logger().info(
                f"Received {self.from_square} position: "
                f"[{msg.point.x:.3f}, {msg.point.y:.3f}, {msg.point.z:.3f}]"
            )

    def to_square_callback(self, msg):
        """Receive destination square position."""
        if self.to_position is None:
            self.to_position = [msg.point.x, msg.point.y, msg.point.z]
            self.get_logger().info(
                f"Received {self.to_square} position: "
                f"[{msg.point.x:.3f}, {msg.point.y:.3f}, {msg.point.z:.3f}]"
            )

    def check_and_start(self):
        """Check if we have all required data and start movement."""
        if self.positions_received:
            return

        if (self.from_position is not None and
            self.to_position is not None and
            self.joint_state is not None):

            self.positions_received = True
            self.get_logger().info("All positions received, building job queue...")

            # Build and execute job queue
            self.build_job_queue()
            self.execute_jobs()

    def build_job_queue(self):
        """
        Build movement sequence:
        1. Move to pre-grasp above origin square
        2. Move down to grasp piece at origin square
        3. Close gripper
        4. Lift piece
        5. Move to destination square (elevated)
        6. Move down to place piece
        7. Open gripper
        8. Retreat
        """
        from_x, from_y, from_z = self.from_position
        to_x, to_y, to_z = self.to_position

        # Apply user-specified offsets to origin position
        from_x += self.offset_x
        from_y += self.offset_y

        to_x += self.offset_x
        to_y += self.offset_y

        # Use the board surface height (from calibrated positions)
        # Add offsets for approach and grasp heights
        z_approach = from_z + 0.30           # 30cm above square
        z_grasp = from_z + self.offset_z_grasp  # User-specified grasp height

        self.get_logger().info(f"Origin position (with offsets): x={from_x:.3f}, y={from_y:.3f}, z_grasp={z_grasp:.3f}")

        # Build job sequence
        # Pre-grasp position at origin
        pg_from = (from_x, from_y, z_approach)

        # Grasp position at origin
        grasp_from = (from_x, from_y, z_grasp)

        # Lift from origin
        lift_from = pg_from

        # Pre-place position at destination (no offsets for destination)
        pg_to = (to_x, to_y, z_approach)

        # Place position at destination (slightly higher than grasp)
        place_to = (to_x, to_y, z_grasp + 0.02)

        # Retreat from destination
        retreat_to = pg_to

        # Add jobs to queue
        self.job_queue.extend([
            ("ik", pg_from),         # Approach origin
            ("ik", grasp_from),      # Lower to piece
            ("grip", None),          # Close gripper (grasp)
            ("ik", lift_from),       # Lift piece
            ("ik", pg_to),           # Move to destination
            ("ik", place_to),        # Lower to board
            ("grip", None),          # Open gripper (release)
            ("ik", retreat_to),      # Retreat
        ])

        self.get_logger().info(f"Job queue built with {len(self.job_queue)} steps")

    def execute_jobs(self):
        """Execute jobs sequentially."""
        if not self.job_queue:
            self.get_logger().info("=== CHESS MOVE COMPLETED ===")
            rclpy.shutdown()
            return

        job_type, data = self.job_queue.pop(0)

        if job_type == "ik":
            self.do_ik_motion(data)
        else:
            self.do_grip()

    def do_ik_motion(self, pos):
        """Execute IK motion to target position."""
        if self.joint_state is None:
            self.get_logger().error("No joint state available for IK")
            return

        x, y, z = pos
        self.get_logger().info(f"Computing IK for target: ({x:.3f}, {y:.3f}, {z:.3f})")

        q = self.ik_planner.compute_ik(
            self.joint_state, x, y, z,
            qx=0.0, qy=1.0, qz=0.0, qw=0.0  # Gripper pointing down
        )

        if q is None:
            self.get_logger().error("IK computation failed")
            rclpy.shutdown()
            return

        traj = self.ik_planner.plan_to_joints(q)
        if traj is None:
            self.get_logger().error("Planning failed.")
            rclpy.shutdown()
            return

        self.execute_trajectory(traj.joint_trajectory)

    def do_grip(self):
        """Toggle gripper."""
        if not self.gripper_cli.wait_for_service(timeout_sec=5.0):
            self.get_logger().error("Gripper service unavailable")
            rclpy.shutdown()
            return

        req = Trigger.Request()
        future = self.gripper_cli.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=2.0)

        self.get_logger().info("Gripper toggled.")
        self.execute_jobs()

    def execute_trajectory(self, joint_traj):
        """Execute joint trajectory."""
        self.exec_ac.wait_for_server()

        goal = FollowJointTrajectory.Goal()
        goal.trajectory = joint_traj

        send_future = self.exec_ac.send_goal_async(goal)
        send_future.add_done_callback(self._on_goal_sent)

    def _on_goal_sent(self, future):
        """Callback when goal is sent."""
        goal_handle = future.result()

        if not goal_handle.accepted:
            self.get_logger().error("Trajectory rejected")
            rclpy.shutdown()
            return

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._on_motion_done)

    def _on_motion_done(self, future):
        """Callback when motion is complete."""
        self.get_logger().info("Motion complete.")
        self.execute_jobs()


def main(args=None):
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Chess Piece Movement (ArUco Calibrated)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Basic move:
    ros2 run planning chess_move_aruco --from e2 --to e4

  With position offsets (fine-tuning):
    ros2 run planning chess_move_aruco --from e2 --to e4 --offset-x 0.01 --offset-y -0.02 --offset-z 0.25

Position offsets:
  --offset-x, --offset-y: Horizontal offsets added to origin square (meters)
  --offset-z: Z-height for grasping piece above board surface (meters, default 0.22)
        """
    )
    parser.add_argument(
        "--from",
        dest="from_square",
        type=str,
        required=True,
        help="Origin square (e.g., e2)"
    )
    parser.add_argument(
        "--to",
        dest="to_square",
        type=str,
        required=True,
        help="Destination square (e.g., e4)"
    )
    parser.add_argument(
        "--offset-x",
        dest="offset_x",
        type=float,
        default=0.0,
        help="X-axis offset for origin position in meters (default: 0.0)"
    )
    parser.add_argument(
        "--offset-y",
        dest="offset_y",
        type=float,
        default=0.0,
        help="Y-axis offset for origin position in meters (default: 0.0)"
    )
    parser.add_argument(
        "--offset-z",
        dest="offset_z",
        type=float,
        default=0.22,
        help="Z-height offset for grasp height in meters (default: 0.22)"
    )

    ros_args = rclpy.utilities.remove_ros_args(sys.argv)
    parsed = parser.parse_args(ros_args[1:])

    rclpy.init(args=args)

    node = ChessMoveAruco(
        from_square=parsed.from_square,
        to_square=parsed.to_square,
        offset_x=parsed.offset_x,
        offset_y=parsed.offset_y,
        offset_z=parsed.offset_z
    )

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
