# Chess Game Files

This directory contains example chess games that can be replayed by the robot.

## Available Games

### 1. Ladder Checkmate (`ladder_checkmate.txt`)

**Description:** Classic two-rook checkmate pattern

**Pieces needed:**
- White: King, 2 Rooks
- Black: King

**Total moves:** 7 (4 White moves, 3 Black moves, checkmate on move 4 White)

**Starting position:**
- White King: b4
- White Rooks: g4, a4
- Black King: e5

**Pattern:** The two rooks work together to push the enemy king to the edge of the board, delivering checkmate.

**Command:**
```bash
ros2 run planning chess_game_replay --game-file games/ladder_checkmate.txt
```

---

### 2. Bishop and Knight Checkmate (`bishop_knight_checkmate.txt`)

**Description:** One of the most difficult basic endgame patterns. Forces the king from a1 corner to h1 corner for checkmate.

**Source:** Chess.com - https://www.chess.com/terms/bishop-knight-checkmate

**Pieces needed:**
- White: King, Bishop, Knight
- Black: King

**Total moves:** 40 (20 moves per side)

**Starting position (FEN):** `8/8/8/8/1N6/1BK5/8/k7 w - - 0 1`
- White King: c3
- White Bishop: b3
- White Knight: b4
- Black King: a1

**Pattern:**
- Knight leads in a V-shape pattern
- Bishop controls light squares
- King follows and restricts escape
- Forces king from a1 to h1 corner where checkmate is delivered

**Command:**
```bash
ros2 run planning chess_game_replay --game-file games/bishop_knight_checkmate.txt
```

**With slower pace (recommended for this complex pattern):**
```bash
ros2 run planning chess_game_replay --game-file games/bishop_knight_checkmate.txt --delay 5.0
```

---

## Usage

### Basic Replay

```bash
ros2 run planning chess_game_replay --game-file games/<filename>
```

### With Options

```bash
ros2 run planning chess_game_replay \
  --game-file games/<filename> \
  --offset-z 0.25 \
  --delay 5.0
```

### Parameters

- `--game-file`: Path to game file (required)
- `--offset-x`: X-axis offset in meters (default: 0.0)
- `--offset-y`: Y-axis offset in meters (default: 0.0)
- `--offset-z`: Z-height for grasping in meters (default: 0.22)
- `--delay`: Seconds between moves (default: 3.0)

---

## Creating Your Own Games

### File Format

```
# Comments start with #
# Format: from_square-to_square

e2-e4  # Move pawn from e2 to e4
e7-e5  # Move pawn from e7 to e5
```

### Example

Create a new file `my_game.txt`:

```bash
cat > games/my_game.txt << 'EOF'
# My Custom Game
e2-e4
e7-e5
g1-f3
b8-c6
EOF
```

Then play it:

```bash
ros2 run planning chess_game_replay --game-file games/my_game.txt
```

---

## Tips for Setting Up Pieces

1. **Use the correct starting position** - Each game file lists the required setup
2. **Place pieces precisely** - Align centers with square centers
3. **Test single moves first** - Before full replay, test critical moves
4. **Adjust offsets if needed** - Fine-tune with `--offset-z` parameter

---

## Difficulty Levels

### Beginner
- **Ladder Checkmate**: Simple, repetitive pattern (7 moves)

### Advanced
- **Bishop and Knight Checkmate**: Complex coordination (40 moves)

---

## Quick Reference

| Game | Moves | Pieces | Difficulty |
|------|-------|--------|------------|
| Ladder Checkmate | 7 | K+2R vs K | ⭐ Beginner |
| Bishop Knight Mate | 40 | K+B+N vs K | ⭐⭐⭐⭐ Advanced |

---

## Adding More Games

Want to add famous games or patterns? Create a new `.txt` file in this directory following the format:

```
# Game Name
# Description

# Move 1
from_square-to_square
from_square-to_square

# Move 2
from_square-to_square
...
```

Then replay with:
```bash
ros2 run planning chess_game_replay --game-file games/your_game.txt
```
