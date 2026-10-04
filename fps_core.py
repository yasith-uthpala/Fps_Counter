"""
fps_core.py - Core FPS and Frame Time Measurement Engine

Provides high-precision timing, smoothed moving averages, 1% / 0.1% lows,
and frame performance metrics for games and real-time graphics applications.
"""

from __future__ import annotations
import collections
import dataclasses
import time
from typing import Deque, List, Optional


@dataclasses.dataclass
class FpsMetrics:
    """Represents current performance metrics for a frame snapshot."""
    fps: float
    instant_fps: float
    frame_time_ms: float
    one_percent_low: float
    zero_point_one_percent_low: float
    min_fps: float
    max_fps: float
    total_frames: int
    color_hex: str


class FpsCounter:
    """
    High-precision frame rate and frame time calculator.
    
    Features:
    - Microsecond-accurate timing using time.perf_counter()
    - Rolling window smoothing to avoid rapid text jitter
    - 1% and 0.1% Lows (the gaming industry standard for detecting micro-stutter)
    - Dynamic color coding (Green: 60+, Yellow: 30-59, Red: <30)
    """

    def __init__(
        self,
        window_size: int = 120,
        green_threshold: float = 60.0,
        yellow_threshold: float = 30.0,
    ) -> None:
        """
        Initialize the FPS counter.
        
        :param window_size: Number of recent frames to retain for smoothing and 1% lows.
        :param green_threshold: Minimum FPS for green status indicator.
        :param yellow_threshold: Minimum FPS for yellow status indicator (below is red).
        """
        self.window_size = max(10, window_size)
        self.green_threshold = green_threshold
        self.yellow_threshold = yellow_threshold

        self._frame_times: Deque[float] = collections.deque(maxlen=self.window_size)
        self._last_timestamp: Optional[float] = None
        self._total_frames: int = 0
        self._cached_metrics: Optional[FpsMetrics] = None

    def tick(self, custom_timestamp: Optional[float] = None) -> FpsMetrics:
        """
        Record a frame completion. Call this once per frame in your render/game loop.
        
        :param custom_timestamp: Optional high-res timestamp in seconds (defaults to time.perf_counter()).
        :return: Updated FpsMetrics instance.
        """
        now = custom_timestamp if custom_timestamp is not None else time.perf_counter()

        if self._last_timestamp is None:
            self._last_timestamp = now
            self._total_frames += 1
            # Return initial placeholder without polluting buffer
            return FpsMetrics(
                fps=0.0,
                instant_fps=0.0,
                frame_time_ms=0.0,
                one_percent_low=0.0,
                zero_point_one_percent_low=0.0,
                min_fps=0.0,
                max_fps=0.0,
                total_frames=self._total_frames,
                color_hex="#00FF66",
            )

        dt = now - self._last_timestamp
        self._last_timestamp = now
        self._total_frames += 1

        # Guard against zero or negative delta times (e.g. system clock jumps)
        dt = max(0.000001, min(dt, 5.0))
        self._frame_times.append(dt)

        metrics = self._compute_metrics(instant_dt=dt)
        self._cached_metrics = metrics
        return metrics

    def _compute_metrics(self, instant_dt: float) -> FpsMetrics:
        """Calculate aggregate performance metrics over the rolling history window."""
        count = len(self._frame_times)
        if count == 0:
            return FpsMetrics(
                fps=0.0,
                instant_fps=0.0,
                frame_time_ms=0.0,
                one_percent_low=0.0,
                zero_point_one_percent_low=0.0,
                min_fps=0.0,
                max_fps=0.0,
                total_frames=self._total_frames,
                color_hex="#888888",
            )

        total_time = sum(self._frame_times)
        avg_dt = total_time / count if total_time > 0 else 0.016
        avg_fps = (count / total_time) if total_time > 0 else 0.0
        instant_fps = 1.0 / instant_dt
        frame_time_ms = avg_dt * 1000.0

        # Sort frame times (ascending: smallest dt = fastest frame; largest dt = slowest frame)
        sorted_times: List[float] = sorted(self._frame_times)

        # Max FPS corresponds to the fastest frame (smallest delta time)
        max_fps = 1.0 / sorted_times[0] if sorted_times[0] > 0 else 0.0
        # Min FPS corresponds to the slowest frame (largest delta time)
        min_fps = 1.0 / sorted_times[-1] if sorted_times[-1] > 0 else 0.0

        # 1% Low: 99th percentile frame time (or average of worst 1% frames)
        # Using index-based percentile or average of top 1% slowest frames
        one_pct_count = max(1, int(round(count * 0.01)))
        worst_1pct_times = sorted_times[-one_pct_count:]
        worst_1pct_avg_dt = sum(worst_1pct_times) / len(worst_1pct_times)
        one_percent_low = 1.0 / worst_1pct_avg_dt if worst_1pct_avg_dt > 0 else 0.0

        # 0.1% Low: Average of worst 0.1% slowest frame times
        tenth_pct_count = max(1, int(round(count * 0.001)))
        worst_01pct_times = sorted_times[-tenth_pct_count:]
        worst_01pct_avg_dt = sum(worst_01pct_times) / len(worst_01pct_times)
        zero_point_one_low = 1.0 / worst_01pct_avg_dt if worst_01pct_avg_dt > 0 else 0.0

        # Determine color coding based on average FPS
        if avg_fps >= self.green_threshold:
            color = "#00FF66"  # Vibrant Emerald Green (Optimal)
        elif avg_fps >= self.yellow_threshold:
            color = "#FFD600"  # Amber Yellow (Playable / Sub-optimal)
        else:
            color = "#FF3344"  # Crimson Red (Laggy / Poor)

        return FpsMetrics(
            fps=avg_fps,
            instant_fps=instant_fps,
            frame_time_ms=frame_time_ms,
            one_percent_low=one_percent_low,
            zero_point_one_percent_low=zero_point_one_low,
            min_fps=min_fps,
            max_fps=max_fps,
            total_frames=self._total_frames,
            color_hex=color,
        )

    def get_metrics(self) -> FpsMetrics:
        """Return the latest cached performance metrics, or compute default if none."""
        if self._cached_metrics is None:
            return self.tick()
        return self._cached_metrics

    def reset(self) -> None:
        """Clear all historical frame times and reset the counter."""
        self._frame_times.clear()
        self._last_timestamp = None
        self._total_frames = 0
        self._cached_metrics = None
