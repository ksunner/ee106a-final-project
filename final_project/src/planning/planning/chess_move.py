# ROS Libraries
from std_srvs.srv import Trigger
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from geometry_msgs.msg import PointStamped
from sensor_msgs.msg import JointState
import sys

from planning.ik import IKPlanner
from planning.chess_coords import ChessCoords


class ChessMove(Node):
    """
    Chess piece movement node.

    Moves a chess piece from one square to another using the ArUco marker
    at the center of the board as reference.

    Usage:
        ros2 run planning chess_move --from e2 --to e4
    """

    def __init__(self, from_square, to_square):
        super().__init__("chess_move")

        # Validate and store squares
        self.chess_coords = ChessCoords(square_size=0.055)  # 5.5cm squares

        if not self.chess_coords.validate_square(from_square):
            raise ValueError(f"Invalid origin square: {from_square}")
        if not self.chess_coords.validate_square(to_square):
            raise ValueError(f"Invalid destination square: {to_square}")

        self.from_square = from_square
        self.to_square = to_square

        # Announce configuration
        self.get_logger().info("=== Chess Move Node Initialized ===")
        self.get_logger().info(f"Moving piece: {from_square} -> {to_square}")

        # -------------------------------------------------------
        # Subscribers
        # -------------------------------------------------------
        self.board_center_pose = None
        self.joint_state = None

        # Subscribe to the ArUco marker pose (board center)
        self.subscription_aruco = self.create_subscription(
            PointStamped,
            "/cube_pose_base_link",  # Reusing existing topic
            self.aruco_callback,
            1
        )

        self.subscription_joints = self.create_subscription(
            JointState,
            "/joint_states",
            self.joint_state_callback,
            1
        )

        # -------------------------------------------------------
        # Action + Service Clients
        # -------------------------------------------------------
        self.exec_ac = ActionClient(
            self,
            FollowJointTrajectory,
            "/scaled_joint_trajectory_controller/follow_joint_trajectory"
        )
        self.gripper_cli = self.create_client(Trigger, "/toggle_gripper")

        self.ik_planner = IKPlanner()

        # -------------------------------------------------------
        # Job queue
        # -------------------------------------------------------
        self.job_queue = []

        self.get_logger().info("Waiting for ArUco marker and joint states...")

    # ==========================================================
    # Joint state callback
    # ==========================================================
    def joint_state_callback(self, msg):
        self.joint_state = msg

    # ==========================================================
    # ArUco marker callback (starts pipeline)
    # ==========================================================
    def aruco_callback(self, msg):
        if self.board_center_pose is not None:
            return  # Only handle first detection

        if self.joint_state is None:
            return

        self.board_center_pose = msg
        cx, cy, cz = msg.point.x, msg.point.y, msg.point.z

        self.get_logger().info(
            f"Received board center pose:\n"
            f"x={cx:.3f}, y={cy:.3f}, z={cz:.3f}"
        )

        # Build job queue
        self.build_job_queue(cx, cy, cz)

        # Start execution
        self.execute_jobs()

    # ==========================================================
    # Build job queue for chess move
    # ==========================================================
    def build_job_queue(self, cx, cy, cz):
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

        # Get offsets for origin and destination squares
        dx_from, dy_from = self.chess_coords.square_to_offset(self.from_square)
        dx_to, dy_to = self.chess_coords.square_to_offset(self.to_square)

        self.get_logger().info(
            f"Origin offset: dx={dx_from:.3f}, dy={dy_from:.3f}\n"
            f"Destination offset: dx={dx_to:.3f}, dy={dy_to:.3f}"
        )

        # Z-heights (using same strategy as cube grasp code)
        z_approach = cz + 0.30 #safe approach height (18cm above ArUco marker)
        z_grasp = cz + 0.22   # Grasp height (16cm above ArUco marker)

        # Calculate absolute positions
        # Origin square positions
        from_x = cx + dx_from
        from_y = cy + dy_from

        # Destination square positions
        to_x = cx + dx_to
        to_y = cy + dy_to

        # Build job sequence (using same approach as cube grasp)
        # Pre-grasp position at origin (with same offset adjustments)
        pg_from = (from_x - 0.01, from_y - 0.08, z_approach)

        # Grasp position at origin
        grasp_from = (pg_from[0], pg_from[1], z_grasp)

        # Lift from origin
        lift_from = pg_from

        # Pre-place position at destination
        pg_to = (to_x - 0.01, to_y - 0.08, z_approach)

        # Place position at destination (0.5cm higher than grasp)
        place_to = (pg_to[0], pg_to[1], z_grasp + 0.005)

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

    # ==========================================================
    # Executor — runs one job at a time
    # ==========================================================
    def execute_jobs(self):
        if not self.job_queue:
            self.get_logger().info("=== CHESS MOVE COMPLETED ===")
            rclpy.shutdown()
            return

        job_type, data = self.job_queue.pop(0)

        if job_type == "ik":
            self.do_ik_motion(data)
        else:
            self.do_grip()

    # ==========================================================
    # IK MOTION
    # ==========================================================
    def do_ik_motion(self, pos):
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

    # ==========================================================
    # GRIPPER OPERATION
    # ==========================================================
    def do_grip(self):
        if not self.gripper_cli.wait_for_service(timeout_sec=5.0):
            self.get_logger().error("Gripper service unavailable")
            rclpy.shutdown()
            return

        req = Trigger.Request()
        future = self.gripper_cli.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=2.0)

        self.get_logger().info("Gripper toggled.")
        self.execute_jobs()

    # ==========================================================
    # TRAJECTORY EXECUTION
    # ==========================================================
    def execute_trajectory(self, joint_traj):
        self.exec_ac.wait_for_server()

        goal = FollowJointTrajectory.Goal()
        goal.trajectory = joint_traj

        send_future = self.exec_ac.send_goal_async(goal)
        send_future.add_done_callback(self._on_goal_sent)

    def _on_goal_sent(self, future):
        goal_handle = future.result()

        if not goal_handle.accepted:
            self.get_logger().error("Trajectory rejected")
            rclpy.shutdown()
            return

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._on_motion_done)

    def _on_motion_done(self, future):
        self.get_logger().info("Motion complete.")
        self.execute_jobs()


# ==========================================================
# Main entry
# ==========================================================
def main(args=None):
    import argparse

    parser = argparse.ArgumentParser(description="Chess Piece Movement")
    parser.add_argument("--from", dest="from_square", type=str, required=True,
                        help="Origin square (e.g., e2)")
    parser.add_argument("--to", dest="to_square", type=str, required=True,
                        help="Destination square (e.g., e4)")

    ros_args = rclpy.utilities.remove_ros_args(sys.argv)
    parsed = parser.parse_args(ros_args[1:])

    rclpy.init(args=args)

    node = ChessMove(
        from_square=parsed.from_square,
        to_square=parsed.to_square
    )

    rclpy.spin(node)
    node.destroy_node()


if __name__ == "__main__":
    main()
