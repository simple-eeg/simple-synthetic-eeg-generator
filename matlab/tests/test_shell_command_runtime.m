function tests = test_shell_command_runtime
% Runtime coverage for the exact POSIX command-construction boundary.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
matlabDir = fullfile(root, 'matlab');
addpath(matlabDir);
testCase.addTeardown(@() rmpath(matlabDir));
testCase.TestData.root = root;
end

function testQuoteTextAndApostropheExactly(testCase)
sq = char(39);
dq = char(34);
verifyEqual(testCase, string(shell_command("ordinary", strings(1, 0))), ...
    string([sq 'ordinary' sq]));
verifyEqual(testCase, string(shell_command("two words", strings(1, 0))), ...
    string([sq 'two words' sq]));
verifyEqual(testCase, string(shell_command("O'Brien", strings(1, 0))), ...
    string([sq 'O' sq dq sq dq sq 'Brien' sq]));
verifyEqual(testCase, string(shell_command("", strings(1, 0))), string([sq sq]));
end

function testProductionHelperResolvesUniquely(testCase)
expected = string(fullfile(testCase.TestData.root, 'matlab', 'shell_command.m'));
verifyEqual(testCase, string(which('shell_command', '-all')), expected);
end

function testArgumentsRoundTripThroughRealShell(testCase)
python = string(getenv('SIMPLE_SYNTH_PYTHON'));
assert(strlength(python) > 0, ...
    'Set SIMPLE_SYNTH_PYTHON to the selected source-local interpreter for this test.');
code = 'import json,sys;print(json.dumps(sys.argv[1:],separators=(chr(44),chr(58))))';
expected = ["ordinary", "two words", "O'Brien", ""];
[status, output] = system(shell_command(python, ["-I", "-c", string(code), expected]));
verifyEqual(testCase, status, 0);
verifyEqual(testCase, string(jsondecode(strtrim(output))), expected.');
end

function testExactGitCommandConstructionAndExecution(testCase)
root = string(testCase.TestData.root);
command = shell_command('/usr/bin/git', ["-C", root, "rev-parse", "HEAD"]);
expected = join(arrayfun(@expected_quote, ...
    ["/usr/bin/git", "-C", root, "rev-parse", "HEAD"]), ' ');
verifyEqual(testCase, string(command), expected);
[status, output] = system(command);
verifyEqual(testCase, status, 0);
verifyMatches(testCase, string(strtrim(output)), "^[0-9a-f]{40}$");
end

function testSelectedPythonCommandConstructionAndExecution(testCase)
python = string(getenv('SIMPLE_SYNTH_PYTHON'));
assert(strlength(python) > 0, ...
    'Set SIMPLE_SYNTH_PYTHON to the selected source-local interpreter for this test.');
code = ['import json,sys;' ...
    'print(json.dumps({"version":sys.version.split()[0],"executable":sys.executable},separators=(",",":")))'];
arguments = ["-I", "-c", string(code)];
command = shell_command(python, arguments);
expected = join(arrayfun(@expected_quote, [python, arguments]), ' ');
verifyEqual(testCase, string(command), expected);
[status, output] = system(command);
verifyEqual(testCase, status, 0);
identity = jsondecode(strtrim(output));
verifyGreaterThan(testCase, strlength(string(identity.version)), 0);
verifyEqual(testCase, string(identity.executable), python);
end

function quoted = expected_quote(value)
sq = string(char(39));
dq = string(char(34));
quoted = sq + replace(string(value), sq, sq + dq + sq + dq + sq) + sq;
end
