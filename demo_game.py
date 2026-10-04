"""
demo_game.py - Interactive Playable Arcade Game with Built-In FPS Counter & Lag Simulator

Demonstrates how to integrate FpsCounter directly into a game loop,
with live frame-rate throttling, lag spike injection, and real-time frame time graphing.
"""

from __future__ import annotations
import collections
import math
import random
import sys
import time
import tkinter as tk
from typing import List, Tuple

from fps_core import FpsCounter


class Particle:
    """Explosion / trail particle."""
    def __init__(self, x: float, y: float, vx: float, vy: float, color: str, life: int = 25):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.life = life
        self.max_life = life

    def update(self) -> bool:
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.95
        self.vy *= 0.95
        self.life -= 1
        return self.life > 0


class Crystal:
    """Collectible energy crystal."""
    def __init__(self, width: int, height: int):
        self.x = random.uniform(50, width - 50)
        self.y = random.uniform(50, height - 120)
        self.radius = random.uniform(10, 16)
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(40, 120)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.color = random.choice(["#00e5ff", "#ff007f", "#ffe600", "#76ff03", "#d500f9"])
        self.pulsar = random.uniform(0, 2 * math.pi)

    def update(self, dt: float, width: int, height: int):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.pulsar += dt * 4

        # Bounce off walls
        if self.x - self.radius < 10:
            self.x = 10 + self.radius
            self.vx = abs(self.vx)
        elif self.x + self.radius > width - 10:
            self.x = width - 10 - self.radius
            self.vx = -abs(self.vx)

        if self.y - self.radius < 10:
            self.y = 10 + self.radius
            self.vy = abs(self.vy)
        elif self.y + self.radius > height - 80:
            self.y = height - 80 - self.radius
            self.vy = -abs(self.vy)


class DemoGame:
    """Arcade Game Demo showcasing in-game FPS counter and performance metrics."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Arcade Demo - FPS Counter Showcase")
        self.width = 900
        self.height = 640
        self.root.geometry(f"{self.width}x{self.height}")
        self.root.minsize(800, 560)
        self.root.configure(bg="#0d1117")

        # Game State
        self.player_x = self.width / 2
        self.player_y = self.height / 2
        self.player_target_x = self.player_x
        self.player_target_y = self.player_y
        self.player_radius = 16
        self.score = 0
        self.combo = 0

        # Performance & FPS Setup
        self.fps_counter = FpsCounter(window_size=120)
        self.target_fps = 60
        self.frame_delay_target = 1.0 / self.target_fps
        self.artificial_lag_ms = 0.0
        self.frame_time_history: collections.deque[float] = collections.deque(maxlen=70)

        # Entities
        self.crystals: List[Crystal] = [Crystal(self.width, self.height) for _ in range(12)]
        self.particles: List[Particle] = []

        # UI & Canvas
        self._build_ui()
        self._bind_events()

        # Timing loop variables
        self.last_loop_time = time.perf_counter()
        self.is_running = True

        # Start game loop
        self.root.after(10, self._game_loop)

    def _build_ui(self):
        # Header / Control Toolbar at bottom
        control_frame = tk.Frame(self.root, bg="#161b22", height=60)
        control_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=0, pady=0)

        title_lbl = tk.Label(
            control_frame,
            text="🎮 FPS Benchmark Controls:",
            fg="#8b949e",
            bg="#161b22",
            font=("Segoe UI", 10, "bold"),
        )
        title_lbl.pack(side=tk.LEFT, padx=(16, 8), pady=12)

        # FPS preset buttons
        self.fps_buttons = {}
        for fps_val in [30, 60, 120, 144, 0]:
            label_text = f"{fps_val} FPS" if fps_val > 0 else "Uncapped"
            btn = tk.Button(
                control_frame,
                text=label_text,
                font=("Segoe UI", 9, "bold"),
                bg="#238636" if fps_val == 60 else "#21262d",
                fg="#ffffff",
                activebackground="#2ea043",
                activeforeground="#ffffff",
                relief=tk.FLAT,
                padx=10,
                pady=4,
                cursor="hand2",
                command=lambda val=fps_val: self.set_target_fps(val),
            )
            btn.pack(side=tk.LEFT, padx=4, pady=12)
            self.fps_buttons[fps_val] = btn

        # Lag Spike Trigger button
        lag_btn = tk.Button(
            control_frame,
            text="💥 Inject 100ms Lag Spike",
            font=("Segoe UI", 9, "bold"),
            bg="#da3633",
            fg="#ffffff",
            activebackground="#f85149",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=4,
            cursor="hand2",
            command=self.inject_lag,
        )
        lag_btn.pack(side=tk.RIGHT, padx=(8, 16), pady=12)

        # Main Game Canvas
        self.canvas = tk.Canvas(
            self.root,
            bg="#090d13",
            highlightthickness=0,
        )
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def _bind_events(self):
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.root.bind("<Configure>", self._on_resize)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_mouse_move(self, event):
        self.player_target_x = event.x
        self.player_target_y = event.y

    def _on_resize(self, event):
        if event.widget == self.root:
            self.width = max(300, event.width)
            self.height = max(300, event.height)

    def _on_close(self):
        self.is_running = False
        self.root.destroy()

    def set_target_fps(self, fps: int):
        self.target_fps = fps
        self.frame_delay_target = (1.0 / fps) if fps > 0 else 0.0
        for val, btn in self.fps_buttons.items():
            if val == fps:
                btn.configure(bg="#238636")
            else:
                btn.configure(bg="#21262d")

    def inject_lag(self):
        """Simulates a heavy frame drop or CPU freeze for 100ms."""
        self.artificial_lag_ms = 100.0

    def _spawn_explosion(self, x: float, y: float, color: str):
        for _ in range(16):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(50, 220)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            self.particles.append(Particle(x, y, vx, vy, color, life=random.randint(18, 30)))

    def _game_loop(self):
        if not self.is_running:
            return

        frame_start = time.perf_counter()

        # Handle artificial lag spike if triggered
        if self.artificial_lag_ms > 0:
            time.sleep(self.artificial_lag_ms / 1000.0)
            self.artificial_lag_ms = 0.0

        # Calculate time delta since last frame
        now = time.perf_counter()
        dt = now - self.last_loop_time
        self.last_loop_time = now

        # Update FPS counter
        metrics = self.fps_counter.tick(custom_timestamp=now)
        self.frame_time_history.append(metrics.frame_time_ms)

        # Update Game Logic
        self._update_game(dt)

        # Render Frame
        self._render(metrics)

        # Frame Rate Pacing
        elapsed = time.perf_counter() - frame_start
        if self.frame_delay_target > 0 and elapsed < self.frame_delay_target:
            sleep_time = self.frame_delay_target - elapsed
            ms = max(1, int(sleep_time * 1000.0))
            self.root.after(ms, self._game_loop)
        else:
            self.root.after(1, self._game_loop)

    def _update_game(self, dt: float):
        # Smooth player movement towards mouse
        lerp = min(1.0, dt * 14.0)
        self.player_x += (self.player_target_x - self.player_x) * lerp
        self.player_y += (self.player_target_y - self.player_y) * lerp

        # Update particles
        self.particles = [p for p in self.particles if p.update()]

        # Update crystals and check collisions
        for crystal in self.crystals:
            crystal.update(dt, self.width, self.height)
            dx = self.player_x - crystal.x
            dy = self.player_y - crystal.y
            dist = math.hypot(dx, dy)
            if dist < (self.player_radius + crystal.radius):
                # Collect crystal!
                self.score += 100 + self.combo * 20
                self.combo += 1
                self._spawn_explosion(crystal.x, crystal.y, crystal.color)
                # Respawn crystal
                crystal.x = random.uniform(50, self.width - 50)
                crystal.y = random.uniform(50, self.height - 120)

    def _render(self, metrics):
        self.canvas.delete("all")

        # Subtle grid background
        grid_step = 60
        for x in range(0, self.width, grid_step):
            self.canvas.create_line(x, 0, x, self.height, fill="#121820", width=1)
        for y in range(0, self.height, grid_step):
            self.canvas.create_line(0, y, self.width, y, fill="#121820", width=1)

        # Draw Collectible Crystals
        for crystal in self.crystals:
            pulse = math.sin(crystal.pulsar) * 2.5
            r = max(4, crystal.radius + pulse)
            # Outer glow
            self.canvas.create_oval(
                crystal.x - r - 4, crystal.y - r - 4,
                crystal.x + r + 4, crystal.y + r + 4,
                outline=crystal.color, width=1
            )
            # Inner core
            self.canvas.create_oval(
                crystal.x - r, crystal.y - r,
                crystal.x + r, crystal.y + r,
                fill=crystal.color, outline="#ffffff", width=1
            )

        # Draw Particles
        for p in self.particles:
            size = (p.life / p.max_life) * 3.5
            self.canvas.create_oval(
                p.x - size, p.y - size, p.x + size, p.y + size,
                fill=p.color, outline=""
            )

        # Draw Player Ship
        px, py = self.player_x, self.player_y
        self.canvas.create_oval(
            px - self.player_radius, py - self.player_radius,
            px + self.player_radius, py + self.player_radius,
            fill="#3b82f6", outline="#60a5fa", width=2
        )
        self.canvas.create_oval(
            px - 5, py - 5, px + 5, py + 5,
            fill="#ffffff", outline=""
        )

        # Score & Instructions Display
        self.canvas.create_text(
            self.width / 2, 24,
            text=f"SCORE: {self.score}   COMBO: x{self.combo}",
            fill="#c9d1d9",
            font=("Segoe UI", 12, "bold")
        )
        self.canvas.create_text(
            self.width / 2, 48,
            text="Move your mouse to collect crystals and test FPS stability",
            fill="#8b949e",
            font=("Segoe UI", 9)
        )

        # ==========================================
        # RENDER IN-GAME FPS HUD OVERLAY (TOP-LEFT)
        # ==========================================
        self._render_fps_hud(metrics, 16, 16)

    def _render_fps_hud(self, metrics, x: int, y: int):
        hud_w = 210
        hud_h = 100

        # Translucent HUD Background Badge
        self.canvas.create_rectangle(
            x, y, x + hud_w, y + hud_h,
            fill="#0b0f14", outline="#30363d", width=1
        )
        # Accent left border indicator
        self.canvas.create_rectangle(
            x, y, x + 4, y + hud_h,
            fill=metrics.color_hex, outline=""
        )

        # Main Large FPS Value
        fps_text = f"{int(round(metrics.fps))}"
        self.canvas.create_text(
            x + 14, y + 26,
            anchor="w",
            text=fps_text,
            fill=metrics.color_hex,
            font=("Segoe UI", 26, "bold")
        )
        self.canvas.create_text(
            x + 14 + len(fps_text) * 19, y + 28,
            anchor="w",
            text="FPS",
            fill="#8b949e",
            font=("Segoe UI", 11, "bold")
        )

        # Frame time in ms
        ft_text = f"{metrics.frame_time_ms:.1f} ms"
        self.canvas.create_text(
            x + hud_w - 12, y + 26,
            anchor="e",
            text=ft_text,
            fill="#c9d1d9",
            font=("Segoe UI", 11, "bold")
        )

        # 1% Low FPS metric
        one_pct_text = f"1% Low: {int(round(metrics.one_percent_low))} FPS"
        self.canvas.create_text(
            x + 14, y + 54,
            anchor="w",
            text=one_pct_text,
            fill="#8b949e",
            font=("Segoe UI", 9)
        )

        # Mini Sparkline Frame Time Graph (bottom of badge)
        gx = x + 14
        gy = y + 92
        gw = hud_w - 28
        gh = 26
        self.canvas.create_line(gx, gy, gx + gw, gy, fill="#21262d", width=1)

        history_len = len(self.frame_time_history)
        if history_len > 1:
            step = gw / max(1, history_len - 1)
            points = []
            for i, ft in enumerate(self.frame_time_history):
                # Clamp visual scale: 0ms at gy, 33ms (30fps) or 50ms at gy - gh
                clamped_ft = min(50.0, max(0.0, ft))
                py = gy - (clamped_ft / 50.0) * gh
                points.extend([gx + i * step, py])

            if len(points) >= 4:
                self.canvas.create_line(points, fill=metrics.color_hex, width=1.5, smooth=True)


def main():
    root = tk.Tk()
    app = DemoGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
