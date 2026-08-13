"""Frozen procedural signal construction.

Production background generation calls NeuroDSP 2.3.0 directly. No fallback,
mock, or alternate coloured-noise implementation exists in this module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .canonical import sha256_bytes
from .errors import ContractError
from .seeds import DerivedSeed, derive_seed


PARAMETER_COMPONENTS = {
    "chi": "chi",
    "sigma_uv": "sigma",
    "response_multiplier": "response_scale",
    "response_delay_seconds": "response_latency",
    "response_width_multiplier": "response_width",
    "spectral_amplitude_uv": "burst_amplitude",
    "spectral_frequency_hz": "burst_frequency",
    "spectral_phase_radians": "burst_phase",
}
BACKGROUND_COMPONENT = "background"


@dataclass(frozen=True)
class RealisedDraw:
    raw: float
    realised: float
    seed: DerivedSeed


@dataclass
class SubjectResult:
    subject_id: str
    parameters: dict[str, RealisedDraw]
    seeds: dict[str, DerivedSeed]
    components: dict[str, Any]
    composite_float64: Any
    staged_float32: Any


def _np():
    try:
        import numpy as np
    except ImportError as exc:
        raise ContractError("The locked NumPy dependency is required") from exc
    return np


def _normal_draw(subject_id: str, component: str, mean: float, sd: float, clip: list[float]) -> RealisedDraw:
    np = _np()
    seed = derive_seed(subject_id, component)
    rng = np.random.Generator(np.random.PCG64DXSM(seed.seed128))
    raw = float(rng.normal(mean, sd))
    realised = float(np.clip(raw, float(clip[0]), float(clip[1])))
    return RealisedDraw(raw=raw, realised=realised, seed=seed)


def _uniform_phase_draw(subject_id: str, component: str) -> RealisedDraw:
    np = _np()
    seed = derive_seed(subject_id, component)
    rng = np.random.Generator(np.random.PCG64DXSM(seed.seed128))
    raw = float(rng.uniform(0.0, 2.0 * math.pi))
    return RealisedDraw(raw=raw, realised=raw, seed=seed)


def realise_parameters(subject_id: str, settings: dict[str, Any]) -> dict[str, RealisedDraw]:
    background = settings["signal"]["background"]
    response = settings["signal"]["response"]
    spectral = settings["signal"]["spectral"]
    values = {
        "chi": _normal_draw(subject_id, PARAMETER_COMPONENTS["chi"], **background["exponent"]),
        "sigma_uv": _normal_draw(
            subject_id, PARAMETER_COMPONENTS["sigma_uv"], **background["sigma_uv"]
        ),
        "response_multiplier": _normal_draw(
            subject_id,
            PARAMETER_COMPONENTS["response_multiplier"],
            **response["amplitude_multiplier"],
        ),
        "response_delay_seconds": _normal_draw(
            subject_id,
            PARAMETER_COMPONENTS["response_delay_seconds"],
            **response["delay_seconds"],
        ),
        "response_width_multiplier": _normal_draw(
            subject_id,
            PARAMETER_COMPONENTS["response_width_multiplier"],
            **response["width_multiplier"],
        ),
        "spectral_amplitude_uv": _normal_draw(
            subject_id,
            PARAMETER_COMPONENTS["spectral_amplitude_uv"],
            **spectral["amplitude_uv"],
        ),
        "spectral_frequency_hz": _normal_draw(
            subject_id,
            PARAMETER_COMPONENTS["spectral_frequency_hz"],
            **spectral["frequency_hz"],
        ),
        "spectral_phase_radians": _uniform_phase_draw(
            subject_id, PARAMETER_COMPONENTS["spectral_phase_radians"]
        ),
    }
    return values


def discrete_tukey(length: int, alpha: float):
    """Return SciPy's frozen symmetric Tukey definition on `length` samples."""

    np = _np()
    if length < 1:
        raise ContractError("Tukey length must be positive")
    if not 0.0 <= alpha <= 1.0:
        raise ContractError("Tukey alpha must lie in [0, 1]")
    try:
        from scipy.signal.windows import tukey
    except ImportError as exc:
        raise ContractError("The locked SciPy dependency is required for the Tukey window") from exc
    return np.asarray(tukey(length, alpha=alpha, sym=True), dtype=np.float64)


def supported_tukey_component(
    sample_offsets: Any,
    sample_rate_hz: int,
    start_seconds: float,
    end_seconds: float,
    alpha: float,
    amplitude: float,
    frequency_hz: float,
    phase_radians: float,
):
    """Construct a sinusoid with exact zeroes outside inclusive sample support."""

    np = _np()
    start_sample = int(round(start_seconds * sample_rate_hz))
    end_sample = int(round(end_seconds * sample_rate_hz))
    if start_sample < 0 or end_sample < start_sample:
        raise ContractError("Invalid Tukey support")
    mask = (sample_offsets >= start_sample) & (sample_offsets <= end_sample)
    expected_length = end_sample - start_sample + 1
    if int(np.count_nonzero(mask)) != expected_length:
        raise ContractError("Continuous record does not contain the full declared Tukey support")
    component = np.zeros(sample_offsets.shape, dtype=np.float64)
    tau = sample_offsets[mask].astype(np.float64) / float(sample_rate_hz)
    component[mask] = (
        amplitude
        * discrete_tukey(expected_length, alpha)
        * np.sin(2.0 * math.pi * frequency_hz * tau + phase_radians)
    )
    component[~mask] = 0.0
    return component


def analytic_components(
    subject_id: str, settings: dict[str, Any], parameters: dict[str, RealisedDraw]
) -> dict[str, Any]:
    """Construct the deterministic event-locked components only."""

    np = _np()
    dataset = settings["dataset"]
    response = settings["signal"]["response"]
    spectral = settings["signal"]["spectral"]
    artifact = settings["signal"]["artifact"]
    sample_rate = int(dataset["sample_rate_hz"])
    event_index = int(dataset["event_latency_eeglab"]) - 1
    sample_offsets = np.arange(int(dataset["sample_count"]), dtype=np.int64) - event_index
    tau = sample_offsets.astype(np.float64) / float(sample_rate)

    multiplier = parameters["response_multiplier"].realised
    delay = parameters["response_delay_seconds"].realised
    width_multiplier = parameters["response_width_multiplier"].realised
    early_spec = response["early"]
    late_spec = response["late"]
    early = multiplier * float(early_spec["amplitude_uv"]) * np.exp(
        -((tau - (float(early_spec["centre_seconds"]) + delay)) ** 2)
        / (2.0 * (float(early_spec["width_seconds"]) * width_multiplier) ** 2)
    )
    late = multiplier * float(late_spec["amplitude_uv"]) * np.exp(
        -((tau - (float(late_spec["centre_seconds"]) + delay)) ** 2)
        / (2.0 * (float(late_spec["width_seconds"]) * width_multiplier) ** 2)
    )
    oscillation = supported_tukey_component(
        sample_offsets,
        sample_rate,
        float(spectral["start_seconds"]),
        float(spectral["end_seconds"]),
        float(spectral["tukey_alpha"]),
        parameters["spectral_amplitude_uv"].realised,
        parameters["spectral_frequency_hz"].realised,
        parameters["spectral_phase_radians"].realised,
    )
    artifact_component = np.zeros(int(dataset["sample_count"]), dtype=np.float64)
    if subject_id == artifact["subject_id"]:
        artifact_component = supported_tukey_component(
            sample_offsets,
            sample_rate,
            float(artifact["start_seconds"]),
            float(artifact["end_seconds"]),
            float(artifact["tukey_alpha"]),
            float(artifact["amplitude_uv"]),
            float(artifact["frequency_hz"]),
            float(artifact["phase_radians"]),
        )
    return {
        "early_negative": early.astype(np.float64, copy=False),
        "late_positive": late.astype(np.float64, copy=False),
        "spectral": oscillation,
        "artifact": artifact_component,
    }


def generate_neurodsp_background(duration: float, sample_rate: int, exponent: float, seed32: int):
    """Call the frozen NeuroDSP implementation once and restore legacy RNG state."""

    np = _np()
    state = np.random.get_state()
    import os
    from pathlib import Path

    mplconfig = os.environ.get("MPLCONFIGDIR", "")
    if not mplconfig or not Path(mplconfig).is_dir() or not os.access(mplconfig, os.W_OK):
        raise ContractError("MPLCONFIGDIR must name the controlled writable build cache before NeuroDSP import")
    try:
        try:
            from neurodsp.sim import set_random_seed, sim_powerlaw
        except ImportError as exc:
            raise ContractError("NeuroDSP 2.3.0 is required; no fallback is permitted") from exc
        set_random_seed(seed32)
        raw = sim_powerlaw(duration, sample_rate, exponent=-float(exponent))
    finally:
        np.random.set_state(state)
    raw = np.asarray(raw, dtype=np.float64)
    expected_count = int(round(duration * sample_rate))
    if raw.ndim != 1 or raw.size != expected_count or not np.all(np.isfinite(raw)):
        raise ContractError("NeuroDSP returned an invalid background shape or nonfinite value")
    centred = raw - float(np.mean(raw))
    sample_sd = float(np.std(centred, ddof=1))
    if not math.isfinite(sample_sd) or sample_sd <= 0.0:
        raise ContractError("NeuroDSP background has nonpositive sample SD")
    normalised = centred / sample_sd
    return raw, normalised


def generate_subject(subject_id: str, settings: dict[str, Any]) -> SubjectResult:
    """Generate one production subject under the frozen recipe."""

    np = _np()
    parameters = realise_parameters(subject_id, settings)
    seeds = {name: draw.seed for name, draw in parameters.items()}
    background_seed = derive_seed(subject_id, BACKGROUND_COMPONENT)
    seeds["background"] = background_seed
    dataset = settings["dataset"]
    raw, normalised = generate_neurodsp_background(
        float(dataset["duration_seconds"]),
        int(dataset["sample_rate_hz"]),
        parameters["chi"].realised,
        background_seed.seed32,
    )
    scaled = normalised * parameters["sigma_uv"].realised
    analytic = analytic_components(subject_id, settings, parameters)
    composite = compose_float64(scaled, analytic)
    if not np.all(np.isfinite(composite)):
        raise ContractError(f"Subject {subject_id} composite contains a nonfinite value")
    staged = np.asarray(composite, dtype="<f4")
    components = {
        "aperiodic_raw": raw,
        "background_normalised": normalised,
        "background_scaled": scaled,
        **analytic,
    }
    return SubjectResult(
        subject_id=subject_id,
        parameters=parameters,
        seeds=seeds,
        components=components,
        composite_float64=composite,
        staged_float32=staged,
    )


def canonical_array_bytes(array: Any, dtype: str) -> bytes:
    np = _np()
    if dtype == "float32":
        return np.asarray(array, dtype="<f4").tobytes(order="C")
    if dtype == "float64":
        return np.asarray(array, dtype="<f8").tobytes(order="C")
    raise ContractError(f"Unsupported canonical dtype: {dtype}")


def component_sha256(array: Any) -> str:
    return sha256_bytes(canonical_array_bytes(array, "float64"))


def compose_float64(background_scaled: Any, analytic: dict[str, Any]):
    """Apply the normative ordered float64 sum before the one final cast."""

    np = _np()
    arrays = [
        np.asarray(background_scaled, dtype=np.float64),
        np.asarray(analytic["early_negative"], dtype=np.float64),
        np.asarray(analytic["late_positive"], dtype=np.float64),
        np.asarray(analytic["spectral"], dtype=np.float64),
        np.asarray(analytic["artifact"], dtype=np.float64),
    ]
    shape = arrays[0].shape
    if any(array.shape != shape for array in arrays):
        raise ContractError("Component shapes differ before composition")
    composite = arrays[0].copy()
    for array in arrays[1:]:
        composite = np.add(composite, array, dtype=np.float64)
    return composite
