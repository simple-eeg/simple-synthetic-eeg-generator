"""Preregistered, candidate-independent generator validation gates."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable

from .errors import ContractError, ValidationError
from .model import SubjectResult, canonical_array_bytes, compose_float64
from .oracle import reconstruct_analytic_components


def _scientific_modules():
    try:
        import numpy as np
        from scipy.signal import periodogram, welch
    except ImportError as exc:
        raise ContractError("The locked NumPy and SciPy dependencies are required") from exc
    return np, welch, periodogram


def _fail(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _event_window(array: Any, event_zero: int, fs: int, start: float, end: float):
    start_index = event_zero + int(round(start * fs))
    end_index = event_zero + int(round(end * fs))
    if start_index < 0 or end_index >= array.size or end_index < start_index:
        raise ValidationError("Requested event-relative validation window is outside the record")
    return array[start_index : end_index + 1]


def _baseline_corrected_epoch(array: Any, event_zero: int, fs: int, gate: dict[str, Any]):
    """Return exact inclusive [-200,+1000] ms after half-open [-200,0) baseline."""

    np, _, _ = _scientific_modules()
    epoch_start, epoch_end = map(float, gate["epoch_window_seconds"])
    baseline_start, baseline_end = map(float, gate["baseline_window_seconds"])
    _fail(gate["window_endpoints_inclusive"] is True, "Response windows must be inclusive")
    _fail(gate["baseline_end_inclusive"] is False, "Baseline end must be exclusive")
    epoch = _event_window(array, event_zero, fs, epoch_start, epoch_end).astype(np.float64, copy=True)
    expected_epoch_count = int(round((epoch_end - epoch_start) * fs)) + 1
    _fail(epoch.size == expected_epoch_count == 1201, "Raw validation epoch must have exactly 1201 samples")
    baseline_first = event_zero + int(round(baseline_start * fs))
    baseline_stop = event_zero + int(round(baseline_end * fs))
    baseline = np.asarray(array[baseline_first:baseline_stop], dtype=np.float64)
    _fail(baseline.size == 200, "Half-open baseline must contain exactly 200 samples")
    return epoch - float(np.mean(baseline))


def _relative_epoch_window(epoch: Any, fs: int, epoch_start: float, start: float, end: float):
    first = int(round((start - epoch_start) * fs))
    last = int(round((end - epoch_start) * fs))
    selected = epoch[first : last + 1]
    expected = int(round((end - start) * fs)) + 1
    _fail(selected.size == expected, "Inclusive response validation window has wrong sample count")
    return selected


def _band_power(array: Any, fs: int, gate: dict[str, Any], periodogram: Any, np: Any) -> float:
    frequencies, power = periodogram(
        array,
        fs=fs,
        window=gate["window"],
        nfft=int(gate["nfft"]),
        detrend=gate["detrend"],
        scaling=gate["scaling"],
        return_onesided=True,
    )
    low, high = map(float, gate["band_hz"])
    selected = (frequencies >= low) & (frequencies <= high)
    _fail(int(np.count_nonzero(selected)) >= 2, "Spectral band contains too few frequency bins")
    value = float(np.trapezoid(power[selected], frequencies[selected]))
    _fail(math.isfinite(value) and value > 0.0, "Spectral band power is not finite and positive")
    return value


def validate_subject(result: SubjectResult, settings: dict[str, Any]) -> dict[str, float]:
    np, welch, _ = _scientific_modules()
    dataset = settings["dataset"]
    gates = settings["validation"]
    fs = int(dataset["sample_rate_hz"])
    count = int(dataset["sample_count"])
    _fail(result.subject_id in dataset["subject_ids"], "Unexpected subject identity")
    _fail(result.composite_float64.shape == (count,), "Composite shape is not exact")
    _fail(result.staged_float32.shape == (count,), "Staged array shape is not exact")
    _fail(result.staged_float32.dtype == np.dtype("<f4"), "Staged dtype is not little-endian float32")
    _fail(bool(np.all(np.isfinite(result.composite_float64))), "Composite contains nonfinite values")
    _fail(bool(np.all(np.isfinite(result.staged_float32))), "Staged array contains nonfinite values")

    expected_composite = compose_float64(result.components["background_scaled"], result.components)
    _fail(
        bool(np.array_equal(result.composite_float64, expected_composite)),
        "Composite is not the exact ordered float64 component sum",
    )
    expected_staged = np.asarray(expected_composite, dtype="<f4")
    _fail(
        bool(np.array_equal(result.staged_float32, expected_staged)),
        "Staged samples are not the one final direct little-endian float32 cast",
    )

    background = result.components["background_normalised"]
    mean = float(np.mean(background))
    sample_sd = float(np.std(background, ddof=1))
    _fail(abs(mean) <= float(gates["background_mean_atol"]), "Normalised background mean gate failed")
    _fail(
        abs(sample_sd - 1.0) <= float(gates["background_sample_sd_atol"]),
        "Normalised background sample-SD gate failed",
    )

    psd_gate = gates["background_psd"]
    frequencies, power = welch(
        background,
        fs=fs,
        window=psd_gate["window"],
        nperseg=int(psd_gate["nperseg"]),
        noverlap=int(psd_gate["noverlap"]),
        detrend=psd_gate["detrend"],
        scaling=psd_gate["scaling"],
        average=psd_gate["average"],
    )
    low, high = map(float, psd_gate["frequency_hz"])
    selected = (frequencies >= low) & (frequencies <= high) & (power > 0.0)
    _fail(int(np.count_nonzero(selected)) >= 3, "Background PSD slope has too few valid bins")
    slope = float(np.polyfit(np.log10(frequencies[selected]), np.log10(power[selected]), 1)[0])
    slope_error = abs(slope + result.parameters["chi"].realised)
    _fail(
        slope_error <= float(psd_gate["individual_slope_error_max"]),
        f"Subject {result.subject_id} background slope error exceeded preregistered maximum",
    )

    realised = {name: draw.realised for name, draw in result.parameters.items()}
    oracle = reconstruct_analytic_components(result.subject_id, settings, realised)
    oracle_max = 0.0
    for name in ("early_negative", "late_positive", "spectral", "artifact"):
        difference = float(np.max(np.abs(result.components[name] - oracle[name])))
        oracle_max = max(oracle_max, difference)
        _fail(
            difference <= float(gates["analytic_component_atol_uv"]),
            f"Subject {result.subject_id} {name} differs from independent oracle",
        )

    event_zero = int(dataset["event_latency_eeglab"]) - 1
    offsets = np.arange(count, dtype=np.int64) - event_zero
    for name, spec in (
        ("spectral", settings["signal"]["spectral"]),
        ("artifact", settings["signal"]["artifact"]),
    ):
        component = result.components[name]
        if name == "artifact" and result.subject_id != spec["subject_id"]:
            _fail(bool(np.all(component == 0.0)), "Non-artifact subject has an artefact component")
            continue
        start = int(round(float(spec["start_seconds"]) * fs))
        end = int(round(float(spec["end_seconds"]) * fs))
        outside = (offsets < start) | (offsets > end)
        _fail(
            bool(np.all(np.abs(component[outside]) <= float(gates["support_atol_uv"]))),
            f"Subject {result.subject_id} {name} is nonzero outside declared support",
        )

    float32_bytes = canonical_array_bytes(result.staged_float32, "float32")
    reloaded = np.frombuffer(float32_bytes, dtype="<f4")
    _fail(bool(np.array_equal(reloaded, result.staged_float32)), "Float32 canonical byte round trip failed")
    return {
        "background_mean": mean,
        "background_sample_sd": sample_sd,
        "background_psd_slope": slope,
        "background_psd_slope_error": slope_error,
        "analytic_oracle_max_abs_error_uv": oracle_max,
    }


def validate_cohort(results: Iterable[SubjectResult], settings: dict[str, Any]) -> dict[str, Any]:
    np, _, periodogram = _scientific_modules()
    ordered = list(results)
    dataset = settings["dataset"]
    gates = settings["validation"]
    expected_ids = list(dataset["subject_ids"])
    _fail([item.subject_id for item in ordered] == expected_ids, "Cohort IDs or order differ from 001..031")
    per_subject = {item.subject_id: validate_subject(item, settings) for item in ordered}
    slope_errors = [per_subject[item.subject_id]["background_psd_slope_error"] for item in ordered]
    median_slope_error = float(np.median(slope_errors))
    _fail(
        median_slope_error <= float(gates["background_psd"]["median_slope_error_max"]),
        "Cohort median PSD-slope error gate failed",
    )

    fs = int(dataset["sample_rate_hz"])
    true_zero = int(dataset["event_latency_eeglab"]) - 1
    reference_zero = int(round(gates["group_response"]["reference_event_time_seconds"] * fs))
    early_window = gates["group_response"]["early_window_seconds"]
    late_window = gates["group_response"]["late_window_seconds"]
    ordinary = ordered[: int(gates["group_response"]["ordinary_subject_count"])]
    early_differences: list[float] = []
    late_differences: list[float] = []
    sd_ratios: list[float] = []
    power_ratios: list[float] = []
    positive_power_pairs = 0
    spectral_gate = gates["spectral_power"]
    spectral_window = spectral_gate["window_seconds"]
    epoch_maxima: dict[str, dict[str, float]] = {}

    for result in ordered:
        signal = result.staged_float32.astype(np.float64)
        true_epoch = _event_window(signal, true_zero, fs, -0.2, 1.0)
        reference_epoch = _event_window(signal, reference_zero, fs, -0.2, 1.0)
        epoch_maxima[result.subject_id] = {
            "true": float(np.max(np.abs(true_epoch))),
            "reference": float(np.max(np.abs(reference_epoch))),
        }

    for result in ordinary:
        signal = result.staged_float32.astype(np.float64)
        response_gate = gates["group_response"]
        true_epoch_bc = _baseline_corrected_epoch(signal, true_zero, fs, response_gate)
        reference_epoch_bc = _baseline_corrected_epoch(signal, reference_zero, fs, response_gate)
        epoch_start = float(response_gate["epoch_window_seconds"][0])
        early_true = _relative_epoch_window(true_epoch_bc, fs, epoch_start, *early_window)
        early_reference = _relative_epoch_window(reference_epoch_bc, fs, epoch_start, *early_window)
        late_true = _relative_epoch_window(true_epoch_bc, fs, epoch_start, *late_window)
        late_reference = _relative_epoch_window(reference_epoch_bc, fs, epoch_start, *late_window)
        early_differences.append(float(np.mean(early_true) - np.mean(early_reference)))
        late_differences.append(float(np.mean(late_true) - np.mean(late_reference)))
        ratio = float(np.std(signal, ddof=1) / result.parameters["sigma_uv"].realised)
        sd_ratios.append(ratio)
        low_ratio, high_ratio = map(float, gates["ordinary_whole_record_sd_ratio"])
        _fail(low_ratio <= ratio <= high_ratio, f"Subject {result.subject_id} whole-record SD ratio failed")

        true_spectral = _event_window(signal, true_zero, fs, *spectral_window)
        reference_spectral = _event_window(signal, reference_zero, fs, *spectral_window)
        true_power = _band_power(true_spectral, fs, spectral_gate, periodogram, np)
        reference_power = _band_power(reference_spectral, fs, spectral_gate, periodogram, np)
        power_ratios.append(true_power / reference_power)
        if true_power > reference_power:
            positive_power_pairs += 1

    early_group = float(np.mean(early_differences))
    late_group = float(np.mean(late_differences))
    _fail(
        early_group <= float(gates["group_response"]["early_mean_difference_max_uv"]),
        "Group early true-minus-reference mean gate failed",
    )
    _fail(
        late_group >= float(gates["group_response"]["late_mean_difference_min_uv"]),
        "Group late true-minus-reference mean gate failed",
    )
    median_power_ratio = float(np.median(power_ratios))
    _fail(
        median_power_ratio >= float(spectral_gate["minimum_ratio_median"]),
        "Median 9-11-Hz true/reference power-ratio gate failed",
    )
    _fail(
        positive_power_pairs >= int(spectral_gate["minimum_positive_pairs"]),
        "Too few positive paired 9-11-Hz power differences",
    )

    artifact_max = epoch_maxima["031"]["true"]
    ordinary_maxima = [
        values[event]
        for subject_id, values in epoch_maxima.items()
        for event in ("true", "reference")
        if not (subject_id == "031" and event == "true")
    ]
    next_largest = max(ordinary_maxima)
    _fail(artifact_max >= float(gates["artifact_min_absolute_uv"]), "Subject 31 artefact amplitude gate failed")
    _fail(
        next_largest <= float(gates["ordinary_epoch_max_absolute_uv"]),
        "An ordinary true/reference epoch exceeded the preregistered maximum",
    )
    _fail(
        artifact_max >= float(gates["artifact_min_next_largest_ratio"]) * next_largest,
        "Subject 31 is not at least twice the next-largest epoch",
    )
    return {
        "schema": "simple-synthetic-python-validation-v1",
        "status": "passed",
        "subject_count": len(ordered),
        "per_subject": per_subject,
        "cohort": {
            "median_background_psd_slope_error": median_slope_error,
            "early_true_minus_reference_mean_uv": early_group,
            "late_true_minus_reference_mean_uv": late_group,
            "median_true_reference_9_11_hz_power_ratio": median_power_ratio,
            "positive_9_11_hz_power_pairs": positive_power_pairs,
            "ordinary_whole_record_sd_ratio_min": min(sd_ratios),
            "ordinary_whole_record_sd_ratio_max": max(sd_ratios),
            "subject_031_true_epoch_max_absolute_uv": artifact_max,
            "next_largest_epoch_max_absolute_uv": next_largest,
        },
    }


def validate_staged_array(path: Path, expected: SubjectResult, sample_count: int) -> None:
    np, _, _ = _scientific_modules()
    _fail(path.is_file() and not path.is_symlink(), f"Missing regular staged array: {path.name}")
    expected_bytes = sample_count * 4
    _fail(path.stat().st_size == expected_bytes, f"Staged array byte count differs: {path.name}")
    actual = np.fromfile(path, dtype="<f4")
    _fail(actual.size == sample_count, f"Staged array sample count differs: {path.name}")
    _fail(bool(np.array_equal(actual, expected.staged_float32)), f"Staged array values differ: {path.name}")
