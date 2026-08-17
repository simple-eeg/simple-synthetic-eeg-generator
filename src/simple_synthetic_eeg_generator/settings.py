"""Load and enforce the approved scientific recipe and input contract."""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import canonical_json_bytes
from .errors import ContractError
from .seeds import DOMAIN, MASTER_SEED, MASTER_SEED_HEX

SCHEMA = "simple-synthetic-generator-settings-v3"
EXPECTED_SUBJECTS = tuple(f"{index:03d}" for index in range(1, 32))
SIMPLE_INPUT_CONTRACT = "simple-synthetic-input-v1"
TESTED_SIMPLE_COMMIT = "7d31744d46ddba1bf11c686825e3420fb8328d19"
RECIPE_SHA256 = "0ec28e6841fdbf2e1cbffdd6932880e96b5a0f1ad8f69cda716bbe2ce5eda2d3"


@dataclass(frozen=True)
class FrozenSettings:
    source_path: Path
    values: dict[str, Any]

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.values)

    @property
    def subjects(self) -> tuple[str, ...]:
        return tuple(self.values["dataset"]["subject_ids"])


def _require_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ContractError(f"Frozen setting {label} must be {expected!r}, got {actual!r}")


def _require_keys(mapping: dict[str, Any], expected: set[str], label: str) -> None:
    keys = set(mapping)
    if keys != expected:
        raise ContractError(
            f"{label} keys differ; missing={sorted(expected - keys)!r}, "
            f"unexpected={sorted(keys - expected)!r}"
        )


def validate_frozen_settings(values: dict[str, Any]) -> None:
    """Fail closed if any structural identity central to the freeze changes."""

    _require_keys(
        values,
        {
            "schema",
            "build",
            "compatibility",
            "dataset",
            "provenance",
            "seed",
            "signal",
            "validation",
        },
        "top-level settings",
    )
    _require_equal(values["schema"], SCHEMA, "schema")
    dataset = values["dataset"]
    _require_equal(tuple(dataset["subject_ids"]), EXPECTED_SUBJECTS, "subject_ids")
    _require_equal(dataset["session_id"], "01", "session_id")
    _require_equal(dataset["run_id"], "01", "run_id")
    _require_equal(dataset["duration_seconds"], 30.0, "duration_seconds")
    _require_equal(dataset["sample_count"], 30000, "sample_count")
    _require_equal(dataset["sample_rate_hz"], 1000.0, "sample_rate_hz")
    _require_equal(dataset["channel"], "Cz", "channel")
    _require_equal(dataset["event_label"], "stimulus", "event_label")
    _require_equal(dataset["event_time_seconds"], 15.0, "event_time_seconds")
    _require_equal(dataset["event_latency_eeglab"], 15001, "event_latency_eeglab")

    seed = values["seed"]
    _require_equal(seed["master_decimal"], MASTER_SEED, "master_decimal")
    _require_equal(seed["master_hex"], MASTER_SEED_HEX, "master_hex")
    _require_equal(seed["derivation_domain"], DOMAIN, "derivation_domain")
    _require_equal(seed["digest"], "SHA-256", "seed digest")
    _require_equal(seed["numpy_bit_generator"], "PCG64DXSM", "NumPy bit generator")

    compatibility = values["compatibility"]
    _require_keys(
        compatibility,
        {"simple_input_contract", "tested_simple_commit"},
        "compatibility settings",
    )
    _require_equal(
        compatibility["simple_input_contract"],
        SIMPLE_INPUT_CONTRACT,
        "SIMPLE input contract",
    )
    _require_equal(
        compatibility["tested_simple_commit"],
        TESTED_SIMPLE_COMMIT,
        "tested SIMPLE commit",
    )

    signal = values["signal"]
    _require_equal(
        signal["composition"],
        {
            "dtype": "float64",
            "order": ["background_scaled", "early_negative", "late_positive", "spectral", "artifact"],
            "staging_cast": "one final little-endian float32 cast",
        },
        "signal composition",
    )
    _require_equal(signal["artifact"]["subject_id"], "031", "artifact subject")
    _require_equal(signal["artifact"]["amplitude_uv"], 120.0, "artifact amplitude")
    _require_equal(signal["artifact"]["frequency_hz"], 20.0, "artifact frequency")
    _require_equal(signal["artifact"]["start_seconds"], 0.3, "artifact start")
    _require_equal(signal["artifact"]["end_seconds"], 0.5, "artifact end")
    _require_equal(signal["artifact"]["tukey_alpha"], 0.5, "artifact Tukey alpha")

    validation = values["validation"]
    _require_equal(
        validation["mixed_signal_source"],
        "staged_float32_promoted_to_float64",
        "mixed-signal validation source",
    )
    expected_gates = {
        "analytic_component_atol_uv": 1e-12,
        "artifact_min_absolute_uv": 80.0,
        "artifact_min_next_largest_ratio": 2.0,
        "background_mean_atol": 1e-12,
        "background_sample_sd_atol": 1e-12,
        "ordinary_epoch_max_absolute_uv": 60.0,
        "support_atol_uv": 0.0,
    }
    for name, expected in expected_gates.items():
        _require_equal(validation[name], expected, f"validation.{name}")
    _require_equal(validation["ordinary_whole_record_sd_ratio"], [0.9, 1.1], "ordinary SD ratio")


def load_settings(path: Path) -> FrozenSettings:
    if not path.is_file() or path.is_symlink():
        raise ContractError("Settings path must be one existing regular file")
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"Cannot read settings JSON: {exc}") from exc
    if not isinstance(values, dict):
        raise ContractError("Settings root must be a JSON object")
    validate_frozen_settings(values)
    actual_digest = hashlib.sha256(canonical_json_bytes(values)).hexdigest()
    if actual_digest != RECIPE_SHA256:
        raise ContractError(
            "Settings differ from the complete approved scientific recipe: "
            f"expected {RECIPE_SHA256}, got {actual_digest}"
        )
    return FrozenSettings(source_path=path, values=values)
