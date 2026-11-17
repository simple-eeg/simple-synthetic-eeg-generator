function tests = test_packaging_helpers_runtime
% Isolated MATLAB-only tests using temporary synthetic fixtures.
% No participant EEG or existing workflow data is read.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
matlabDir = fullfile(root, 'matlab');
addpath(matlabDir);
testCase.addTeardown(@() rmpath(matlabDir));
end

function testEquivalentV6StructSavesReloadSemantically(testCase)
root = fresh_root(testCase);
left = fullfile(root, 'left.set'); right = fullfile(root, 'right.set');
fixture = fixture_struct;
save(left, '-v6', '-mat', '-struct', 'fixture');
save(right, '-v6', '-mat', '-struct', 'fixture');
verifyEqual(testCase, load(left, '-mat'), fixture);
verifyEqual(testCase, load(right, '-mat'), fixture);
end

function testTopLevelStructSanitisationChangesPathOnly(testCase)
root = fresh_root(testCase); pathValue = fullfile(root, 'fixture.set');
before = fixture_struct; before.filepath = fullfile(root, 'absolute', 'native');
save(pathValue, '-v6', '-mat', '-struct', 'before');
loaded = load(pathValue, '-mat'); verifyFalse(testCase, isfield(loaded, 'EEG'));
loaded.filepath = ''; save(pathValue, '-v6', '-mat', '-struct', 'loaded');
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

function testExactStalePartialSiblingMatching(testCase)
root = fresh_root(testCase);
expectedHelper = string(fullfile(fileparts(fileparts(fileparts(mfilename('fullpath')))), ...
    'matlab', 'find_stale_partial_siblings.m'));
verifyEqual(testCase, string(which('find_stale_partial_siblings', '-all')), expectedHelper);
outputRoot = fullfile(root, 'pristine-candidate-003');
mkdir(fullfile(root, 'ordinary-sibling'));
mkdir(fullfile(root, '.hidden-sibling'));
mkdir(fullfile(root, 'pristine-candidate-003.partialish'));
mkdir(fullfile(root, 'other.partial.1234'));
write_bytes(fullfile(root, '.DS_Store'), uint8([0 1 2 255]));
verifyEmpty(testCase, find_stale_partial_siblings(outputRoot));
staleName = 'pristine-candidate-003.partial.01234567-89ab-cdef-0123-456789abcdef';
mkdir(fullfile(root, staleName));
verifyEqual(testCase, find_stale_partial_siblings(outputRoot), string(staleName));

hiddenOutputRoot = fullfile(root, '.hidden-candidate');
hiddenStaleName = '.hidden-candidate.partial.token';
mkdir(fullfile(root, hiddenStaleName));
verifyEqual(testCase, find_stale_partial_siblings(hiddenOutputRoot), string(hiddenStaleName));
end

function testReadOnlyInputTreeRemainsConsumable(testCase)
container = [tempname ' read-only fixture'];
input = fullfile(container, "input O'Brien"); output = fullfile(container, 'output');
mkdir(input); mkdir(output); testCase.addTeardown(@() safe_remove_readonly(container));
write_bytes(fullfile(input, 'note.txt'), unicode2native(sprintf('synthetic-only\n'), 'UTF-8'));
write_bytes(fullfile(input, 'array.f32le'), typecast(single([1 -2 3.5]), 'uint8'));
write_bytes(fullfile(input, 'list.csv'), unicode2native(sprintf('subjectID,value\n001,ok\n'), 'UTF-8'));
before = recursive_files(input, input);
[status, diagnostic] = system(shell_command('/bin/chmod', ["-R", "a-w", string(input)]));
assert(status == 0, 'Cannot make isolated input fixture read-only: %s', diagnostic);
[status, ~] = system(shell_command('/bin/test', ["!", "-w", string(input)]));
verifyEqual(testCase, status, 0, 'Isolated input fixture did not become read-only.');
verifyEqual(testCase, fileread(fullfile(input, 'note.txt')), sprintf('synthetic-only\n'));
fid = fopen(fullfile(input, 'array.f32le'), 'r', 'ieee-le');
assert(fid >= 0); cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
verifyEqual(testCase, fread(fid, Inf, '*single').', single([1 -2 3.5]));
tableValue = readtable(fullfile(input, 'list.csv'), 'TextType', 'string');
verifyEqual(testCase, string(tableValue.value), "ok");
copyfile(fullfile(input, 'note.txt'), fullfile(output, 'note.txt'));
verifyEqual(testCase, fileread(fullfile(output, 'note.txt')), sprintf('synthetic-only\n'));
verifyEqual(testCase, recursive_files(input, input), before, ...
    'Reading and copying from a read-only input tree must not add or change its inventory.');
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

function safe_remove_readonly(root)
if isfolder(root)
    system(shell_command('/bin/chmod', ["-R", "u+w", string(root)]));
    rmdir(root, 's');
end
end
