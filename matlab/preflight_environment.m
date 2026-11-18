%% Preflight the MATLAB and EEGLAB capabilities used by native packaging
% This creates and removes one tiny wholly synthetic fixture in the system
% temporary directory. It does not generate the tutorial dataset or write
% workflow outputs.

clearvars;

scriptDir = string(fileparts(mfilename('fullpath')));
generatorRoot = require_canonical_root('SIMPLE_SYNTH_GENERATOR_ROOT');
assert(strcmp(scriptDir, fullfile(generatorRoot, 'matlab')), ...
    'Preflight script must be the tracked file beneath the selected generator root.');
assert(strcmp(string(pwd), scriptDir), ...
    'MATLAB current folder must be the generator matlab directory.');

eeglabRoot = require_canonical_root('SIMPLE_SYNTH_EEGLAB_ROOT');
restoredefaultpath;
addpath(eeglabRoot);
assert_unique_binding('eeglab', fullfile(eeglabRoot, 'eeglab.m'));
eeglab('nogui');
assert_unique_binding('validate_runtime_capabilities', ...
    fullfile(scriptDir, 'validate_runtime_capabilities.m'));
identity = validate_runtime_capabilities(eeglabRoot, true);
fprintf('MATLAB %s and EEGLAB %s passed the required native save/reload capability checks.\n', ...
    identity.matlab_version, identity.eeglab_version);

function root = require_canonical_root(variableName)
root = string(getenv(variableName));
jpath = java.nio.file.Paths.get(char(root), javaArray('java.lang.String', 0));
assert(strlength(root) > 0 && jpath.isAbsolute(), '%s must be absolute.', variableName);
assert(isfolder(root) && ~path_is_symlink(root), '%s must be an ordinary directory.', variableName);
canonical = string(char(java.nio.file.Paths.get(char(root), ...
    javaArray('java.lang.String', 0)).toRealPath(javaArray('java.nio.file.LinkOption', 0)).toString));
assert(strcmp(root, canonical), '%s must be canonical and contain no symlink component.', variableName);
current = jpath;
while ~isempty(current)
    assert(~java.nio.file.Files.isSymbolicLink(current), '%s contains a symlink component.', variableName);
    current = current.getParent();
end
end

function assert_unique_binding(name, expected)
locations = string(which(name, '-all'));
locations = locations(:);
assert(numel(locations) == 1 && strcmp(locations(1), expected), ...
    'Function binding differs from the selected installation: %s', name);
end

function tf = path_is_symlink(pathValue)
jpath = java.nio.file.Paths.get(char(pathValue), javaArray('java.lang.String', 0));
tf = java.nio.file.Files.isSymbolicLink(jpath);
end
