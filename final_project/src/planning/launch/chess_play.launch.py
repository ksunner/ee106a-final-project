#!/usr/bin/env python3
"""
Chess Play Launch File

Launches all necessary nodes for chess piece movement:
- Camera
- ArUco detection
- Static transforms
- Board center pose publisher
- MoveIt
- IK planner

To use:
    ros2 launch planning chess_play.launch.py

Then in another terminal:
    ros2 run planning chess_move --from e2 --to e4
"""

import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from launch.actions import RegisterEventHandler, EmitEvent
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration


def generate_launch_description():

    # -----------------------------------------------------
    # 1. USB CAMERA LAUNCH
    # -----------------------------------------------------
    usb_cam_launch_dir = os.path.join(
        get_package_share_directory('usb_cam'),
        'launch'
    )

    camera_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(usb_cam_launch_dir, 'camera.launch.py')
        )
    )

    # -----------------------------------------------------
    # 2. ARUCO DETECTION NODE
    # -----------------------------------------------------
    aruco_node = Node(
        package='ros2_aruco',
        executable='aruco_node',
        name='aruco_node',
        output='screen',
        parameters=[
            {
                "image_topic": "/camera1/image_raw",
                "camera_info_topic": "/camera1/camera_info",
                "camera_frame": "camera1",
                "marker_size": 0.09,  # 90mm = 0.09m
                "aruco_dictionary_id": "DICT_5X5_250"
            }
        ]
    )

    # -----------------------------------------------------
    # 3. STATIC TRANSFORM: ar_marker_8 → base_link
    # (Uses your existing static transform node)
    # -----------------------------------------------------
    static_tf = Node(
        package='planning',
        executable='static_tf_transform',
        name='static_tf_marker_to_base'
    )

    # -----------------------------------------------------
    # 4. BOARD CENTER POSE PUBLISHER
    # (Reuses your cube_pose_from_aruco node)
    # -----------------------------------------------------
    board_pose = Node(
        package='planning',
        executable='cube_pose_from_aruco',
        name='chess_board_center_pose',
        output='screen',
        parameters=[
            {'cube_marker_id': 8}  # Marker ID 8 for chess board center (90mm)
        ]
    )

    # -----------------------------------------------------
    # 5. IK PLANNER NODE
    # -----------------------------------------------------
    ik_planner_node = Node(
        package='planning',
        executable='ik',
        name='ik_planner',
        output='screen'
    )

    # -----------------------------------------------------
    # 6. STATIC TF: base_link → world
    # -----------------------------------------------------
    static_base_world = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_base_world',
        arguments=['0', '0', '0', '0', '0', '0', '1', 'base_link', 'world'],
        output='screen',
    )

    # -----------------------------------------------------
    # 7. MOVEIT LAUNCH
    # -----------------------------------------------------
    ur_type = LaunchConfiguration("ur_type", default="ur7e")
    launch_rviz = LaunchConfiguration("launch_rviz", default="true")

    moveit_launch_file = os.path.join(
        get_package_share_directory("ur_moveit_config"),
        "launch",
        "ur_moveit.launch.py"
    )

    moveit_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(moveit_launch_file),
        launch_arguments={
            "ur_type": ur_type,
            "launch_rviz": launch_rviz
        }.items(),
    )

    # -----------------------------------------------------
    # 8. SHUTDOWN ON EXIT HANDLER
    # -----------------------------------------------------
    shutdown_on_any_exit = RegisterEventHandler(
        OnProcessExit(
            on_exit=[EmitEvent(event=Shutdown(reason='A node exited'))]
        )
    )

    return LaunchDescription([
        camera_launch,
        aruco_node,
        static_tf,
        board_pose,
        static_base_world,
        moveit_launch,
        shutdown_on_any_exit,
        ik_planner_node
    ])
