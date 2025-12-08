#!/usr/bin/env python3
"""
Chess Board Calibration Launch File

This launch file starts:
1. USB camera
2. ArUco detection node (configured for chess markers 100-103)
3. Chess board calibrator node
4. Static TF transforms

Usage:
    ros2 launch planning chess_calibration.launch.py

After launch, call the calibration service:
    ros2 service call /calibrate_chess_board std_srvs/srv/Trigger
"""

import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
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
    # Configured to detect chess board markers (IDs 100-103)
    aruco_node = Node(
        package='ros2_aruco',
        executable='aruco_node',
        name='aruco_node',
        output='screen',
        parameters=[
            {
                # Camera topics (must match usb_cam configuration)
                "image_topic": "/camera1/image_raw",
                "camera_info_topic": "/camera1/camera_info",
                "camera_frame": "camera1",

                # ArUco marker configuration
                "marker_size": 0.05,  # 50mm markers
                "aruco_dictionary_id": "DICT_5X5_250",

                # Publish TF transforms for detected markers
                # This will create transforms: camera1 -> aruco_marker_{id}
            }
        ]
    )

    # -----------------------------------------
    # 3. Static TF: camera1 -> base_link
    # -----------------------------------------
    # This transform positions the camera in the robot's coordinate system
    # Adjust these values based on your actual camera mounting position
    static_camera_to_base = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_camera_to_base',
        arguments=[
            '0.0', '0.0', '0.5',  # x, y, z (camera position relative to base_link)
            '0', '0', '0', '1',    # qx, qy, qz, qw (orientation)
            'base_link',           # parent frame
            'camera1'              # child frame
        ],
        output='screen',
    )

    # Alternative: Use your existing static_tf_transform node if it's configured
    # tf_node = Node(
    #     package='planning',
    #     executable='static_tf_transform',
    #     name='static_tf_marker_to_base',
    #     output='screen',
    # )

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
    # 5. Static TF: base_link -> world (for MoveIt compatibility)
    # -----------------------------------------
    static_base_world = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_base_world',
        arguments=['0', '0', '0', '0', '0', '0', '1', 'base_link', 'world'],
        output='screen',
    )

    return LaunchDescription([
        camera_launch,              # Launch USB camera
        aruco_node,                 # Launch ArUco detection
        static_camera_to_base,      # TF: base_link -> camera1
        static_base_world,          # TF: base_link -> world
        chess_calibrator_node,      # Launch chess calibrator
    ])
