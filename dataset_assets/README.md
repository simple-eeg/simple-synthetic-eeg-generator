# SIMPLE synthetic EEG demonstration dataset

This bundle contains wholly synthetic procedural tutorial signals. It contains
no recording, metadata, identifier, fitted parameter, or other information
from a real person. It is not biologically realistic EEG, a pain model, a
clinical tool, or evidence validating any neural response function.

Each of 31 synthetic subjects (`001`–`031`) has one 30.000-second, 1,000-Hz
recording with one simulated `Cz` channel and one `stimulus` event at 15.000
seconds (EEGLAB latency 15001). Subject 31 alone contains the declared smooth
120-microvolt, 20-Hz tutorial contaminant from +0.300 through +0.500 seconds.
No exclusion is pre-filled; screening is manual.

The exact generator, compatible `simple-framework`, SIMPLE, environment,
settings, seeds, realised parameters, component hashes, dataset-list rows, and
file hashes are recorded in `provenance/` and `MANIFEST.sha256`.

`simple-framework` progressively updates `data_lists/dataset_list.csv` and
creates derived files. Preserve this bundle byte-for-byte and run the workflow
only on an extracted working copy.

## Citation requested

CC0 does not legally require attribution, but scholarly citation is strongly
requested. Please cite the eventual SIMPLE methods paper, archived dataset
version/DOI, and exact generator software release recorded in the build
receipt. Hosting, DOI, and publication timing are deliberately unset in this
local candidate.

## Licence and release status

The intended dataset dedication is CC0 1.0 Universal. Public application of
CC0 and release remain conditional on a separate rights-authority check. This
candidate must not be published merely because the CC0 text is bundled.
