%% Package and verify the SIMPLE synthetic EEG demonstration bundle
% Native packaging transaction for MATLAB 26.1.0.3312084 (R2026a Update 4)
% and EEGLAB 2026.0.0. This script only reads the accepted Python array
% stage and writes one new sibling partial before exclusive atomic promotion.
%
% Required environment variables:
%   SIMPLE_SYNTH_INPUT_ROOT     immutable Python array-stage root
%   SIMPLE_SYNTH_OUTPUT_ROOT    absent final bundle destination
%   SIMPLE_SYNTH_EEGLAB_ROOT    exact canonical EEGLAB 2026.0.0 root
%   SIMPLE_SYNTH_GENERATOR_ROOT exact clean frozen generator checkout
%   SIMPLE_SYNTH_PYTHON         exact <generator>/.venv/bin/python link
%
% The current MATLAB folder must be this tracked matlab/ directory. EEGLAB
% must already be initialised from the exact root. No workflow script runs.

clearvars;

EXPECTED_MATLAB_RELEASE = '2026a';
EXPECTED_MATLAB_VERSION = '26.1.0.3312084 (R2026a) Update 4';
EXPECTED_EEGLAB_VERSION = '2026.0.0';
EXPECTED_SUBJECTS = compose('%03d', (1:31)');
EXPECTED_INPUT_SCHEMA = 'simple-synthetic-array-stage-receipt-v1';
EXPECTED_SAMPLE_COUNT = 30000;
EXPECTED_RATE_HZ = 1000;
EXPECTED_EVENT_LATENCY = 15001;
% Update once, immediately before the generator source checkpoint, from the
% exact final tracked canonical settings bytes. Never derive this at runtime.
EXPECTED_SETTINGS_SHA256 = '7c76309cd16bfb72440594512fd27fcd511d7f7435c19e0b764456fad8198607';
EXPECTED_SIMPLE_COMMIT = 'c87ad575403336fe3bdea805fab0ebd28d77df1f';
EXPECTED_FRAMEWORK_COMMIT = '4907ad49a55e3dec22a74a0a13acdddd63bcddf7';
EXPECTED_EXCLUSIVE_RENAME_HELPER_SHA256 = 'e2c5d209c1034cb52fc8eb79fef3ca3722575e52b243cffdc9a5b46cbf76fc11';
EXPECTED_PYTHON_VERSION = '3.13.6';
EXPECTED_PYTHON_LINK_TEXT = 'python3.13';
EXPECTED_PYTHON313_LINK_TEXT = '/opt/homebrew/opt/python@3.13/bin/python3.13';
EXPECTED_PYTHON_CANONICAL_TARGET = '/opt/homebrew/Cellar/python@3.13/3.13.6/Frameworks/Python.framework/Versions/3.13/bin/python3.13';
EXPECTED_PYTHON_BASE_PREFIX = '/opt/homebrew/opt/python@3.13/Frameworks/Python.framework/Versions/3.13';
EXPECTED_PYTHON_TARGET_SHA256 = '0d1fc12cf4887074b3eb257241f152cb85ca5a135879120b7e8e3b9aa57d5094';
EXPECTED_LOCK_SHA256 = 'ed84d519fd102843c2da38e7174d829a352eabfb4babdb8321018dbb9cce6b05';
EXPECTED_PYTHON_PACKAGES = {
    'contourpy','1.3.3'; 'cycler','0.12.1'; 'fonttools','4.63.0'; 'iniconfig','2.3.0';
    'kiwisolver','1.5.0'; 'matplotlib','3.10.0'; 'neurodsp','2.3.0'; 'numpy','2.2.2';
    'packaging','26.3'; 'pillow','12.3.0'; 'pip','25.2'; 'pluggy','1.6.0';
    'pyparsing','3.3.2'; 'pytest','8.3.4'; 'python-dateutil','2.9.0.post0';
    'scipy','1.15.1'; 'setuptools','76.0.0'; 'six','1.17.0'; 'wheel','0.45.1'};
EXPECTED_EEGLAB_FILES = {
    'eeglab.m', '227ee7b89f2a852d78b342aa9c88e2accbf5fad3915979d1077a109e839a7d10';
    'functions/popfunc/eeg_emptyset.m', '5359ea9eeb4dc8c85c3465cf6ef7ad8c769f839f027734b268e2b37018cb76be';
    'functions/adminfunc/eeg_checkset.m', 'fa6356b4a64ea6e16683acc4c65b257084dd1bfc995848de402244ccba00d6f0';
    'functions/popfunc/pop_saveset.m', 'dab9ddec4475be7ec97a5f2409dc3f6321e1f8b61eb9f90ea83f498648bb71c1';
    'functions/popfunc/pop_loadset.m', '2c688149f710c9b6f2d340fefdf185db0db60f4828215cb201c12728d5de7fc2';
    'functions/adminfunc/eeg_getversion.m', '0369d508b5b9e77d7ba12e486fa3b6998f8e34d259818a883e0a21366aa803f4'};

scriptDir = fileparts(mfilename('fullpath'));
generatorRoot = require_canonical_root('SIMPLE_SYNTH_GENERATOR_ROOT', true);
assert(strcmp(scriptDir, fullfile(generatorRoot, 'matlab')), ...
    'Script must be the tracked file beneath the exact generator root.');
assert(strcmp(pwd, scriptDir), 'Run unchanged with MATLAB current folder = tracked matlab/.');
assert(strcmp(version('-release'), EXPECTED_MATLAB_RELEASE), 'MATLAB release differs.');
assert(strcmp(version, EXPECTED_MATLAB_VERSION), 'MATLAB full version/build differs.');
assert_unique_function_binding('shell_command', fullfile(scriptDir, 'shell_command.m'));
assert_unique_function_binding('contains_ascii_case_insensitive_bytes', ...
    fullfile(scriptDir, 'contains_ascii_case_insensitive_bytes.m'));
assert_unique_function_binding('find_stale_partial_siblings', ...
    fullfile(scriptDir, 'find_stale_partial_siblings.m'));
generatorHead = verify_clean_generator_checkout(generatorRoot);

eeglabRoot = require_canonical_root('SIMPLE_SYNTH_EEGLAB_ROOT', true);
verify_eeglab_environment(eeglabRoot, EXPECTED_EEGLAB_FILES, EXPECTED_EEGLAB_VERSION);
pythonPath = verify_python_environment(generatorRoot, EXPECTED_PYTHON_LINK_TEXT, ...
    EXPECTED_PYTHON313_LINK_TEXT, EXPECTED_PYTHON_CANONICAL_TARGET, EXPECTED_PYTHON_BASE_PREFIX, ...
    EXPECTED_PYTHON_TARGET_SHA256, EXPECTED_PYTHON_VERSION, EXPECTED_LOCK_SHA256, EXPECTED_PYTHON_PACKAGES);
helperPath = fullfile(generatorRoot, 'tools', 'exclusive_rename_macos.py');
assert(isfile(helperPath) && ~path_is_symlink(helperPath), 'Tracked exclusive-rename helper is absent or a symlink.');
helperSha256 = sha256_file(helperPath);
assert(strcmp(helperSha256, EXPECTED_EXCLUSIVE_RENAME_HELPER_SHA256), 'Exclusive-rename helper source hash differs.');
require_tracked_clean_paths(generatorRoot, ...
    ["matlab/package_and_verify_eeglab.m"; "matlab/shell_command.m"; ...
     "matlab/contains_ascii_case_insensitive_bytes.m"; ...
     "matlab/find_stale_partial_siblings.m"; ...
     "tools/exclusive_rename_macos.py"; ...
     "config/generator_settings.json"; "requirements/producing.lock"]);

inputRoot = require_canonical_root('SIMPLE_SYNTH_INPUT_ROOT', true);
outputRoot = require_absent_canonical_destination('SIMPLE_SYNTH_OUTPUT_ROOT');
outputParent = string(fileparts(outputRoot));
assert(~strcmp(inputRoot, outputParent) && ~startsWith(outputParent + filesep, inputRoot + filesep), ...
    'Output parent must be outside the immutable input stage.');
assert(~strcmp(generatorRoot, outputParent) && ~startsWith(outputParent + filesep, generatorRoot + filesep), ...
    'Output parent must be outside the generator checkout.');
refuse_stale_partials(outputRoot);
partialRoot = outputRoot + ".partial." + string(java.util.UUID.randomUUID);
assert(~path_exists_including_symlink(partialRoot), 'Unique partial path unexpectedly exists.');
create_directory_exclusive(partialRoot);
assert(same_file_store(partialRoot, outputParent), 'Partial and final parent are not on the same file store.');
failureCleanup = onCleanup(@() mark_failure(partialRoot));

verify_sha256_manifest(inputRoot);
settingsPath = fullfile(inputRoot, 'provenance', 'generator_settings.json');
receiptPath = fullfile(inputRoot, 'provenance', 'build_receipt.json');
assert(strcmp(sha256_file(settingsPath), EXPECTED_SETTINGS_SHA256), 'Frozen settings SHA-256 differs.');
settings = jsondecode(fileread(settingsPath));
receipt = jsondecode(fileread(receiptPath));
reproducibility = jsondecode(fileread(fullfile(inputRoot, 'provenance', 'reproducibility_receipt.json')));
assert(strcmp(receipt.schema, EXPECTED_INPUT_SCHEMA) && strcmp(receipt.status, 'passed'), 'Input receipt is not accepted.');
assert(strcmp(receipt.generator_commit, generatorHead), 'Array stage was not produced by this exact clean generator checkout.');
assert(strcmp(receipt.framework_commit, EXPECTED_FRAMEWORK_COMMIT), 'Framework source checkpoint differs.');
assert(strcmp(receipt.simple_commit, EXPECTED_SIMPLE_COMMIT), 'SIMPLE source checkpoint differs.');
assert(strcmp(reproducibility.schema, 'simple-synthetic-reproducibility-v1') && ...
    strcmp(reproducibility.status, 'passed') && reproducibility.fresh_process_count == 3 && ...
    reproducibility.canonical_process_count == 2 && reproducibility.shuffled_process_count == 1, ...
    'Input stage lacks the exact three-fresh-process reproducibility gate.');
assert(receipt.subject_count == 31 && receipt.sample_count_per_subject == EXPECTED_SAMPLE_COUNT, 'Input receipt counts differ.');
assert(strcmp(settings.dataset.channel, 'Cz') && strcmp(settings.dataset.event_label, 'stimulus'), 'Dataset labels differ.');
assert(settings.dataset.sample_rate_hz == EXPECTED_RATE_HZ && ...
    settings.dataset.event_latency_eeglab == EXPECTED_EVENT_LATENCY, 'Dataset timing differs.');

datasetList = read_dataset_list(fullfile(inputRoot, 'data_lists', 'dataset_list.csv'), EXPECTED_SUBJECTS);
copy_bundle_scaffold(inputRoot, partialRoot);

roundTripRows = cell(31, 5);
expectedSetPaths = strings(31, 1);
pathAuditTokens = unique([inputRoot; partialRoot; outputRoot; outputParent; generatorRoot; ...
    scriptDir; eeglabRoot; string(getenv('HOME')); string(tempdir); string(getenv('USER'))]);
pathAuditTokens(strlength(pathAuditTokens) == 0) = [];
for i = 1:31
    subjectID = char(EXPECTED_SUBJECTS(i));
    arrayName = sprintf('sub-%s_ses-01_run-01_eeg.f32le', subjectID);
    arrayPath = fullfile(inputRoot, 'staging', 'arrays', arrayName);
    samples = read_f32le_exact(arrayPath, EXPECTED_SAMPLE_COUNT);
    rawDir = char(fullfile(partialRoot, 'data', 'raw', ['sub-' subjectID], 'ses-01', 'eeg'));
    mkdir(rawDir);
    setName = sprintf('sub-%s_ses-01_run-01_eeg.set', subjectID);
    assert(ischar(rawDir) && isrow(rawDir) && ischar(setName) && isrow(setName), ...
        'EEGLAB path and filename arguments must be character row vectors.');

    EEG = make_eeg(subjectID, setName, samples, EXPECTED_SAMPLE_COUNT, ...
        EXPECTED_RATE_HZ, EXPECTED_EVENT_LATENCY, receipt, EXPECTED_SETTINGS_SHA256);
    EEG = eeg_checkset(EEG, 'eventconsistency');
    savedEEG = pop_saveset(EEG, 'filename', setName, 'filepath', rawDir, ...
        'savemode', 'onefile', 'version', '6');
    setPath = fullfile(rawDir, setName);
    assert(isfile(setPath), 'Expected .set was not created.');
    assert(isempty(find_files_case_insensitive(rawDir, '.fdt')), 'One-file save created an .fdt.');
    nativeStored = load(setPath, '-mat');
    assert(isstruct(nativeStored) && isfield(nativeStored, 'data') && ~isfield(nativeStored, 'EEG'), ...
        'EEGLAB one-file save must use the canonical top-level field structure.');
    assert(strcmp(nativeStored.filepath, rawDir), 'Native EEGLAB save did not record its actual path as expected.');
    assert(strcmp(savedEEG.filepath, rawDir), 'Returned native EEGLAB structure path differs.');
    sanitisedStored = nativeStored;
    sanitisedStored.filepath = '';
    sanitisedStored.filename = setName;
    assert_semantic_equal_except_path(nativeStored, sanitisedStored, rawDir, setName);
    save(setPath, '-v6', '-mat', '-struct', 'sanitisedStored');
    normalise_mat_header(setPath);
    storedCheck = load(setPath, '-mat');
    assert_semantic_equal_except_path(nativeStored, storedCheck, rawDir, setName);
    assert(isempty(storedCheck.filepath) && strcmp(storedCheck.filename, setName), 'Serialized path was not neutralised.');
    assert(isempty(storedCheck.datfile) && isnumeric(storedCheck.data), 'One-file dataset contains an external-data reference.');
    audit_serialized_structure(storedCheck, pathAuditTokens);
    audit_raw_mat_bytes(setPath, pathAuditTokens);
    reloaded = pop_loadset('filename', setName, 'filepath', rawDir, 'loadmode', 'all');
    reloaded = eeg_checkset(reloaded, 'eventconsistency');
    verify_reloaded_eeg(reloaded, samples, EXPECTED_SAMPLE_COUNT, EXPECTED_RATE_HZ, EXPECTED_EVENT_LATENCY);
    relativeSet = string(fullfile('data', 'raw', ['sub-' subjectID], 'ses-01', 'eeg', setName));
    expectedSetPaths(i) = replace(relativeSet, filesep, '/');
    roundTripRows(i,:) = {subjectID, '01', '01', sha256_file(arrayPath), sha256_file(setPath)};
end

assert_dataset_list_bijection(partialRoot, datasetList, expectedSetPaths);
assert(isempty(find_files_case_insensitive(partialRoot, '.fdt')), 'Bundle contains an .fdt with unexpected case.');
write_roundtrip_csv(fullfile(partialRoot, 'provenance', 'eeglab_roundtrip.csv'), roundTripRows);
write_packaging_receipt(fullfile(partialRoot, 'provenance', 'eeglab_packaging_receipt.json'), ...
    receipt, EXPECTED_SETTINGS_SHA256, helperSha256, EXPECTED_PYTHON_TARGET_SHA256, EXPECTED_LOCK_SHA256);
write_manifest(partialRoot);
verify_sha256_manifest(partialRoot);
assert(~path_exists_including_symlink(outputRoot), 'Final output appeared during the transaction.');
exclusive_atomic_move(partialRoot, outputRoot, pythonPath, helperPath);
clear failureCleanup;
fprintf('Packaged and round-trip verified 31 one-file EEGLAB datasets; zero .fdt files.\n');

function pathValue = require_canonical_root(variableName, mustExist)
pathValue = string(getenv(variableName));
assert(strlength(pathValue) > 0 && startsWith(pathValue, filesep), '%s must be an absolute POSIX path.', variableName);
assert(is_lexically_canonical(pathValue), '%s must be lexically canonical.', variableName);
if mustExist, assert(isfolder(pathValue), '%s must be an existing directory.', variableName); end
assert_no_symlink_components(pathValue, true);
assert(strcmp(canonical_existing_path(pathValue), pathValue), '%s differs from its canonical path.', variableName);
end

function destination = require_absent_canonical_destination(variableName)
destination = string(getenv(variableName));
assert(strlength(destination) > 0 && startsWith(destination, filesep), '%s must be absolute.', variableName);
assert(is_lexically_canonical(destination), '%s must be lexically canonical.', variableName);
assert(~path_exists_including_symlink(destination), '%s must be absent including symlinks.', variableName);
parent = string(fileparts(destination));
assert(isfolder(parent) && strcmp(canonical_existing_path(parent), parent), 'Destination parent must be canonical and existing.');
assert_no_symlink_components(parent, true);
end

function tf = is_lexically_canonical(pathValue)
text = char(pathValue);
tf = startsWith(text, '/') && ~contains(text, '//') && ...
    isempty(regexp(text, '(^|/)\.\.?(/|$)', 'once')) && ...
    (strcmp(text, '/') || ~endsWith(text, '/'));
end

function canonical = canonical_existing_path(pathValue)
canonical = string(char(java.nio.file.Paths.get(char(pathValue), ...
    javaArray('java.lang.String', 0)).toRealPath(javaArray('java.nio.file.LinkOption', 0)).toString));
end

function assert_no_symlink_components(pathValue, includeLeaf)
parts = split(extractAfter(string(pathValue), 1), filesep);
current = string(filesep);
limit = numel(parts) - (~includeLeaf);
for i = 1:limit
    if strlength(parts(i)) == 0, continue; end
    current = fullfile(current, parts(i));
    assert(~path_is_symlink(current), 'Path contains a forbidden symlink component: %s', current);
end
end

function tf = path_is_symlink(pathValue)
jpath = java.nio.file.Paths.get(char(pathValue), javaArray('java.lang.String', 0));
tf = java.nio.file.Files.isSymbolicLink(jpath);
end

function assert_unique_function_binding(name, expectedPath)
locations = string(which(name, '-all'));
assert(isscalar(locations) && strcmp(locations, expectedPath), ...
    'Production helper must resolve uniquely to its exact tracked path: %s', name);
end

function tf = path_exists_including_symlink(pathValue)
jpath = java.nio.file.Paths.get(char(pathValue), javaArray('java.lang.String', 0));
options = javaArray('java.nio.file.LinkOption', 1);
options(1) = java.nio.file.LinkOption.NOFOLLOW_LINKS;
tf = java.nio.file.Files.exists(jpath, options);
end

function tf = same_file_store(left, right)
tf = java.nio.file.Files.getFileStore(java.nio.file.Paths.get(char(left), javaArray('java.lang.String', 0))).equals( ...
    java.nio.file.Files.getFileStore(java.nio.file.Paths.get(char(right), javaArray('java.lang.String', 0))));
end

function create_directory_exclusive(pathValue)
jpath = java.nio.file.Paths.get(char(pathValue), javaArray('java.lang.String', 0));
attributes = javaArray('java.nio.file.attribute.FileAttribute', 0);
java.nio.file.Files.createDirectory(jpath, attributes);
assert(isfolder(pathValue) && ~path_is_symlink(pathValue), 'Exclusive partial directory creation failed.');
end

function refuse_stale_partials(outputRoot)
candidateNames = find_stale_partial_siblings(outputRoot);
assert(isempty(candidateNames), 'A stale sibling packaging partial exists; inspect it and stop.');
end

function verify_eeglab_environment(root, expectedFiles, expectedVersion)
for i = 1:size(expectedFiles, 1)
    pathValue = fullfile(root, strrep(expectedFiles{i,1}, '/', filesep));
    assert(isfile(pathValue) && ~path_is_symlink(pathValue), 'Pinned EEGLAB source is absent/symlinked.');
    assert(strcmp(sha256_file(pathValue), expectedFiles{i,2}), 'Pinned EEGLAB source hash differs: %s', expectedFiles{i,1});
end
required = {'eeglab','eeg_emptyset','eeg_checkset','pop_saveset','pop_loadset','eeg_getversion'};
for i = 1:numel(required)
    locations = string(which(required{i}, '-all'));
    assert(isscalar(locations) && startsWith(locations(1), root + filesep), ...
        'EEGLAB function must resolve uniquely beneath the pinned root: %s', required{i});
end
assert(strcmp(char(eeg_getversion), expectedVersion), 'EEGLAB version differs.');
end

function head = verify_clean_generator_checkout(root)
[status, top] = system(shell_command('/usr/bin/git', ["-C",root,"rev-parse","--show-toplevel"]));
assert(status == 0 && strcmp(strtrim(top), root), 'Generator root is not its exact Git top level.');
[status, head] = system(shell_command('/usr/bin/git', ["-C",root,"rev-parse","HEAD"]));
head = string(strtrim(head));
assert(status == 0 && ~isempty(regexp(head, '^[0-9a-f]{40}$', 'once')), 'Generator HEAD is not one exact commit.');
[status, dirty] = system(shell_command('/usr/bin/git', ["-C",root,"status","--porcelain=v1","--untracked-files=all"]));
assert(status == 0 && isempty(strtrim(dirty)), 'Generator checkout must be clean with no unexpected untracked files.');
end

function require_tracked_clean_paths(root, relativePaths)
for i = 1:numel(relativePaths)
    relative = relativePaths(i);
    [status, output] = system(shell_command('/usr/bin/git', ["-C",root,"ls-files","--error-unmatch","--",relative]));
    assert(status == 0 && strcmp(strtrim(output), relative), 'Producing source path is not tracked exactly: %s', relative);
    [status, ~] = system(shell_command('/usr/bin/git', ["-C",root,"diff","--quiet","HEAD","--",relative]));
    assert(status == 0, 'Producing source path differs from clean HEAD: %s', relative);
end
end

function pythonPath = verify_python_environment(generatorRoot, linkText, python313LinkText, ...
    expectedTarget, expectedBasePrefix, targetDigest, expectedVersion, lockDigest, expectedPackages)
pythonPath = string(getenv('SIMPLE_SYNTH_PYTHON'));
expectedPath = fullfile(generatorRoot, '.venv', 'bin', 'python');
assert(strcmp(pythonPath, expectedPath), 'SIMPLE_SYNTH_PYTHON must be exact <generator>/.venv/bin/python.');
assert(path_is_symlink(pythonPath) && strcmp(string(java.nio.file.Files.readSymbolicLink( ...
    java.nio.file.Paths.get(char(pythonPath), javaArray('java.lang.String', 0))).toString), linkText), ...
    'The one accepted venv interpreter symlink differs.');
pythonBin = string(fileparts(pythonPath));
pythonVenv = string(fileparts(pythonBin));
assert_no_symlink_components(pythonVenv, true);
assert(isfolder(pythonBin) && ~path_is_symlink(pythonBin), 'Virtual-environment bin directory differs.');
python313 = fullfile(generatorRoot, '.venv', 'bin', 'python3.13');
assert(path_is_symlink(python313) && strcmp(string(java.nio.file.Files.readSymbolicLink( ...
    java.nio.file.Paths.get(char(python313), javaArray('java.lang.String', 0))).toString), python313LinkText), ...
    'The pinned python3.13 symlink differs.');
target = canonical_existing_path(pythonPath);
assert(strcmp(target, expectedTarget) && strcmp(sha256_file(target), targetDigest), 'Canonical Python target identity/hash differs.');
lockPath = fullfile(generatorRoot, 'requirements', 'producing.lock');
assert(isfile(lockPath) && ~path_is_symlink(lockPath) && strcmp(sha256_file(lockPath), lockDigest), ...
    'Complete producing lock identity/hash differs.');
code = ['import importlib.metadata as m,json,sys;' ...
    'print(json.dumps({"version":sys.version.split()[0],"executable":sys.executable,' ...
    '"prefix":sys.prefix,"base_prefix":sys.base_prefix,' ...
    '"packages":sorted((d.metadata["Name"].lower(),d.version) for d in m.distributions())},separators=(",",":")))'];
[status, output] = system(shell_command(pythonPath, ["-I","-c",string(code)]));
assert(status == 0, 'Locked Python identity query failed.');
identity = jsondecode(strtrim(output));
assert(strcmp(identity.version, expectedVersion) && strcmp(identity.executable, pythonPath) && ...
    strcmp(identity.prefix, fullfile(generatorRoot, '.venv')) && strcmp(identity.base_prefix, expectedBasePrefix) && ...
    numel(identity.packages) == 19, ...
    'Locked Python identity or exact 19-package count differs.');
actualPackages = strings(numel(identity.packages), 2);
for i = 1:numel(identity.packages)
    pair = string(identity.packages{i});
    assert(numel(pair) == 2, 'Installed Python package receipt row differs.');
    actualPackages(i,:) = reshape(pair, 1, 2);
end
assert(isequal(actualPackages, string(expectedPackages)), 'Installed Python package names/versions differ from the exact lock.');
end

function exclusive_atomic_move(source, destination, pythonPath, helperPath)
assert(~path_exists_including_symlink(destination), 'Exclusive destination unexpectedly exists.');
[status, output] = system(shell_command(pythonPath, ["-I", string(helperPath), string(source), string(destination)]));
assert(status == 0, 'Exclusive atomic promotion failed without overwrite: %s', strtrim(output));
assert(isfolder(destination) && ~path_exists_including_symlink(source), 'Exclusive atomic promotion did not complete exactly.');
end

function EEG = make_eeg(subjectID, setName, samples, sampleCount, rateHz, eventLatency, receipt, settingsDigest)
EEG = eeg_emptyset;
EEG.setname = sprintf('SIMPLE synthetic subject %s', subjectID);
EEG.filename = setName; EEG.filepath = ''; EEG.subject = subjectID; EEG.session = 1; EEG.run = 1;
EEG.comments = 'Wholly synthetic procedural tutorial data; no real person; simulated Cz relative to a synthetic common reference.';
EEG.ref = 'synthetic common reference'; EEG.nbchan = 1; EEG.trials = 1; EEG.pnts = sampleCount;
EEG.srate = rateHz; EEG.xmin = 0; EEG.xmax = (sampleCount - 1) / rateHz;
EEG.times = single((0:(sampleCount - 1)) ./ rateHz .* 1000); EEG.data = reshape(samples, 1, []);
EEG.chanlocs = struct('labels', 'Cz', 'type', 'synthetic', 'ref', 'synthetic common reference');
EEG.event = struct('type', 'stimulus', 'latency', eventLatency, 'duration', 0, 'urevent', 1);
EEG.urevent = struct('type', 'stimulus', 'latency', eventLatency, 'duration', 0);
EEG.etc.simple_synthetic = struct('schema', 'simple-synthetic-eeglab-metadata-v1', ...
    'wholly_synthetic', true, 'generator_commit', receipt.generator_commit, ...
    'framework_commit', receipt.framework_commit, 'simple_commit', receipt.simple_commit, ...
    'settings_sha256', settingsDigest, 'subjectID', subjectID, 'sessionID', '01', 'runID', '01');
end

function assert_semantic_equal_except_path(before, after, expectedNativePath, expectedFilename)
assert(strcmp(before.filepath, expectedNativePath) && isempty(after.filepath), 'Path-only rewrite contract differs.');
assert(strcmp(before.filename, expectedFilename) && strcmp(after.filename, expectedFilename), 'Filename changed during rewrite.');
before.filepath = ''; after.filepath = '';
assert(isequaln(before, after), 'Post-native rewrite changed more than filepath.');
end

function verify_reloaded_eeg(EEG, samples, sampleCount, rateHz, eventLatency)
assert(isa(EEG.data, 'single') && isequal(size(EEG.data), [1 sampleCount]) && all(isfinite(EEG.data), 'all'), 'Reloaded data differs in type/shape/finiteness.');
assert(isequal(EEG.data, reshape(samples, 1, [])), 'Reloaded samples differ exactly.');
assert(EEG.nbchan == 1 && EEG.srate == rateHz && EEG.pnts == sampleCount && EEG.trials == 1, 'Reloaded geometry differs.');
assert(EEG.xmin == 0 && EEG.xmax == (sampleCount - 1) / rateHz, 'Reloaded time limits differ.');
assert(isscalar(EEG.chanlocs) && strcmp(EEG.chanlocs.labels, 'Cz'), 'Reloaded channel differs.');
assert(isscalar(EEG.event) && strcmp(EEG.event.type, 'stimulus') && EEG.event.latency == eventLatency, 'Reloaded event differs.');
assert(isempty(EEG.epoch) && ~any(strcmpi(string({EEG.event.type}), 'boundary')), 'Unexpected epoch/boundary structure.');
assert(EEG.etc.simple_synthetic.wholly_synthetic, 'Synthetic flag differs.');
end

function list = read_dataset_list(pathValue, expectedSubjects)
raw = fileread(pathValue);
assert(~contains(raw, sprintf('\r')) && raw(end) == newline, 'Dataset list must use canonical LF rows.');
lines = splitlines(string(raw)); lines(end) = [];
assert(numel(lines) == 32 && lines(1) == "subjectID,sessionID,runID,path_raw,EEGfile_raw", ...
    'Dataset list must contain the exact header and 31 rows.');
for i = 2:numel(lines), assert(numel(split(lines(i), ',')) == 5, 'Dataset-list row must contain exactly five fields.'); end
options = detectImportOptions(pathValue, 'Delimiter', ',', 'TextType', 'string');
options = setvartype(options, 'string'); list = readtable(pathValue, options);
assert(isequal(list.Properties.VariableNames, {'subjectID','sessionID','runID','path_raw','EEGfile_raw'}), 'Dataset-list columns differ.');
assert(height(list) == 31 && isequal(list.subjectID, expectedSubjects), 'Dataset-list subject rows/order differ.');
assert(all(list.sessionID == "01") && all(list.runID == "01"), 'Dataset-list session/run differ.');
keys = list.path_raw + "/" + list.EEGfile_raw;
assert(numel(unique(keys)) == 31, 'Dataset-list paths are not unique.');
for i = 1:31
    subject = expectedSubjects(i);
    assert(list.path_raw(i) == "data/raw/sub-" + subject + "/ses-01/eeg", 'Dataset-list path differs.');
    assert(list.EEGfile_raw(i) == "sub-" + subject + "_ses-01_run-01_eeg.set", 'Dataset-list filename differs.');
end
end

function assert_dataset_list_bijection(root, list, expectedPaths)
listed = list.path_raw + "/" + list.EEGfile_raw;
actual = list_relative_regular_files(root);
actual = actual(endsWith(lower(actual), '.set'));
assert(isequal(sort(listed), sort(expectedPaths)) && isequal(sort(actual), sort(expectedPaths)), ...
    'Dataset list and complete .set inventory are not an exact bijection.');
end

function copy_bundle_scaffold(inputRoot, partialRoot)
names = {'README.md','CITATION.cff','RIGHTS_AUTHORITY_CHECK_REQUIRED.txt','CC0-1.0.txt'};
targets = {'README.md','CITATION.cff','RIGHTS_AUTHORITY_CHECK_REQUIRED.txt','LICENSE'};
for i = 1:numel(names), copyfile(fullfile(inputRoot, 'dataset_assets', names{i}), fullfile(partialRoot, targets{i})); end
mkdir(fullfile(partialRoot, 'provenance'));
names = {'generator_settings.json','realised_parameters.csv','seed_manifest.csv','ground_truth_manifest.csv', ...
    'python_validation.json','build_receipt.json','reproducibility_receipt.json'};
for i = 1:numel(names), copyfile(fullfile(inputRoot, 'provenance', names{i}), fullfile(partialRoot, 'provenance', names{i})); end
mkdir(fullfile(partialRoot, 'data_lists'));
copyfile(fullfile(inputRoot, 'data_lists', 'dataset_list.csv'), fullfile(partialRoot, 'data_lists', 'dataset_list.csv'));
end

function samples = read_f32le_exact(pathValue, expectedCount)
info = dir(pathValue); assert(isscalar(info) && ~info.isdir && info.bytes == expectedCount * 4, 'Array byte count differs.');
fid = fopen(pathValue, 'r', 'ieee-le'); assert(fid >= 0, 'Cannot open canonical array.');
cleanup = onCleanup(@() fclose(fid));
[samples, count] = fread(fid, expectedCount, '*single');
assert(count == expectedCount && isempty(fread(fid, 1, '*uint8')) && all(isfinite(samples)), 'Canonical array content differs.');
end

function digest = sha256_file(pathValue)
fid = fopen(pathValue, 'r', 'ieee-le'); assert(fid >= 0, 'Cannot hash required file.');
cleanup = onCleanup(@() fclose(fid));
md = java.security.MessageDigest.getInstance('SHA-256');
while true
    [chunk, count] = fread(fid, 1024 * 1024, '*uint8'); if count > 0, md.update(chunk); end
    if count == 0, break; end
end
digest = lower(reshape(dec2hex(typecast(md.digest(), 'uint8'), 2).', 1, []));
end

function verify_sha256_manifest(root)
manifest = fullfile(root, 'MANIFEST.sha256'); assert(isfile(manifest) && ~path_is_symlink(manifest), 'Manifest absent/symlinked.');
raw = fileread(manifest); assert(~isempty(raw) && raw(end) == newline && ~contains(raw, sprintf('\r')), 'Manifest line endings differ.');
lines = splitlines(string(raw)); lines(end) = [];
seen = strings(0,1);
for i = 1:numel(lines)
    tokens = regexp(char(lines(i)), '^([0-9a-f]{64})  ([A-Za-z0-9._/-]+)$', 'tokens', 'once');
    assert(~isempty(tokens), 'Malformed manifest row.'); relative = string(tokens{2});
    assert(is_safe_relative_posix(relative) && ~any(seen == relative), 'Unsafe/duplicate manifest path.');
    seen(end+1,1) = relative; %#ok<AGROW>
    pathValue = fullfile(root, strrep(relative, '/', filesep));
    assert(isfile(pathValue) && ~path_is_symlink(pathValue) && strcmp(sha256_file(pathValue), tokens{1}), 'Manifest file/digest differs: %s', relative);
end
assert(isequal(seen, sort(seen)), 'Manifest rows are not in canonical POSIX path order.');
actual = list_relative_regular_files(root); actual(actual == "MANIFEST.sha256") = [];
assert(isequal(sort(seen), sort(actual)), 'Manifest omits or invents a bundle file.');
assert(~any(endsWith(lower(actual), ".fdt")), 'Bundle contains an .fdt file.');
end

function tf = is_safe_relative_posix(value)
parts = split(value, '/');
tf = strlength(value) > 0 && ~startsWith(value, '/') && ~contains(value, '\\') && ...
    ~contains(value, '//') && all(parts ~= ".") && all(parts ~= "..") && all(strlength(parts) > 0);
end

function write_manifest(root)
relative = list_relative_regular_files(root); relative(relative == "MANIFEST.sha256") = []; relative = sort(relative);
lines = strings(numel(relative), 1);
for i = 1:numel(relative), lines(i) = sha256_file(fullfile(root, strrep(relative(i), '/', filesep))) + "  " + relative(i); end
write_text_exclusive(fullfile(root, 'MANIFEST.sha256'), join(lines + newline, ''));
end

function relative = list_relative_regular_files(root)
root = string(root); relative = walk_regular_files(root, root);
assert(numel(unique(relative)) == numel(relative), 'Duplicate canonical bundle path.'); relative = sort(relative);
end

function relative = walk_regular_files(root, current)
entries = dir(current); relative = strings(0,1);
for i = 1:numel(entries)
    if strcmp(entries(i).name, '.') || strcmp(entries(i).name, '..'), continue; end
    fullPath = string(fullfile(entries(i).folder, entries(i).name));
    assert(~path_is_symlink(fullPath), 'Bundle contains a symlink.');
    if entries(i).isdir
        relative = [relative; walk_regular_files(root, fullPath)]; %#ok<AGROW>
        continue;
    end
    jpath = java.nio.file.Paths.get(char(fullPath), javaArray('java.lang.String', 0));
    assert(java.nio.file.Files.isRegularFile(jpath, javaArray('java.nio.file.LinkOption', 0)), 'Bundle contains a non-regular object.');
    rel = replace(extractAfter(fullPath, strlength(root) + 1), filesep, '/');
    assert(is_safe_relative_posix(rel), 'Unsafe bundle path.'); relative(end+1,1) = rel; %#ok<AGROW>
end
end

function files = find_files_case_insensitive(root, extension)
all = list_relative_regular_files(root); files = all(endsWith(lower(all), lower(string(extension))));
end

function audit_serialized_structure(value, forbiddenTokens)
texts = collect_text_values(value);
for i = 1:numel(texts)
    current = texts(i); lowerCurrent = lower(current);
    assert(~contains(lowerCurrent, "petal") && ~contains(lowerCurrent, "noci-prem") && ...
        ~contains(lowerCurrent, "patient") && ~contains(lowerCurrent, "participant") && ~contains(lowerCurrent, "hospital"), ...
        'Serialized structure contains forbidden real-data vocabulary.');
    assert(~looks_like_absolute_path(current), 'Serialized structure contains an absolute path.');
    for k = 1:numel(forbiddenTokens), assert(~contains(lowerCurrent, lower(forbiddenTokens(k))), 'Serialized structure leaks an environment token.'); end
end
end

function tf = looks_like_absolute_path(value)
tf = startsWith(value, '/') || ~isempty(regexp(char(value), '(^|[[:space:]])/[A-Za-z0-9._-]+/', 'once'));
end

function texts = collect_text_values(value)
texts = strings(0,1);
if ischar(value), texts = string(value);
elseif isstring(value), texts = value(:);
elseif iscell(value), for i = 1:numel(value), texts = [texts; collect_text_values(value{i})]; end %#ok<AGROW>
elseif isstruct(value)
    names = fieldnames(value);
    for i = 1:numel(value), for k = 1:numel(names), texts = [texts; collect_text_values(value(i).(names{k}))]; end, end %#ok<AGROW>
end
end

function normalise_mat_header(pathValue)
canonical = 'MATLAB 5.0 MAT-file, Platform: MACA64, Created by SIMPLE synthetic EEG generator; deterministic header';
header = uint8([canonical repmat(' ', 1, 116 - numel(canonical))]);
fid = fopen(pathValue, 'r+', 'ieee-le'); assert(fid >= 0, 'Cannot normalise MAT header.');
cleanup = onCleanup(@() fclose(fid));
assert(fseek(fid, 0, 'bof') == 0 && fwrite(fid, header, 'uint8') == 116, 'Cannot write canonical MAT header.');
end

function audit_raw_mat_bytes(pathValue, tokens)
fid = fopen(pathValue, 'r', 'ieee-le'); assert(fid >= 0, 'Cannot scan MAT bytes.');
cleanup = onCleanup(@() fclose(fid));
bytes = fread(fid, Inf, '*uint8')';
tokens = unique(["petal","noci-prem","patient","participant","hospital",tokens(:)']);
for k = 1:numel(tokens)
    if strlength(tokens(k)) == 0, continue; end
    assert(~contains_ascii_case_insensitive_bytes(bytes, uint8(char(tokens(k)))), ...
        'Serialized MAT bytes contain forbidden text.');
end
end

function write_roundtrip_csv(pathValue, rows)
lines = "subjectID,sessionID,runID,array_sha256,set_sha256";
for i = 1:size(rows,1), lines(end+1,1) = join(string(rows(i,:)), ','); end %#ok<AGROW>
write_text_exclusive(pathValue, join(lines + newline, ''));
end

function write_packaging_receipt(pathValue, inputReceipt, settingsDigest, helperDigest, pythonDigest, lockDigest)
receipt = struct('schema', 'simple-synthetic-eeglab-packaging-v1', 'status', 'passed', ...
    'matlab_release', version('-release'), 'matlab_version', version, 'eeglab_version', char(eeg_getversion), ...
    'set_count', 31, 'fdt_count', 0, 'settings_sha256', settingsDigest, ...
    'generator_commit', inputReceipt.generator_commit, 'framework_commit', inputReceipt.framework_commit, ...
    'simple_commit', inputReceipt.simple_commit, 'exclusive_rename_helper_sha256', helperDigest, ...
    'python_executable_role', '.venv/bin/python', 'python_target_sha256', pythonDigest, ...
    'python_lock_sha256', lockDigest);
write_text_exclusive(pathValue, string(jsonencode(receipt)) + newline);
end

function write_text_exclusive(pathValue, text)
pathValue = string(pathValue);
assert(~path_exists_including_symlink(pathValue), 'Exclusive text output unexpectedly exists.');
jpath = java.nio.file.Paths.get(char(pathValue), javaArray('java.lang.String', 0));
options = javaArray('java.nio.file.OpenOption', 2);
options(1) = java.nio.file.StandardOpenOption.CREATE_NEW;
options(2) = java.nio.file.StandardOpenOption.WRITE;
channel = java.nio.channels.FileChannel.open(jpath, options);
cleanup = onCleanup(@() channel.close());
bytes = unicode2native(char(text), 'UTF-8');
buffer = java.nio.ByteBuffer.wrap(typecast(uint8(bytes), 'int8'));
while buffer.hasRemaining(), channel.write(buffer); end
channel.force(true);
end

function mark_failure(partialRoot)
if isfolder(partialRoot) && ~isfile(fullfile(partialRoot, 'PACKAGING_FAILED_NOT_PROMOTED.txt'))
    try
        write_text_exclusive(fullfile(partialRoot, 'PACKAGING_FAILED_NOT_PROMOTED.txt'), "failed-not-promoted" + newline);
    catch
    end
end
end
