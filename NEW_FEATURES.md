# New Features - Calibration Persistence & Position Offsets

## Feature 1: Persistent Calibration Storage

### Problem
Having to recalibrate the chess board every time you restart the system was frustrating, even though the board position hadn't changed.

### Solution
The calibrator now **automatically saves** calibration data and **loads it on startup**!

### How It Works

1. **First time calibration:**
   ```bash
   ros2 launch planning chess_calibration.launch.py
   ros2 service call /calibrate_chess_board std_srvs/srv/Trigger
   ```

2. **Calibration is saved automatically** to `~/.ros/chess_calibration.yaml`

3. **Next time you start the system:**
   ```bash
   ros2 launch planning chess_calibration.launch.py
   ```

   Output:
   ```
   [chess_board_calibrator]: Chess Board Calibrator initialized
   [chess_board_calibrator]: ✓ Loaded previous calibration from file
   [chess_board_calibrator]:   File: /home/user/.ros/chess_calibration.yaml
   [chess_board_calibrator]:   To recalibrate, call service '/calibrate_chess_board'
   [chess_board_calibrator]: Loaded 64 square positions
   ```

4. **Ready to play immediately** - no need to recalibrate!

### Recalibration

If you move the board or need to recalibrate for any reason:
```bash
ros2 service call /calibrate_chess_board std_srvs/srv/Trigger
```

This will overwrite the saved calibration file with new data.

### Calibration File Location

- **File path:** `~/.ros/chess_calibration.yaml`
- **Format:** YAML file with all 64 square positions
- **View calibration:**
  ```bash
  cat ~/.ros/chess_calibration.yaml
  ```

- **Delete calibration** (forces recalibration on next start):
  ```bash
  rm ~/.ros/chess_calibration.yaml
  ```

---

## Feature 2: Position Offset Parameters

### Problem
The gripper position isn't always exactly where the calibration says it should be. Small mechanical inaccuracies mean you need to fine-tune positions.

### Solution
Added command-line parameters to adjust the grasp position!

### Usage

Basic syntax:
```bash
ros2 run planning chess_move_aruco --from <origin> --to <dest> \
  [--offset-x X] [--offset-y Y] [--offset-z Z]
```

### Parameters

| Parameter | Description | Default | Units |
|-----------|-------------|---------|-------|
| `--offset-x` | Horizontal X offset added to origin square | 0.0 | meters |
| `--offset-y` | Horizontal Y offset added to origin square | 0.0 | meters |
| `--offset-z` | Z-height for grasping piece (above board) | 0.22 | meters |

### Examples

**1. Basic move (no offsets):**
```bash
ros2 run planning chess_move_aruco --from e2 --to e4
```

**2. Gripper consistently misses to the right by 1cm:**
```bash
ros2 run planning chess_move_aruco --from e2 --to e4 --offset-x -0.01
```

**3. Gripper too high, piece not grasped:**
```bash
ros2 run planning chess_move_aruco --from e2 --to e4 --offset-z 0.20
```
(Lowers grasp height by 2cm)

**4. Gripper too low, hits board:**
```bash
ros2 run planning chess_move_aruco --from e2 --to e4 --offset-z 0.25
```
(Raises grasp height by 3cm)

**5. Multiple offsets combined:**
```bash
ros2 run planning chess_move_aruco --from e2 --to e4 \
  --offset-x 0.01 \
  --offset-y -0.02 \
  --offset-z 0.25
```

### How Offsets Work

```
Origin Square Position (from calibration):
  from_x, from_y, from_z

With offsets:
  actual_x = from_x + offset_x
  actual_y = from_y + offset_y
  z_grasp  = from_z + offset_z

Destination Square:
  No offsets applied (uses calibrated position exactly)
```

### Output

When using offsets, the node will log the adjusted positions:

```
[chess_move_aruco]: === Chess Move (ArUco Calibrated) ===
[chess_move_aruco]: Moving piece: e2 -> e4
[chess_move_aruco]: Position offsets: x=+0.010, y=-0.020, z_grasp=+0.250
[chess_move_aruco]: Origin position (with offsets): x=0.460, y=0.300, z_grasp=0.494
```

### Finding the Right Offsets

1. **Start with defaults** (no offset parameters)
2. **Observe where the gripper actually goes**
3. **Adjust incrementally:**
   - If gripper is 1cm to the left → add `--offset-x 0.01`
   - If gripper is 1cm forward → add `--offset-y 0.01`
   - If gripper doesn't grasp → lower with `--offset-z 0.20`
   - If gripper hits board → raise with `--offset-z 0.25`

4. **Test and iterate** until grasp is reliable

### Typical Offset Values

- **X/Y offsets:** Usually ±0.01 to ±0.03 meters (±1-3cm)
- **Z offset:** Usually 0.18 to 0.26 meters
  - 0.18m = very low (almost touching board)
  - 0.22m = default (standard piece height)
  - 0.26m = higher (tall pieces or safety margin)

---

## Benefits

### Persistent Calibration
✅ **Save time** - No recalibration needed after restart
✅ **Consistency** - Same calibration data across sessions
✅ **Convenience** - Board ready to use immediately

### Position Offsets
✅ **Fine-tuning** - Compensate for mechanical inaccuracies
✅ **Flexibility** - Adjust per-move if needed
✅ **Testing** - Easy to experiment with different heights
✅ **Piece variety** - Adjust z-offset for tall/short pieces

---

## Complete Workflow Example

### Initial Setup (Once)

```bash
# 1. Start system
ros2 launch planning chess_calibration.launch.py

# 2. Calibrate board (first time only)
ros2 service call /calibrate_chess_board std_srvs/srv/Trigger
```

Calibration saved to `~/.ros/chess_calibration.yaml`

### Daily Usage (No Recalibration Needed!)

```bash
# 1. Start system - calibration loads automatically
ros2 launch planning chess_calibration.launch.py

# Output:
# [chess_board_calibrator]: ✓ Loaded previous calibration from file

# 2. Play chess immediately
ros2 run planning chess_move_aruco --from e2 --to e4

# 3. If grip is off, adjust with offsets
ros2 run planning chess_move_aruco --from g1 --to f3 --offset-z 0.25
```

### If Board is Moved

```bash
# Recalibrate (overwrites saved file)
ros2 service call /calibrate_chess_board std_srvs/srv/Trigger
```

---

## Implementation Details

### Files Modified

1. **[chess_coords_aruco.py](final_project/src/planning/planning/chess_coords_aruco.py)**
   - Added `save_calibration()` method
   - Added `load_calibration()` method
   - Auto-loads on startup
   - Saves after each calibration

2. **[chess_move_aruco.py](final_project/src/planning/planning/chess_move_aruco.py)**
   - Added `offset_x`, `offset_y`, `offset_z` parameters to `__init__()`
   - Modified `build_job_queue()` to apply offsets
   - Updated `main()` to parse offset arguments
   - Added helpful examples in `--help`

### Dependencies

- **PyYAML** - For saving/loading calibration file
  ```bash
  pip install pyyaml
  ```

  (Usually already installed with ROS2)

---

## Help and Troubleshooting

### View command help
```bash
ros2 run planning chess_move_aruco --help
```

### Check if calibration file exists
```bash
ls -lh ~/.ros/chess_calibration.yaml
```

### View calibration data
```bash
cat ~/.ros/chess_calibration.yaml
```

### Force recalibration
```bash
# Option 1: Delete file and restart
rm ~/.ros/chess_calibration.yaml
ros2 launch planning chess_calibration.launch.py

# Option 2: Call calibration service (overwrites file)
ros2 service call /calibrate_chess_board std_srvs/srv/Trigger
```

### Reset to defaults (no offsets)
```bash
ros2 run planning chess_move_aruco --from e2 --to e4
# Equivalent to: --offset-x 0.0 --offset-y 0.0 --offset-z 0.22
```

---

## Summary

**Before:**
- Had to recalibrate every time
- No way to fine-tune grip positions
- Mechanical inaccuracies caused failures

**Now:**
- Calibrate once, use forever ✓
- Fine-tune positions with command-line parameters ✓
- Compensate for mechanical issues easily ✓
- Much more reliable and convenient! ✓
