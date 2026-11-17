# SIMPLE synthetic EEG generator

This repository creates one fixed, wholly synthetic demonstration dataset for
the SIMPLE tutorial. It contains the generator code, not generated EEG data.
Every identifier and sample is synthetic and corresponds to no real person.

**Software credits:** [Marianne van der Vaart](https://github.com/mvandervaart), [Simon Marchant](https://github.com/simonmarchant), and [Luke Baxter](https://github.com/lukebax) contributed equally to the development of this software.

## First-time setup

The generator is currently supported on macOS. You need:

- Python 3.10 or later;
- MATLAB installed under `/Applications`;
- EEGLAB installed under `Documents/MATLAB`; and
- a licensed MATLAB session able to start EEGLAB and save and reload a native
  one-file `.set` dataset.

From the root of a fresh checkout, copy and run this one setup command:

```sh
./setup_environment
```

The command creates the checkout-local `.venv` and installs the required
Python packages into it. It does not alter the system Python, MATLAB or EEGLAB,
and it does not build the generator package inside the checkout. You do not
need to activate the environment. If setup is interrupted, run the same
command again; no manual cleanup is needed.

The reference-tested environment uses macOS on Apple silicon, MATLAB R2026a
Update 4, EEGLAB 2026.0.0, Python 3.13.6, NumPy 2.2.2, SciPy 1.15.1,
NeuroDSP 2.3.0 and Matplotlib 3.10.0. These exact versions are not required.
At runtime the generator selects installed MATLAB and EEGLAB versions, checks
the capabilities it actually needs, and records the versions used in every
generated `.set` file. This capability check covers dataset generation; it
does not certify every function in the `simple` workflow.

If several conventional installations exist, the newest recognised MATLAB
and EEGLAB installations are selected and printed before generation. For a
nonstandard installation, advanced users can set
`SIMPLE_SYNTH_MATLAB_EXECUTABLE` and `SIMPLE_SYNTH_EEGLAB_ROOT` to canonical,
non-symlink paths before running the generation command.

## Create the dataset

Remain in the repository root. To create the dataset alongside the generator
checkout, copy and run:

```sh
./generate_dataset "$(cd .. && pwd -P)"
```

The shell expression supplies the canonical absolute path of the directory
containing the checkout. To use a different existing parent directory outside
every Git worktree, replace it with that directory's absolute path:

```sh
./generate_dataset /path/to/existing-parent
```

The parent directory is the only user choice. The command always creates the
fixed leaf directory `simple-synthetic-eeg-demo`; subject count, signal recipe,
filenames, metadata and validation are not configurable.

On success, the command creates this folder in the selected parent:

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

The generator never reads, writes or locates `simple`. After a successful
build, the user manually copies these two entries:

- `simple-synthetic-eeg-demo/raw/` to `simple/data/raw/`;
- `simple-synthetic-eeg-demo/dataset_list.csv` to
  `simple/data_lists/dataset_list.csv`.

The CSV deliberately stores repository-relative `data/raw/...` paths. Those
paths become valid after the manual copy. Do not commit the generated inputs
to the `simple` repository.

The generated metadata records the `simple` input contract and the `simple`
commit against which this dataset design was tested. The tested commit is
`7d31744d46ddba1bf11c686825e3420fb8328d19`. This is provenance for the
tutorial dataset, not a check that prevents the data being used with a
different `simple` commit.

## What the generation command does internally

The entry point runs the full fail-closed production process:

1. audits the clean Git checkout and fixed scientific recipe, then selects the
   installed MATLAB and EEGLAB runtimes;
2. uses a tiny temporary dataset to prove that EEGLAB can initialise and save
   and reload the required native one-file format without an `.fdt` sidecar;
3. generates and scientifically validates the fixed 31-subject tutorial
   signals once;
4. launches MATLAB and uses native EEGLAB to save, reload and verify every
   one-file dataset;
5. constructs a hidden transfer partial containing only `dataset_list.csv`
   and `raw/`;
6. checks the exact 31-subject hierarchy, CSV/file bijection, ordinary-file
   boundary, absence of symlinks and sidecars, and zero `.fdt` files;
7. removes the rich array and packaging intermediates; and
8. exclusively and atomically promotes the minimal transfer folder.

Internal array stages, manifests, receipts, parameter tables and packaging
scaffolds are validation machinery, not user outputs. They use unique hidden
siblings and are removed before success. The durable scientific recipe and
rights/citation records remain versioned in this repository, while each `.set`
embeds its synthetic identity, tested `simple` contract, recipe digest and
actual runtime versions.

Low-level Python and MATLAB entry points remain available to maintainers for
testing and auditing, but they are not the normal user interface.

## Scientific contract

- subjects `001` through `031`; session `01`; run `01`;
- one 30.000-second recording (30,000 samples) per subject at 1,000 Hz;
- one exact channel `Cz`, simulated relative to a synthetic common reference;
- one exact `stimulus` event at 15.000 seconds (EEGLAB latency 15001);
- a NeuroDSP `sim_powerlaw` background, explicitly demeaned and
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
validated during generation and omitted from the final transfer folder.

## Validation boundary

The fixed recipe and validation gates live in
`config/generator_settings.json`; executable checks live in
[validation.py](src/simple_synthetic_eeg_generator/validation.py).
They test seeded construction, structure, finite values, background slope,
declared component support,
untuned response and oscillation contrasts, and the sole subject-31 outlier.
They do not use NRF outputs, inferential results or a desired conclusion.

Fixed seeds make runs repeatable within ordinary numerical-library behaviour,
but byte-identical files across different compatible Python, MATLAB or EEGLAB
versions are not required. The scientific and structural checks, followed by
native save/reload verification of every dataset, determine whether a build is
accepted.

Screening remains manual. The generator never writes an exclusion decision.
If subject 31 is not the only visually accepted exclusion, stop and document a
successor design; never tune parameters silently.

## Licensing and release

Generator code is Apache-2.0. The generated dataset is selected for CC0-1.0
with a scholarly citation request, but public release requires the separate
rights-authority check. The tracked records are in `dataset_assets/` and
`CITATION.cff`. Hosting, DOI, archive URL and publication timing remain unset.
