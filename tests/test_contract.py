from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from simple_synthetic_eeg_generator.canonical import (
    build_manifest,
    canonical_csv_bytes,
    canonical_json_bytes,
    verify_manifest,
    write_new_bytes,
)
from simple_synthetic_eeg_generator.errors import ContractError
from simple_synthetic_eeg_generator.provenance import (
    CANONICAL_CAUSAL_SEED_STREAM_ORDER,
    COMPONENT_CAUSAL_STREAMS,
    causal_seed_sha256_lists,
    dataset_list_rows,
    ground_truth_rows,
    seed_manifest_rows,
)
from simple_synthetic_eeg_generator.model import SubjectResult
from simple_synthetic_eeg_generator.seeds import MASTER_SEED, STREAMS, derive_seed
from simple_synthetic_eeg_generator.settings import (
    EXPECTED_SUBJECTS,
    RECIPE_SHA256,
    SIMPLE_INPUT_CONTRACT,
    TESTED_SIMPLE_COMMIT,
    load_settings,
    validate_frozen_settings,
)

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "config" / "generator_settings.json"


class FrozenContractTests(unittest.TestCase):
    @staticmethod
    def synthetic_subject_result(subject_id: str) -> SubjectResult:
        import numpy as np
        from simple_synthetic_eeg_generator.model import RealisedDraw

        seeds_by_stream = {
            stream: derive_seed(subject_id, stream)
            for stream in CANONICAL_CAUSAL_SEED_STREAM_ORDER
        }
        parameter_streams = {
            "chi": "chi",
            "sigma_uv": "sigma",
            "response_multiplier": "response_scale",
            "response_delay_seconds": "response_latency",
            "response_width_multiplier": "response_width",
            "spectral_amplitude_uv": "burst_amplitude",
            "spectral_frequency_hz": "burst_frequency",
            "spectral_phase_radians": "burst_phase",
        }
        parameters = {
            name: RealisedDraw(0.0, 0.0, seeds_by_stream[stream])
            for name, stream in parameter_streams.items()
        }
        array = np.zeros(1, dtype=np.float64)
        return SubjectResult(
            subject_id=subject_id,
            parameters=parameters,
            seeds={
                **{name: draw.seed for name, draw in parameters.items()},
                "background": seeds_by_stream["background"],
            },
            components={
                name: array.copy()
                for name in (
                    "aperiodic_raw", "background_normalised", "background_scaled",
                    "early_negative", "late_positive", "spectral", "artifact",
                )
            },
            composite_float64=array.copy(),
            staged_float32=array.astype("<f4"),
        )

    def test_software_and_dataset_license_assets_are_exact(self) -> None:
        self.assertEqual((ROOT / "LICENSE").stat().st_size, 11357)
        self.assertEqual(
            hashlib.sha256((ROOT / "LICENSE").read_bytes()).hexdigest(),
            "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4",
        )
        self.assertEqual((ROOT / "dataset_assets/CC-BY-4.0.txt").stat().st_size, 18656)
        self.assertEqual(
            hashlib.sha256((ROOT / "dataset_assets/CC-BY-4.0.txt").read_bytes()).hexdigest(),
            "9e5f1b3c610b9c2da5c313bf81d577a7d1acec686bdb0384edefa6df0f90cd94",
        )
        citation = (ROOT / "dataset_assets/CITATION.cff").read_text(encoding="utf-8")
        self.assertIn("license: CC-BY-4.0", citation)

    def test_settings_are_complete_canonical_freeze(self) -> None:
        settings = load_settings(SETTINGS)
        self.assertEqual(
            hashlib.sha256(settings.canonical_bytes).hexdigest(),
            RECIPE_SHA256,
        )
        self.assertEqual(settings.subjects, EXPECTED_SUBJECTS)
        self.assertEqual(
            settings.values["compatibility"]["tested_simple_commit"],
            TESTED_SIMPLE_COMMIT,
        )
        self.assertEqual(
            settings.values["compatibility"]["simple_input_contract"],
            SIMPLE_INPUT_CONTRACT,
        )

    def test_unexpected_compatibility_identity_is_rejected(self) -> None:
        values = json.loads(SETTINGS.read_text(encoding="utf-8"))
        values["compatibility"]["unexpected_repository_commit"] = "0" * 40
        with self.assertRaises(ContractError):
            validate_frozen_settings(values)

    def test_settings_schema_has_one_exact_compatibility_shape(self) -> None:
        schema = json.loads(
            (ROOT / "config/generator_settings.schema.json").read_text(encoding="utf-8")
        )
        compatibility = schema["properties"]["compatibility"]
        self.assertFalse(compatibility["additionalProperties"])
        self.assertEqual(set(compatibility["required"]), set(compatibility["properties"]))
        self.assertEqual(
            set(compatibility["properties"]),
            set(load_settings(SETTINGS).values["compatibility"]),
        )
        self.assertEqual(
            compatibility["properties"]["tested_simple_commit"]["const"],
            TESTED_SIMPLE_COMMIT,
        )

    def test_any_nested_settings_change_is_rejected_by_digest(self) -> None:
        values = json.loads(SETTINGS.read_text(encoding="utf-8"))
        changed = copy.deepcopy(values)
        changed["validation"]["background_psd"]["average"] = "median"
        validate_frozen_settings(changed)  # subset validation is not the identity gate
        self.assertNotEqual(
            hashlib.sha256(canonical_json_bytes(changed)).hexdigest(),
            RECIPE_SHA256,
        )

    def test_known_seed_vectors(self) -> None:
        chi = derive_seed("001", "chi")
        self.assertEqual(
            chi.sha256,
            "73bd8639c8c7b5bd2ca69ef098a32b8719a30219771d92a3c9d5d03aaa4e07a1",
        )
        self.assertEqual(chi.seed128, 153845286042558996882991915529744362375)
        self.assertEqual(chi.seed32, 1941800505)
        background = derive_seed("031", "background")
        self.assertEqual(
            background.sha256,
            "00078165188e91baef11a74ef8526dfb1c44591ab14214d189f72382bf94a564",
        )
        self.assertEqual(background.seed128, 38970518493024693141206425679326715)
        self.assertEqual(background.seed32, 491877)
        first_background = derive_seed("001", "background")
        self.assertEqual(
            first_background.sha256,
            "403225630e7202f17d8549aeeb30914d830a753f65d387328e94933dcbf42e8c",
        )
        self.assertEqual(first_background.seed128, 85330964870375402851623187117170004301)
        self.assertEqual(first_background.seed32, 1077028195)
        last_phase = derive_seed("031", "burst_phase")
        self.assertEqual(
            last_phase.sha256,
            "df85b66e235c14cc7ecb58ee5c3a6646ef2007736b012da1fa9004d8495ad5d1",
        )
        self.assertEqual(last_phase.seed128, 297112118666810407643991389912788788806)
        self.assertEqual(last_phase.seed32, 3750082158)

    def test_exact_seed_payload_and_uniqueness(self) -> None:
        expected_payload = (
            "simple-synthetic-eeg-generator/v1\n"
            f"master={MASTER_SEED}\n"
            "subject=001\n"
            "stream=chi\n"
        ).encode("utf-8")
        self.assertEqual(hashlib.sha256(expected_payload).hexdigest(), derive_seed("001", "chi").sha256)
        seeds = [derive_seed(subject, stream) for subject in EXPECTED_SUBJECTS for stream in sorted(STREAMS)]
        self.assertEqual(len(seeds), 31 * 9)
        self.assertEqual(len({seed.sha256 for seed in seeds}), 31 * 9)
        backgrounds = [derive_seed(subject, "background").seed32 for subject in EXPECTED_SUBJECTS]
        self.assertEqual(len(set(backgrounds)), 31)

    def test_seed_inputs_fail_closed(self) -> None:
        for subject, stream in (("1", "chi"), ("001", "unknown"), ("001 ", "chi")):
            with self.subTest(subject=subject, stream=stream), self.assertRaises(ContractError):
                derive_seed(subject, stream)

    def test_exact_dataset_list_contract(self) -> None:
        rows = dataset_list_rows(EXPECTED_SUBJECTS)
        self.assertEqual(len(rows), 31)
        self.assertEqual(list(rows[0]), ["subjectID", "sessionID", "runID", "path_raw", "EEGfile_raw"])
        self.assertEqual(
            rows[0],
            {
                "subjectID": "001",
                "sessionID": "01",
                "runID": "01",
                "path_raw": "data/raw/sub-001/ses-01/eeg",
                "EEGfile_raw": "sub-001_ses-01_run-01_eeg.set",
            },
        )
        self.assertEqual(rows[-1]["subjectID"], "031")

    @unittest.skipUnless(__import__("importlib").util.find_spec("numpy"), "NumPy is absent")
    def test_ground_truth_causal_seed_lists_are_exact_and_cross_manifest_bound(self) -> None:
        settings = load_settings(SETTINGS).values
        results = [self.synthetic_subject_result(subject_id) for subject_id in EXPECTED_SUBJECTS]
        manifest_rows = seed_manifest_rows(results)
        manifest_by_subject = {
            subject_id: {
                row["stream"]: row["seed_sha256"]
                for row in manifest_rows
                if row["subjectID"] == subject_id
            }
            for subject_id in EXPECTED_SUBJECTS
        }
        for result in results:
            subject_id = result.subject_id
            with self.subTest(subject_id=subject_id):
                by_stream = manifest_by_subject[subject_id]
                self.assertEqual(set(by_stream), set(CANONICAL_CAUSAL_SEED_STREAM_ORDER))
                self.assertEqual(len(by_stream), 9)
                self.assertEqual(len(set(by_stream.values())), 9)

                expected = {
                    component: [by_stream[stream] for stream in streams]
                    for component, streams in COMPONENT_CAUSAL_STREAMS.items()
                }
                causal = causal_seed_sha256_lists(result)
                self.assertEqual(
                    {component: ([] if not value else value.split(";")) for component, value in causal.items()},
                    expected,
                )
                rows = ground_truth_rows(result, settings)
                self.assertEqual(len(rows), len(COMPONENT_CAUSAL_STREAMS))
                self.assertEqual(
                    {row["component"] for row in rows},
                    set(COMPONENT_CAUSAL_STREAMS),
                )
                for row in rows:
                    listed = (
                        []
                        if not row["causal_seed_sha256_list"]
                        else str(row["causal_seed_sha256_list"]).split(";")
                    )
                    self.assertEqual(listed, expected[str(row["component"])])
                    self.assertEqual(len(listed), len(set(listed)))
                    self.assertTrue(all(digest in by_stream.values() for digest in listed))
                self.assertEqual(expected["artifact"], [])
                self.assertEqual(
                    expected["composite_float64"],
                    [by_stream[stream] for stream in CANONICAL_CAUSAL_SEED_STREAM_ORDER],
                )
                self.assertEqual(expected["staged_float32"], expected["composite_float64"])


class CanonicalEncodingTests(unittest.TestCase):
    def test_json_is_utf8_sorted_compact_and_final_newline(self) -> None:
        self.assertEqual(canonical_json_bytes({"z": 1, "a": "µ"}), b'{"a":"\xc2\xb5","z":1}\n')
        with self.assertRaises(ValueError):
            canonical_json_bytes({"bad": float("nan")})

    def test_csv_has_fixed_order_and_lf(self) -> None:
        payload = canonical_csv_bytes([{"b": "x,y", "a": "1"}], ["a", "b"])
        self.assertEqual(payload, b'a,b\n1,"x,y"\n')

    def test_exclusive_write_and_manifest_extra_file_detection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_new_bytes(root / "a.txt", b"a\n")
            with self.assertRaises(ContractError):
                write_new_bytes(root / "a.txt", b"changed\n")
            write_new_bytes(root / "MANIFEST.sha256", build_manifest(root))
            verify_manifest(root)
            write_new_bytes(root / "extra.txt", b"unexpected\n")
            with self.assertRaises(ContractError):
                verify_manifest(root)

    def test_manifest_refuses_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target.txt").write_text("x", encoding="utf-8")
            (root / "link.txt").symlink_to(root / "target.txt")
            with self.assertRaises(ContractError):
                build_manifest(root)


if __name__ == "__main__":
    unittest.main()
