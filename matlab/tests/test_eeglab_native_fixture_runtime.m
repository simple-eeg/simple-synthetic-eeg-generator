function tests = test_eeglab_native_fixture_runtime
% Native EEGLAB capability regression against temporary synthetic fixtures.
tests = functiontests(localfunctions);
end

function testSharedCapabilityGateRunsNativeRoundTrip(testCase)
root = initialise_eeglab(testCase);
identity = validate_runtime_capabilities(root, true);
verifyNotEmpty(testCase, strtrim(identity.matlab_release));
verifyNotEmpty(testCase, strtrim(identity.matlab_version));
verifyNotEmpty(testCase, strtrim(identity.eeglab_version));
verifyEqual(testCase, identity.matlab_release, version('-release'));
verifyEqual(testCase, identity.matlab_version, version);
verifyEqual(testCase, identity.eeglab_version, char(eeg_getversion));
end

function testProductionStyleStringComposedPathCrossesEEGLABAsChar(testCase)
initialise_eeglab(testCase);
container = string(tempname);
partialRoot = container + ".partial." + string(java.util.UUID.randomUUID);
rawDir = char(fullfile(partialRoot, 'data', 'raw', 'sub-001', 'ses-01', 'eeg'));
verifyClass(testCase, partialRoot, 'string');
verifyClass(testCase, rawDir, 'char');
verifyTrue(testCase, isrow(rawDir));
mkdir(rawDir);
testCase.addTeardown(@() safe_remove(char(partialRoot)));
samples = single(reshape(cos((0:29999) ./ 41), 1, []));
name = 'production_style_fixture.set';
EEG = fixture_eeg(name, samples);
EEG = eeg_checkset(EEG, 'eventconsistency');
saved = pop_saveset(EEG, 'filename', name, 'filepath', rawDir, ...
    'savemode', 'onefile', 'version', '6');
verifyTrue(testCase, isstruct(saved));
verifyEqual(testCase, saved.filename, name);
reloaded = pop_loadset('filename', name, 'filepath', rawDir, 'loadmode', 'all');
verifyEqual(testCase, single(reloaded.data), samples);
verifyEqual(testCase, reloaded.filename, name);
verifyEmpty(testCase, dir(fullfile(rawDir, '*.fdt')));
end

function root = initialise_eeglab(testCase)
root = string(getenv('SIMPLE_SYNTH_EEGLAB_ROOT'));
assumeTrue(testCase, strlength(root) > 0 && isfolder(root), ...
    'No EEGLAB root is selected for the native runtime test.');
oldPath = path;
testCase.addTeardown(@() path(oldPath));
matlabDir = fileparts(fileparts(mfilename('fullpath')));
addpath(matlabDir);
addpath(root);
eeglab('nogui');
end

function EEG = fixture_eeg(name, samples)
EEG = eeg_emptyset;
EEG.setname = 'fixture';
EEG.filename = name;
EEG.filepath = '';
EEG.subject = '001';
EEG.nbchan = 1;
EEG.trials = 1;
EEG.pnts = 30000;
EEG.srate = 1000;
EEG.xmin = 0;
EEG.xmax = 29.999;
EEG.times = single(0:29999);
EEG.data = samples;
EEG.chanlocs = struct('labels', 'Cz');
EEG.event = struct('type', 'stimulus', 'latency', 15001, 'duration', 0, 'urevent', 1);
EEG.urevent = struct('type', 'stimulus', 'latency', 15001, 'duration', 0);
end

function safe_remove(root)
if isfolder(root), rmdir(root, 's'); end
end
