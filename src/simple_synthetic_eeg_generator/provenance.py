"""Machine-readable provenance records for the immutable Python stage."""

from __future__ import annotations

import math
from typing import Any, Iterable

from .model import SubjectResult, canonical_array_bytes, component_sha256
from .seeds import DOMAIN, MASTER_SEED

PARAMETER_ORDER = (
    "chi",
    "sigma_uv",
    "response_multiplier",
    "response_delay_seconds",
    "response_width_multiplier",
    "spectral_amplitude_uv",
    "spectral_frequency_hz",
    "spectral_phase_radians",
)

CANONICAL_CAUSAL_SEED_STREAM_ORDER = (
    "background",
    "chi",
    "sigma",
    "response_scale",
    "response_latency",
    "response_width",
    "burst_amplitude",
    "burst_frequency",
    "burst_phase",
)

COMPONENT_CAUSAL_STREAMS = {
    "aperiodic_raw": ("background", "chi"),
    "background_normalised": ("background", "chi"),
    "background_scaled": ("background", "chi", "sigma"),
    "early_negative": ("response_scale", "response_latency", "response_width"),
    "late_positive": ("response_scale", "response_latency", "response_width"),
    "spectral": ("burst_amplitude", "burst_frequency", "burst_phase"),
    "artifact": (),
    "composite_float64": CANONICAL_CAUSAL_SEED_STREAM_ORDER,
    "staged_float32": CANONICAL_CAUSAL_SEED_STREAM_ORDER,
}


def float_text(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("Provenance floats must be finite")
    return format(value, ".17g")


def realised_parameter_fields() -> list[str]:
    fields = ["subjectID", "sessionID", "runID"]
    for name in PARAMETER_ORDER:
        fields.extend(
            [
                f"{name}_raw",
                f"{name}_realised",
                f"{name}_seed_sha256",
                f"{name}_seed128",
                f"{name}_seed32",
            ]
        )
    fields.extend(
        [
            "background_seed_sha256",
            "background_seed128",
            "background_seed32",
            "background_normalised_mean",
            "background_normalised_sample_sd",
            "composite_float64_sha256",
            "staged_float32_sha256",
        ]
    )
    return fields


def realised_parameter_row(result: SubjectResult) -> dict[str, object]:
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("NumPy is required for producing provenance") from exc
    row: dict[str, object] = {
        "subjectID": result.subject_id,
        "sessionID": "01",
        "runID": "01",
    }
    for name in PARAMETER_ORDER:
        draw = result.parameters[name]
        row[f"{name}_raw"] = float_text(draw.raw)
        row[f"{name}_realised"] = float_text(draw.realised)
        row[f"{name}_seed_sha256"] = draw.seed.sha256
        row[f"{name}_seed128"] = str(draw.seed.seed128)
        row[f"{name}_seed32"] = str(draw.seed.seed32)
    background_seed = result.seeds["background"]
    row.update(
        {
            "background_seed_sha256": background_seed.sha256,
            "background_seed128": str(background_seed.seed128),
            "background_seed32": str(background_seed.seed32),
            "background_normalised_mean": float_text(
                float(np.mean(result.components["background_normalised"]))
            ),
            "background_normalised_sample_sd": float_text(
                float(np.std(result.components["background_normalised"], ddof=1))
            ),
            "composite_float64_sha256": component_sha256(result.composite_float64),
            "staged_float32_sha256": __import__("hashlib").sha256(
                canonical_array_bytes(result.staged_float32, "float32")
            ).hexdigest(),
        }
    )
    return row


def ground_truth_fields() -> list[str]:
    return [
        "subjectID",
        "sessionID",
        "runID",
        "component",
        "units",
        "dtype",
        "byte_order",
        "sample_count",
        "sha256",
        "causal_seed_sha256_list",
        "declared_support_start_seconds",
        "declared_support_end_seconds",
    ]


def causal_seed_sha256_lists(result: SubjectResult) -> dict[str, str]:
    """Return exact, canonically ordered causal seed lists for every component."""

    by_stream = {seed.stream: seed for seed in result.seeds.values()}
    expected = set(CANONICAL_CAUSAL_SEED_STREAM_ORDER)
    if set(by_stream) != expected or len(by_stream) != len(result.seeds):
        raise ValueError("Subject result must contain each of the nine canonical seed streams once")
    if any(seed.subject_id != result.subject_id for seed in by_stream.values()):
        raise ValueError("Subject result contains a seed belonging to another subject")
    digests = [by_stream[stream].sha256 for stream in CANONICAL_CAUSAL_SEED_STREAM_ORDER]
    if len(set(digests)) != len(digests):
        raise ValueError("Subject result contains duplicate canonical seed digests")
    return {
        component: ";".join(by_stream[stream].sha256 for stream in streams)
        for component, streams in COMPONENT_CAUSAL_STREAMS.items()
    }


def ground_truth_rows(result: SubjectResult, settings: dict[str, Any]) -> list[dict[str, object]]:
    spectral = settings["signal"]["spectral"]
    artifact = settings["signal"]["artifact"]
    rows: list[dict[str, object]] = []
    causal_seeds = causal_seed_sha256_lists(result)
    components = [
        ("aperiodic_raw", result.components["aperiodic_raw"], causal_seeds["aperiodic_raw"], "", ""),
        (
            "background_normalised",
            result.components["background_normalised"],
            causal_seeds["background_normalised"],
            "",
            "",
        ),
        (
            "background_scaled",
            result.components["background_scaled"],
            causal_seeds["background_scaled"],
            "",
            "",
        ),
        ("early_negative", result.components["early_negative"], causal_seeds["early_negative"], "", ""),
        ("late_positive", result.components["late_positive"], causal_seeds["late_positive"], "", ""),
        (
            "spectral",
            result.components["spectral"],
            causal_seeds["spectral"],
            float_text(float(spectral["start_seconds"])),
            float_text(float(spectral["end_seconds"])),
        ),
        (
            "artifact",
            result.components["artifact"],
            causal_seeds["artifact"],
            float_text(float(artifact["start_seconds"])),
            float_text(float(artifact["end_seconds"])),
        ),
        (
            "composite_float64",
            result.composite_float64,
            causal_seeds["composite_float64"],
            "",
            "",
        ),
    ]
    for name, array, seed_sha, support_start, support_end in components:
        rows.append(
            {
                "subjectID": result.subject_id,
                "sessionID": "01",
                "runID": "01",
                "component": name,
                "units": "unitless" if name in {"aperiodic_raw", "background_normalised"} else "microvolts",
                "dtype": "float64",
                "byte_order": "little",
                "sample_count": str(array.size),
                "sha256": component_sha256(array),
                "causal_seed_sha256_list": seed_sha,
                "declared_support_start_seconds": support_start,
                "declared_support_end_seconds": support_end,
            }
        )
    rows.append(
        {
            "subjectID": result.subject_id,
            "sessionID": "01",
            "runID": "01",
            "component": "staged_float32",
            "units": "microvolts",
            "dtype": "float32",
            "byte_order": "little",
            "sample_count": str(result.staged_float32.size),
            "sha256": __import__("hashlib").sha256(
                canonical_array_bytes(result.staged_float32, "float32")
            ).hexdigest(),
            "causal_seed_sha256_list": causal_seeds["staged_float32"],
            "declared_support_start_seconds": "",
            "declared_support_end_seconds": "",
        }
    )
    return rows


def dataset_list_rows(subject_ids: Iterable[str]) -> list[dict[str, str]]:
    rows = []
    for subject_id in subject_ids:
        rows.append(
            {
                "subjectID": subject_id,
                "sessionID": "01",
                "runID": "01",
                "path_raw": f"data/raw/sub-{subject_id}/ses-01/eeg",
                "EEGfile_raw": f"sub-{subject_id}_ses-01_run-01_eeg.set",
            }
        )
    return rows


def seed_manifest_fields() -> list[str]:
    return [
        "subjectID",
        "sessionID",
        "runID",
        "derivation_domain",
        "master_decimal",
        "stream",
        "seed_sha256",
        "seed128",
        "seed32",
        "draw_raw",
        "draw_realised",
    ]


def seed_manifest_rows(results: Iterable[SubjectResult]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for result in results:
        draws = {draw.seed.stream: draw for draw in result.parameters.values()}
        seeds = {seed.stream: seed for seed in result.seeds.values()}
        if set(seeds) != {
            "background", "chi", "sigma", "response_scale", "response_latency",
            "response_width", "burst_amplitude", "burst_frequency", "burst_phase",
        }:
            raise ValueError(f"Subject {result.subject_id} seed streams are not exact")
        for stream in sorted(seeds):
            seed = seeds[stream]
            draw = draws.get(stream)
            rows.append(
                {
                    "subjectID": result.subject_id,
                    "sessionID": "01",
                    "runID": "01",
                    "derivation_domain": DOMAIN,
                    "master_decimal": str(MASTER_SEED),
                    "stream": stream,
                    "seed_sha256": seed.sha256,
                    "seed128": str(seed.seed128),
                    "seed32": str(seed.seed32),
                    "draw_raw": "" if draw is None else float_text(draw.raw),
                    "draw_realised": "" if draw is None else float_text(draw.realised),
                }
            )
    if len(rows) != 31 * 9:
        raise ValueError("Seed manifest must contain exactly 31 x 9 rows")
    digests = [str(row["seed_sha256"]) for row in rows]
    if len(set(digests)) != len(digests):
        raise ValueError("Every subject/stream digest must be unique")
    background_seed32 = [str(row["seed32"]) for row in rows if row["stream"] == "background"]
    if len(background_seed32) != 31 or len(set(background_seed32)) != 31:
        raise ValueError("All 31 NeuroDSP background seed32 values must be unique")
    return rows
