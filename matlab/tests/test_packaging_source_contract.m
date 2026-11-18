function tests = test_packaging_source_contract
% Static gates for capability-based native packaging. Runtime gates are separate.
tests = functiontests(localfunctions);
end

function testRequiredScientificAndNativeCalls(testCase)
source = packaging_source;
required = {'eeg_emptyset','eeg_checkset','pop_saveset','savemode'', ''onefile', ...
    'version'', ''6','load(setPath, ''-mat'')','-struct'', ''sanitisedStored', ...
    'pop_loadset','EXPECTED_SAMPLE_COUNT = 30000','EXPECTED_EVENT_LATENCY = 15001', ...
    'EXPECTED_INPUT_SCHEMA = ''simple-synthetic-array-stage-receipt-v3''', ...
    'EXPECTED_TESTED_SIMPLE_COMMIT = ''7d31744d46ddba1bf11c686825e3420fb8328d19''', ...
    'EXPECTED_SIMPLE_INPUT_CONTRACT = ''simple-synthetic-input-v1''', ...
    '''simple-synthetic-eeglab-metadata-v3''','''simple-synthetic-eeglab-packaging-v3''', ...
    'strcmp(EEG.event.type, ''stimulus'')','assert_semantic_equal_except_path', ...
    'assert_dataset_list_bijection','verify_sha256_manifest(partialRoot)', ...
    'create_directory_exclusive(partialRoot)', ...
    'exclusive_atomic_move(partialRoot, outputRoot, pythonPath, helperPath)'};
for i = 1:numel(required), verifyNotEmpty(testCase, strfind(source, required{i})); end
end

function testRuntimeAcceptanceIsCapabilityBased(testCase)
packager = packaging_source;
preflight = preflight_source;
helper = capability_source;
verifyNotEmpty(testCase, strfind(packager, 'validate_runtime_capabilities(eeglabRoot, false)'));
verifyNotEmpty(testCase, strfind(preflight, 'validate_runtime_capabilities(eeglabRoot, true)'));
for required = {'eeglab','eeg_emptyset','eeg_checkset','pop_saveset','pop_loadset','eeg_getversion'}
    verifyNotEmpty(testCase, strfind(helper, required{1}));
end
for required = {'tempname','eeg_checkset','pop_saveset','pop_loadset','savemode'', ''onefile','version'', ''6', ...
        'endsWith(names, ''.fdt'')','isequal(single(reloaded.data), samples)', ...
        'options(1) = java.nio.file.LinkOption.NOFOLLOW_LINKS', ...
        'status == 1 && ~java.nio.file.Files.exists(jpath, options)'}
    verifyNotEmpty(testCase, strfind(helper, required{1}));
end
verifyEmpty(testCase, strfind(helper, 'catch'));
combined = strjoin({packager, preflight, helper}, newline);
verifyEmpty(testCase, regexp(combined, ...
    'assert\s*\(\s*strcmp\s*\(\s*version(?:\(''-release''\))?', 'once'));
end

function testActualRuntimeProvenanceIsEmbedded(testCase)
source = packaging_source;
required = {'recipe_sha256','python_version','numpy_version','scipy_version', ...
    'neurodsp_version','matlab_release','matlab_version','eeglab_version', ...
    'tested_simple_commit','simple_input_contract','native_onefile_save_reload', ...
    'python_runtime'};
for i = 1:numel(required), verifyNotEmpty(testCase, strfind(source, required{i})); end
end

function testRecipeIdentityIsAProspectiveConstant(testCase)
source = packaging_source;
tokens = regexp(source, 'EXPECTED_RECIPE_SHA256 = ''([^'']+)'';', 'tokens', 'once');
verifyNotEmpty(testCase, tokens);
verifyNotEmpty(testCase, regexp(tokens{1}, '^[0-9a-f]{64}$', 'once'));
verifyEqual(testCase, tokens{1}, ...
    '0ec28e6841fdbf2e1cbffdd6932880e96b5a0f1ad8f69cda716bbe2ce5eda2d3');
verifyNotEmpty(testCase, strfind(source, ...
    'sha256_file(settingsPath), EXPECTED_RECIPE_SHA256'));
end

function testEEGLABPathArgumentsCrossAsChar(testCase)
source = packaging_source;
verifyNotEmpty(testCase, strfind(source, ...
    "rawDir = char(fullfile(partialRoot, 'data', 'raw'"));
verifyNotEmpty(testCase, strfind(source, ...
    "ischar(rawDir) && isrow(rawDir) && ischar(setName) && isrow(setName)"));
verifyNotEmpty(testCase, strfind(source, ...
    "pop_saveset(EEG, 'filename', setName, 'filepath', rawDir"));
verifyNotEmpty(testCase, strfind(source, ...
    "pop_loadset('filename', setName, 'filepath', rawDir, 'loadmode', 'all')"));
verifyEmpty(testCase, strfind(source, "'filepath', char(rawDir)"));
end

function testExactFiveEnvironmentVariables(testCase)
source = packaging_source;
names = regexp(source, 'SIMPLE_SYNTH_[A-Z_]+', 'match');
verifyEqual(testCase, sort(unique(names)), sort({'SIMPLE_SYNTH_EEGLAB_ROOT', ...
    'SIMPLE_SYNTH_GENERATOR_ROOT','SIMPLE_SYNTH_INPUT_ROOT','SIMPLE_SYNTH_OUTPUT_ROOT','SIMPLE_SYNTH_PYTHON'}));
end

function testSelectedRuntimeEntriesAreCapabilityScoped(testCase)
source = packaging_source;
required = {'require_python_entry(generatorRoot)', ...
    'SIMPLE_SYNTH_PYTHON must be the checkout-local virtual-environment interpreter.', ...
    'isfile(pythonPath) && java.nio.file.Files.isExecutable(jpath)', ...
    'validate_runtime_capabilities(eeglabRoot, false)'};
for i = 1:numel(required), verifyNotEmpty(testCase, strfind(source, required{i})); end
end

function testNoUnsafePublicationFallback(testCase)
source = packaging_source;
for forbidden = {'StandardCopyOption.ATOMIC_MOVE','movefile(','copyfile(partialRoot', ...
        '''f''','rm -','rmdir(outputRoot','delete(outputRoot'}
    verifyEmpty(testCase, strfind(source, forbidden{1}));
end
end

function testManifestAndPathHardening(testCase)
source = packaging_source;
required = {'path_exists_including_symlink','assert_no_symlink_components','canonical_existing_path', ...
    'same_file_store','refuse_stale_partials','is_safe_relative_posix','walk_regular_files', ...
    'isRegularFile','Bundle contains a symlink','Bundle contains a non-regular object', ...
    'Manifest omits or invents a bundle file','Unsafe/duplicate manifest path', ...
    'endsWith(lower(actual), ".fdt")','looks_like_absolute_path','audit_raw_mat_bytes'};
for i = 1:numel(required), verifyNotEmpty(testCase, strfind(source, required{i})); end
end

function testNoExternalEEGOrTemplateSearch(testCase)
source = lower(packaging_source);
for forbidden = {'.edf','.bdf','/volumes/','uigetfile','nrf.mat','nrfutils'}
    verifyEmpty(testCase, strfind(source, forbidden{1}));
end
end

function testTrackedProducingHelpersRemainBound(testCase)
source = packaging_source;
required = {'require_tracked_clean_paths','matlab/package_and_verify_eeglab.m', ...
    'matlab/run_command.m','matlab/contains_ascii_case_insensitive_bytes.m', ...
    'matlab/find_stale_partial_siblings.m','matlab/validate_runtime_capabilities.m', ...
    'tools/exclusive_rename.py'};
for i = 1:numel(required), verifyNotEmpty(testCase, strfind(source, required{i})); end
verifyNotEmpty(testCase, strfind(source, ...
    'assert_unique_function_binding(''validate_runtime_capabilities'''));
end

function testInputRootHasOnlyReviewedReadUses(testCase)
source = packaging_source;
lines = splitlines(string(source));
actual = strtrim(lines(contains(lines, 'inputRoot')));
expected = [
    "inputRoot = require_canonical_root('SIMPLE_SYNTH_INPUT_ROOT', true);"
    "assert(~strcmp(inputRoot, outputParent) && ~startsWith(outputParent + filesep, inputRoot + filesep), ..."
    "verify_sha256_manifest(inputRoot);"
    "settingsPath = fullfile(inputRoot, 'provenance', 'generator_settings.json');"
    "receiptPath = fullfile(inputRoot, 'provenance', 'build_receipt.json');"
    "datasetList = read_dataset_list(fullfile(inputRoot, 'data_lists', 'dataset_list.csv'), EXPECTED_SUBJECTS);"
    "copy_bundle_scaffold(inputRoot, partialRoot);"
    "pathAuditTokens = unique([inputRoot; partialRoot; outputRoot; outputParent; generatorRoot; ..."
    "arrayPath = fullfile(inputRoot, 'staging', 'arrays', arrayName);"
    "function copy_bundle_scaffold(inputRoot, partialRoot)"
    "for i = 1:numel(names), copyfile(fullfile(inputRoot, 'dataset_assets', names{i}), fullfile(partialRoot, targets{i})); end"
    "for i = 1:numel(names), copyfile(fullfile(inputRoot, 'provenance', names{i}), fullfile(partialRoot, 'provenance', names{i})); end"
    "copyfile(fullfile(inputRoot, 'data_lists', 'dataset_list.csv'), fullfile(partialRoot, 'data_lists', 'dataset_list.csv'));"
    ];
verifyEqual(testCase, sort(actual), sort(expected), ...
    'Every inputRoot use must remain an explicitly reviewed read/source operation.');
end

function source = packaging_source
source = fileread(fullfile(fileparts(fileparts(mfilename('fullpath'))), 'package_and_verify_eeglab.m'));
end

function source = preflight_source
source = fileread(fullfile(fileparts(fileparts(mfilename('fullpath'))), 'preflight_environment.m'));
end

function source = capability_source
source = fileread(fullfile(fileparts(fileparts(mfilename('fullpath'))), 'validate_runtime_capabilities.m'));
end
