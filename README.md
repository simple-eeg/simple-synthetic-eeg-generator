# SIMPLE synthetic EEG generator

This repository contains the deterministic source recipe for the wholly
synthetic SIMPLE tutorial dataset. It does **not** contain EEG recordings,
generated arrays, EEGLAB datasets, workflow outputs, or screening decisions.
Every generated identifier and sample is synthetic and corresponds to no real
person.

The generator is deliberately sensor-level and procedural. It creates one
simulated `Cz` channel, not biologically realistic EEG and not a model of pain,
an anatomical generator, or a clinical/diagnostic signal. It must never read,
copy, fit, or tune to Petal, NOCI-Prem, an NRF template, or any other real EEG,
metadata, identifier, fitted parameter, confidence interval, or desired
analysis result.

## Frozen contract

- subjects `001` through `031`; session `01`; run `01`;
- one 30.000-second recording (30,000 samples) per subject at 1,000 Hz;
- one exact channel `Cz`, described as simulated relative to a synthetic
  common reference;
- one exact `stimulus` event at 15.000 seconds (EEGLAB latency 15001);
- direct NeuroDSP 2.3.0 `sim_powerlaw` background, explicitly demeaned and
  sample-SD normalised before microvolt scaling;
- neutral Gaussian early-negative and late-positive event components;
- phase-randomised Tukey-windowed 9–11-Hz tutorial oscillation;
- subject 31 alone has the declared 120-microvolt, 20-Hz Tukey-windowed burst
  from +0.300 through +0.500 seconds; and
- one embedded-data `.set` per recording and zero `.fdt` files after the
  native EEGLAB transaction.

The master seed is `0x53494D504C450001` (decimal
`6001412985720209409`). All subordinate seeds are SHA-256 digests over the
following exact UTF-8 string, including its final newline:

```text
simple-synthetic-eeg-generator/v1
master=6001412985720209409
subject=<three-digit-id>
stream=<exact-stream-name>
```

The first sixteen digest bytes, interpreted unsigned big-endian, seed NumPy
`PCG64DXSM` parameter draws. The only stream names are `background`, `chi`,
`sigma`, `response_scale`, `response_latency`, `response_width`,
`burst_amplitude`, `burst_frequency`, and `burst_phase`. The first four bytes
of the `background` digest seed NeuroDSP's
legacy NumPy random stream immediately around the sole `sim_powerlaw` call;
the previous global state is restored afterwards. Full digests and realised
raw and clipped draws are retained.

`seed_manifest.csv` and `realised_parameters.csv` are the authoritative
subject/stream provenance. Each ground-truth component row uses the explicitly
plural `causal_seed_sha256_list` field and lists every direct stochastic seed
that determines that component; it never presents one response or spectral
seed as the complete causal identity. Lists follow the fixed order
`background`, `chi`, `sigma`, `response_scale`, `response_latency`,
`response_width`, `burst_amplitude`, `burst_frequency`, `burst_phase`, with
only the applicable subsequence retained for individual components. The
deterministic artifact has a blank seed list; composite and staged rows contain
all nine digests.

## Two no-overwrite transactions

Generation and native EEGLAB packaging are separate. Neither mutates an
accepted predecessor.

1. `simple-synthetic-eeg generate` creates three unique same-filesystem
   `<output>.partial.<random>.<run>` siblings plus a control partial, validates
   all Python-stage gates, and requires the two canonical and one shuffled
   fresh-process builds to match byte-for-byte. It deletes the two comparison
   runs and control partial before atomically renaming the sole accepted run to
   the previously absent `output`. A failed stage remains marked for diagnosis
   and is never promoted.
2. `matlab/package_and_verify_eeglab.m` reads that immutable stage, creates a
   separately specified unique `<dataset-output>.partial.<random>` sibling, constructs every `.set`
   natively in EEGLAB 2026.0.0, saves in `onefile` mode, reloads and verifies
   it, writes the final manifest, and atomically promotes it. It refuses an
   existing output or build directory.

Do not run either transaction until the producing environment, complete
hash-pinned dependency lock, compatible `simple-framework` commit, and local
workspace destinations have been separately checked.

The Python transaction accepts only the reviewed 19-package lock with exact
SHA-256
`ed84d519fd102843c2da38e7174d829a352eabfb4babdb8321018dbb9cce6b05`
and the compatible framework commit
`2cb9227e75468e9393105e729b4ce590b76dab02`. The executing interpreter is the
source checkout's exact `.venv/bin/python` chain under CPython 3.13.6. Every
executing generator module must resolve to that same audited checkout. Fresh
workers use Python isolation, an explicit audited `src` bootstrap and a
sanitised environment; ambient `PYTHONPATH` and installed/shadow generator
copies are not admitted.

Example shape only (paths are deliberately not prescribed here):

```sh
<clean-generator-git-checkout>/.venv/bin/python -I \
  <clean-generator-git-checkout>/tools/run_generator.py generate \
  --settings config/generator_settings.json \
  --lock-file requirements/producing.lock \
  --source-root <clean-generator-git-checkout> \
  --framework-commit 2cb9227e75468e9393105e729b4ce590b76dab02 \
  --output <new-array-stage>
```

The source checkout audit uses file names only outside `.git` and the
allowlisted `.venv`; it does not open ignored content. It fails if any ignored
or untracked data-like/user-output path exists outside `.venv`, including EEG,
arrays, workflow outputs, provenance, manifests or failed-build partials. Its
claim is therefore limited to zero such paths in the audited generator source
tree; it does not claim to have searched the machine for real EEG.

For native packaging, define exactly these five environment variables:

- `SIMPLE_SYNTH_INPUT_ROOT`: absolute canonical path to the existing,
  immutable Python array stage;
- `SIMPLE_SYNTH_OUTPUT_ROOT`: absolute canonical path for the absent final
  dataset bundle, beneath an existing canonical parent and on the same
  filesystem as its sibling partial;
- `SIMPLE_SYNTH_EEGLAB_ROOT`: absolute canonical non-symlink root of the exact
  EEGLAB 2026.0.0 installation;
- `SIMPLE_SYNTH_PYTHON`: exact lexical
  `<generator-root>/.venv/bin/python` producing interpreter. This link to
  `python3.13`, and that intermediate absolute interpreter link, are the sole
  accepted symlink exception; their link texts, canonical target, executable
  hash, `sys.prefix`, `sys.base_prefix`, `sys.executable`, full version and
  exact 19 installed distributions are pinned; and
- `SIMPLE_SYNTH_GENERATOR_ROOT`: absolute canonical non-symlink path to the
  clean frozen generator checkout that produced the input-stage receipt.

All other relevant roots and path components must not be symlinks. Run the
unchanged packaging script from the tracked `matlab/` directory after EEGLAB
has been initialised from the exact canonical root. A stale
`<output>.partial.*` sibling causes a fail-closed stop. Publication uses the
tracked `tools/exclusive_rename_macos.py` helper through
`SIMPLE_SYNTH_PYTHON -I`, and macOS `renamex_np(..., RENAME_EXCL)` guarantees
an existing or racing destination is never overwritten.

The generator commit is deliberately not embedded in its own tracked source,
which would create a circular commit hash. Instead, the Python source audit
requires a clean Git checkout and writes its exact `HEAD` into
`build_receipt.json`; packaging requires the clean
`SIMPLE_SYNTH_GENERATOR_ROOT` `HEAD` to equal that receipt. Durable external
checkpoint evidence then freezes the accepted generator commit.

## Dataset bundle

The packaged bundle has this starting shape:

```text
README.md
LICENSE
MANIFEST.sha256
provenance/
  generator_settings.json
  realised_parameters.csv
  seed_manifest.csv
  ground_truth_manifest.csv
  build_receipt.json
data/raw/sub-001/ses-01/eeg/sub-001_ses-01_run-01_eeg.set
...
data/raw/sub-031/ses-01/eeg/sub-031_ses-01_run-01_eeg.set
data_lists/dataset_list.csv
```

The five-column dataset list is exactly
`subjectID,sessionID,runID,path_raw,EEGfile_raw`. `simple-framework`
progressively edits this CSV and creates derived files, so users must run the
workflow on an extracted working copy and preserve the pristine bundle.

## Scientific and validation boundary

All preregistered gates live in `config/generator_settings.json` and executable
checks live in `validation.py`. Gates test deterministic construction,
structure, finite values, background slope, declared component support,
untuned response and oscillation contrasts, and the sole subject-31 outlier.
They do not use NRF outputs, inferential results, or a desired conclusion.

Screening remains manual: the generator never writes an exclusion decision.
If subject 31 is not the only visually accepted exclusion, the candidate must
stop and become an explicitly documented successor; parameters must not be
silently tuned.

Unit tests deliberately separate pure construction/oracle tests from the
production NeuroDSP call. Tests may skip NumPy-dependent cases when no locked
environment exists, but production generation never substitutes, mocks, or
reimplements `sim_powerlaw`.

## Licensing and citation

Generator code is Apache-2.0. The generated dataset is selected for CC0-1.0
with a prominent scholarly citation request, but public release requires the
separate rights-authority check. Hosting, DOI, archive URL, and publication
timing remain deliberately unset. See `CITATION.cff` and the packaged dataset
README.
