function tests = test_run_command_runtime
% Arguments are literal on every platform; a command shell is never used.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
matlabDir = fullfile(root, 'matlab');
addpath(matlabDir);
testCase.addTeardown(@() rmpath(matlabDir));
testCase.TestData.root = root;
end

function testProductionHelperResolvesUniquely(testCase)
expected = string(fullfile(testCase.TestData.root, 'matlab', 'run_command.m'));
verifyEqual(testCase, string(which('run_command', '-all')), expected);
end

function testArgumentsRoundTripWithoutShellExpansion(testCase)
python = string(getenv('SIMPLE_SYNTH_PYTHON'));
assert(strlength(python) > 0, 'Set SIMPLE_SYNTH_PYTHON to the checkout-local interpreter.');
code = 'import json,sys;print(json.dumps(sys.argv[1:],separators=(chr(44),chr(58))))';
expected = ["ordinary", "two words", "O'Brien", "", "$HOME", "%PATH%", "x&y", "x|y"];
[status, output] = run_command(python, ["-I", "-c", string(code), expected]);
verifyEqual(testCase, status, 0);
verifyEqual(testCase, string(jsondecode(strtrim(output))), expected.');
end

function testGitExecution(testCase)
[status, output] = run_command('git', ["-C", string(testCase.TestData.root), "rev-parse", "HEAD"]);
verifyEqual(testCase, status, 0);
verifyMatches(testCase, string(strtrim(output)), "^[0-9a-f]{40}$");
end

function testFailurePreservesStatusAndDiagnostic(testCase)
python = string(getenv('SIMPLE_SYNTH_PYTHON'));
[status, output] = run_command(python, ["-I", "-c", "import sys;print('failure',file=sys.stderr);sys.exit(7)"]);
verifyEqual(testCase, status, 7);
verifyEqual(testCase, strtrim(output), 'failure');
end
