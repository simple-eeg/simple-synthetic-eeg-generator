from __future__ import annotations

import os
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import numpy as np
    import scipy
except ImportError:
    np = None

from simple_synthetic_eeg_generator.model import (
    analytic_components,
    compose_float64,
    discrete_tukey,
    generate_neurodsp_background,
    realise_parameters,
)
from simple_synthetic_eeg_generator.oracle import reconstruct_analytic_components
from simple_synthetic_eeg_generator.settings import load_settings
from simple_synthetic_eeg_generator.validation import _baseline_corrected_epoch, _relative_epoch_window


@unittest.skipIf(np is None, "NumPy/SciPy test environment is not installed")
class ScientificHelperTests(unittest.TestCase):
    def test_event_components_match_independent_oracle_and_exact_supports(self) -> None:
        settings = load_settings(Path(__file__).resolve().parents[1] / "config/generator_settings.json").values
        for subject in ("001", "031"):
            parameters = realise_parameters(subject, settings)
            built = analytic_components(subject, settings, parameters)
            realised = {name: draw.realised for name, draw in parameters.items()}
            oracle = reconstruct_analytic_components(subject, settings, realised)
            for name in ("early_negative", "late_positive", "spectral", "artifact"):
                self.assertLessEqual(float(np.max(np.abs(built[name] - oracle[name]))), 1e-12)
            offsets = np.arange(30000) - 15000
            spectral_support = (offsets >= 150) & (offsets <= 850)
            artifact_support = (offsets >= 300) & (offsets <= 500)
            self.assertEqual(int(np.count_nonzero(spectral_support)), 701)
            self.assertTrue(np.all(built["spectral"][~spectral_support] == 0.0))
            if subject == "031":
                self.assertEqual(int(np.count_nonzero(artifact_support)), 201)
                self.assertTrue(np.all(built["artifact"][~artifact_support] == 0.0))
            else:
                self.assertTrue(np.all(built["artifact"] == 0.0))

    def test_symmetric_tukey_support_lengths_and_endpoints(self) -> None:
        for length in (701, 201):
            window = discrete_tukey(length, 0.5)
            self.assertEqual(window.shape, (length,))
            self.assertEqual(window[0], 0.0)
            self.assertEqual(window[-1], 0.0)
            self.assertTrue(np.all(window >= 0.0))

    def test_ordered_float64_composition_and_one_final_cast(self) -> None:
        background = np.array([1.0, 2.0**-24, -3.0], dtype=np.float64)
        analytic = {
            "early_negative": np.array([2.0**-53, 1.0, 0.25], dtype=np.float64),
            "late_positive": np.array([0.5, -1.0, 0.125], dtype=np.float64),
            "spectral": np.array([0.25, 0.125, -0.5], dtype=np.float64),
            "artifact": np.array([0.0, 0.0, 120.0], dtype=np.float64),
        }
        result = compose_float64(background, analytic)
        expected = background.copy()
        for name in ("early_negative", "late_positive", "spectral", "artifact"):
            expected = np.add(expected, analytic[name], dtype=np.float64)
        self.assertTrue(np.array_equal(result, expected))
        staged = np.asarray(result, dtype="<f4")
        self.assertTrue(np.array_equal(staged, expected.astype("<f4")))

    def test_baseline_and_inclusive_response_endpoints(self) -> None:
        signal = np.arange(2000, dtype=np.float64)
        gate = {
            "epoch_window_seconds": [-0.2, 1.0],
            "baseline_window_seconds": [-0.2, 0.0],
            "window_endpoints_inclusive": True,
            "baseline_end_inclusive": False,
        }
        event_zero = 500
        epoch = _baseline_corrected_epoch(signal, event_zero, 1000, gate)
        self.assertEqual(epoch.size, 1201)
        expected_baseline = float(np.mean(signal[300:500]))
        self.assertEqual(epoch[0], signal[300] - expected_baseline)
        self.assertEqual(epoch[200], signal[500] - expected_baseline)
        early = _relative_epoch_window(epoch, 1000, -0.2, 0.17, 0.27)
        late = _relative_epoch_window(epoch, 1000, -0.2, 0.38, 0.58)
        self.assertEqual(early.size, 101)
        self.assertEqual(late.size, 201)

    def test_neurodsp_first_import_and_call_restores_global_random_state(self) -> None:
        if importlib.util.find_spec("neurodsp") is None:
            self.skipTest("NeuroDSP test environment is not installed")
        self.assertNotIn("neurodsp", sys.modules)
        np.random.seed(123456)
        before = np.random.get_state()
        with tempfile.TemporaryDirectory() as directory:
            old = os.environ.get("MPLCONFIGDIR")
            os.environ["MPLCONFIGDIR"] = directory
            try:
                raw, normalised = generate_neurodsp_background(0.25, 1000, 1.5, 123)
            finally:
                if old is None:
                    os.environ.pop("MPLCONFIGDIR", None)
                else:
                    os.environ["MPLCONFIGDIR"] = old
        after = np.random.get_state()
        self.assertEqual(raw.shape, (250,))
        self.assertAlmostEqual(float(np.mean(normalised)), 0.0, places=12)
        self.assertAlmostEqual(float(np.std(normalised, ddof=1)), 1.0, places=12)
        self.assertEqual(before[0], after[0])
        self.assertTrue(np.array_equal(before[1], after[1]))
        self.assertEqual(before[2:], after[2:])


if __name__ == "__main__":
    unittest.main()
