function [status, output] = run_command(executable, arguments)
%RUN_COMMAND Run literal arguments without an intervening command shell.
pieces = [string(executable), reshape(string(arguments), 1, [])];
assert(~any(ismissing(pieces)) && strlength(pieces(1)) > 0, ...
    'Command and arguments must be nonmissing scalar text.');
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
