# SIMPLE synthetic EEG demonstration dataset

This document describes the dataset created by the
[SIMPLE synthetic EEG generator](https://github.com/simple-eeg/simple-synthetic-eeg-generator). The signals are wholly
synthetic: no recording, metadata, identifier, fitted parameter, or other
information comes from a real person. They are not biologically realistic
EEG, a pain model, a clinical tool, or evidence validating a neurodynamic
response function (NRF).

## Dataset contents

Each of 31 synthetic subjects (`001`–`031`) has one 30.000-second, 1,000-Hz
recording with one simulated `Cz` channel and one `stimulus` event at 15.000
seconds (EEGLAB latency 15001). Subject 31 alone contains a smooth
120-microvolt, 20-Hz tutorial contaminant from +0.300 through +0.500 seconds.
No exclusion is pre-filled; screening is manual.

The generator checks the recipe, seeds, realised parameters, signal
components, and dataset-list rows, then saves and reloads every native EEGLAB
file to verify it. Each `.set` records the generator commit, tested `simple`
input contract, recipe digest, and actual Python, numerical-library, MATLAB,
and EEGLAB versions used to create it. Internal build records are checked and
removed before the output folder is completed.

The generated folder contains only `dataset_list.csv` and `raw/`; the licence
and citation records in this directory remain with the generator source.
Follow the [copying instructions](https://github.com/simple-eeg/simple-synthetic-eeg-generator#copy-the-data-into-simple) to
place the data in `simple`. Keep the generated folder as the source copy:
`simple` progressively updates its copy of `data_lists/dataset_list.csv` and
creates derived files.

## Licence and attribution

The synthetic dataset and this dataset documentation are licensed under
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
You may use, modify, and share them, including commercially. Credit the SIMPLE
project contributors, link to the dataset and licence, and indicate any changes.
The [dataset citation metadata](CITATION.cff) identifies the dataset; a
ready-made copy is available in
[simple-data](https://github.com/simple-eeg/simple-data/tree/main/synthetic-eeg).

For research use, please also cite the SIMPLE methods paper when available and
identify the generator version or commit recorded in the dataset metadata.
The generator software remains licensed under
[Apache 2.0](https://github.com/simple-eeg/simple-synthetic-eeg-generator/blob/main/LICENSE).
