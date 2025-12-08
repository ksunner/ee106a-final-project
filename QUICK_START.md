# Chess System Quick Start Guide

## TL;DR

1. Place 4 ArUco markers at corners: 100(a1), 101(h1), 102(h8), 103(a8)
2. Run calibrator: `ros2 run planning chess_board_calibrator`
3. Calibrate: `ros2 service call /calibrate_chess_board std_srvs/srv/Trigger`
4. Move pieces: `ros2 run planning chess_move_aruco --from e2 --to e4`

## Marker Setup

```
     Chess Board (White's Perspective)

  a8 [103] ─ ─ ─ ─ ─ ─ ─ h8 [102]
   │                         │
   │      Your Board         │
   │                         │
  a1 [100] ─ ─ ─ ─ ─ ─ ─ h1 [101]
```

## Commands Cheat Sheet

```bash
# Build package
cd ~/ros_workspaces/ee106a-final-project/final_project
colcon build --packages-select planning
source install/setup.bash

# ============================================
# OPTION 1: Launch everything together (RECOMMENDED)
# ============================================
ros2 launch planning chess_calibration.launch.py

# In another terminal: Trigger calibration
ros2 service call /calibrate_chess_board std_srvs/srv/Trigger

# Move pieces (in another terminal)
ros2 run planning chess_move_aruco --from e2 --to e4

# ============================================
# OPTION 2: Launch with full robot system
# ============================================
ros2 launch planning chess_system.launch.py

# ============================================
# OPTION 3: Manual launch (step by step)
# ============================================
# Terminal 1: Camera
ros2 launch usb_cam camera.launch.py

# Terminal 2: ArUco detection
ros2 launch ros2_aruco aruco_recognition.launch.py

# Terminal 3: Calibrator
ros2 run planning chess_board_calibrator

# Terminal 4: Trigger calibration
ros2 service call /calibrate_chess_board std_srvs/srv/Trigger

# ============================================
# Debugging Commands
# ============================================
# Check if ArUco markers are being detected
ros2 run planning check_aruco_detection

# View camera feed
ros2 run rqt_image_view rqt_image_view

# Check camera topics
ros2 topic list | grep camera
ros2 topic echo /camera1/image_raw --no-arr

# Check ArUco topics
ros2 topic list | grep aruco
ros2 topic echo /aruco_markers

# Check TF transforms
ros2 run tf2_tools view_frames
ros2 run tf2_ros tf2_echo base_link aruco_marker_100

# ============================================
# Chess Commands
# ============================================
# Visualize board (optional)
ros2 run planning visualize_board

# Move pieces
ros2 run planning chess_move_aruco --from e2 --to e4
ros2 run planning chess_move_aruco --from g1 --to f3
ros2 run planning chess_move_aruco --from d7 --to d5

# Check topics
ros2 topic list | grep chess
ros2 topic echo /chess_square/e4
ros2 topic echo /chess_board_center
```

## Expected Calibration Output

```
[chess_board_calibrator]: Chess Board Calibrator initialized
[chess_board_calibrator]: Place ArUco markers at: a1(100), h1(101), h8(102), a8(103)
[chess_board_calibrator]: Call service '/calibrate_chess_board' when ready
...
[chess_board_calibrator]: Corner marker positions:
[chess_board_calibrator]:   a1: [0.450, 0.320, 0.244]
[chess_board_calibrator]:   h1: [0.450, -0.120, 0.245]
[chess_board_calibrator]:   h8: [-0.010, -0.120, 0.246]
[chess_board_calibrator]:   a8: [-0.010, 0.320, 0.245]
[chess_board_calibrator]: Calibrated 64 square centers
[chess_board_calibrator]: Board calibrated successfully! 64 squares computed.
```

## Common Moves

```bash
# Opening moves
ros2 run planning chess_move_aruco --from e2 --to e4  # King's pawn
ros2 run planning chess_move_aruco --from e7 --to e5  # King's pawn (black)
ros2 run planning chess_move_aruco --from g1 --to f3  # Knight to f3
ros2 run planning chess_move_aruco --from b8 --to c6  # Knight to c6

# Standard notation: any square to any square
ros2 run planning chess_move_aruco --from [source] --to [destination]
```

## Troubleshooting Quick Fixes

### ArUco Markers Not Detected

**Run the debug tool first:**
```bash
ros2 run planning check_aruco_detection
```

This will tell you exactly what's wrong!

| Problem | Solution |
|---------|----------|
| No camera image | Check: `ls /dev/video*`, restart camera node |
| ArUco node not running | Verify: `ros2 node list \| grep aruco` |
| Markers not detected | 1. View camera: `ros2 run rqt_image_view rqt_image_view` <br> 2. Check lighting (avoid glare) <br> 3. Verify marker size = 50mm <br> 4. Ensure markers are flat, not wrinkled |
| Wrong dictionary | Must use DICT_5X5_250 (5x5 markers) |
| TF not available | Check: `ros2 run tf2_ros tf2_echo base_link aruco_marker_100` |

### Other Issues

| Problem | Solution |
|---------|----------|
| Calibration fails | Ensure all 4 markers (100-103) visible simultaneously |
| Wrong square | Re-calibrate, check with `ros2 run planning visualize_board` |
| IK fails | Position out of reach, adjust z-heights in chess_move_aruco.py |
| No movement | Check joint_states topic, verify robot controllers running |
| Camera frame wrong | Check `static_tf_transform` node or adjust in launch file |

## File Locations

- Calibrator: `src/planning/planning/chess_coords_aruco.py`
- Move node: `src/planning/planning/chess_move_aruco.py`
- Visualizer: `src/planning/planning/visualize_board.py`
- Full docs: `src/planning/planning/CHESS_ARUCO_README.md`
- System summary: `CHESS_SYSTEM_SUMMARY.md`

## Key Topics

- `/chess_board_center` - Board center position
- `/chess_square/{a1-h8}` - Individual square positions (64 topics)
- `/calibrate_chess_board` - Service to trigger calibration

## System Requirements

- ROS2 (tested on Humble/Foxy)
- 4 ArUco markers (50mm, 5x5 dictionary, IDs: 100-103)
- Camera with ArUco detection (ros2_aruco package)
- Robot with gripper and IK support
- Chess board (any size, system auto-adapts)

---

**Need more details?** See `CHESS_ARUCO_README.md` or `CHESS_SYSTEM_SUMMARY.md`
