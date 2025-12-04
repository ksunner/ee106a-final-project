# Chess Board Setup Guide

## ArUco Marker Placement and Orientation

### Marker Position
Place the ArUco marker at the **exact center of the chess board**, which is the intersection point where the four center squares meet (d4, d5, e4, e5).

```
   a   b   c   d   e   f   g   h
8  ░░░ ▓▓▓ ░░░ ▓▓▓ ░░░ ▓▓▓ ░░░ ▓▓▓
7  ▓▓▓ ░░░ ▓▓▓ ░░░ ▓▓▓ ░░░ ▓▓▓ ░░░
6  ░░░ ▓▓▓ ░░░ ▓▓▓ ░░░ ▓▓▓ ░░░ ▓▓▓
5  ▓▓▓ ░░░ ▓▓▓ ░░░ ▓▓▓ ░░░ ▓▓▓ ░░░
4  ░░░ ▓▓▓ ░░░ ▓▓▓ ░░░ ▓▓▓ ░░░ ▓▓▓
3  ▓▓▓ ░░░ ▓▓▓ ░░░ ▓▓▓ ░░░ ▓▓▓ ░░░
2  ░░░ ▓▓▓ ░░░ ▓▓▓ ░░░ ▓▓▓ ░░░ ▓▓▓
1  ▓▓▓ ░░░ ▓▓▓ ░░░ ▓▓▓ ░░░ ▓▓▓ ░░░
   a   b   c   d   e   f   g   h

              ┌─────┬─────┐
              │  d5 │ e5  │
       CENTER ├─────┼─────┤ ← ArUco marker HERE
       POINT  │  d4 │ e4  │
              └─────┴─────┘
```

### Coordinate System Mapping

Based on your `chess_coords.py` implementation:

```
X-axis (dx): Increases from rank 1 → rank 8
Y-axis (dy): Increases from file a → file h
```

The transformation matrix in your `static_tf_transform.py` is:
```python
G_ar_base = [
    [-1,  0,  0,  0.0  ],
    [ 0,  0,  1,  0.16 ],
    [ 0,  1,  0, -0.13 ],
    [ 0,  0,  0,  1.0  ]
]
```

This means:
- **ArUco X-axis** → **-1 × Robot X-axis**
- **ArUco Y-axis** → **Robot Z-axis**
- **ArUco Z-axis** → **Robot Y-axis**

### How to Orient the ArUco Marker

#### ArUco Marker Coordinate Convention
ArUco markers have a built-in coordinate system:
- **+X axis**: Points to the RIGHT edge when looking at the marker
- **+Y axis**: Points to the TOP edge when looking at the marker
- **+Z axis**: Points OUT of the marker (towards the camera)
- **Origin**: At the center of the marker

#### Recommended Orientation

To ensure the chess coordinates work correctly, orient your ArUco marker so that:

```
                  RANK 8 (Black's back rank)
                           ↑
                           │ +dx direction
                           │
        FILE a ←───────────┼───────────→ FILE h
        (queenside)        │            (kingside)
                      [ARUCO]
                      MARKER
                           │
                           ↓ -dx direction
                  RANK 1 (White's back rank)
```

**Specific Orientation Rules:**

1. **ArUco +X axis should point towards FILE A (left side)**
   - When moving from e4 to a4, you're moving in the -dy (negative Y offset) direction

2. **ArUco +Y axis should point towards RANK 1 (white's side)**
   - When moving from e4 to e1, you're moving in the -dx (negative X offset) direction

3. **ArUco +Z axis points UP** (towards the camera above the board)

### Visual Marker Orientation

```
     ┌──────────────────────┐
     │  ┏━━━━━━━━━━━━━━┓   │  ← Top edge
  Y+ │  ┃              ┃   │
  ↑  │  ┃   ARUCO      ┃   │
  │  │  ┃   MARKER     ┃   │
  │  │  ┃    ID: 8     ┃   │
  │  │  ┃              ┃   │
  └──┗━━━━━━━━━━━━━━┛───┘
     └───────────────→ X+
         Right edge

This orientation should have:
- Top edge (Y+) pointing towards RANK 1
- Right edge (X+) pointing towards FILE a
```

### Testing the Orientation

After placing the ArUco marker, test with simple moves to verify:

```bash
# Move from center to the left (towards file a)
ros2 run planning chess_move --from e4 --to a4

# Move from center to the bottom (towards rank 1)
ros2 run planning chess_move --from e4 --to e1

# Move from center to the right (towards file h)
ros2 run planning chess_move --from e4 --to h4

# Move from center to the top (towards rank 8)
ros2 run planning chess_move --from e4 --to e8
```

### Offset Examples from Center

Here are the calculated offsets for reference:

| Square | dx (m)    | dy (m)    | Direction from Center |
|--------|-----------|-----------|----------------------|
| a1     | -0.1925   | -0.1925   | Bottom-Left          |
| a8     | +0.2475   | -0.1925   | Top-Left             |
| h1     | -0.1925   | +0.2475   | Bottom-Right         |
| h8     | +0.2475   | +0.2475   | Top-Right            |
| e4     | -0.0275   | +0.0275   | Center-Right-Bottom  |
| d5     | +0.0275   | -0.0275   | Center-Left-Top      |

### Common Issues

1. **Moves go in opposite direction**: Rotate the ArUco marker 180°
2. **Moves go perpendicular to expected**: Rotate the ArUco marker 90°
3. **Files and ranks are swapped**: Rotate the ArUco marker 90° or 270°

### Physical Setup Tips

1. **Secure the marker**: Tape it down flat at the board center
2. **Lighting**: Ensure good, even lighting for ArUco detection
3. **Camera height**: Position camera high enough to see the entire board
4. **Marker size**: Ensure your ArUco marker is approximately 5cm × 5cm (matching your marker_size parameter)
