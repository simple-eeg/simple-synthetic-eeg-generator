function tests = test_packaging_source_contract
% Static gates for the native packager. Runtime gates are separate below.
tests = functiontests(localfunctions);
end

function testRequiredFrozenAndNativeCalls(testCase)
source = source_text;
required = {'eeg_emptyset','eeg_checkset','pop_saveset','savemode'', ''onefile', ...
    'version'', ''6','load(setPath, ''-mat'')','-struct'', ''sanitisedStored', ...
    'normalise_mat_header(setPath)','pop_loadset','EXPECTED_SAMPLE_COUNT = 30000', ...
    'EXPECTED_EVENT_LATENCY = 15001','EXPECTED_MATLAB_VERSION = ''26.1.0.3312084 (R2026a) Update 4''', ...
    'EXPECTED_EEGLAB_VERSION = ''2026.0.0''','EXPECTED_INPUT_SCHEMA = ''simple-synthetic-array-stage-receipt-v2''', ...
    '''simple-synthetic-eeglab-metadata-v2''','''simple-synthetic-eeglab-packaging-v2''', ...
    'strcmp(EEG.event.type, ''stimulus'')','assert_semantic_equal_except_path', ...
    'assert_dataset_list_bijection','verify_sha256_manifest(partialRoot)', ...
    'create_directory_exclusive(partialRoot)', ...
    'exclusive_atomic_move(partialRoot, outputRoot, pythonPath, helperPath)'};
for i = 1:numel(required), verifyNotEmpty(testCase, strfind(source, required{i})); end
end

function testEEGLABPathArgumentsCrossAsChar(testCase)
source = source_text;
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
source = source_text;
names = regexp(source, 'SIMPLE_SYNTH_[A-Z_]+', 'match');
verifyEqual(testCase, sort(unique(names)), sort({'SIMPLE_SYNTH_EEGLAB_ROOT', ...
    'SIMPLE_SYNTH_GENERATOR_ROOT','SIMPLE_SYNTH_INPUT_ROOT','SIMPLE_SYNTH_OUTPUT_ROOT','SIMPLE_SYNTH_PYTHON'}));
end

function testProducingMatlabIdentityMatchesRuntime(testCase)
verifyEqual(testCase, version('-release'), '2026a');
verifyEqual(testCase, version, '26.1.0.3312084 (R2026a) Update 4');
end

function testPinnedEEGLABSourcesAndPythonBoundary(testCase)
source = source_text;
verifyEqual(testCase, numel(regexp(source, '''[0-9a-f]{64}''', 'match')), 10);
required = {'eeglab.m','eeg_emptyset.m','eeg_checkset.m','pop_saveset.m','pop_loadset.m', ...
    'eeg_getversion.m','EXPECTED_PYTHON_LINK_TEXT = ''python3.13''', ...
    'EXPECTED_PYTHON_TARGET_SHA256','EXPECTED_LOCK_SHA256','numel(identity.packages) == 19', ...
    'tools'', ''exclusive_rename_macos.py','-I'};
for i = 1:numel(required), verifyNotEmpty(testCase, strfind(source, required{i})); end
end

function testNoUnsafePublicationFallback(testCase)
source = source_text;
for forbidden = {'StandardCopyOption.ATOMIC_MOVE','movefile(','copyfile(partialRoot', ...
        '''f''','rm -','rmdir(outputRoot','delete(outputRoot'}
    verifyEmpty(testCase, strfind(source, forbidden{1}));
end
end

function testManifestAndPathHardening(testCase)
source = source_text;
required = {'path_exists_including_symlink','assert_no_symlink_components','canonical_existing_path', ...
    'same_file_store','refuse_stale_partials','is_safe_relative_posix','walk_regular_files', ...
    'isRegularFile','Bundle contains a symlink','Bundle contains a non-regular object', ...
    'Manifest omits or invents a bundle file','Unsafe/duplicate manifest path', ...
    'endsWith(lower(actual), ".fdt")','looks_like_absolute_path','audit_raw_mat_bytes'};
for i = 1:numel(required), verifyNotEmpty(testCase, strfind(source, required{i})); end
end

function testNoExternalEEGOrTemplateSearch(testCase)
source = lower(source_text);
for forbidden = {'.edf','.bdf','/volumes/','uigetfile','nrf.mat','nrfutils'}
    verifyEmpty(testCase, strfind(source, forbidden{1}));
end
end

function testRequiredConstantsAreFrozen(testCase)
source = source_text;
verifyNotEmpty(testCase, strfind(source, 'EXPECTED_MATLAB_RELEASE = ''2026a'''));
verifyNotEmpty(testCase, strfind(source, 'EXPECTED_SIMPLE_COMMIT = ''e4843b858131d7d6e019740de24f44ade12bc813'''));
verifyNotEmpty(testCase, strfind(source, 'EXPECTED_EXCLUSIVE_RENAME_HELPER_SHA256 = ''5340a2ba3f408aa86f97309ad89daa1b52fe4a0e144cf4cb6a9ce0c7dc273a54'''));
verifyNotEmpty(testCase, strfind(source, 'EXPECTED_SETTINGS_SHA256 = ''44b776635e010dfffa874260d340c6ea38d7e7e142bf78bf1b3b50ca68c14ae7'''));
verifyEmpty(testCase, strfind(source, '__FREEZE_'));
verifyEmpty(testCase, strfind(source, 'EXPECTED_GENERATOR_COMMIT'));
verifyNotEmpty(testCase, strfind(source, 'strcmp(receipt.generator_commit, generatorHead)'));
verifyNotEmpty(testCase, strfind(source, 'require_tracked_clean_paths'));
verifyNotEmpty(testCase, strfind(source, 'matlab/package_and_verify_eeglab.m'));
verifyNotEmpty(testCase, strfind(source, 'matlab/shell_command.m'));
verifyNotEmpty(testCase, strfind(source, 'matlab/contains_ascii_case_insensitive_bytes.m'));
verifyNotEmpty(testCase, strfind(source, 'matlab/find_stale_partial_siblings.m'));
verifyNotEmpty(testCase, strfind(source, 'tools/exclusive_rename_macos.py'));
verifyEmpty(testCase, strfind(source, 'function command = shell_command'));
verifyEmpty(testCase, strfind(source, 'contains(haystack'));
verifyNotEmpty(testCase, strfind(source, ...
    'assert_unique_function_binding(''shell_command'', fullfile(scriptDir, ''shell_command.m''))'));
verifyNotEmpty(testCase, strfind(source, ...
    'assert_unique_function_binding(''contains_ascii_case_insensitive_bytes'''));
verifyNotEmpty(testCase, strfind(source, ...
    'assert_unique_function_binding(''find_stale_partial_siblings'''));
verifyNotEmpty(testCase, strfind(source, ...
    'candidateNames = find_stale_partial_siblings(outputRoot)'));
verifyEmpty(testCase, strfind(source, 'string([name ext ''.partial.''])'));
end

function testInputRootHasOnlyReviewedReadUses(testCase)
source = source_text;
lines = splitlines(string(source));
actual = strtrim(lines(contains(lines, 'inputRoot')));
expected = [
    "inputRoot = require_canonical_root('SIMPLE_SYNTH_INPUT_ROOT', true);"
    "assert(~strcmp(inputRoot, outputParent) && ~startsWith(outputParent + filesep, inputRoot + filesep), ..."
    "verify_sha256_manifest(inputRoot);"
    "settingsPath = fullfile(inputRoot, 'provenance', 'generator_settings.json');"
    "receiptPath = fullfile(inputRoot, 'provenance', 'build_receipt.json');"
    "reproducibility = jsondecode(fileread(fullfile(inputRoot, 'provenance', 'reproducibility_receipt.json')));"
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

function testCanonicalSettingsHashNotPrettySourceHash(testCase)
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
pretty = fileread(fullfile(root, 'config', 'generator_settings.json'));
jsondecode(pretty); % prove the pretty source remains valid JSON
canonical = canonical_json;
verifyNotEqual(testCase, sha256_text(pretty), sha256_text(canonical));
verifyEqual(testCase, sha256_text(canonical), '44b776635e010dfffa874260d340c6ea38d7e7e142bf78bf1b3b50ca68c14ae7');
source = source_text;
verifyNotEmpty(testCase, strfind(source, 'sha256_file(settingsPath), EXPECTED_SETTINGS_SHA256'));
end

function text = canonical_json
% Mirror Python's sort_keys=True, separators=(',', ':'), final newline for
% this fixed settings document by invoking the exact reviewed serializer.
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
python = string(getenv('SIMPLE_SYNTH_PYTHON'));
assert(strlength(python) > 0, ...
    'Set SIMPLE_SYNTH_PYTHON to the exact reviewed interpreter for this test.');
config = fullfile(root, 'config', 'generator_settings.json');
code = 'import json,sys;print(json.dumps(json.load(open(sys.argv[1])),sort_keys=True,separators=(chr(44),chr(58))))';
matlabDir = fullfile(root, 'matlab');
addpath(matlabDir); cleanup = onCleanup(@() rmpath(matlabDir)); %#ok<NASGU>
command = shell_command(python, ["-I", "-c", string(code), string(config)]);
[status, text] = system(command); assert(status == 0);
end

function digest = sha256_text(text)
md = java.security.MessageDigest.getInstance('SHA-256'); md.update(uint8(text));
digest = lower(reshape(dec2hex(typecast(md.digest(), 'uint8'),2).',1,[]));
end

function source = source_text
source = fileread(fullfile(fileparts(fileparts(mfilename('fullpath'))), 'package_and_verify_eeglab.m'));
end
