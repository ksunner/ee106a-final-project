# Chess System with ArUco Calibration - Complete Summary

## Overview

This system provides a complete solution for chess board calibration and piece movement using ArUco markers. The board is calibrated once using 4 corner markers, then all 64 square positions are computed and made available for moving pieces.

## System Components

### 1. Chess Board Calibrator (`chess_coords_aruco.py`)

**Purpose**: Calibrate the chess board using 4 ArUco markers at corners

**Key Features**:
- Reads TF transforms for 4 corner markers (IDs: 100, 101, 102, 103)
- Uses bilinear interpolation to compute all 64 square centers
- Publishes positions continuously for use by movement nodes
- Handles board rotation, scaling, and slight non-planarity automatically

**Marker Placement**:
```
a8 (103) ────────────────── h8 (102)
   │                           │
   │         Chess             │
   │         Board             │
   │                           │
a1 (100) ────────────────── h1 (101)
```

**ROS Interface**:
- **Subscribes**: TF transforms `aruco_marker_100`, `aruco_marker_101`, `aruco_marker_102`, `aruco_marker_103`
- **Publishes**:
  - `/chess_board_center` - Center of the board
  - `/chess_square/{square}` - Individual square positions (64 topics)
- **Services**: `/calibrate_chess_board` - Trigger calibration

### 2. Chess Move Node (`chess_move_aruco.py`)

**Purpose**: Move chess pieces between squares using calibrated positions

**Key Features**:
- Subscribes to square positions from calibrator
- Plans and executes complete pick-and-place sequence
- Uses IK planning for smooth motion
- Handles gripper control automatically

**Movement Sequence**:
1. Approach origin square (elevated)
2. Lower to grasp height
3. Close gripper
4. Lift piece
5. Move to destination (elevated)
6. Lower to place height
7. Open gripper
8. Retreat

**ROS Interface**:
- **Subscribes**:
  - `/chess_square/{from_square}` - Origin position
  - `/chess_square/{to_square}` - Destination position
  - `/joint_states` - Current robot state
- **Uses**:
  - `/scaled_joint_trajectory_controller/follow_joint_trajectory` - Action for movement
  - `/toggle_gripper` - Service for gripper control

### 3. Board Visualizer (`visualize_board.py`)

**Purpose**: Debug and verify calibration

**Key Features**:
- Displays all 64 square positions in a grid
- Shows board statistics (dimensions, square sizes)
- Calculates board center
- Detects distortions

**Example Output**:
```
CHESS BOARD CALIBRATION - Square Positions
================================================================
Board layout (z-heights in mm above base_link):

     a      b      c      d      e      f      g      h
  ----------------------------------------------------------------
8 |  245   245   245   246   246   246   246   246 | 8
7 |  245   245   245   246   246   246   246   246 | 7
...
1 |  244   244   244   245   245   245   245   245 | 1
  ----------------------------------------------------------------
     a      b      c      d      e      f      g      h

Corner positions (in meters, base_link frame):
  a1: x= 0.4500, y= 0.3200, z= 0.2440
  h1: x= 0.4500, y=-0.1200, z= 0.2450
  h8: x=-0.0100, y=-0.1200, z= 0.2460
  a8: x=-0.0100, y= 0.3200, z= 0.2450

Board Statistics:
  Bottom width (a1-h1): 440.0 mm
  Top width (a8-h8):    440.0 mm
  Left height (a1-a8):  460.0 mm
  Right height (h1-h8): 460.0 mm
  Average square width:  62.9 mm
  Average square height: 65.7 mm
  Square deviation: 4.5%
  Board center: x= 0.2200, y= 0.1000, z= 0.2455
```

## Mathematical Foundation

### Bilinear Interpolation

The system uses bilinear interpolation to calculate square positions from the 4 corners:

Given corner positions:
- P_a1 at (file=0, rank=0)
- P_h1 at (file=7, rank=0)
- P_h8 at (file=7, rank=7)
- P_a8 at (file=0, rank=7)

For any square at (file_idx, rank_idx):
```
u = file_idx / 7.0  # Normalized file position [0, 1]
v = rank_idx / 7.0  # Normalized rank position [0, 1]

P(u,v) = (1-u)(1-v) * P_a1 +  # Bottom-left corner weight
         u(1-v)     * P_h1 +  # Bottom-right corner weight
         u*v        * P_h8 +  # Top-right corner weight
         (1-u)*v    * P_a8    # Top-left corner weight
```

This formula:
- Handles rotation: Board doesn't need to be aligned with robot axes
- Handles scaling: Automatically adapts to actual board size
- Handles non-planarity: Z-coordinate is also interpolated
- Is computationally efficient: Single matrix operation

### Why 8 Squares Between Markers?

The chess board has 8 files (a-h) and 8 ranks (1-8), giving 64 squares total.

Markers at corners:
- a1 to h1: 7 square intervals (8 squares including endpoints)
- a1 to a8: 7 square intervals (8 squares including endpoints)
- Total squares in each direction: 8

The interpolation divides these 7 intervals into equal segments.

## Usage Workflow

### Step 1: Physical Setup

1. Print 4 ArUco markers (50mm, 5x5 dictionary):
   - Marker ID 100
   - Marker ID 101
   - Marker ID 102
   - Marker ID 103

2. Place markers at chess board corners:
   - 100 at a1 (bottom-left)
   - 101 at h1 (bottom-right)
   - 102 at h8 (top-right)
   - 103 at a8 (top-left)

3. Ensure marker centers align roughly with square centers

### Step 2: Build and Source

```bash
cd ~/ros_workspaces/ee106a-final-project/final_project
colcon build --packages-select planning
source install/setup.bash
```

### Step 3: Start System

```bash
# Terminal 1: Start robot and camera
ros2 launch <your_robot_bringup>

# Terminal 2: Start ArUco detection
ros2 launch ros2_aruco aruco_recognition.launch.py

# Terminal 3: Start board calibrator
ros2 run planning chess_board_calibrator
```

### Step 4: Calibrate Board

```bash
# Terminal 4: Trigger calibration when all markers visible
ros2 service call /calibrate_chess_board std_srvs/srv/Trigger
```

Expected response:
```
success: True
message: 'Board calibrated successfully! 64 squares computed.'
```

### Step 5: Verify Calibration (Optional)

```bash
# Terminal 5: Visualize board
ros2 run planning visualize_board
```

### Step 6: Move Chess Pieces

```bash
# Move pawn from e2 to e4
ros2 run planning chess_move_aruco --from e2 --to e4

# Move knight from g1 to f3
ros2 run planning chess_move_aruco --from g1 --to f3

# Move any piece between any squares
ros2 run planning chess_move_aruco --from d7 --to d5
```

## Complete Example Session

```bash
# 1. Build
colcon build --packages-select planning && source install/setup.bash

# 2. Start robot (in separate terminals)
ros2 launch ur_moveit_config ur_moveit.launch.py
ros2 launch usb_cam camera.launch.py
ros2 launch ros2_aruco aruco_recognition.launch.py

# 3. Start calibrator
ros2 run planning chess_board_calibrator

# 4. Verify markers detected
ros2 topic list | grep aruco_marker

# 5. Calibrate
ros2 service call /calibrate_chess_board std_srvs/srv/Trigger

# 6. Visualize (optional)
ros2 run planning visualize_board

# 7. Make moves
ros2 run planning chess_move_aruco --from e2 --to e4
ros2 run planning chess_move_aruco --from e7 --to e5
ros2 run planning chess_move_aruco --from g1 --to f3
```

## Troubleshooting

### Markers Not Detected

**Problem**: Calibrator can't find all 4 markers

**Solutions**:
1. Check camera view includes all corners
2. Verify marker IDs are correct (100-103)
3. Ensure good lighting conditions
4. Check if ArUco detection node is running:
   ```bash
   ros2 topic list | grep aruco
   ros2 topic echo /aruco_markers
   ```

### Calibration Fails

**Problem**: Service call returns `success: False`

**Solutions**:
1. Verify all 4 markers are visible simultaneously
2. Check TF tree:
   ```bash
   ros2 run tf2_tools view_frames
   # Should show aruco_marker_100, 101, 102, 103
   ```
3. Restart calibrator and try again

### Movement Goes to Wrong Square

**Problem**: Robot moves to incorrect position

**Solutions**:
1. Verify calibration with visualizer:
   ```bash
   ros2 run planning visualize_board
   ```
2. Check if board statistics look reasonable (square size ~50-60mm)
3. Re-calibrate if needed:
   ```bash
   ros2 service call /calibrate_chess_board std_srvs/srv/Trigger
   ```
4. Verify square topics are publishing:
   ```bash
   ros2 topic echo /chess_square/e4
   ```

### IK Fails

**Problem**: "IK computation failed" error

**Solutions**:
1. Check if target position is within robot reach
2. Try moving to intermediate squares first
3. Adjust z-heights in chess_move_aruco.py:
   ```python
   z_approach = from_z + 0.30  # Increase if needed
   z_grasp = from_z + 0.22     # Adjust for piece height
   ```

### Board Appears Distorted

**Problem**: Visualizer shows >5% square deviation

**Solutions**:
1. Check marker placement - ensure they're on correct squares
2. Verify markers are flat and not warped
3. Ensure board is reasonably flat (small tilt is OK)
4. Re-measure and re-place markers if necessary

## Advanced Topics

### Custom Board Sizes

To use a different square size, the system automatically adapts based on marker positions. No configuration needed!

### Multiple Boards

Run multiple calibrator instances with different namespaces:
```bash
ros2 run planning chess_board_calibrator --ros-args -r __ns:=/board1
ros2 run planning chess_board_calibrator --ros-args -r __ns:=/board2
```

### Integration with Chess Engine

The movement system can be integrated with a chess engine by:
1. Chess engine decides moves
2. Sends move commands to ROS
3. System executes physical movement

Example integration script:
```python
import chess
import subprocess

board = chess.Board()

while not board.is_game_over():
    # Get move from engine
    move = get_engine_move(board)

    # Convert to squares
    from_square = chess.square_name(move.from_square)
    to_square = chess.square_name(move.to_square)

    # Execute physical move
    subprocess.run([
        'ros2', 'run', 'planning', 'chess_move_aruco',
        '--from', from_square,
        '--to', to_square
    ])

    # Update board
    board.push(move)
```

## Files Reference

```
final_project/src/planning/planning/
├── chess_coords_aruco.py      # Board calibrator node
├── chess_move_aruco.py        # Chess move execution node
├── visualize_board.py         # Board visualization tool
├── CHESS_ARUCO_README.md      # Detailed documentation
└── ik.py                      # IK planning utilities

final_project/src/planning/
├── setup.py                   # Package configuration
└── package.xml               # ROS package metadata
```

## Entry Points

After building, the following commands are available:

- `ros2 run planning chess_board_calibrator` - Start calibration node
- `ros2 run planning chess_move_aruco` - Move chess pieces
- `ros2 run planning visualize_board` - Visualize calibrated board

## Summary

This system provides a robust, automatic chess board calibration solution that:

✅ Requires only 4 ArUco markers at corners
✅ Calculates all 64 square positions automatically
✅ Handles board rotation and scaling
✅ Provides easy-to-use movement interface
✅ Includes visualization tools for debugging
✅ Works with standard ROS2 robot controllers

The bilinear interpolation approach ensures accuracy across the entire board while requiring minimal manual setup. Once calibrated, you can move pieces between any squares with simple commands like `--from e2 --to e4`.
