"""
tests/test_fps_core.py - Unit tests for FpsCounter
"""

import unittest
import math
import sys
import os

# Add parent directory to path so we can import fps_core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fps_core import FpsCounter, FpsMetrics


class TestFpsCounter(unittest.TestCase):
    def test_steady_60_fps(self):
        """Simulate perfectly steady 60 FPS (dt = 1/60s)."""
        counter = FpsCounter(window_size=60)
        dt = 1.0 / 60.0
        timestamp = 100.0

        # First tick establishes baseline t0
        counter.tick(custom_timestamp=timestamp)
        # Next 60 ticks record 60 frame intervals
        for _ in range(60):
            timestamp += dt
            metrics = counter.tick(custom_timestamp=timestamp)

        self.assertAlmostEqual(metrics.fps, 60.0, places=1)
        self.assertAlmostEqual(metrics.frame_time_ms, 16.67, places=1)
        self.assertAlmostEqual(metrics.one_percent_low, 60.0, places=1)
        self.assertEqual(metrics.color_hex, "#00FF66")

    def test_steady_144_fps(self):
        """Simulate high refresh rate 144 FPS."""
        counter = FpsCounter(window_size=144)
        dt = 1.0 / 144.0
        timestamp = 0.0

        # Baseline t0
        counter.tick(custom_timestamp=timestamp)
        for _ in range(144):
            timestamp += dt
            metrics = counter.tick(custom_timestamp=timestamp)

        self.assertAlmostEqual(metrics.fps, 144.0, places=1)
        self.assertAlmostEqual(metrics.frame_time_ms, 6.94, places=1)
        self.assertEqual(metrics.color_hex, "#00FF66")

    def test_low_fps_color_thresholds(self):
        """Verify color changes: yellow for 45 FPS, red for 20 FPS."""
        counter = FpsCounter(window_size=30)

        # 45 FPS (Yellow)
        t = 0.0
        counter.tick(custom_timestamp=t)
        for _ in range(30):
            t += 1.0 / 45.0
            metrics = counter.tick(custom_timestamp=t)
        self.assertEqual(metrics.color_hex, "#FFD600")

        # 20 FPS (Red)
        counter.reset()
        t = 0.0
        counter.tick(custom_timestamp=t)
        for _ in range(30):
            t += 1.0 / 20.0
            metrics = counter.tick(custom_timestamp=t)
        self.assertEqual(metrics.color_hex, "#FF3344")

    def test_one_percent_lows_with_stutter(self):
        """
        Verify that a frame stutter drops 1% lows while average stays relatively high.
        Simulate 100 frames at 60 FPS (16.6ms) + 1 stutter frame of 100ms.
        """
        counter = FpsCounter(window_size=100)
        t = 0.0
        counter.tick(custom_timestamp=t)

        # 99 normal frames (16.66ms each)
        for _ in range(99):
            t += 1.0 / 60.0
            counter.tick(custom_timestamp=t)

        # 1 stutter frame (100ms = 0.1s -> 10 FPS)
        t += 0.100
        metrics = counter.tick(custom_timestamp=t)

        # Average FPS should still be around ~56 FPS
        self.assertTrue(50.0 < metrics.fps < 60.0)
        # But 1% Low should reflect the 100ms stutter frame (10 FPS)
        self.assertAlmostEqual(metrics.one_percent_low, 10.0, delta=1.0)
        self.assertAlmostEqual(metrics.min_fps, 10.0, delta=1.0)

    def test_reset(self):
        """Verify reset clears state properly."""
        counter = FpsCounter()
        counter.tick(1.0)
        counter.tick(2.0)
        self.assertEqual(counter._total_frames, 2)
        counter.reset()
        self.assertEqual(counter._total_frames, 0)
        self.assertIsNone(counter._last_timestamp)


if __name__ == "__main__":
    unittest.main()
