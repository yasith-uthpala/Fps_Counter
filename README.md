# 🎮 Simple FPS Counter & Game Overlay

A lightweight, ban-safe, high-precision FPS (Frames Per Second) counter suite for PC gaming and game development on Windows.

---

## 🌟 Key Features

- **100% Anti-Cheat Safe**: Zero DLL injection or game file hooking. Works using native Windows compositor timing and high-precision event calculation, making it safe for multiplayer games (VAC, BattlEye, EasyAntiCheat).
- **Transparent Click-Through Overlay**: Renders as an always-on-top HUD with `WS_EX_TRANSPARENT`. Mouse clicks pass directly through into the game, so your aiming and gameplay are never interrupted.
- **Micro-Stutter Detection (1% Lows)**: Computes 1% and 0.1% low frame rates — the gold standard for measuring game smoothness and stutter.
- **Global Hotkeys**:
  - `F11`: Hide / Show the overlay anytime.
  - `F10`: Move overlay across screen corners (Top-Left, Top-Right, Bottom-Right, Bottom-Left).
  - `F9`: Toggle between **Compact Mode** (`[ 144 FPS | 6.9 ms ]`) and **Detailed Mode** (FPS, Frame Time, 1% Lows, Active Game Name, CPU/RAM load).
- **Multi-Flavor Support**:
  - **Native Windows Executable (`FpsOverlay.exe`)**: A single 10 KB standalone `.exe` with zero installation required.
  - **Python Overlay (`fps_overlay.py`)**: Python transparent overlay with process detection and live telemetry.
  - **Modular In-Engine Component (`fps_core.py`)**: Drop into any game loop you're coding.
  - **Interactive Benchmark Game (`demo_game.py`)**: Playable arcade demo with built-in frame throttlers and lag spike simulators.

---

## 🚀 Quick Start

### 1. Run the Native Standalone Overlay (Recommended for Gamers)
Simply double-click:
```cmd
FpsOverlay.exe
```
Or rebuild it anytime using `build.bat`.

### 2. Run the Python Overlay
```powershell
python fps_overlay.py
```

### 3. Play the Interactive Demo & Test Game
Launch the built-in arcade test game:
```powershell
python demo_game.py
```
- Move your mouse to fly your ship and collect glowing energy crystals.
- Click **30 FPS**, **60 FPS**, **120 FPS**, **144 FPS**, or **Uncapped** to throttle frame rate and see the counter respond.
- Click **"Inject 100ms Lag Spike"** to simulate micro-stutters and see the 1% Lows and frame-time graph react in real time!

---

## 🕹️ In-Game Controls & Hotkeys

| Hotkey | Action | Description |
| :--- | :--- | :--- |
| **`F11`** | **Toggle Visibility** | Hide or show the overlay during gameplay |
| **`F10`** | **Cycle Position** | Top-Left ➔ Top-Right ➔ Bottom-Right ➔ Bottom-Left |
| **`F9`** | **Toggle View Mode** | Switch between Compact Mini-HUD and Detailed Telemetry |

---

## 💻 Developer Integration: Using `FpsCounter` in Your Own Game

If you are developing your own game (in Pygame, Ursina, Arcade, Raylib, or a custom game loop), you can integrate `fps_core.py` in just two lines of code:

```python
from fps_core import FpsCounter

# 1. Initialize counter
counter = FpsCounter(window_size=120)

# 2. Inside your main game loop:
while running:
    # ... your game update & render logic ...

    # Call tick() once per frame:
    metrics = counter.tick()

    # Read real-time performance:
    print(f"FPS: {metrics.fps:.1f}")
    print(f"Frame Time: {metrics.frame_time_ms:.2f} ms")
    print(f"1% Low: {metrics.one_percent_low:.1f} FPS")
    print(f"Color: {metrics.color_hex}")  # Green / Yellow / Red
```

---

## 🧪 Running Automated Tests

Run the unit test suite to verify math and smoothing algorithms:
```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 📁 Repository Structure

```
Fps_Counter/
│
├── FpsOverlay.exe         # Standalone compiled native Windows executable (~10 KB)
├── FpsOverlay.cs          # C# source code for native Windows Forms overlay
├── build.bat              # One-click build script to compile FpsOverlay.cs
│
├── fps_overlay.py         # Python transparent click-through desktop overlay
├── fps_core.py            # Core FPS, frame time, and 1% low math engine
├── demo_game.py           # Playable arcade test game with lag spike simulator
│
├── tests/
│   └── test_fps_core.py   # Unit test suite verifying calculation accuracy
│
└── README.md              # Documentation and guide
```

---

## 🎨 Color Coding Legend

- 🟢 **Emerald Green (`>= 60 FPS`)**: Smooth, high-performance gameplay.
- 🟡 **Amber Yellow (`30 - 59 FPS`)**: Playable, but suboptimal or frame drops occurring.
- 🔴 **Crimson Red (`< 30 FPS`)**: Stuttering or laggy gameplay.
