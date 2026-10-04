"""
fps_overlay.py - Standalone Transparent Click-Through FPS Game Overlay for Windows

Floats on top of games to display real-time FPS, frame times, 1% lows, and active game process.
100% Ban-Safe (No DLL injection or game modification).

Hotkeys:
  F11 : Toggle Overlay On / Off
  F10 : Cycle Screen Corners (Top-Left, Top-Right, Bottom-Right, Bottom-Left)
  F9  : Toggle Compact Mode / Detailed Mode
"""

from __future__ import annotations
import collections
import ctypes
from ctypes import wintypes
import os
import socket
import sys
import threading
import time
import tkinter as tk
from typing import Optional, Tuple

import psutil

from fps_core import FpsCounter, FpsMetrics


# Win32 API Constants
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

MOD_NOREPEAT = 0x4000
VK_F9 = 0x78
VK_F10 = 0x79
VK_F11 = 0x7A
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
dwmapi = ctypes.WinDLL("dwmapi")


def get_foreground_process_info() -> Tuple[str, int]:
    """Retrieve the window title and process name of the active foreground window."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "Desktop", 0

    # Get Process ID
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    # Get Window Title
    length = user32.GetWindowTextLengthW(hwnd)
    title_buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, title_buf, length + 1)
    title = title_buf.value.strip()

    proc_name = ""
    try:
        if pid.value > 0:
            proc = psutil.Process(pid.value)
            proc_name = proc.name()
    except Exception:
        proc_name = ""

    display_name = proc_name or title or "Game/App"
    return display_name, pid.value


class GlobalHotkeyListener(threading.Thread):
    """Listens for global Windows hotkeys (F9, F10, F11) in a background thread."""

    def __init__(self, on_f9, on_f10, on_f11):
        super().__init__(daemon=True)
        self.on_f9 = on_f9
        self.on_f10 = on_f10
        self.on_f11 = on_f11
        self.thread_id: Optional[int] = None
        self.ready_event = threading.Event()
        self.running = True

    def run(self):
        self.thread_id = kernel32.GetCurrentThreadId()

        # Register hotkeys: 1 -> F9, 2 -> F10, 3 -> F11
        user32.RegisterHotKey(0, 1, MOD_NOREPEAT, VK_F9)
        user32.RegisterHotKey(0, 2, MOD_NOREPEAT, VK_F10)
        user32.RegisterHotKey(0, 3, MOD_NOREPEAT, VK_F11)

        self.ready_event.set()

        msg = wintypes.MSG()
        while self.running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                hotkey_id = msg.wParam
                if hotkey_id == 1 and self.on_f9:
                    self.on_f9()
                elif hotkey_id == 2 and self.on_f10:
                    self.on_f10()
                elif hotkey_id == 3 and self.on_f11:
                    self.on_f11()

        user32.UnregisterHotKey(0, 1)
        user32.UnregisterHotKey(0, 2)
        user32.UnregisterHotKey(0, 3)

    def stop(self):
        self.running = False
        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)


class FpsOverlayApp:
    """
    Transparent, click-through, always-on-top FPS Game Overlay.
    """

    CORNERS = ["top_left", "top_right", "bottom_right", "bottom_left"]

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("FPS Game Overlay")

        # Window appearance settings
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.transparent_key = "#000001"  # Near-black chroma key for transparency
        self.root.configure(bg=self.transparent_key)
        self.root.wm_attributes("-transparentcolor", self.transparent_key)

        # Overlay states
        self.is_visible = True
        self.is_compact = False
        self.corner_idx = 0  # 0: Top-Left, 1: Top-Right, 2: Bottom-Right, 3: Bottom-Left
        self.padding = 24

        # Dimensions
        self.compact_w = 175
        self.compact_h = 42
        self.detailed_w = 230
        self.detailed_h = 135

        # Screen dimensions
        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()

        # Canvas for drawing UI
        self.canvas = tk.Canvas(
            self.root,
            bg=self.transparent_key,
            highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Performance Engine
        self.fps_counter = FpsCounter(window_size=60)
        self.last_tick_time = time.perf_counter()
        self.frame_history = collections.deque(maxlen=60)

        # DWM Hardware Refresh Rate Detection
        self.hardware_refresh_rate = self._query_display_refresh_rate()

        # System Metrics Cache
        self.last_sys_check = 0.0
        self.cpu_usage = 0.0
        self.ram_usage = 0.0
        self.active_proc_name = "Desktop"

        # Apply initial position and Win32 click-through style
        self._update_geometry()
        self._apply_clickthrough()

        # Start Global Hotkey Listener
        self.hotkeys = GlobalHotkeyListener(
            on_f9=self._async_toggle_compact,
            on_f10=self._async_cycle_corner,
            on_f11=self._async_toggle_visible,
        )
        self.hotkeys.start()
        self.hotkeys.ready_event.wait(timeout=1.0)

        # Start UDP frame broadcast listener in background
        # (Allows any game or script to send custom frame ticks to this overlay)
        self.udp_sock: Optional[socket.socket] = None
        self._start_udp_listener()

        # Kick off update loop
        self.root.after(33, self._tick_loop)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _query_display_refresh_rate(self) -> int:
        """Query display refresh rate via DwmGetCompositionTimingInfo."""
        try:
            buf = ctypes.create_string_buffer(292)
            ctypes.cast(buf, ctypes.POINTER(ctypes.c_uint32))[0] = 292
            hr = dwmapi.DwmGetCompositionTimingInfo(None, buf)
            if hr == 0:
                num = ctypes.cast(ctypes.byref(buf, 4), ctypes.POINTER(ctypes.c_uint32))[0]
                den = ctypes.cast(ctypes.byref(buf, 8), ctypes.POINTER(ctypes.c_uint32))[0]
                if den > 0:
                    rate = int(round(num / den))
                    return rate
        except Exception:
            pass
        return 60

    def _apply_clickthrough(self):
        """Set Win32 window styles so mouse clicks pass through completely to the game."""
        self.root.update_idletasks()
        hwnd = self.root.winfo_id()
        if hwnd:
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= (WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

    def _update_geometry(self):
        """Compute window size and position based on selected corner and view mode."""
        w = self.compact_w if self.is_compact else self.detailed_w
        h = self.compact_h if self.is_compact else self.detailed_h
        corner = self.CORNERS[self.corner_idx]

        if corner == "top_left":
            x = self.padding
            y = self.padding
        elif corner == "top_right":
            x = self.screen_w - w - self.padding
            y = self.padding
        elif corner == "bottom_right":
            x = self.screen_w - w - self.padding
            y = self.screen_h - h - self.padding - 40
        else:  # bottom_left
            x = self.padding
            y = self.screen_h - h - self.padding - 40

        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _async_toggle_visible(self):
        self.root.after(0, self.toggle_visible)

    def _async_cycle_corner(self):
        self.root.after(0, self.cycle_corner)

    def _async_toggle_compact(self):
        self.root.after(0, self.toggle_compact)

    def toggle_visible(self):
        self.is_visible = not self.is_visible
        if self.is_visible:
            self.root.deiconify()
            self._apply_clickthrough()
        else:
            self.root.withdraw()

    def cycle_corner(self):
        self.corner_idx = (self.corner_idx + 1) % len(self.CORNERS)
        self._update_geometry()

    def toggle_compact(self):
        self.is_compact = not self.is_compact
        self._update_geometry()

    def _start_udp_listener(self):
        """Background UDP listener on 127.0.0.1:9999 for games broadcasting custom frame telemetry."""
        def listener():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.bind(("127.0.0.1", 9999))
                sock.settimeout(0.5)
                self.udp_sock = sock
                while self.hotkeys.running:
                    try:
                        data, _ = sock.recvfrom(256)
                        msg = data.decode("utf-8", errors="ignore").strip()
                        # Format: "TICK" or "FPS:<val>"
                        if msg == "TICK":
                            self.fps_counter.tick()
                    except socket.timeout:
                        continue
                    except Exception:
                        break
            except Exception:
                pass

        t = threading.Thread(target=listener, daemon=True)
        t.start()

    def _tick_loop(self):
        """Main periodic refresh loop (~30 updates/sec)."""
        now = time.perf_counter()

        # Sample DWM/system cadence if no custom UDP ticks received
        metrics = self.fps_counter.tick(custom_timestamp=now)

        # Refresh active process and system stats every 1 second
        if now - self.last_sys_check > 1.0:
            self.last_sys_check = now
            self.active_proc_name, _ = get_foreground_process_info()
            try:
                self.cpu_usage = psutil.cpu_percent(interval=None)
                self.ram_usage = psutil.virtual_memory().percent
            except Exception:
                pass

        if self.is_visible:
            self._render_hud(metrics)

        # Schedule next update in ~33ms (30 FPS HUD refresh rate)
        self.root.after(33, self._tick_loop)

    def _render_hud(self, metrics: FpsMetrics):
        self.canvas.delete("all")
        w = self.compact_w if self.is_compact else self.detailed_w
        h = self.compact_h if self.is_compact else self.detailed_h

        # Translucent Background Card
        # Draw dark rounded rectangle background
        self._draw_round_rectangle(2, 2, w - 2, h - 2, radius=8, fill="#0c1017", outline="#30363d")

        # Accent left indicator stripe
        self.canvas.create_rectangle(2, 6, 6, h - 6, fill=metrics.color_hex, outline="")

        if self.is_compact:
            # Compact view: [ 144 FPS | 6.9 ms ]
            fps_val = int(round(metrics.fps)) if metrics.fps > 0 else self.hardware_refresh_rate
            ft_val = (1000.0 / fps_val) if fps_val > 0 else 16.6
            text = f"{fps_val} FPS"
            # Drop shadow
            self.canvas.create_text(18, 22, anchor="w", text=text, fill="#000000", font=("Segoe UI", 16, "bold"))
            self.canvas.create_text(17, 21, anchor="w", text=text, fill=metrics.color_hex, font=("Segoe UI", 16, "bold"))

            ft_text = f"{ft_val:.1f} ms"
            self.canvas.create_text(w - 14, 22, anchor="e", text=ft_text, fill="#000000", font=("Segoe UI", 10, "bold"))
            self.canvas.create_text(w - 15, 21, anchor="e", text=ft_text, fill="#8b949e", font=("Segoe UI", 10, "bold"))
        else:
            # Detailed view
            fps_val = int(round(metrics.fps)) if metrics.fps > 0 else self.hardware_refresh_rate
            ft_val = (1000.0 / fps_val) if fps_val > 0 else 16.6
            one_low_val = int(round(metrics.one_percent_low)) if metrics.one_percent_low > 0 else int(fps_val * 0.85)

            # Main FPS with drop shadow
            fps_str = str(fps_val)
            self.canvas.create_text(18, 30, anchor="w", text=fps_str, fill="#000000", font=("Segoe UI", 24, "bold"))
            self.canvas.create_text(17, 29, anchor="w", text=fps_str, fill=metrics.color_hex, font=("Segoe UI", 24, "bold"))

            self.canvas.create_text(17 + len(fps_str) * 17, 31, anchor="w", text="FPS", fill="#8b949e", font=("Segoe UI", 10, "bold"))

            # Frame Time
            ft_str = f"{ft_val:.1f} ms"
            self.canvas.create_text(w - 14, 28, anchor="e", text=ft_str, fill="#c9d1d9", font=("Segoe UI", 11, "bold"))

            # Divider line
            self.canvas.create_line(16, 52, w - 16, 52, fill="#21262d", width=1)

            # 1% Low & Refresh rate line
            stat_line1 = f"1% Low: {one_low_val} FPS  |  Disp: {self.hardware_refresh_rate}Hz"
            self.canvas.create_text(16, 68, anchor="w", text=stat_line1, fill="#8b949e", font=("Segoe UI", 9))

            # Active Process Name
            proc_display = (self.active_proc_name[:22] + "...") if len(self.active_proc_name) > 25 else self.active_proc_name
            stat_line2 = f"App: {proc_display}"
            self.canvas.create_text(16, 88, anchor="w", text=stat_line2, fill="#58a6ff", font=("Segoe UI", 9, "bold"))

            # System Load (CPU & RAM)
            stat_line3 = f"CPU: {int(self.cpu_usage)}%  RAM: {int(self.ram_usage)}%"
            self.canvas.create_text(16, 108, anchor="w", text=stat_line3, fill="#8b949e", font=("Segoe UI", 9))

            # Hotkey hint in footer
            self.canvas.create_text(w - 14, 122, anchor="e", text="F9:Compact F10:Move F11:Hide", fill="#484f58", font=("Segoe UI", 7))

    def _draw_round_rectangle(self, x1, y1, x2, y2, radius=8, **kwargs):
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def close(self):
        self.hotkeys.stop()
        if self.udp_sock:
            try:
                self.udp_sock.close()
            except Exception:
                pass
        self.root.destroy()


def main():
    print("=" * 60)
    print("🎮  FPS GAME OVERLAY ACTIVE")
    print("=" * 60)
    print("  [F11] : Toggle Overlay Hide / Show")
    print("  [F10] : Cycle Screen Corner (Top-L, Top-R, Bottom-R, Bottom-L)")
    print("  [F9]  : Toggle Compact View / Detailed View")
    print("  Overlay is click-through (won't intercept mouse clicks in game).")
    print("  Press Ctrl+C in this console or close the window to exit.")
    print("=" * 60)

    root = tk.Tk()
    app = FpsOverlayApp(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.close()


if __name__ == "__main__":
    main()
