#!/usr/bin/env python3


import os
from pathlib import Path

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

from ament_index_python.packages import get_package_share_directory

from launch.actions import DeclareLaunchArgument
from launch.events import Shutdown
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, RegisterEventHandler, EmitEvent
from launch.event_handlers import OnProcessExit
from launch.substitutions import LaunchConfiguration


def generate_launch_description():

    # -----------------------------------------------------
    # 1. USB CAMERA LAUNCH (from your usb_cam package)
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
                "marker_size": 0.05,         # default size (ID-specific overridden inside node)
                "aruco_dictionary_id": "DICT_5X5_250"
            }
        ]
    )

    # -----------------------------------------------------
    # 3. STATIC TRANSFORM: ar_marker_8 → base_link
    # -----------------------------------------------------
    static_tf = Node(
        package='planning',
        executable='static_tf_transform',
        name='static_tf_marker_to_base'
    )

    # -----------------------------------------------------
    # 4. MULTI-CUBE POSE PUBLISHER
    # -----------------------------------------------------
    multi_cube_pose = Node(
        package='planning',
        executable='multi_cube_pose_from_aruco',
        name='multi_cube_pose_from_aruco',
        output='screen'
    )

    ik_planner_node = Node(
        package='planning',
        executable='ik',
        name='ik_planner',
        output='screen'
    )

   # Static TF: base_link -> world
    # -------------------------------------------------
    # This TF is static because the "world" frame does not move.
    # It is necessary to define the "world" frame for MoveIt to work properly as this is the defualt planning frame.
    # -------------------------------------------------
    static_base_world = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_base_world',
        arguments=['0','0','0','0','0','0','1','base_link','world'],
        output='screen',
    )

    # MoveIt 
    ur_type = LaunchConfiguration("ur_type", default="ur7e")
    launch_rviz = LaunchConfiguration("launch_rviz", default="true")

    # Path to the MoveIt launch file
    moveit_launch_file = os.path.join(
                get_package_share_directory("ur_moveit_config"),
                "launch",
                "ur_moveit.launch.py"
            )

    # Include the MoveIt launch description
    moveit_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(moveit_launch_file),
        launch_arguments={
            "ur_type": ur_type,
            "launch_rviz": launch_rviz
        }.items(),
    )

    shutdown_on_any_exit = RegisterEventHandler(
        OnProcessExit(
            on_exit=[EmitEvent(event=Shutdown(reason='SOMETHING BONKED'))]
        )
    )


    return LaunchDescription([
        camera_launch,
        aruco_node,
        static_tf,
        multi_cube_pose,
        static_base_world,
        moveit_launch,
        shutdown_on_any_exit,
        ik_planner_node
    ])
