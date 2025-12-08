#!/usr/bin/env python3
"""
Complete Chess System Launch File

This launch file starts the complete chess system including:
1. USB camera
2. ArUco detection node (configured for chess markers 100-103)
3. Chess board calibrator node
4. MoveIt planning interface
5. IK planner
6. Static TF transforms

Usage:
    ros2 launch planning chess_system.launch.py

After launch:
1. Calibrate board:
    ros2 service call /calibrate_chess_board std_srvs/srv/Trigger

2. Move pieces:
    ros2 run planning chess_move_aruco --from e2 --to e4

Optional: Visualize board
    ros2 run planning visualize_board
"""

import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, RegisterEventHandler, EmitEvent
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.events import Shutdown
from launch.event_handlers import OnProcessExit
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():

    # -----------------------------------------
    # 1. USB Camera Launch
    # -----------------------------------------
    usb_cam_launch_dir = os.path.join(
        get_package_share_directory('usb_cam'),
        'launch'
    )

    camera_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(usb_cam_launch_dir, 'camera.launch.py')
        )
    )

    # -----------------------------------------
    # 2. ArUco Detection Node
    # -----------------------------------------
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
                "marker_size": 0.05,  # 50mm markers
                "aruco_dictionary_id": "DICT_5X5_250",
            }
        ]
    )

    # -----------------------------------------
    # 3. Static TF Transforms
    # -----------------------------------------
    # TF: camera1 -> base_link
    # NOTE: Adjust these values based on your camera mounting!
    static_camera_to_base = Node(
        package='planning',
        executable='static_tf_transform',
        name='static_tf_marker_to_base',
        output='screen',
    )

    # TF: base_link -> world
    static_base_world = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_base_world',
        arguments=['0', '0', '0', '0', '0', '0', '1', 'base_link', 'world'],
        output='screen',
    )

    # -----------------------------------------
    # 4. Chess Board Calibrator Node
    # -----------------------------------------
    chess_calibrator_node = Node(
        package='planning',
        executable='chess_board_calibrator',
        name='chess_board_calibrator',
        output='screen',
    )

    # -----------------------------------------
    # 5. IK Planner Node
    # -----------------------------------------
    ik_planner_node = Node(
        package='planning',
        executable='ik',
        name='ik_planner',
        output='screen'
    )

    # -----------------------------------------
    # 6. MoveIt Launch
    # -----------------------------------------
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

    # -----------------------------------------
    # 7. Shutdown Handler
    # -----------------------------------------
    shutdown_on_any_exit = RegisterEventHandler(
        OnProcessExit(
            on_exit=[EmitEvent(event=Shutdown(reason='A node exited'))]
        )
    )

    return LaunchDescription([
        camera_launch,              # USB camera
        aruco_node,                 # ArUco detection
        static_camera_to_base,      # TF: camera -> base
        static_base_world,          # TF: base -> world
        chess_calibrator_node,      # Chess calibrator
        ik_planner_node,            # IK planner
        moveit_launch,              # MoveIt
        shutdown_on_any_exit,       # Shutdown handler
    ])
