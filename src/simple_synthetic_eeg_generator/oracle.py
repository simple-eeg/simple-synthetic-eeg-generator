"""Independent arithmetic oracle for event-locked component verification.

This intentionally does not call construction helpers from ``model.py``.
It duplicates the frozen equations so a helper defect cannot agree with
itself merely by being called twice.
"""

from __future__ import annotations

import math
from typing import Any

from .errors import ContractError


def reconstruct_analytic_components(
    subject_id: str, settings: dict[str, Any], realised: dict[str, float]
) -> dict[str, Any]:
    try:
        import numpy as np
    except ImportError as exc:
        raise ContractError("The locked NumPy dependency is required") from exc

    dataset = settings["dataset"]
    response = settings["signal"]["response"]
    spectral = settings["signal"]["spectral"]
    artifact_spec = settings["signal"]["artifact"]
    fs = int(dataset["sample_rate_hz"])
    count = int(dataset["sample_count"])
    event_zero = int(dataset["event_latency_eeglab"]) - 1
    offsets = np.arange(count, dtype=np.int64) - event_zero
    tau = offsets.astype(np.float64) / fs

    multiplier = realised["response_multiplier"]
    delay = realised["response_delay_seconds"]
    width = realised["response_width_multiplier"]
    early_spec = response["early"]
    late_spec = response["late"]
    early = multiplier * early_spec["amplitude_uv"] * np.exp(
        -0.5
        * ((tau - (early_spec["centre_seconds"] + delay)) / (early_spec["width_seconds"] * width))
        ** 2
    )
    late = multiplier * late_spec["amplitude_uv"] * np.exp(
        -0.5
        * ((tau - (late_spec["centre_seconds"] + delay)) / (late_spec["width_seconds"] * width))
        ** 2
    )

    def windowed(spec: dict[str, Any], amplitude: float, frequency: float, phase: float):
        start = int(round(spec["start_seconds"] * fs))
        end = int(round(spec["end_seconds"] * fs))
        mask = (offsets >= start) & (offsets <= end)
        indices = offsets[mask]
        if indices.size != end - start + 1:
            raise ContractError("Oracle support lies outside the continuous record")
        fraction = (indices - start).astype(np.float64) / float(end - start)
        alpha = float(spec["tukey_alpha"])
        taper = np.ones(indices.size, dtype=np.float64)
        left = fraction < alpha / 2.0
        right = fraction > 1.0 - alpha / 2.0
        taper[left] = 0.5 * (1.0 + np.cos(math.pi * (2.0 * fraction[left] / alpha - 1.0)))
        taper[right] = 0.5 * (
            1.0 + np.cos(math.pi * (2.0 * fraction[right] / alpha - 2.0 / alpha + 1.0))
        )
        taper[0] = 0.0
        taper[-1] = 0.0
        output = np.zeros(count, dtype=np.float64)
        local_tau = indices.astype(np.float64) / fs
        output[mask] = amplitude * taper * np.sin(2.0 * math.pi * frequency * local_tau + phase)
        output[~mask] = 0.0
        return output

    spectral_component = windowed(
        spectral,
        realised["spectral_amplitude_uv"],
        realised["spectral_frequency_hz"],
        realised["spectral_phase_radians"],
    )
    artifact = np.zeros(count, dtype=np.float64)
    if subject_id == artifact_spec["subject_id"]:
        artifact = windowed(
            artifact_spec,
            artifact_spec["amplitude_uv"],
            artifact_spec["frequency_hz"],
            artifact_spec["phase_radians"],
        )
    return {
        "early_negative": early,
        "late_positive": late,
        "spectral": spectral_component,
        "artifact": artifact,
    }
