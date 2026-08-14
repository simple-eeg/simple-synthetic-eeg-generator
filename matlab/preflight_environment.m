%% Preflight the fixed MATLAB and EEGLAB producing prerequisites
% This performs no generation, packaging, workflow execution, or data write.

clearvars;

EXPECTED_MATLAB_RELEASE = '2026a';
EXPECTED_MATLAB_VERSION = '26.1.0.3312084 (R2026a) Update 4';
EXPECTED_EEGLAB_VERSION = '2026.0.0';
EXPECTED_EEGLAB_FILES = {
    'eeglab.m', '227ee7b89f2a852d78b342aa9c88e2accbf5fad3915979d1077a109e839a7d10';
    'functions/popfunc/eeg_emptyset.m', '5359ea9eeb4dc8c85c3465cf6ef7ad8c769f839f027734b268e2b37018cb76be';
    'functions/adminfunc/eeg_checkset.m', 'fa6356b4a64ea6e16683acc4c65b257084dd1bfc995848de402244ccba00d6f0';
    'functions/popfunc/pop_saveset.m', 'dab9ddec4475be7ec97a5f2409dc3f6321e1f8b61eb9f90ea83f498648bb71c1';
    'functions/popfunc/pop_loadset.m', '2c688149f710c9b6f2d340fefdf185db0db60f4828215cb201c12728d5de7fc2';
    'functions/adminfunc/eeg_getversion.m', '0369d508b5b9e77d7ba12e486fa3b6998f8e34d259818a883e0a21366aa803f4'};

scriptDir = string(fileparts(mfilename('fullpath')));
generatorRoot = require_canonical_root('SIMPLE_SYNTH_GENERATOR_ROOT');
assert(strcmp(scriptDir, fullfile(generatorRoot, 'matlab')), ...
    'Preflight script must be the tracked file beneath the selected generator root.');
assert(strcmp(string(pwd), scriptDir), ...
    'MATLAB current folder must be the generator matlab directory.');
assert(strcmp(version('-release'), EXPECTED_MATLAB_RELEASE), 'MATLAB release differs.');
assert(strcmp(version, EXPECTED_MATLAB_VERSION), 'MATLAB full version/build differs.');

eeglabRoot = require_canonical_root('SIMPLE_SYNTH_EEGLAB_ROOT');
for i = 1:size(EXPECTED_EEGLAB_FILES, 1)
    pathValue = fullfile(eeglabRoot, strrep(EXPECTED_EEGLAB_FILES{i,1}, '/', filesep));
    assert(isfile(pathValue) && ~path_is_symlink(pathValue), ...
        'Pinned EEGLAB source is absent or a symlink.');
    assert(strcmp(sha256_file(pathValue), EXPECTED_EEGLAB_FILES{i,2}), ...
        'Pinned EEGLAB source hash differs: %s', EXPECTED_EEGLAB_FILES{i,1});
end

restoredefaultpath;
addpath(eeglabRoot);
assert_unique_binding('eeglab', fullfile(eeglabRoot, 'eeglab.m'));
eeglab('nogui');
required = {'eeglab','eeg_emptyset','eeg_checkset','pop_saveset','pop_loadset','eeg_getversion'};
for i = 1:numel(required)
    locations = string(which(required{i}, '-all'));
    assert(isscalar(locations) && startsWith(locations, eeglabRoot + filesep), ...
        'EEGLAB function must resolve uniquely beneath the pinned root: %s', required{i});
end
assert(strcmp(char(eeg_getversion), EXPECTED_EEGLAB_VERSION), 'EEGLAB version differs.');
fprintf('Exact MATLAB R2026a Update 4 and EEGLAB 2026.0.0 prerequisites passed.\n');

function root = require_canonical_root(variableName)
root = string(getenv(variableName));
assert(strlength(root) > 0 && startsWith(root, filesep), '%s must be absolute.', variableName);
assert(isfolder(root) && ~path_is_symlink(root), '%s must be an ordinary directory.', variableName);
canonical = string(char(java.nio.file.Paths.get(char(root), ...
    javaArray('java.lang.String', 0)).toRealPath(javaArray('java.nio.file.LinkOption', 0)).toString));
assert(strcmp(root, canonical), '%s must be canonical and contain no symlink component.', variableName);
parts = split(extractAfter(root, 1), filesep);
current = string(filesep);
for i = 1:numel(parts)
    if strlength(parts(i)) == 0, continue; end
    current = fullfile(current, parts(i));
    assert(~path_is_symlink(current), '%s contains a symlink component.', variableName);
end
end

function assert_unique_binding(name, expected)
locations = string(which(name, '-all'));
assert(isscalar(locations) && strcmp(locations, expected), ...
    'Function binding differs from the exact selected installation: %s', name);
end

function tf = path_is_symlink(pathValue)
jpath = java.nio.file.Paths.get(char(pathValue), javaArray('java.lang.String', 0));
tf = java.nio.file.Files.isSymbolicLink(jpath);
end

function digest = sha256_file(pathValue)
fid = fopen(pathValue, 'r', 'ieee-le'); assert(fid >= 0, 'Cannot hash required file.');
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
md = java.security.MessageDigest.getInstance('SHA-256');
while true
    [chunk, count] = fread(fid, 1024 * 1024, '*uint8');
    if count > 0, md.update(chunk); end
    if count == 0, break; end
end
digest = lower(reshape(dec2hex(typecast(md.digest(), 'uint8'), 2).', 1, []));
end
