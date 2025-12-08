# Chess Board Calibration and Movement using ArUco Markers

This system provides chess board calibration using 4 ArUco markers placed at the corners of the board, and enables moving chess pieces between any squares.

## Overview

The system consists of two main components:

1. **ChessBoardCalibrator** (`chess_coords_aruco.py`): Calibrates the board using ArUco markers
2. **ChessMoveAruco** (`chess_move_aruco.py`): Moves pieces between squares using calibrated positions

## Setup

### ArUco Marker Placement

Place four 50mm 5x5 ArUco markers at the corners of the chessboard:

- **aruco_marker_100** at square **a1** (bottom-left, white's perspective)
- **aruco_marker_101** at square **h1** (bottom-right)
- **aruco_marker_102** at square **h8** (top-right)
- **aruco_marker_103** at square **a8** (top-left)

The origin of each ArUco marker should roughly align with the center of the square.

## How It Works

### 1. Board Calibration

The calibrator uses **bilinear interpolation** between the 4 corner markers to calculate the center position of all 64 squares on the board.

Given the 4 corner positions:
- a1, h1, h8, a8

For each square at position (file, rank):
- file: 0-7 representing a-h
- rank: 0-7 representing 1-8

The position is calculated using bilinear interpolation:
```
u = file / 7.0  (0 at 'a', 1 at 'h')
v = rank / 7.0  (0 at rank 1, 1 at rank 8)

P(u,v) = (1-u)(1-v)*a1 + u(1-v)*h1 + u*v*h8 + (1-u)*v*a8
```

This accounts for any rotation, scaling, or slight non-planarity of the board.

### 2. Square Position Publishing

After calibration, the system publishes the position of each square on individual topics:
- `/chess_square/a1`, `/chess_square/a2`, ..., `/chess_square/h8`

Each message is a `PointStamped` with the (x, y, z) position in the `base_link` frame.

### 3. Chess Piece Movement

The movement node subscribes to the positions of the origin and destination squares, then executes a sequence:

1. Approach origin square (elevated)
2. Lower to grasp piece
3. Close gripper
4. Lift piece
5. Move to destination square (elevated)
6. Lower to place piece
7. Open gripper
8. Retreat

## Usage

### Step 1: Build the package

```bash
cd ~/ros_workspaces/ee106a-final-project/final_project
colcon build --packages-select planning
source install/setup.bash
```

### Step 2: Start the ArUco detection node

Make sure your ArUco detection node is running and publishing TF transforms for the markers.

```bash
# Example (adjust based on your launch file)
ros2 launch ros2_aruco aruco_recognition.launch.py
```

### Step 3: Run the calibrator

```bash
ros2 run planning chess_board_calibrator
```

The calibrator will continuously look for the 4 corner markers via TF transforms.

### Step 4: Trigger calibration

Once all 4 markers are visible, trigger the calibration:

```bash
ros2 service call /calibrate_chess_board std_srvs/srv/Trigger
```

You should see output like:
```
Board calibrated successfully! 64 squares computed.
Corner marker positions:
  a1: [x, y, z]
  h1: [x, y, z]
  h8: [x, y, z]
  a8: [x, y, z]
Sample square positions:
  a1: [x, y, z]
  e4: [x, y, z]
  ...
```

### Step 5: Move chess pieces

In a new terminal, run the chess move node:

```bash
ros2 run planning chess_move_aruco --from e2 --to e4
```

This will move a piece from square e2 to square e4.

## Topics

### Published by Calibrator
- `/chess_board_center` (PointStamped): Center of the board
- `/chess_square/{square}` (PointStamped): Position of each square (e.g., `/chess_square/e4`)

### Subscribed by Move Node
- `/chess_square/{from_square}` (PointStamped): Origin square position
- `/chess_square/{to_square}` (PointStamped): Destination square position
- `/joint_states` (JointState): Current robot joint states

## Services

- `/calibrate_chess_board` (Trigger): Trigger board calibration

## Notes

- The system assumes 8 squares between the markers (corner to corner = 7 square intervals)
- The board doesn't need to be perfectly aligned with the robot frame
- Small rotations and scaling are handled automatically by the bilinear interpolation
- The z-height is also interpolated, so the board can be slightly tilted

## Debugging

To view all published square positions:
```bash
ros2 topic list | grep chess_square
```

To see a specific square's position:
```bash
ros2 topic echo /chess_square/e4
```

To check if calibration was successful:
```bash
ros2 topic echo /chess_board_center
```

## Architecture

```
┌─────────────────────────────────────┐
│   ArUco Detection (ros2_aruco)      │
│   Publishes TF: aruco_marker_100-103│
└──────────────┬──────────────────────┘
               │ TF Transforms
               ▼
┌─────────────────────────────────────┐
│   ChessBoardCalibrator              │
│   - Reads marker TFs                │
│   - Computes 64 square positions    │
│   - Publishes positions on topics   │
└──────────────┬──────────────────────┘
               │ /chess_square/* topics
               ▼
┌─────────────────────────────────────┐
│   ChessMoveAruco                    │
│   - Subscribes to square positions  │
│   - Plans and executes movement     │
│   - Controls gripper                │
└─────────────────────────────────────┘
```

## Example Workflow

```bash
# Terminal 1: Start robot and camera
ros2 launch <your_robot_launch_file>

# Terminal 2: Start ArUco detection
ros2 launch ros2_aruco aruco_recognition.launch.py

# Terminal 3: Start calibrator
ros2 run planning chess_board_calibrator

# Terminal 4: Trigger calibration when markers visible
ros2 service call /calibrate_chess_board std_srvs/srv/Trigger

# Terminal 5: Move pieces
ros2 run planning chess_move_aruco --from e2 --to e4
ros2 run planning chess_move_aruco --from g1 --to f3
ros2 run planning chess_move_aruco --from d7 --to d5
```

## Files

- `chess_coords_aruco.py`: Board calibrator node
- `chess_move_aruco.py`: Chess piece movement node
- `CHESS_ARUCO_README.md`: This documentation file
