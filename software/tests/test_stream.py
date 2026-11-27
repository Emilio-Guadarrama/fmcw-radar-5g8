"""Simulated source schedule, settings checks and stream statistics."""

import numpy as np
import pytest
from radar_display.metrics import StreamStats
from radar_display.simulated import (
    SimSettings,
    SimulatedSource,
    echo_amplitude_v,
    moving_range_m,
    scene_targets,
    validated,
)


class FakeTime:
    def __init__(self):
        self.now = 100.0

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def make_source(**kwargs):
    fake = FakeTime()
    source = SimulatedSource(
        frame_rate_hz=10.0, seed=1, clock=fake.clock, sleep=fake.sleep, **kwargs
    )
    return source, fake


def test_frames_arrive_on_schedule_with_consecutive_numbers():
    source, fake = make_source()
    frames = [source.read_frame(1.0) for _ in range(5)]
    assert [f.seq for f in frames] == [0, 1, 2, 3, 4]
    assert np.diff([f.captured_s for f in frames]) == pytest.approx([0.1] * 4)
    assert frames[0].chirps_v.shape == (16, 100)
    assert source.is_simulated
    assert fake.now == pytest.approx(frames[-1].captured_s)


def test_short_timeout_returns_none_without_losing_a_frame():
    source, _ = make_source()
    assert source.read_frame(0.04) is None
    assert source.read_frame(0.04) is None
    assert source.read_frame(0.04).seq == 0


def test_slow_reader_sees_a_gap():
    source, fake = make_source()
    source.read_frame(1.0)
    fake.now += 0.45  # about four periods spent elsewhere
    assert source.read_frame(1.0).seq == 4


def test_requested_drop_leaves_a_gap_of_that_size():
    source, _ = make_source()
    first = source.read_frame(1.0)
    source.drop_frames(5)
    second = source.read_frame(1.0)
    assert second.seq - first.seq == 6
    assert second.captured_s - first.captured_s == pytest.approx(0.6)


def test_sweep_setting_changes_the_frame_config():
    source, _ = make_source()
    assert source.read_frame(1.0).config.bandwidth_hz == 115e6
    source.update({"sweep": "150"})
    assert source.read_frame(1.0).config.bandwidth_hz == 150e6


@pytest.mark.parametrize(
    "changes",
    [
        {"sweep": "125"},
        {"sweep": ["115"]},
        {"scene": "drone"},
        {"distance_m": 2.0},
        {"distance_m": float("nan")},
        {"distance_m": "12"},
        {"noise_mv": True},
        {"noise_mv": 0},
        {"tx_enable": True},
    ],
)
def test_bad_settings_are_rejected(changes):
    with pytest.raises(ValueError):
        validated(SimSettings(), changes)


def test_a_rejected_change_changes_nothing():
    source, _ = make_source()
    with pytest.raises(ValueError):
        source.update({"scene": "pair", "distance_m": -1})
    assert source.settings == SimSettings()


def test_echo_power_falls_40_db_from_3_m_to_30_m():
    drop_db = 20 * np.log10(echo_amplitude_v(3.0) / echo_amplitude_v(30.0))
    assert drop_db == pytest.approx(40.0)


def test_scenes():
    pair = scene_targets(SimSettings(scene="pair", distance_m=10, separation_m=2.5), 0)
    assert [r for r, _ in pair] == [10, 12.5]
    assert pair[0][1] == pair[1][1]  # equal echoes
    assert len(scene_targets(SimSettings(scene="three"), 0)) == 3
    assert scene_targets(SimSettings(scene="empty"), 0) == ()


def test_moving_target_bounces_between_its_limits():
    assert moving_range_m(0) == 4.0
    assert moving_range_m(24) == 28.0
    assert moving_range_m(25) == 27.0
    assert moving_range_m(48) == 4.0


def test_rate_latency_and_drop_counting():
    stats = StreamStats(rate_window_s=2.0)
    assert stats.update_rate_hz is None and stats.processing_ms is None
    for i, seq in enumerate([0, 1, 2, 5, 6]):
        stats.add(seq, captured_s=i * 0.1, done_s=i * 0.1 + 0.004)
    assert stats.update_rate_hz == pytest.approx(10.0)
    assert stats.processing_ms == pytest.approx(4.0)
    assert stats.received == 5
    assert stats.dropped == 2
    assert stats.dropped_last_10_s == 2
    assert stats.dropped_fraction == pytest.approx(2 / 7)
    stats.add(7, 20.0, 20.0)
    assert stats.dropped_last_10_s == 0 and stats.dropped == 2


def test_source_restart_is_not_counted_as_loss():
    stats = StreamStats()
    stats.add(500, 0.0, 0.0)
    stats.add(0, 0.1, 0.1)
    assert stats.dropped == 0
