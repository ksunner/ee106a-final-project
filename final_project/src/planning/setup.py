from setuptools import find_packages, setup
from glob import glob

package_name = 'planning'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (('share/' + package_name + '/launch'), glob('launch/*.launch.py'))
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ee106a-tah',
    maintainer_email='danielmunicio360@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'main = planning.main:main',
            'static_tf_transform = planning.static_tf_transform:main',
            'ik = planning.ik:main',
            'transform_cube_pose = planning.transform_cube_pose:main',
            'cube_pose_from_aruco = planning.cube_pose_from_aruco:main',
            'multi_cube_pose_from_aruco = planning.multi_cube_pose_from_aruco:main',
            'chess_move = planning.chess_move:main',
            'chess_board_calibrator = planning.chess_coords_aruco:main_calibrator',
            'chess_move_aruco = planning.chess_move_aruco:main',
            'chess_game_replay = planning.chess_game_replay:main',
            'chess_take = planning.chess_take:main',
            'visualize_board = planning.visualize_board:main',
            'check_aruco_detection = planning.check_aruco_detection:main'
        ],
    },

)
