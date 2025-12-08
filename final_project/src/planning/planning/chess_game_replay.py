#!/usr/bin/env python3
"""
Chess Game Replay

Replays a full chess game from a file, executing moves sequentially.

Usage:
    ros2 run planning chess_game_replay --game-file games/ladder_checkmate.txt
    ros2 run planning chess_game_replay --game-file games/ladder_checkmate.txt --offset-z 0.25
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from geometry_msgs.msg import PointStamped
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger
import sys
import time

from planning.ik import IKPlanner
from planning.chess_game_parser import ChessGameParser


class ChessGameReplay(Node):
    """
    Replays a chess game from a file.
    """

    def __init__(self, game_file, offset_x=0.0, offset_y=0.0, offset_z=0.22, delay=3.0):
        super().__init__("chess_game_replay")

        self.game_file = game_file
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.offset_z_grasp = offset_z
        self.move_delay = delay  # Delay between moves in seconds

        self.get_logger().info("=== Chess Game Replay ===")
        self.get_logger().info(f"Game file: {game_file}")
        self.get_logger().info(f"Delay between moves: {delay}s")

        if offset_x != 0.0 or offset_y != 0.0 or offset_z != 0.22:
            self.get_logger().info(f"Position offsets: x={offset_x:+.3f}, y={offset_y:+.3f}, z={offset_z:+.3f}")

        # Parse game file
        parser = ChessGameParser()
        try:
            self.moves = parser.parse_game_file(game_file)
            self.get_logger().info(f"✓ Loaded {len(self.moves)} moves from game file")
        except Exception as e:
            self.get_logger().error(f"Failed to parse game file: {e}")
            raise

        # Track current move
        self.current_move_index = 0
        self.move_in_progress = False

        # Square position subscribers
        self.square_positions = {}
        self.square_subs = {}

        # Subscribe to all squares we need
        self._subscribe_to_squares()

        # Joint state
        self.joint_state = None
        self.subscription_joints = self.create_subscription(
            JointState,
            "/joint_states",
            self.joint_state_callback,
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

        # Job queue for current move
        self.job_queue = []

        # Timer to check if ready to start
        self.create_timer(0.5, self.check_ready)

        self.get_logger().info("Waiting for square positions and joint states...")

    def _subscribe_to_squares(self):
        """Subscribe to position topics for all squares used in the game."""
        # Get unique squares from moves
        squares_needed = set()
        for from_sq, to_sq in self.moves:
            squares_needed.add(from_sq)
            squares_needed.add(to_sq)

        self.get_logger().info(f"Subscribing to {len(squares_needed)} square positions")

        for square in squares_needed:
            topic = f'/chess_square/{square}'
            self.square_subs[square] = self.create_subscription(
                PointStamped,
                topic,
                lambda msg, sq=square: self.square_callback(msg, sq),
                10
            )

    def square_callback(self, msg, square):
        """Store received square position."""
        self.square_positions[square] = [msg.point.x, msg.point.y, msg.point.z]

    def joint_state_callback(self, msg):
        """Update joint state."""
        self.joint_state = msg

    def check_ready(self):
        """Check if ready to start replay."""
        if self.move_in_progress:
            return

        # Check if we have all required squares
        squares_needed = set()
        for from_sq, to_sq in self.moves:
            squares_needed.add(from_sq)
            squares_needed.add(to_sq)

        if not all(sq in self.square_positions for sq in squares_needed):
            missing = squares_needed - set(self.square_positions.keys())
            if len(missing) <= 5:  # Only log if few missing
                self.get_logger().info(f"Waiting for squares: {sorted(missing)}")
            return

        if self.joint_state is None:
            return

        # Ready! Start replay
        if self.current_move_index == 0:
            self.get_logger().info("✓ All positions received. Starting game replay!")
            time.sleep(2)  # Give user time to see message
            self.execute_next_move()

    def execute_next_move(self):
        """Execute the next move in the game."""
        if self.current_move_index >= len(self.moves):
            self.get_logger().info("=== GAME REPLAY COMPLETED ===")
            self.get_logger().info(f"Executed {len(self.moves)} moves")
            rclpy.shutdown()
            return

        # Get current move
        from_sq, to_sq = self.moves[self.current_move_index]
        move_num = self.current_move_index + 1

        self.get_logger().info(f"Move {move_num}/{len(self.moves)}: {from_sq} -> {to_sq}")

        # Get positions
        from_pos = self.square_positions[from_sq]
        to_pos = self.square_positions[to_sq]

        # Build and execute job queue for this move
        self.move_in_progress = True
        self.build_job_queue(from_pos, to_pos)
        self.execute_jobs()

    def build_job_queue(self, from_position, to_position):
        """Build movement sequence for current move."""
        from_x, from_y, from_z = from_position
        to_x, to_y, to_z = to_position

        # Apply offsets
        from_x += self.offset_x
        from_y += self.offset_y

        # Heights
        z_approach = from_z + 0.30
        z_grasp = from_z + self.offset_z_grasp

        # Build job sequence
        pg_from = (from_x, from_y, z_approach)
        grasp_from = (from_x, from_y, z_grasp)
        lift_from = pg_from
        pg_to = (to_x, to_y, z_approach)
        place_to = (to_x, to_y, z_grasp + 0.005)
        retreat_to = pg_to

        self.job_queue = [
            ("ik", pg_from),
            ("ik", grasp_from),
            ("grip", None),
            ("ik", lift_from),
            ("ik", pg_to),
            ("ik", place_to),
            ("grip", None),
            ("ik", retreat_to),
        ]

    def execute_jobs(self):
        """Execute jobs sequentially."""
        if not self.job_queue:
            # Move complete
            self.move_in_progress = False
            self.current_move_index += 1

            # Wait before next move
            time.sleep(self.move_delay)

            # Execute next move
            self.execute_next_move()
            return

        job_type, data = self.job_queue.pop(0)

        if job_type == "ik":
            self.do_ik_motion(data)
        else:
            self.do_grip()

    def do_ik_motion(self, pos):
        """Execute IK motion."""
        if self.joint_state is None:
            self.get_logger().error("No joint state available")
            return

        x, y, z = pos

        q = self.ik_planner.compute_ik(
            self.joint_state, x, y, z,
            qx=0.0, qy=1.0, qz=0.0, qw=0.0
        )

        if q is None:
            self.get_logger().error("IK computation failed")
            rclpy.shutdown()
            return

        traj = self.ik_planner.plan_to_joints(q)
        if traj is None:
            self.get_logger().error("Planning failed")
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
        description="Chess Game Replay",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Basic game replay:
    ros2 run planning chess_game_replay --game-file games/ladder_checkmate.txt

  With position offsets and custom delay:
    ros2 run planning chess_game_replay --game-file games/my_game.txt --offset-z 0.25 --delay 5.0
        """
    )
    parser.add_argument(
        "--game-file",
        dest="game_file",
        type=str,
        required=True,
        help="Path to game file"
    )
    parser.add_argument(
        "--offset-x",
        dest="offset_x",
        type=float,
        default=0.0,
        help="X-axis offset in meters (default: 0.0)"
    )
    parser.add_argument(
        "--offset-y",
        dest="offset_y",
        type=float,
        default=0.0,
        help="Y-axis offset in meters (default: 0.0)"
    )
    parser.add_argument(
        "--offset-z",
        dest="offset_z",
        type=float,
        default=0.22,
        help="Z-height offset for grasp in meters (default: 0.22)"
    )
    parser.add_argument(
        "--delay",
        dest="delay",
        type=float,
        default=3.0,
        help="Delay between moves in seconds (default: 3.0)"
    )

    ros_args = rclpy.utilities.remove_ros_args(sys.argv)
    parsed = parser.parse_args(ros_args[1:])

    rclpy.init(args=args)

    node = ChessGameReplay(
        game_file=parsed.game_file,
        offset_x=parsed.offset_x,
        offset_y=parsed.offset_y,
        offset_z=parsed.offset_z,
        delay=parsed.delay
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
