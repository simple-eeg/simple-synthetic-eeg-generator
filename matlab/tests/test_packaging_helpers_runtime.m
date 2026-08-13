function tests = test_packaging_helpers_runtime
% Isolated MATLAB-only adversarial tests. No workflow or EEG data is read.
tests = functiontests(localfunctions);
end

function testCanonicalHeaderMakesEquivalentSavesByteIdentical(testCase)
root = fresh_root(testCase);
left = fullfile(root, 'left.set'); right = fullfile(root, 'right.set');
fixture = fixture_struct;
save(left, '-v6', '-mat', '-struct', 'fixture'); pause(1.1);
save(right, '-v6', '-mat', '-struct', 'fixture');
normalise_header(left); normalise_header(right);
verifyEqual(testCase, file_bytes(left), file_bytes(right));
end

function testTopLevelStructSanitisationChangesPathOnly(testCase)
root = fresh_root(testCase); pathValue = fullfile(root, 'fixture.set');
before = fixture_struct; before.filepath = fullfile(root, 'absolute', 'native');
save(pathValue, '-v6', '-mat', '-struct', 'before');
loaded = load(pathValue, '-mat'); verifyFalse(testCase, isfield(loaded, 'EEG'));
loaded.filepath = ''; save(pathValue, '-v6', '-mat', '-struct', 'loaded'); normalise_header(pathValue);
after = load(pathValue, '-mat'); before.filepath = '';
verifyTrue(testCase, isempty(after.filepath)); verifyEqual(testCase, after, before);
verifyClass(testCase, after.data, 'single'); verifySize(testCase, after.data, [1 30000]);
end

function testManifestAdversaryFixtureCoverage(testCase)
root = fresh_root(testCase);
mkdir(fullfile(root, 'visible')); write_bytes(fullfile(root, 'visible', 'a.bin'), uint8(1));
write_bytes(fullfile(root, '.hidden'), uint8(2));
actual = recursive_files(root, root);
verifyEqual(testCase, sort(actual), sort([".hidden";"visible/a.bin"]));
symlink = fullfile(root, 'link'); [status,~] = system(sprintf('ln -s %s %s', quote(fullfile(root, '.hidden')), quote(symlink)));
assumeEqual(testCase, status, 0); verifyError(testCase, @() recursive_files(root, root), 'SIMPLE:Symlink');
end

function testUnsafeManifestPathsAreRejected(testCase)
unsafe = ["../x";"a/../x";"/absolute";"a\\b";"a//b";"./x";"a/./b";""];
for i = 1:numel(unsafe), verifyFalse(testCase, safe_relative(unsafe(i)), unsafe(i)); end
verifyTrue(testCase, safe_relative("data/raw/sub-001/ses-01/eeg/a.set"));
end

function testDatasetListBijectionOracle(testCase)
listed = ["data/raw/a.set";"data/raw/b.set"];
verifyTrue(testCase, isequal(sort(listed), sort(["data/raw/b.set";"data/raw/a.set"])));
verifyFalse(testCase, isequal(sort(listed), sort(["data/raw/a.set";"data/raw/c.set"])));
verifyEqual(testCase, numel(unique(listed)), 2);
end

function root = fresh_root(testCase)
root = tempname; mkdir(root); testCase.addTeardown(@() safe_remove(root));
end

function fixture = fixture_struct
fixture = struct('setname','fixture','filename','fixture.set','filepath','', ...
    'subject','001','session',1,'run',1,'nbchan',1,'trials',1,'pnts',30000, ...
    'srate',1000,'xmin',0,'xmax',29.999,'times',single(0:29999), ...
    'data',single(reshape(1:30000,1,[])),'chanlocs',struct('labels','Cz'), ...
    'event',struct('type','stimulus','latency',15001),'datfile','');
end

function normalise_header(pathValue)
canonical = 'MATLAB 5.0 MAT-file, Platform: MACA64, Created by SIMPLE synthetic EEG generator; deterministic header';
header = uint8([canonical repmat(' ', 1, 116 - numel(canonical))]);
fid = fopen(pathValue, 'r+'); cleanup = onCleanup(@() fclose(fid));
fseek(fid, 0, 'bof'); fwrite(fid, header, 'uint8');
end

function bytes = file_bytes(pathValue)
fid = fopen(pathValue, 'r'); cleanup = onCleanup(@() fclose(fid));
bytes = fread(fid, Inf, '*uint8');
end

function write_bytes(pathValue, bytes)
fid = fopen(pathValue, 'w'); cleanup = onCleanup(@() fclose(fid));
fwrite(fid, bytes, 'uint8');
end

function relative = recursive_files(root, current)
entries = dir(current); relative = strings(0,1);
for i = 1:numel(entries)
    if strcmp(entries(i).name,'.') || strcmp(entries(i).name,'..'), continue; end
    pathValue = string(fullfile(entries(i).folder, entries(i).name));
    jp = java.nio.file.Paths.get(char(pathValue), javaArray('java.lang.String',0));
    if java.nio.file.Files.isSymbolicLink(jp), error('SIMPLE:Symlink','symlink'); end
    if entries(i).isdir, relative = [relative; recursive_files(root,pathValue)]; %#ok<AGROW>
    else, relative(end+1,1) = replace(extractAfter(pathValue,strlength(root)+1),filesep,'/'); end %#ok<AGROW>
end
end

function tf = safe_relative(value)
parts = split(value,'/');
tf = strlength(value)>0 && ~startsWith(value,'/') && ~contains(value,'\\') && ...
    ~contains(value,'//') && all(parts~=".") && all(parts~="..") && all(strlength(parts)>0);
end

function output = quote(value)
output = ['''' strrep(char(value), '''', '''"''"''') ''''];
end

function safe_remove(root)
if isfolder(root), rmdir(root, 's'); end
end
