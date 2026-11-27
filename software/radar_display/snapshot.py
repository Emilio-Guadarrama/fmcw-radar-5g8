"""Turn a processed frame into the plain JSON the web page draws.

The page does no radar maths: every number it shows is computed here or in
processing.py, except display latency, which only the browser can time.
"""

import numpy as np
from fmcw import RadarConfig

from .metrics import StreamStats
from .processing import (
    DetectionSettings,
    FrameResult,
    quantization_noise_power_v2,
    threshold_factor,
)
from .source import Frame

PLOT_MAX_RANGE_M = 45.0  # same axis for both sweeps
WATERFALL_STEP = 4  # every 4th point of the 16x padded spectrum

# Decision 002. Targets (assumptions), not demonstrated performance.
TARGETS = {
    "resolution_m": {"115": 2.5, "150": 2.0},
    "accuracy_m": 0.20,
    "accuracy_snr_db": 20.0,
    "pd": 0.90,
    "pfa": 1e-4,
    "update_rate_hz": 10.0,
    "latency_ms": 200.0,
    "min_range_m": 3.0,
    "max_range_m": 30.0,
}

SWEEP_NOTES = {
    "115": "Radiated design case",
    "150": "Simulation and cable / dummy load only",
}


def to_db(amplitude_v) -> np.ndarray:
    """dB relative to 1 V peak."""
    return 20 * np.log10(np.maximum(amplitude_v, 1e-9))


def _rounded(values, digits: int = 2) -> list:
    return np.round(np.asarray(values, dtype=float), digits).tolist()


def settings_info(
    cfg: RadarConfig,
    chirps_per_frame: int,
    window: str,
    detection: DetectionSettings,
    cells_tested: int,
    frame_rate_hz: float | None,
) -> dict:
    """Values that follow from the settings (all calculated)."""
    factor = threshold_factor(chirps_per_frame, detection.pfa)
    return {
        "f_start_ghz": cfg.f_start_hz / 1e9,
        "f_stop_ghz": (cfg.f_start_hz + cfg.bandwidth_hz) / 1e9,
        "bandwidth_mhz": cfg.bandwidth_hz / 1e6,
        "chirp_ms": cfg.chirp_s * 1e3,
        "sample_rate_ksps": cfg.sample_rate_hz / 1e3,
        "samples_per_chirp": cfg.n_samples,
        "chirps_per_frame": chirps_per_frame,
        # assumption: chirps run back to back (repetition not decided, R-05)
        "frame_capture_ms": chirps_per_frame * cfg.chirp_s * 1e3,
        "window": window,
        "range_cell_m": cfg.range_resolution_m,
        "max_unaliased_range_m": cfg.max_range_m,
        "adc_bits": cfg.adc_bits,
        "adc_full_scale_v": cfg.adc_full_scale_v,
        "pfa": detection.pfa,
        "threshold_above_noise_db": float(10 * np.log10(factor)),
        "integration_gain_db": float(10 * np.log10(chirps_per_frame)),
        "cells_tested": cells_tested,
        # Expected rate with no target, if the noise assumptions hold. This
        # counts cells above threshold; the peak rule can only lower it.
        "false_alarm_every_s": (
            None
            if not frame_rate_hz or not cells_tested
            else 1 / (cells_tested * detection.pfa * frame_rate_hz)
        ),
        "quantization_floor_db": float(
            10 * np.log10(quantization_noise_power_v2(cfg, window, chirps_per_frame))
        ),
    }


def build_snapshot(
    frame: Frame,
    result: FrameResult,
    stats: StreamStats,
    window: str,
    detection: DetectionSettings,
) -> dict:
    cfg = frame.config
    shown = result.range_m <= PLOT_MAX_RANGE_M
    cells_shown = result.cell_range_m <= PLOT_MAX_RANGE_M
    floor_db = float(to_db(result.noise_floor_v))
    spectrum_db = to_db(result.amplitude_v[shown])
    above_floor_db = np.clip(spectrum_db[::WATERFALL_STEP] - floor_db, 0.0, 60.0)
    lsb = 2 * cfg.adc_full_scale_v / 2**cfg.adc_bits
    clipped = bool(np.any(np.abs(frame.chirps_v) >= cfg.adc_full_scale_v - 1.5 * lsb))
    rate = stats.update_rate_hz

    detections = [
        {
            "range_m": d.range_m,
            "snr_db": d.snr_db,
            "amplitude_dbv": float(to_db(d.amplitude_v)),
            "beat_hz": d.beat_hz,
        }
        for d in result.detections
    ]
    truth = None
    if frame.truth is not None:
        truth = [{"range_m": r, "amplitude_v": a} for r, a in frame.truth]

    return {
        "seq": frame.seq,
        "beat": {
            "t_ms": _rounded(cfg.sample_times() * 1e3, 4),
            "first_chirp_mv": _rounded(frame.chirps_v[0] * 1e3),
            "average_mv": _rounded(frame.chirps_v.mean(axis=0) * 1e3),
            "clipped": clipped,
        },
        "spectrum": {
            "range_step_m": float(result.range_m[1] - result.range_m[0]),
            "db": _rounded(spectrum_db),
            "cell_range_m": _rounded(result.cell_range_m[cells_shown], 3),
            "cell_db": _rounded(to_db(result.cell_amplitude_v[cells_shown])),
            "threshold_db": _rounded(to_db(result.threshold_v[cells_shown])),
            "noise_floor_db": floor_db,
        },
        "waterfall": {
            "range_step_m": float(
                (result.range_m[1] - result.range_m[0]) * WATERFALL_STEP
            ),
            "above_floor_db": _rounded(above_floor_db, 1),
        },
        "detections": detections,
        "truth": truth,
        "stream": {
            "update_rate_hz": rate,
            "processing_ms": stats.processing_ms,
            "received": stats.received,
            "dropped": stats.dropped,
            "dropped_last_10_s": stats.dropped_last_10_s,
            "dropped_fraction": stats.dropped_fraction,
        },
        "settings": settings_info(
            cfg,
            frame.chirps_v.shape[0],
            window,
            detection,
            int(result.gate.size),
            rate,
        ),
    }
