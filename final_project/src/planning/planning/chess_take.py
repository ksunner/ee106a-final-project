#!/usr/bin/env python3
"""
Chess Piece Capture (Take)

Executes a capture move by:
1. Removing the piece at the destination square (moving it off-board)
2. Moving the attacking piece from origin to destination

Usage:
    ros2 run planning chess_take --from e2 --to e4

    This will:
    - Pick up piece at e4 and move it off the board
    - Then pick up piece at e2 and move it to e4
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


class ChessTake(Node):
    """
    Chess piece capture node using ArUco-calibrated board positions.
    """

    def __init__(self, from_square, to_square, offset_x=0.0, offset_y=0.0, offset_z=0.22,
                 offboard_x=0.0, offboard_y=0.5, offboard_z_offset=0.0):
        super().__init__("chess_take")

        self.from_square = from_square.lower()
        self.to_square = to_square.lower()

        # Position offsets for fine-tuning
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.offset_z_grasp = offset_z

        # Off-board position for captured pieces
        # Default: y=0.5m (50cm to the side of the board)
        self.offboard_x = offboard_x
        self.offboard_y = offboard_y
        self.offboard_z_offset = offboard_z_offset  # Height adjustment for off-board surface

        # Validate squares
        if not self.validate_square(self.from_square):
            raise ValueError(f"Invalid origin square: {from_square}")
        if not self.validate_square(self.to_square):
            raise ValueError(f"Invalid destination square: {to_square}")

        self.get_logger().info("=== Chess Capture (Take) ===")
        self.get_logger().info(f"Capturing: {self.from_square} takes {self.to_square}")
        if offset_x != 0.0 or offset_y != 0.0 or offset_z != 0.22:
            self.get_logger().info(f"Position offsets: x={offset_x:+.3f}, y={offset_y:+.3f}, z={offset_z:+.3f}")
        self.get_logger().info(f"Off-board position: x={offboard_x:.3f}, y={offboard_y:.3f}, z_offset={offboard_z_offset:+.3f}")

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

        # Subscribe to square positions
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

        # Timer to check if ready to start
        self.create_timer(0.5, self.check_and_start)

        self.get_logger().info("Waiting for square positions and joint states...")

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
        """Check if we have all required data and start capture sequence."""
        if self.positions_received:
            return

        if (self.from_position is not None and
            self.to_position is not None and
            self.joint_state is not None):

            self.positions_received = True
            self.get_logger().info("All positions received, building capture sequence...")

            # Build and execute job queue
            self.build_capture_sequence()
            self.execute_jobs()

    def build_capture_sequence(self):
        """
        Build capture sequence:

        Phase 1: Remove captured piece from destination
        1. Move to pre-grasp above destination square
        2. Lower to grasp captured piece
        3. Close gripper
        4. Lift captured piece
        5. Move to off-board position
        6. Lower to off-board surface
        7. Open gripper (release captured piece)
        8. Retreat from off-board position

        Phase 2: Move attacking piece
        9. Move to pre-grasp above origin square
        10. Lower to grasp attacking piece
        11. Close gripper
        12. Lift attacking piece
        13. Move to destination square (elevated)
        14. Lower to place attacking piece
        15. Open gripper
        16. Retreat
        """
        from_x, from_y, from_z = self.from_position
        to_x, to_y, to_z = self.to_position

        # Apply offsets to positions
        from_x += self.offset_x
        from_y += self.offset_y
        to_x += self.offset_x
        to_y += self.offset_y

        # Heights
        z_approach = from_z + 0.30
        z_grasp = from_z + self.offset_z_grasp

        # Off-board position
        # If surfaces are aligned, offboard_z_offset should be 0
        # Place at same height as we grasped from the board
        offboard_z_grasp = from_z + self.offboard_z_offset + self.offset_z_grasp
        offboard_approach = (self.offboard_x, self.offboard_y, from_z + self.offboard_z_offset + 0.30)

        self.get_logger().info(f"Phase 1: Removing captured piece from {self.to_square}")
        self.get_logger().info(f"Phase 2: Moving attacking piece {self.from_square} -> {self.to_square}")

        # === PHASE 1: Remove captured piece ===
        # Pre-grasp at destination
        pg_to = (to_x, to_y, z_approach)
        grasp_to = (to_x, to_y, z_grasp)
        lift_to = pg_to

        # === PHASE 2: Move attacking piece ===
        # Pre-grasp at origin
        pg_from = (from_x, from_y, z_approach)
        grasp_from = (from_x, from_y, z_grasp)
        lift_from = pg_from

        # Place at destination
        place_to = (to_x, to_y, z_grasp + 0.005)
        retreat_to = pg_to

        # Off-board position tuple
        offboard_pos = (self.offboard_x, self.offboard_y, offboard_z_grasp)

        # Build complete job sequence
        self.job_queue = [
            # === PHASE 1: Remove captured piece ===
            ("ik", pg_to),              # 1. Approach destination
            ("ik", grasp_to),           # 2. Lower to captured piece
            ("grip", None),             # 3. Close gripper (grasp captured piece)
            ("ik", lift_to),            # 4. Lift captured piece
            ("ik", offboard_approach),  # 5. Move to off-board (elevated)
            ("ik", offboard_pos),       # 6. Lower to off-board surface (same height as board grasp)
            ("grip", None),             # 7. Open gripper (release captured piece)
            ("ik", offboard_approach),  # 8. Retreat from off-board

            # === PHASE 2: Move attacking piece ===
            ("ik", pg_from),            # 9. Approach origin
            ("ik", grasp_from),         # 10. Lower to attacking piece
            ("grip", None),             # 11. Close gripper (grasp attacking piece)
            ("ik", lift_from),          # 12. Lift attacking piece
            ("ik", pg_to),              # 13. Move to destination (elevated)
            ("ik", place_to),           # 14. Lower to board
            ("grip", None),             # 15. Open gripper (release)
            ("ik", retreat_to),         # 16. Retreat
        ]

        self.get_logger().info(f"Capture sequence built: {len(self.job_queue)} steps")

    def execute_jobs(self):
        """Execute jobs sequentially."""
        if not self.job_queue:
            self.get_logger().info("=== CAPTURE COMPLETED ===")
            rclpy.shutdown()
            return

        job_type, data = self.job_queue.pop(0)

        # Log progress
        remaining = len(self.job_queue)
        if remaining == 8:
            self.get_logger().info("--- Phase 1 complete: Captured piece removed ---")
        elif remaining == 0:
            self.get_logger().info("--- Phase 2 complete: Attacking piece moved ---")

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
        self.execute_jobs()


def main(args=None):
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Chess Piece Capture (Take)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Basic capture:
    ros2 run planning chess_take --from e2 --to e4

  With position offsets:
    ros2 run planning chess_take --from e2 --to e4 --offset-z 0.25

  Custom off-board position:
    ros2 run planning chess_take --from e2 --to e4 --offboard-y 0.6

Capture sequence:
  1. Pick up piece at destination (e4) and move it off the board
  2. Pick up piece at origin (e2) and move it to destination (e4)
        """
    )
    parser.add_argument(
        "--from",
        dest="from_square",
        type=str,
        required=True,
        help="Origin square (attacking piece, e.g., e2)"
    )
    parser.add_argument(
        "--to",
        dest="to_square",
        type=str,
        required=True,
        help="Destination square (captured piece, e.g., e4)"
    )
    parser.add_argument(
        "--offset-x",
        dest="offset_x",
        type=float,
        default=0.0,
        help="X-axis offset for positions in meters (default: 0.0)"
    )
    parser.add_argument(
        "--offset-y",
        dest="offset_y",
        type=float,
        default=0.0,
        help="Y-axis offset for positions in meters (default: 0.0)"
    )
    parser.add_argument(
        "--offset-z",
        dest="offset_z",
        type=float,
        default=0.22,
        help="Z-height offset for grasp height in meters (default: 0.22)"
    )
    parser.add_argument(
        "--offboard-x",
        dest="offboard_x",
        type=float,
        default=0.0,
        help="X-coordinate for off-board captured pieces (default: 0.0)"
    )
    parser.add_argument(
        "--offboard-y",
        dest="offboard_y",
        type=float,
        default=0.5,
        help="Y-coordinate for off-board captured pieces (default: 0.5, 50cm to side)"
    )
    parser.add_argument(
        "--offboard-z-offset",
        dest="offboard_z_offset",
        type=float,
        default=0.0,
        help="Z-height offset for off-board surface relative to board (default: 0.0). Use negative value if table is lower than board."
    )

    ros_args = rclpy.utilities.remove_ros_args(sys.argv)
    parsed = parser.parse_args(ros_args[1:])

    rclpy.init(args=args)

    node = ChessTake(
        from_square=parsed.from_square,
        to_square=parsed.to_square,
        offset_x=parsed.offset_x,
        offset_y=parsed.offset_y,
        offset_z=parsed.offset_z,
        offboard_x=parsed.offboard_x,
        offboard_y=parsed.offboard_y,
        offboard_z_offset=parsed.offboard_z_offset
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
