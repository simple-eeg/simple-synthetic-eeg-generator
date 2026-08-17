# SIMPLE synthetic EEG generator

This repository creates one fixed, wholly synthetic demonstration dataset for
the SIMPLE tutorial. It contains the generator code, not generated EEG data.
Every identifier and sample is synthetic and corresponds to no real person.

## Normal use

From the root of a clean checkout, run exactly:

```sh
./generate_dataset <existing-parent-directory>
```

For example:

```sh
./generate_dataset /path/to/existing-parent
```

The argument is the only user choice. The command always creates the fixed
leaf directory `simple-synthetic-eeg-demo`; subject count, signal recipe,
filenames, metadata and validation are not configurable.

On success the selected parent contains exactly:

```text
simple-synthetic-eeg-demo/
├── dataset_list.csv
└── raw/
    ├── sub-001/ses-01/eeg/sub-001_ses-01_run-01_eeg.set
    ├── ...
    └── sub-031/ses-01/eeg/sub-031_ses-01_run-01_eeg.set
```

There are 31 embedded-data `.set` files and no `.fdt` sidecars. The output is
an ordinary non-Git transfer folder. It is deliberately disposable: delete it
when it is no longer needed and run the same command to recreate it.

The command refuses to overwrite an existing `simple-synthetic-eeg-demo` and
refuses a parent inside any Git worktree. On failure it removes only its own
unique hidden transient siblings and does not publish a partial dataset.

## Install the generated data into `simple`

The generator never reads, writes or locates `simple`. After a
successful build, the user manually copies these two entries:

- `simple-synthetic-eeg-demo/raw/` to `simple/data/raw/`;
- `simple-synthetic-eeg-demo/dataset_list.csv` to
  `simple/data_lists/dataset_list.csv`.

The CSV deliberately stores repository-relative `data/raw/...` paths. Those
paths become valid after the manual copy. Do not commit the generated inputs
to the `simple` repository.

The generated metadata records the required `simple` source commit:
`e4843b858131d7d6e019740de24f44ade12bc813`.

## One-time prerequisites

The command checks prerequisites and stops with an error if any differ. It
never installs, upgrades or downloads anything.

Before the comparatively expensive Python build begins, it starts MATLAB once
to confirm the exact licensed MATLAB build, pinned EEGLAB source hashes and
native EEGLAB initialisation. Packaging later runs in a separate clean MATLAB
process.

- macOS 26.6.1 on Apple silicon;
- Python 3.13.6 at the reviewed Homebrew interpreter identity;
- a checkout-local `.venv/bin/python` containing exactly the 19 distributions
  in `requirements/producing.lock`;
- MATLAB R2026a Update 4 installed as
  `/Applications/MATLAB_R2026a.app`; and
- EEGLAB 2026.0.0 installed in the current user's default folder
  `Documents/MATLAB/eeglab2026.0.0`.

For a new checkout, create the environment once with the reviewed Python and
the hash-pinned lock:

```sh
/opt/homebrew/opt/python@3.13/bin/python3.13 -m venv .venv
./.venv/bin/python -m pip install --require-hashes \
  -r requirements/producing.lock
```

This setup is intentionally manual. The normal dataset command never changes
the Python, MATLAB or EEGLAB installation.

## What the one command does internally

The entry point runs the full fail-closed production process:

1. audits the clean Git checkout, frozen settings and dependency lock, then
   preflights the exact native MATLAB/EEGLAB runtime;
2. builds the fixed arrays in three fresh Python processes—two canonical and
   one shuffled—and requires byte-identical results;
3. launches the exact MATLAB application and uses native EEGLAB 2026.0.0 to
   save, reload and verify each one-file dataset;
4. constructs a hidden transfer partial containing only `dataset_list.csv`
   and `raw/`;
5. checks the exact 31-subject hierarchy, CSV/file bijection, ordinary-file
   boundary, absence of symlinks and sidecars, and zero `.fdt` files;
6. removes the rich array and packaging intermediates; and
7. exclusively and atomically promotes the minimal transfer folder.

Internal array stages, manifests, receipts, parameter tables and packaging
scaffolds are validation machinery, not user outputs. They use unique hidden
siblings and are removed before success. The durable scientific recipe and
rights/citation records remain versioned in this repository, while each `.set`
embeds its synthetic identity and source-commit metadata.

Low-level Python and MATLAB entry points remain available to maintainers for
testing and auditing, but they are not the normal user interface.

## Frozen scientific contract

- subjects `001` through `031`; session `01`; run `01`;
- one 30.000-second recording (30,000 samples) per subject at 1,000 Hz;
- one exact channel `Cz`, simulated relative to a synthetic common reference;
- one exact `stimulus` event at 15.000 seconds (EEGLAB latency 15001);
- direct NeuroDSP 2.3.0 `sim_powerlaw` background, explicitly demeaned and
  sample-SD normalised before microvolt scaling;
- neutral Gaussian early-negative and late-positive event components;
- phase-randomised Tukey-windowed 9–11-Hz tutorial oscillation;
- subject 31 alone has the declared 120-microvolt, 20-Hz Tukey-windowed burst
  from +0.300 through +0.500 seconds; and
- one embedded-data `.set` per recording and zero `.fdt` files.

The generator is sensor-level and procedural. It does not claim biological
realism and is not a model of pain, an anatomical generator, or a clinical or
diagnostic signal. It must never read, copy, fit or tune to Petal, NOCI-Prem,
an NRF template, or any other real EEG, metadata, identifier, fitted
parameter, confidence interval or desired analysis result.

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
of the `background` digest seed NeuroDSP's legacy NumPy random stream only
around the sole `sim_powerlaw` call; the previous global state is restored.

Every component's internal provenance uses the complete applicable causal
seed list in the fixed stream order. The deterministic artefact has no causal
seed; composite and staged rows contain all nine digests. These records are
validated during production and are not added as clutter to the final transfer
folder.

## Validation boundary

All prospectively frozen gates live in `config/generator_settings.json` and
were fixed before candidate results were inspected; executable checks live in
`validation.py`. They test deterministic construction,
structure, finite values, background slope, declared component support,
untuned response and oscillation contrasts, and the sole subject-31 outlier.
They do not use NRF outputs, inferential results or a desired conclusion.

Screening remains manual. The generator never writes an exclusion decision.
If subject 31 is not the only visually accepted exclusion, stop and document a
successor design; never tune parameters silently.

## Licensing and release

Generator code is Apache-2.0. The generated dataset is selected for CC0-1.0
with a scholarly citation request, but public release requires the separate
rights-authority check. The tracked records are in `dataset_assets/` and
`CITATION.cff`. Hosting, DOI, archive URL and publication timing remain unset.
