function tests = test_eeglab_native_fixture_runtime
% One tiny wholly synthetic native EEGLAB save/sanitise/reload regression.
% Set SIMPLE_SYNTH_EEGLAB_ROOT to the pinned 2026.0.0 root before running.
tests = functiontests(localfunctions);
end

function testNativeOneFileRoundTripAndPathNeutralisation(testCase)
root = string(getenv('SIMPLE_SYNTH_EEGLAB_ROOT'));
assumeTrue(testCase, strlength(root) > 0 && isfolder(root), 'Pinned EEGLAB root is not selected.');
oldPath = path; testCase.addTeardown(@() path(oldPath));
addpath(root); eeglab('nogui');
verifyEqual(testCase, char(eeg_getversion), '2026.0.0');
tmp = tempname; mkdir(tmp); testCase.addTeardown(@() safe_remove(tmp));
samples = single(reshape(sin((0:29999) ./ 37), 1, [])); name = 'native_fixture.set';
leftDir=fullfile(tmp,'left'); rightDir=fullfile(tmp,'right'); mkdir(leftDir); mkdir(rightDir);
leftPath=save_sanitised_native(leftDir,name,samples,testCase);
rightPath=save_sanitised_native(rightDir,name,samples,testCase);
verifyEqual(testCase,file_bytes(leftPath),file_bytes(rightPath), ...
    'Two native save/sanitise/header-normalise transactions must be byte-identical.');
reloaded=pop_loadset('filename',name,'filepath',leftDir,'loadmode','all');
verifyClass(testCase,reloaded.data,'single'); verifySize(testCase,reloaded.data,[1 30000]);
verifyEqual(testCase,reloaded.data,samples); verifyEqual(testCase,reloaded.chanlocs.labels,'Cz');
verifyEqual(testCase,numel(reloaded.event),1); verifyEqual(testCase,reloaded.event.type,'stimulus');
verifyEqual(testCase,reloaded.event.latency,15001); verifyEmpty(testCase,reloaded.epoch);
end

function pathValue=save_sanitised_native(outputDir,name,samples,testCase)
EEG=eeg_emptyset; EEG.setname='fixture'; EEG.filename=name; EEG.filepath=''; EEG.subject='001';
EEG.nbchan=1; EEG.trials=1; EEG.pnts=30000; EEG.srate=1000; EEG.xmin=0; EEG.xmax=29.999;
EEG.times=single((0:29999)); EEG.data=samples; EEG.chanlocs=struct('labels','Cz');
EEG.event=struct('type','stimulus','latency',15001,'duration',0,'urevent',1);
EEG.urevent=struct('type','stimulus','latency',15001,'duration',0);
EEG=eeg_checkset(EEG,'eventconsistency');
pop_saveset(EEG,'filename',name,'filepath',outputDir,'savemode','onefile','version','6');
pathValue=fullfile(outputDir,name); verifyTrue(testCase,isfile(pathValue));
verifyEmpty(testCase,dir(fullfile(outputDir,'*.fdt')));
before=load(pathValue,'-mat'); verifyFalse(testCase,isfield(before,'EEG')); verifyEqual(testCase,before.filepath,outputDir);
after=before; after.filepath=''; save(pathValue,'-v6','-mat','-struct','after'); normalise_header(pathValue);
stored=load(pathValue,'-mat'); before.filepath=''; verifyEqual(testCase,stored,before, ...
    'Native sanitisation must change only filepath.');
end

function normalise_header(pathValue)
canonical='MATLAB 5.0 MAT-file, Platform: MACA64, Created by SIMPLE synthetic EEG generator; deterministic header';
fid=fopen(pathValue,'r+'); cleanup=onCleanup(@()fclose(fid));
fwrite(fid,uint8([canonical repmat(' ',1,116-numel(canonical))]),'uint8');
end

function bytes=file_bytes(pathValue)
fid=fopen(pathValue,'r'); cleanup=onCleanup(@()fclose(fid));
bytes=fread(fid,Inf,'*uint8');
end

function safe_remove(root)
if isfolder(root), rmdir(root,'s'); end
end
