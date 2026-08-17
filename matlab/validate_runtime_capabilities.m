function identity = validate_runtime_capabilities(eeglabRoot, runFixture)
%VALIDATE_RUNTIME_CAPABILITIES Verify the native operations used by packaging.
% Version strings are recorded as provenance; acceptance depends on capabilities.

eeglabRoot = string(eeglabRoot);
assert(isscalar(eeglabRoot) && strlength(eeglabRoot) > 0, ...
    'Selected EEGLAB root must be one nonblank path.');
assert(islogical(runFixture) && isscalar(runFixture), ...
    'Fixture selection must be one logical value.');

assert(usejava('jvm'), 'MATLAB must provide the Java runtime used for safe paths and SHA-256.');
requiredMatlab = {'compose','detectImportOptions','endsWith','isfile','isfolder', ...
    'jsondecode','jsonencode','readtable','startsWith','unicode2native'};
for i = 1:numel(requiredMatlab)
    assert(~isempty(which(requiredMatlab{i})), ...
        'MATLAB lacks a function required by the generator: %s', requiredMatlab{i});
end
assert(all(true(2), 'all'), 'MATLAB lacks the required all(...,''all'') behaviour.');
java.security.MessageDigest.getInstance('SHA-256');
java.nio.file.Paths.get(char(eeglabRoot), javaArray('java.lang.String', 0));
java.util.UUID.randomUUID;
jsonProbe = jsondecode(jsonencode(struct('value', 1)));
assert(isstruct(jsonProbe) && jsonProbe.value == 1, ...
    'MATLAB JSON encode/decode behaviour is incompatible.');

requiredEEGLAB = {'eeglab','eeg_emptyset','eeg_checkset','pop_saveset','pop_loadset','eeg_getversion'};
for i = 1:numel(requiredEEGLAB)
    locations = string(which(requiredEEGLAB{i}, '-all'));
    locations = locations(:);
    assert(numel(locations) == 1 && startsWith(locations(1), eeglabRoot + filesep), ...
        'EEGLAB function must resolve uniquely beneath the selected root: %s', requiredEEGLAB{i});
end

identity = struct( ...
    'matlab_release', char(string(version('-release'))), ...
    'matlab_version', char(string(version)), ...
    'eeglab_version', char(string(eeg_getversion)));
assert(~isempty(strtrim(identity.matlab_release)) && ...
    ~isempty(strtrim(identity.matlab_version)) && ...
    ~isempty(strtrim(identity.eeglab_version)), ...
    'MATLAB and EEGLAB must report nonblank version provenance.');

if runFixture
    run_native_fixture;
end
end

function run_native_fixture
fixtureRoot = string(tempname);
mkdir(fixtureRoot);
assert(isfolder(fixtureRoot), 'Could not create the temporary native capability fixture.');
cleanup = onCleanup(@() remove_fixture(fixtureRoot)); %#ok<NASGU>

sampleCount = 128;
sampleRate = 128;
eventLatency = 65;
samples = single(reshape(sin((0:(sampleCount - 1)) ./ 7), 1, []));
setName = 'simple_native_capability_fixture.set';
outputDir = char(fixtureRoot);

EEG = eeg_emptyset;
EEG.setname = 'SIMPLE native capability fixture';
EEG.filename = setName;
EEG.filepath = '';
EEG.subject = 'fixture';
EEG.session = 1;
EEG.run = 1;
EEG.comments = 'Wholly synthetic temporary capability fixture.';
EEG.ref = 'synthetic reference';
EEG.nbchan = 1;
EEG.trials = 1;
EEG.pnts = sampleCount;
EEG.srate = sampleRate;
EEG.xmin = 0;
EEG.xmax = (sampleCount - 1) / sampleRate;
EEG.times = single((0:(sampleCount - 1)) ./ sampleRate .* 1000);
EEG.data = samples;
EEG.chanlocs = struct('labels', 'Cz', 'type', 'synthetic', 'ref', 'synthetic reference');
EEG.event = struct('type', 'stimulus', 'latency', eventLatency, 'duration', 0, 'urevent', 1);
EEG.urevent = struct('type', 'stimulus', 'latency', eventLatency, 'duration', 0);
EEG = eeg_checkset(EEG, 'eventconsistency');
pop_saveset(EEG, 'filename', setName, 'filepath', outputDir, ...
    'savemode', 'onefile', 'version', '6');

setPath = fullfile(outputDir, setName);
assert(isfile(setPath), 'Native capability fixture did not create its .set file.');
entries = dir(outputDir);
names = lower(string({entries(~[entries.isdir]).name}));
assert(~any(endsWith(names, '.fdt')), 'Native one-file save created a forbidden .fdt sidecar.');
stored = load(setPath, '-mat');
assert(isstruct(stored) && isfield(stored, 'data') && ~isfield(stored, 'EEG'), ...
    'Native one-file save did not use the required top-level EEGLAB structure.');
assert(isfield(stored, 'filepath'), 'Native capability fixture omitted its filepath field.');
assert(isnumeric(stored.data) && isequal(single(stored.data), samples), ...
    'Directly loaded native fixture samples differ.');
assert(isfield(stored, 'datfile') && isempty(stored.datfile), ...
    'Native capability fixture contains an external-data reference.');
sanitised = stored;
sanitised.filepath = '';
save(setPath, '-v6', '-mat', '-struct', 'sanitised');
storedAfter = load(setPath, '-mat');
stored.filepath = '';
assert(isequaln(storedAfter, stored), ...
    'MATLAB cannot perform the required path-only v6 structure rewrite.');

csvPath = fullfile(outputDir, 'capability.csv');
fid = fopen(csvPath, 'w');
assert(fid >= 0, 'Cannot create the temporary table capability fixture.');
fileCleanup = onCleanup(@() fclose(fid));
assert(fwrite(fid, unicode2native(sprintf('subjectID,value\n001,ok\n'), 'UTF-8'), 'uint8') > 0, ...
    'Cannot write the temporary table capability fixture.');
clear fileCleanup;
options = detectImportOptions(csvPath, 'Delimiter', ',', 'TextType', 'string');
options = setvartype(options, 'string');
tableProbe = readtable(csvPath, options);
assert(height(tableProbe) == 1 && string(tableProbe.subjectID) == "001" && ...
    string(tableProbe.value) == "ok", 'MATLAB table import behaviour is incompatible.');

reloaded = pop_loadset('filename', setName, 'filepath', outputDir, 'loadmode', 'all');
reloaded = eeg_checkset(reloaded, 'eventconsistency');
assert(isnumeric(reloaded.data) && isequal(size(reloaded.data), [1 sampleCount]) && ...
    all(isfinite(double(reloaded.data)), 'all') && isequal(single(reloaded.data), samples), ...
    'Native EEGLAB reload changed the fixture samples.');
assert(reloaded.nbchan == 1 && reloaded.pnts == sampleCount && ...
    reloaded.srate == sampleRate && reloaded.trials == 1, ...
    'Native EEGLAB reload changed the fixture geometry.');
assert(isscalar(reloaded.chanlocs) && strcmp(reloaded.chanlocs.labels, 'Cz'), ...
    'Native EEGLAB reload changed the fixture channel.');
assert(isscalar(reloaded.event) && strcmp(reloaded.event.type, 'stimulus') && ...
    reloaded.event.latency == eventLatency, ...
    'Native EEGLAB reload changed the fixture event.');
assert(isempty(reloaded.epoch) && ...
    ~any(strcmpi(string({reloaded.event.type}), 'boundary')), ...
    'Native EEGLAB reload added unexpected epoch or boundary structure.');
end

function remove_fixture(root)
jpath = java.nio.file.Paths.get(char(root), javaArray('java.lang.String', 0));
options = javaArray('java.nio.file.LinkOption', 1);
options(1) = java.nio.file.LinkOption.NOFOLLOW_LINKS;
if ~java.nio.file.Files.exists(jpath, options), return; end
assert(isfolder(root) && ~java.nio.file.Files.isSymbolicLink(jpath), ...
    'Temporary capability fixture was replaced by an unsafe object; inspect it manually.');
[status, message] = rmdir(root, 's');
assert(status == 1 && ~java.nio.file.Files.exists(jpath, options), ...
    'Could not remove the temporary capability fixture: %s', message);
end
