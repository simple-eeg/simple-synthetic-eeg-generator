# SIMPLE synthetic EEG demonstration dataset

This document describes the dataset created by the
[SIMPLE synthetic EEG generator](../README.md). The signals are wholly
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
Follow the [copying instructions](../README.md#copy-the-data-into-simple) to
place the data in `simple`. Keep the generated folder as the source copy:
`simple` progressively updates its copy of `data_lists/dataset_list.csv` and
creates derived files.

## Citation requested

CC0 does not legally require attribution, but scholarly citation is strongly
requested. Please cite the eventual SIMPLE methods paper, archived dataset
version/DOI, and generator software commit recorded in the dataset metadata.
Hosting, DOI, and publication timing remain unset for this candidate dataset.

## Licence and release status

The intended dataset dedication is CC0 1.0 Universal. Public application of
CC0 and release remain conditional on a separate
[rights-authority check](RIGHTS_AUTHORITY_CHECK_REQUIRED.txt). This candidate
must not be published merely because the CC0 text is present in this
repository.
