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
    'EXPECTED_EEGLAB_VERSION = ''2026.0.0''','EXPECTED_SIMPLE_COMMIT = ''c87ad575403336fe3bdea805fab0ebd28d77df1f''', ...
    'strcmp(EEG.event.type, ''stimulus'')','assert_semantic_equal_except_path', ...
    'assert_dataset_list_bijection','verify_sha256_manifest(partialRoot)', ...
    'create_directory_exclusive(partialRoot)', ...
    'exclusive_atomic_move(partialRoot, outputRoot, pythonPath, helperPath)'};
for i = 1:numel(required), verifyNotEmpty(testCase, strfind(source, required{i})); end
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
for forbidden = {'.edf','.bdf','/volumes/','uigetfile','nrf.mat','nrfutils','simple/nrfs'}
    verifyEmpty(testCase, strfind(source, forbidden{1}));
end
end

function testCheckpointConstantsAreFrozen(testCase)
source = source_text;
verifyNotEmpty(testCase, strfind(source, 'EXPECTED_MATLAB_RELEASE = ''2026a'''));
verifyNotEmpty(testCase, strfind(source, 'EXPECTED_FRAMEWORK_COMMIT = ''2cb9227e75468e9393105e729b4ce590b76dab02'''));
verifyNotEmpty(testCase, strfind(source, 'EXPECTED_EXCLUSIVE_RENAME_HELPER_SHA256 = ''e2c5d209c1034cb52fc8eb79fef3ca3722575e52b243cffdc9a5b46cbf76fc11'''));
verifyNotEmpty(testCase, strfind(source, 'EXPECTED_SETTINGS_SHA256 = ''9be35cfedf7aa42edc43c6032c75b709c838fb5582fc9ced39bd8ef832424ded'''));
verifyEmpty(testCase, strfind(source, '__FREEZE_'));
verifyEmpty(testCase, strfind(source, 'EXPECTED_GENERATOR_COMMIT'));
verifyNotEmpty(testCase, strfind(source, 'strcmp(receipt.generator_commit, generatorHead)'));
verifyNotEmpty(testCase, strfind(source, 'require_tracked_clean_paths'));
verifyNotEmpty(testCase, strfind(source, 'matlab/package_and_verify_eeglab.m'));
verifyNotEmpty(testCase, strfind(source, 'tools/exclusive_rename_macos.py'));
end

function testCanonicalSettingsHashNotPrettySourceHash(testCase)
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
pretty = fileread(fullfile(root, 'config', 'generator_settings.json'));
jsondecode(pretty); % prove the pretty source remains valid JSON
canonical = canonical_json;
verifyNotEqual(testCase, sha256_text(pretty), sha256_text(canonical));
verifyEqual(testCase, sha256_text(canonical), '9be35cfedf7aa42edc43c6032c75b709c838fb5582fc9ced39bd8ef832424ded');
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
command = sprintf('''%s'' -I -c ''%s'' ''%s''', python, code, config);
[status, text] = system(command); assert(status == 0);
end

function digest = sha256_text(text)
md = java.security.MessageDigest.getInstance('SHA-256'); md.update(uint8(text));
digest = lower(reshape(dec2hex(typecast(md.digest(), 'uint8'),2).',1,[]));
end

function source = source_text
source = fileread(fullfile(fileparts(fileparts(mfilename('fullpath'))), 'package_and_verify_eeglab.m'));
end
