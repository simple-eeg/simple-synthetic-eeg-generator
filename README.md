# SIMPLE synthetic EEG generator

This repository creates one fixed, wholly synthetic demonstration dataset for
the [SIMPLE tutorial](https://github.com/simple-eeg/simple#synthetic-tutorial).
It contains the generator code, not generated EEG data. Every identifier and
sample is synthetic and corresponds to no real person.

**Software credits:** [Luke Baxter](https://github.com/lukebax), [Marianne van der Vaart](https://github.com/mvandervaart), and [Simon Marchant](https://github.com/simonmarchant) contributed to the development of this software.

To create the tutorial data, follow the setup, generation, and copying steps
below. The [dataset design](#dataset-design) describes the signals; the
[technical reference](#technical-reference) gives implementation and
reproducibility details.

## First-time setup

The generator uses one shared workflow for macOS, Linux, and Windows
(see [verification coverage](#runtime-selection)). You need:

- Git and Python 3.10 or later, available in your terminal;
- MATLAB;
- EEGLAB; and
- a licensed MATLAB session able to start EEGLAB and save and reload a native
  one-file `.set` dataset.

Open a terminal in the folder where you want to keep the generator. Choose a
folder outside any existing Git repository, then run:

```sh
git clone https://github.com/simple-eeg/simple-synthetic-eeg-generator.git
cd simple-synthetic-eeg-generator
```

Then set up the Python environment (use `python3` if that is the name of
your Python command):

```sh
python setup_environment
```

If GitHub asks you to sign in, use an account with access to the repository.
Use a Git clone rather than GitHub's **Download ZIP** option: generation
requires a clean Git checkout and records its commit. Keep its tracked
files unchanged, and do not add data or other files to the checkout. The setup
environment and recognised temporary caches are allowed.

The setup command creates a separate Python environment in `.venv` inside the
generator folder and installs the required packages there. It does not alter
the system Python, MATLAB, or EEGLAB, and it does not build the generator
package inside the checkout. You do not need to activate the environment. If
setup is interrupted, run `python setup_environment` again; no manual cleanup is
needed.

The generator looks for MATLAB in its standard installation folder or on
`PATH`, and for EEGLAB under `Documents/MATLAB`. It prints the selected paths
before generation. It checks the operations it needs and records the
versions used in each output file.
For other installation locations, see [runtime selection](#runtime-selection).

## Create the dataset

Remain in the generator's top-level folder. To create the dataset in the
folder containing the generator, run:

```sh
python generate_dataset ..
```

`..` selects the containing folder. To use another location, give the path
of an existing parent folder (absolute or relative to your current folder):

```sh
python generate_dataset "path/to/existing-parent"
```

The parent must be outside every Git repository. Use a real folder, with no
symbolic links in its path. The parent folder is the only user choice: the
output is always named `simple-synthetic-eeg-demo`, and the subject count,
signal recipe, filenames, metadata, and validation are fixed.

On success, the selected parent contains:

```text
simple-synthetic-eeg-demo/
├── dataset_list.csv
└── raw/
    ├── sub-001/ses-01/eeg/sub-001_ses-01_run-01_eeg.set
    ├── ...
    └── sub-031/ses-01/eeg/sub-031_ses-01_run-01_eeg.set
```

Each of the 31 `.set` files contains its EEG data and metadata, so no separate
`.fdt` data files are needed. This output is an ordinary folder outside Git.
You can delete it when it is no longer needed and recreate it with the same
command.

The command will not overwrite an existing `simple-synthetic-eeg-demo` folder.
Move or delete that folder explicitly before generating again. If generation
fails, the command removes only the temporary folders it created beside the
output location and does not leave a partially completed output dataset.

## Copy the data into `simple`

The generator does not locate or change the `simple` repository. After
generation succeeds, manually copy:

- `simple-synthetic-eeg-demo/raw/` to `simple/data/raw/`; and
- `simple-synthetic-eeg-demo/dataset_list.csv` to
  `simple/data_lists/dataset_list.csv`.

The CSV lists paths beginning with `data/raw/`, relative to the `simple`
repository. These paths become valid after copying. Keep the generated folder
as the source copy: the tutorial updates the CSV and creates derived files in
`simple`. Do not commit the generated inputs to Git.

Continue with the [SIMPLE synthetic tutorial](https://github.com/simple-eeg/simple#synthetic-tutorial).

## Dataset design

The dataset provides a fixed example for learning the SIMPLE workflow:

- subjects `001` through `031`, each with session `01` and run `01`;
- one 30.000-second recording (30,000 samples) per subject at 1,000 Hz;
- one channel named `Cz`, simulated relative to a synthetic common reference;
- one `stimulus` event at 15.000 seconds (EEGLAB latency 15001);
- a NeuroDSP `sim_powerlaw` background, with its mean removed and its sample
  standard deviation normalised to one before scaling to microvolts;
- neutral Gaussian early-negative and late-positive event components;
- a phase-randomised, Tukey-windowed 9–11-Hz tutorial oscillation;
- a 120-microvolt, 20-Hz Tukey-windowed burst in subject 31 alone, from +0.300
  through +0.500 seconds; and
- one `.set` file containing all data for each recording, with no `.fdt` files.

These are procedurally generated sensor-level signals. They do not claim
biological realism and are not a model of pain, an anatomical generator, or
clinical or diagnostic signals. The generator must never read, copy, fit, or
tune to Petal, NOCI-Prem, a neurodynamic response function (NRF) template, or
any other real EEG, metadata, identifier, fitted parameter, confidence
interval, or desired analysis result.

Screening remains manual; the generator never writes an exclusion decision.
If subject 31 is not the only visually accepted exclusion, stop and document a
successor dataset design; never tune parameters silently.

## How it works

The command checks the source files and fixed recipe, selects MATLAB and
EEGLAB, and uses a tiny temporary dataset to check that EEGLAB can initialise,
save, and reload the required one-file format. It then generates the 31
recordings once, checks their signals, and uses MATLAB and EEGLAB to save,
reload, and verify every output file.

Before completing the output folder, it checks the exact folder structure and
that each CSV row names one EEG file, with one row for every file. The folder
must contain only `dataset_list.csv` and `raw/`, with ordinary files and
directories, no symbolic links, and no `.fdt` files or other sidecars.
Temporary build files are removed before the completed folder becomes
available. The final move is atomic and refuses to overwrite existing output.

## Technical reference

This section records the tested environment, seed derivation, and validation
details for readers inspecting or maintaining the generator. The normal user
commands remain `python setup_environment` and `python generate_dataset`.

### Runtime selection

The reference build was tested on macOS with Apple silicon, MATLAB R2026a
Update 4, EEGLAB 2026.0.0, Python 3.13.6, NumPy 2.2.2, SciPy 1.15.1,
NeuroDSP 2.3.0, and Matplotlib 3.10.0. These exact versions are not required.
Python tests run on all three operating systems. The full MATLAB/EEGLAB
workflow has been verified locally on macOS; its native save/reload check also
runs before generation on your computer. Runtime checks cover this generator,
not every function in the `simple` workflow.

MATLAB is sought under `/Applications` on macOS, `/usr/local/MATLAB` on Linux,
and `Program Files/MATLAB` on Windows, then on `PATH`. EEGLAB is sought under
`Documents/MATLAB` in your home folder. If several recognised installations
exist in these folders, the newest is selected. For a nonstandard installation, set
`SIMPLE_SYNTH_MATLAB_EXECUTABLE` and `SIMPLE_SYNTH_EEGLAB_ROOT` before
generation. Both must be canonical absolute paths, with no symbolic links in
any path component: the first names the MATLAB executable, and the second
names the EEGLAB folder.

### Seeds and provenance

The master seed is `0x53494D504C450001` (decimal
`6001412985720209409`). All subordinate seeds are SHA-256 digests over the
following exact UTF-8 string, including its final newline:

```text
simple-synthetic-eeg-generator/v1
master=6001412985720209409
subject=<three-digit-id>
stream=<exact-stream-name>
```

The first sixteen digest bytes, interpreted as an unsigned big-endian integer,
seed NumPy `PCG64DXSM` parameter draws. The only stream names are `background`,
`chi`, `sigma`, `response_scale`, `response_latency`, `response_width`,
`burst_amplitude`, `burst_frequency`, and `burst_phase`. The first four bytes
of the `background` digest seed NeuroDSP's legacy NumPy random stream only
around the sole `sim_powerlaw` call; the previous global state is restored.

Each component's internal provenance lists every seed that contributed to it,
in the fixed stream order. No random seed contributes to the deterministic
artefact; composite and staged rows contain all nine digests. These records
are validated during generation and omitted from the final output folder.

Internal arrays, manifests, receipts, parameter tables, and packaging files
are temporary validation records, not user outputs. They occupy uniquely
named hidden folders beside the destination and are removed before success.
The scientific recipe and rights/citation records remain in this repository.
Each `.set` embeds its synthetic identity, tested `simple` input contract,
recipe digest, and actual runtime versions.

The input contract describes the dataset format expected by `simple`. Its
recorded tested commit is `7d31744d46ddba1bf11c686825e3420fb8328d19`.
This identifies the version used to test the dataset design; it does not
prevent using the data with another `simple` commit.

### Validation and repeatability

The fixed recipe and validation criteria are in
[`config/generator_settings.json`](config/generator_settings.json); the
executable checks are in
[`validation.py`](src/simple_synthetic_eeg_generator/validation.py).
They test seeded construction, structure, finite values, background slope,
declared component support, untuned response and oscillation contrasts, and
the sole subject-31 outlier. They do not use NRF outputs, inferential results,
or a desired conclusion.

Fixed seeds make runs repeatable within ordinary numerical-library behaviour.
Byte-identical files across different compatible Python, MATLAB, or EEGLAB
versions are not required. A build is accepted only after the scientific and
structural checks and native save/reload verification of every dataset pass.

Low-level Python and MATLAB entry points remain available to maintainers for
testing and auditing; they are not the normal user interface.

Maintainers can run the **MATLAB and EEGLAB validation** workflow from this
repository's GitHub **Actions** tab. It runs the MATLAB tests and generates a
temporary example on macOS, Windows, and Linux, including native save/reload
verification of all 31 recordings. It uses MATLAB R2026a Update 4 and EEGLAB
2026.0.0, and does not change the shared dataset. The Windows run reports the
Unix file-permission test as skipped.

## Licensing and release

The generator software is licensed under [Apache 2.0](LICENSE). The generated
synthetic dataset and its accompanying dataset documentation are licensed under
[CC BY 4.0](dataset_assets/CC-BY-4.0.txt), which allows reuse with attribution.
See the [dataset guide](dataset_assets/README.md#licence-and-attribution) for
crediting the data and the [software citation metadata](CITATION.cff) for
crediting the generator. A ready-made copy is shared in
[simple-data](https://github.com/simple-eeg/simple-data/tree/main/synthetic-eeg).
