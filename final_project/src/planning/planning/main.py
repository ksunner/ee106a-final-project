# ROS Libraries
from std_srvs.srv import Trigger
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from geometry_msgs.msg import PointStamped
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from sensor_msgs.msg import JointState
from std_msgs.msg import String
from scipy.spatial.transform import Rotation as R
import numpy as np
import sys

from planning.ik import IKPlanner


class UR7e_CubeGrasp(Node):
    """
    Fully fixed + updated version:
    - Multi-cube colors (blue/green/red)
    - Direction-based release (right/left/front/back)
    - CORRECT IK sequencing (IK computed AFTER each motion)
    """

    def __init__(self, cube_color="blue", direction="right"):
        super().__init__("cube_grasp")

        # Announce configuration
        self.get_logger().info("=== UR7e Cube Grasp Node Initialized ===")
        self.get_logger().info(f"Cube color selected: {cube_color}")
        self.get_logger().info(f"Direction selected: {direction}")

        # -------------------------------------------------------
        # Color → topic mapping
        # -------------------------------------------------------
        self.topic_map = {
            "blue": "/cube_pose_blue",
            "green": "/cube_pose_green",
            "red": "/cube_pose_red",
        }

        if cube_color not in self.topic_map:
            raise ValueError("Cube color must be: blue | green | red")

        self.cube_topic = self.topic_map[cube_color]

        # Direction offsets
        self.offset_map = {
            "right": (0.40, 0.00, 0.00),
            "left": (-0.40, 0.00, 0.00),
            "front": (0.00, -0.40, 0.00),
            "back": (0.00, 0.40, 0.00),
        }
        if direction not in self.offset_map:
            raise ValueError("Direction must be: right | left | front | back")

        self.direction = direction

        # -------------------------------------------------------
        # Subscribers
        # -------------------------------------------------------
        self.cube_pose = None
        self.joint_state = None

        self.subscription_cube = self.create_subscription(
            PointStamped, self.cube_topic, self.cube_callback, 1
        )

        self.subscription_joints = self.create_subscription(
            JointState, "/joint_states", self.joint_state_callback, 1
        )

        # -------------------------------------------------------
        # Action + Service Clients
        # -------------------------------------------------------
        self.exec_ac = ActionClient(
            self, FollowJointTrajectory,
            "/scaled_joint_trajectory_controller/follow_joint_trajectory"
        )
        self.gripper_cli = self.create_client(Trigger, "/toggle_gripper")

        self.ik_planner = IKPlanner()

        # -------------------------------------------------------
        # Job queue: tuples (type, data)
        # type = "ik" or "grip"
        # -------------------------------------------------------
        self.job_queue = []

        self.get_logger().info("Waiting for joint states...")

    # ==========================================================
    # Joint state callback
    # ==========================================================
    def joint_state_callback(self, msg):
        self.joint_state = msg

    # ==========================================================
    # Cube pose callback (starts pipeline)
    # ==========================================================
    def cube_callback(self, msg):
        if self.cube_pose is not None:
            return  # Only handle first detection

        if self.joint_state is None:
            return

        self.cube_pose = msg
        x, y, z = msg.point.x, msg.point.y, msg.point.z

        self.get_logger().info(
            f"Received cube pose:\n"
            f"x={x:.3f}, y={y:.3f}, z={z:.3f}"
        )

        # Build job queue with POSITION targets, NOT IK yet
        self.build_job_queue(x, y, z)

        # Start execution
        self.execute_jobs()

    # ==========================================================
    # Build job queue using POSITIONS ONLY
    # (IK is computed later step-by-step)
    # ==========================================================
    def build_job_queue(self, cx, cy, cz):
        # Pre-grasp position
        pg = (cx - 0.01, cy - 0.08, cz + 0.18)

        # Grasp pose
        gp = (pg[0], pg[1], cz + 0.16)

        # Retreat
        rp = pg

        # Release offset
        dx, dy, dz = self.offset_map[self.direction]
        rel = (pg[0] + dx, pg[1] + dy, pg[2] + dz)

        # Add structured jobs
        self.job_queue.extend([
            ("ik", pg),
            ("ik", gp),
            ("grip", None),
            ("ik", rp),
            ("ik", rel),
            ("grip", None),
        ])

    # ==========================================================
    # Executor — runs one job at a time
    # ==========================================================
    def execute_jobs(self):
        if not self.job_queue:
            self.get_logger().info("=== ALL JOBS COMPLETED ===")
            rclpy.shutdown()
            return

        job_type, data = self.job_queue.pop(0)

        if job_type == "ik":
            self.do_ik_motion(data)
        else:
            self.do_grip()

    # ==========================================================
    # IK MOTION — IK computed using FRESH joint state
    # ==========================================================
    def do_ik_motion(self, pos):
        if self.joint_state is None:
            self.get_logger().error("No joint state available for IK")
            return

        x, y, z = pos
        self.get_logger().info(f"Computing IK for target: {pos}")

        q = self.ik_planner.compute_ik(
            self.joint_state, x, y, z,
            qx=0.0, qy=1.0, qz=0.0, qw=0.0
        )

        traj = self.ik_planner.plan_to_joints(q)
        if traj is None:
            self.get_logger().error("Planning failed.")
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

    parser = argparse.ArgumentParser(description="UR7e Multi-Cube Grasping")
    parser.add_argument("--color", type=str, required=True,
                        help="Cube color: blue | green | red")
    parser.add_argument("--direction", type=str, default="right",
                        help="Placement direction: right | left | front | back")

    ros_args = rclpy.utilities.remove_ros_args(sys.argv)
    parsed = parser.parse_args(ros_args[1:])

    rclpy.init(args=args)

    node = UR7e_CubeGrasp(
        cube_color=parsed.color,
        direction=parsed.direction
    )

    rclpy.spin(node)
    node.destroy_node()


if __name__ == "__main__":
    main()
