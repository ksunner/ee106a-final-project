# ArUco Detection - Launch Files and Debugging

## Problem
ArUco markers not being detected even though they're visible in camera feed.

## Solution
Created proper launch files that integrate camera + ArUco detection + chess calibrator.

---

## New Launch Files Created

### 1. **chess_calibration.launch.py** (Recommended for calibration only)

Starts:
- USB camera
- ArUco detection node
- Chess board calibrator
- Static TF transforms

**Usage:**
```bash
ros2 launch planning chess_calibration.launch.py
```

**Then calibrate:**
```bash
ros2 service call /calibrate_chess_board std_srvs/srv/Trigger
```

### 2. **chess_system.launch.py** (Full system with MoveIt)

Starts everything above PLUS:
- MoveIt motion planning
- IK planner
- Robot control system

**Usage:**
```bash
ros2 launch planning chess_system.launch.py
```

---

## New Debug Tool Created

### **check_aruco_detection** - ArUco Detection Checker

This tool tells you exactly what's wrong with ArUco detection!

**Usage:**
```bash
ros2 run planning check_aruco_detection
```

**What it checks:**
- ✓ Is camera publishing images?
- ✓ Is camera info available?
- ✓ Is ArUco node running and publishing?
- ✓ Which markers are detected?
- ✓ Are TF transforms available?
- ✓ Specifically checks for chess markers (100-103)

**Example output:**
```
=== ArUco Detection Checker ===
Waiting for topics...
✓ Camera image received: 1280x720, encoding=rgb8
✓ Camera info received: frame_id=camera1
✓ ArUco markers topic is publishing
✓ NEW MARKERS DETECTED: [100, 101]
✓ TF transform found for marker 100: [0.450, 0.320, 0.244]
✓ TF transform found for marker 101: [0.450, -0.120, 0.245]

--- Status ---
Camera image:     ✓ OK
Camera info:      ✓ OK
ArUco topic:      ✓ OK
Detected markers: [100, 101]
Chess markers detected: [100, 101]
Missing chess markers: [102, 103]
```

---

## Quick Start (Updated)

### Step 1: Build
```bash
cd ~/ros_workspaces/ee106a-final-project/final_project
colcon build --packages-select planning
source install/setup.bash
```

### Step 2: Launch System
```bash
# Option A: Calibration only (lighter)
ros2 launch planning chess_calibration.launch.py

# Option B: Full system with robot
ros2 launch planning chess_system.launch.py
```

### Step 3: Check Detection
In another terminal:
```bash
ros2 run planning check_aruco_detection
```

This will tell you if markers are being detected!

### Step 4: Calibrate
Once all 4 markers are detected:
```bash
ros2 service call /calibrate_chess_board std_srvs/srv/Trigger
```

### Step 5: Move Pieces
```bash
ros2 run planning chess_move_aruco --from e2 --to e4
```

---

## Common Issues and Fixes

### Issue: ArUco node receives images but doesn't detect markers

**Possible causes:**
1. **Wrong marker dictionary** - Must be DICT_5X5_250
2. **Wrong marker size** - Should be 0.05 (50mm)
3. **Poor lighting** - Avoid glare, shadows
4. **Wrinkled/damaged markers** - Print new ones
5. **Markers too far** - Move camera closer

**Check ArUco parameters:**
```bash
ros2 param list /aruco_node
ros2 param get /aruco_node marker_size
ros2 param get /aruco_node aruco_dictionary_id
```

**Should see:**
```
marker_size: 0.05
aruco_dictionary_id: DICT_5X5_250
```

### Issue: Camera not publishing

**Check:**
```bash
# Is camera device available?
ls /dev/video*

# Is camera node running?
ros2 node list | grep camera

# Check camera topics
ros2 topic list | grep camera
ros2 topic hz /camera1/image_raw
```

**Fix:**
```bash
# Restart camera
ros2 launch usb_cam camera.launch.py
```

### Issue: TF transforms not available

**Check:**
```bash
# View TF tree
ros2 run tf2_tools view_frames
# Opens a PDF showing all transforms

# Check specific transform
ros2 run tf2_ros tf2_echo base_link aruco_marker_100
```

**Fix:**
Make sure `static_tf_transform` node is running (included in launch files).

---

## Architecture

```
┌─────────────────────────────────┐
│       USB Camera Node           │
│   Publishes: /camera1/image_raw │
└──────────────┬──────────────────┘
               │ Images
               ▼
┌─────────────────────────────────┐
│      ArUco Detection Node       │
│   Subscribes: /camera1/*        │
│   Publishes: /aruco_markers     │
│   Publishes TF: aruco_marker_*  │
└──────────────┬──────────────────┘
               │ TF Transforms
               ▼
┌─────────────────────────────────┐
│   Chess Board Calibrator        │
│   Reads TF for markers 100-103  │
│   Computes 64 square positions  │
│   Publishes: /chess_square/*    │
└──────────────┬──────────────────┘
               │ Square Positions
               ▼
┌─────────────────────────────────┐
│      Chess Move Node            │
│   Subscribes: /chess_square/*   │
│   Plans and executes movements  │
└─────────────────────────────────┘
```

---

## Files Created/Modified

### New Launch Files
- `src/planning/launch/chess_calibration.launch.py` - Calibration system
- `src/planning/launch/chess_system.launch.py` - Full robot system

### New Tools
- `src/planning/planning/check_aruco_detection.py` - Debug tool for ArUco detection

### Updated Files
- `src/planning/setup.py` - Added `check_aruco_detection` entry point
- `QUICK_START.md` - Updated with new launch files and debugging steps

---

## Summary

**Before:** Had to manually start camera, ArUco node, calibrator separately. ArUco detection issues were hard to debug.

**Now:**
1. Single launch file starts everything: `ros2 launch planning chess_calibration.launch.py`
2. Debug tool shows exactly what's wrong: `ros2 run planning check_aruco_detection`
3. Proper integration ensures topics and parameters are configured correctly

**Next Steps:**
1. Build: `colcon build --packages-select planning`
2. Launch: `ros2 launch planning chess_calibration.launch.py`
3. Debug (if needed): `ros2 run planning check_aruco_detection`
4. Calibrate: `ros2 service call /calibrate_chess_board std_srvs/srv/Trigger`
5. Play chess! `ros2 run planning chess_move_aruco --from e2 --to e4`
