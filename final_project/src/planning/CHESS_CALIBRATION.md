# Chess Board Auto-Calibration System

This system automatically detects your chess board using computer vision and calibrates the coordinate mapping, eliminating the need for precise ArUco marker placement.

## Features

- **Automatic Detection**: Uses OpenCV's `findChessboardCorners` to detect the board
- **Homography-Based**: Handles camera perspective/slant correctly
- **RViz Visualization**: See detected square centers in real-time
- **Persistent Calibration**: Saves calibration to file for reuse

## How It Works

1. **Chessboard Detection**: Detects the 7x7 internal corners of your 8x8 chessboard
2. **Homography Computation**: Computes perspective transform from board to image
3. **Square Center Calculation**: Computes the center of each of the 64 squares
4. **Offset Mapping**: Maps each square center as an offset from the ArUco marker

## Usage

### Step 1: Build the Package

```bash
cd /home/cc/ee106a/fa25/class/ee106a-ahc/ros_workspaces/ee106a-final-project/final_project
colcon build --packages-select planning
source install/setup.bash
```

### Step 2: Launch the Calibrator

**Option A: Standalone Calibrator** (Recommended)

```bash
# Terminal 1: Launch camera + ArUco detection
ros2 launch planning chess_play.launch.py

# Terminal 2: Launch calibrator
ros2 run planning chess_board_calibrator
```

**Option B: Combined Launch** (Create a new launch file if preferred)

### Step 3: Calibrate the Board

1. **Position the board**: Make sure the **entire chess board** is visible to the camera
2. **Trigger calibration**:
   ```bash
   ros2 service call /calibrate_chess_board std_srvs/srv/Trigger
   ```
3. **Wait for success**: You should see:
   ```
   ✓ Calibration successful!
   Calibrated 64 squares
   ```

### Step 4: Visualize in RViz

```bash
rviz2
```

Add the following displays:
- **MarkerArray** on topic `/chess_square_centers`
- **TF** to see coordinate frames

You should see:
- Small spheres at each square center
- Text labels (a1, a2, ..., h8) above each square
- Light squares (tan) and dark squares (brown)

### Step 5: Use Calibrated Coordinates

The calibration is automatically saved to `/tmp/chess_board_calibration.json`. To use it:

**Method 1: Load calibration in chess_coords.py**

Update `chess_coords.py` to load from the calibration file:

```python
import json

class ChessCoords:
    def __init__(self, square_size=0.055, calibration_file='/tmp/chess_board_calibration.json'):
        self.square_size = square_size
        self.square_offsets = {}

        # Load calibration if available
        try:
            with open(calibration_file, 'r') as f:
                self.square_offsets = json.load(f)
            print(f"Loaded calibration for {len(self.square_offsets)} squares")
        except:
            print("No calibration file found, using manual mapping")
            self.center_file = 3.5
            self.center_rank = 4.5

    def square_to_offset(self, square):
        # Use calibrated offset if available
        if square in self.square_offsets:
            return tuple(self.square_offsets[square])

        # Fall back to manual calculation
        # ... existing code ...
```

**Method 2: Direct calibration integration**

The calibrator can be integrated directly into your chess move planning.

## Troubleshooting

### "Chessboard not detected"

**Causes:**
- Board not fully visible
- Poor lighting
- Board too small/large in frame
- Glare on board

**Solutions:**
- Adjust camera position to see entire board
- Improve lighting (even, diffuse light)
- Move camera closer/farther
- Remove reflective surfaces

### "Homography computation failed"

**Causes:**
- Not enough good corner detections
- Board at extreme angle

**Solutions:**
- Make camera more perpendicular to board
- Ensure board is flat
- Better lighting on corners

### Calibration is slightly off

**Causes:**
- Camera moved after calibration
- Board moved after calibration
- ArUco marker detection drift

**Solutions:**
- Recalibrate: `ros2 service call /calibrate_chess_board std_srvs/srv/Trigger`
- Ensure camera and board are stable
- Check ArUco marker is firmly attached

## Technical Details

### Coordinate System

- **Board Frame Origin**: Top-left corner (square a8)
- **ArUco Marker Position**: Center of board (between d4, d5, e4, e5)
- **Square Indexing**: Standard chess notation (a1-h8)

### Homography

The system uses OpenCV's `findHomography` with RANSAC to compute the perspective transform:

```
H: board_coordinates -> image_coordinates
```

This handles:
- Camera perspective distortion
- Board tilt/slant
- Lens distortion (if camera is calibrated)

### Marker Visualization

- **Light Squares**: Tan spheres (RGB: 0.9, 0.9, 0.7)
- **Dark Squares**: Brown spheres (RGB: 0.3, 0.2, 0.1)
- **Size**: 1cm diameter spheres
- **Labels**: White text 3cm above each square

## Parameters

Configured in the calibrator node:

- `image_topic`: Camera image topic (default: `/camera1/image_raw`)
- `board_marker_id`: ArUco marker on board (default: 8)
- `square_size`: Square size in meters (default: 0.055 = 5.5cm)
- `calibration_file`: Save location (default: `/tmp/chess_board_calibration.json`)

## Next Steps

1. ✅ Calibrate your board
2. ✅ Verify visualization in RViz
3. 🔲 Integrate calibration into `chess_move.py`
4. 🔲 Test chess moves with auto-calibrated coordinates
5. 🔲 Add automatic recalibration on startup

## Example Workflow

```bash
# 1. Launch system
ros2 launch planning chess_play.launch.py

# 2. In another terminal, run calibrator
ros2 run planning chess_board_calibrator

# 3. Trigger calibration
ros2 service call /calibrate_chess_board std_srvs/srv/Trigger

# 4. Verify in RViz
rviz2
# Add MarkerArray display on /chess_square_centers

# 5. Make a chess move (uses calibrated coordinates)
ros2 run planning chess_move --from e2 --to e4
```

## Benefits Over Manual Calibration

| Manual | Auto-Calibration |
|--------|------------------|
| Requires precise marker placement | Works with any marker position |
| Sensitive to marker offset | Robust to marker placement |
| No visual feedback | Real-time RViz visualization |
| One-time guess | Easily recalibrate anytime |
| Assumes perpendicular camera | Handles camera perspective |

