function [status, output] = run_command(executable, arguments)
%RUN_COMMAND Run literal arguments without an intervening command shell.
pieces = [string(executable), reshape(string(arguments), 1, [])];
assert(~any(ismissing(pieces)) && strlength(pieces(1)) > 0, ...
    'Command and arguments must be nonmissing scalar text.');
if ispc
    % Python preserves literal Windows arguments across bundled Java versions.
    python = string(getenv('SIMPLE_SYNTH_PYTHON'));
    expectedPython = fullfile(fileparts(fileparts(mfilename('fullpath'))), '.venv', 'Scripts', 'python.exe');
    assert(isfile(python) && strcmpi(char(java.io.File(char(python)).getCanonicalPath()), ...
        char(java.io.File(expectedPython).getCanonicalPath())), ...
        'Set SIMPLE_SYNTH_PYTHON to this checkout''s existing .venv/Scripts/python.exe.');
    payload = matlab.net.base64encode(unicode2native(jsonencode(cellstr(pieces)), 'UTF-8'));
    code = 'import base64,json,subprocess,sys;sys.exit(subprocess.run(json.loads(base64.b64decode(sys.argv[1])),check=False).returncode)';
    pieces = [python, "-I", "-c", string(code), string(payload)];
end
command = javaArray('java.lang.String', numel(pieces));
for i = 1:numel(pieces), command(i) = java.lang.String(char(pieces(i))); end
outputPath = [tempname '.txt'];
cleanup = onCleanup(@() remove_output(outputPath));
builder = java.lang.ProcessBuilder(command);
builder.redirectErrorStream(true);
builder.redirectOutput(java.io.File(outputPath));
process = builder.start();
childCleanup = onCleanup(@() process.destroy());
status = double(process.waitFor());
output = fileread(outputPath);
end

function remove_output(path)
if isfile(path), delete(path); end
end
