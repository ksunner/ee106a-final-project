import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():

    # Path to your ros2_aruco parameter file if you still want defaults.
    aruco_params = os.path.join(
        get_package_share_directory('ros2_aruco'),
        'config',
        'aruco_parameters.yaml'
    )

    return LaunchDescription([
        Node(
            package='ros2_aruco',
            executable='aruco_node',
            output='screen',
            parameters=[
                aruco_params,      # (optional defaults)
                {
                    # --- YOUR USB CAM SETTINGS ---
                    "image_topic": "/camera/image_raw",
                    "camera_info_topic": "/camera/camera_info",

                    # This must match your usb_cam yaml (c922_pro_stream_webcam.yaml)
                    "camera_frame": "camera1",

                    # Marker size in meters (adjust to your printed marker)
                    "marker_size": 0.05,

                    # ArUco dictionary used to generate your markers
                    "aruco_dictionary_id": "DICT_5X5_250",
                }
            ]
        )
    ])
