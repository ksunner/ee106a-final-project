# Chess Game Replay Guide

Replay entire chess games automatically! The system will execute all moves in sequence, allowing you to watch a complete game play out on the physical board.

## Quick Start

```bash
# Build and source
cd ~/ros_workspaces/ee106a-final-project/final_project
colcon build --packages-select planning
source install/setup.bash

# Start system (loads saved calibration)
ros2 launch planning chess_calibration.launch.py

# Replay the ladder checkmate example
ros2 run planning chess_game_replay --game-file games/ladder_checkmate.txt
```

---

## Game File Format

Game files use a simple format with one move per line:

```
# Comments start with #
# Format: from_square-to_square

e2-e4  # Move pawn from e2 to e4
e7-e5  # Move pawn from e7 to e5
g1-f3  # Move knight from g1 to f3
```

### Supported Formats

1. **Simple notation** (recommended):
   ```
   e2-e4
   g1-f3
   b8-c6
   ```

2. **Space-separated**:
   ```
   e2 e4
   g1 f3
   ```

3. **No separator**:
   ```
   e2e4
   g1f3
   ```

---

## Example: Ladder Checkmate

The classic two-rook checkmate pattern is included as an example:

**File:** `games/ladder_checkmate.txt`

```
# Ladder Checkmate Example
# White delivers checkmate with two rooks

# Move 1
g4-g5  # White: Rook to g5
g5-g6  # Black: King to g6

# Move 2
a4-a6  # White: Rook to a6, check!
g6-f7  # Black: King to f7

# Move 3
g5-b7  # White: Rook to b7, check!
f7-e8  # Black: King forced to edge

# Move 4
a6-a8  # White: Rook to a8, checkmate!
```

---

## Command Reference

### Basic Usage

```bash
ros2 run planning chess_game_replay --game-file <path_to_file>
```

### With Options

```bash
ros2 run planning chess_game_replay \
  --game-file games/ladder_checkmate.txt \
  --offset-z 0.25 \
  --delay 5.0
```

### Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--game-file` | Path to game file (required) | - |
| `--offset-x` | X-axis offset in meters | 0.0 |
| `--offset-y` | Y-axis offset in meters | 0.0 |
| `--offset-z` | Z-height for grasping (meters) | 0.22 |
| `--delay` | Seconds to wait between moves | 3.0 |

---

## Creating Your Own Games

### 1. Create a game file

```bash
nano ~/my_game.txt
```

### 2. Add moves in simple notation

```
# My Custom Game
e2-e4
e7-e5
g1-f3
b8-c6
f1-c4
g8-f6
```

### 3. Play it!

```bash
ros2 run planning chess_game_replay --game-file ~/my_game.txt
```

---

## Complete Workflow

### 1. Setup (one time)

```bash
# Start system
ros2 launch planning chess_calibration.launch.py

# Calibrate board (if not already calibrated)
ros2 service call /calibrate_chess_board std_srvs/srv/Trigger
```

### 2. Place pieces at starting positions

For the ladder checkmate example:
- White King: b4
- White Rooks: g4, a4
- Black King: g5

### 3. Run game replay

```bash
ros2 run planning chess_game_replay --game-file games/ladder_checkmate.txt
```

### 4. Watch the game play out!

The robot will:
1. Execute move 1 (both sides)
2. Wait 3 seconds
3. Execute move 2
4. Continue until checkmate!

---

## Advanced Usage

### Custom Delay Between Moves

Adjust timing for dramatic effect or testing:

```bash
# Fast replay (1 second between moves)
ros2 run planning chess_game_replay --game-file my_game.txt --delay 1.0

# Slow replay (10 seconds between moves)
ros2 run planning chess_game_replay --game-file my_game.txt --delay 10.0
```

### Position Offsets

If gripper is slightly off:

```bash
ros2 run planning chess_game_replay \
  --game-file games/ladder_checkmate.txt \
  --offset-x 0.01 \
  --offset-z 0.25
```

### Test Individual Moves First

Before replaying a full game, test individual moves:

```bash
# Test first move
ros2 run planning chess_move_aruco --from e2 --to e4

# If it works, replay the full game
ros2 run planning chess_game_replay --game-file my_game.txt
```

---

## Example Games

### Ladder Checkmate (Included)

**File:** `games/ladder_checkmate.txt`

**Pieces needed:**
- 3 pieces total
- White: 2 Rooks + King
- Black: King

**Description:** Classic endgame checkmate pattern with two rooks

**Command:**
```bash
ros2 run planning chess_game_replay --game-file games/ladder_checkmate.txt
```

### Create Your Own!

Common patterns to try:
- **Scholar's Mate** (4 moves)
- **Back Rank Mate** (simple endgame)
- **Queen and King vs King** (basic checkmate)
- **Famous games** (Morphy, Fischer, etc.)

---

## Game File Examples

### Scholar's Mate

```bash
# Create file
cat > games/scholars_mate.txt << 'EOF'
# Scholar's Mate - Quick checkmate in 4 moves

e2-e4
e7-e5
f1-c4
b8-c6
d1-h5
g8-f6
h5-f7  # Checkmate!
EOF

# Play it
ros2 run planning chess_game_replay --game-file games/scholars_mate.txt
```

### Back Rank Mate

```bash
# Create file
cat > games/back_rank_mate.txt << 'EOF'
# Back Rank Mate Example
# Setup: White Rook on a1, Black King on e8 (trapped by own pawns)

a1-a8  # Rook to a8, checkmate!
EOF

# Play it
ros2 run planning chess_game_replay --game-file games/back_rank_mate.txt
```

---

## Troubleshooting

### "No such file or directory"

Make sure the file path is correct:

```bash
# Use absolute path
ros2 run planning chess_game_replay --game-file /home/user/my_game.txt

# Or relative from workspace
ros2 run planning chess_game_replay --game-file games/my_game.txt
```

### "Waiting for squares"

The calibrator isn't publishing positions:

```bash
# Check if calibrator is running
ros2 node list | grep calibrator

# Check if positions are being published
ros2 topic list | grep chess_square

# Restart calibrator if needed
ros2 launch planning chess_calibration.launch.py
```

### "IK computation failed"

Position out of reach:

1. Check piece positions match your game file
2. Try adjusting z-offset: `--offset-z 0.25`
3. Test individual moves first

### Gripper misses pieces

Fine-tune with offsets:

```bash
ros2 run planning chess_game_replay \
  --game-file my_game.txt \
  --offset-x 0.01 \
  --offset-y -0.02 \
  --offset-z 0.25
```

---

## Tips

1. **Start with simple games** - Test with 2-3 moves before full games

2. **Set up pieces carefully** - Make sure pieces are exactly on their starting squares

3. **Use appropriate delay** - 3-5 seconds gives time to observe each move

4. **Test offsets once** - Find good offsets, then reuse them for all games

5. **Create a games folder** - Organize your game files:
   ```bash
   mkdir -p ~/chess_games
   mv my_game.txt ~/chess_games/
   ```

6. **Comment your files** - Add notes about setup and interesting moments

---

## Backwards Compatibility

The single-move command still works exactly as before:

```bash
# Single move
ros2 run planning chess_move_aruco --from e2 --to e4

# Single move with offsets
ros2 run planning chess_move_aruco --from e2 --to e4 --offset-z 0.25

# Game replay
ros2 run planning chess_game_replay --game-file games/my_game.txt
```

---

## Summary

✅ **Simple format** - Just list moves like `e2-e4`
✅ **Automatic execution** - Sit back and watch
✅ **Customizable** - Adjust timing and positions
✅ **Educational** - Learn famous games and patterns
✅ **Backwards compatible** - Single moves still work

**Get started:**
```bash
ros2 run planning chess_game_replay --game-file games/ladder_checkmate.txt
```

Enjoy watching chess come to life! ♟️
