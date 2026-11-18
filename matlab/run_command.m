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
if ispc
    % Java's legacy Windows encoding can discard empty or quoted arguments.
    previousEncoding = java.lang.System.getProperty('jdk.lang.Process.allowAmbiguousCommands');
    hadEncoding = java.lang.System.getProperties().containsKey('jdk.lang.Process.allowAmbiguousCommands');
    encodingCleanup = onCleanup(@() restore_encoding(previousEncoding, hadEncoding));
    java.lang.System.setProperty('jdk.lang.Process.allowAmbiguousCommands', 'false');
end
process = builder.start();
clear encodingCleanup;
childCleanup = onCleanup(@() process.destroy());
status = double(process.waitFor());
output = fileread(outputPath);
end

function restore_encoding(previous, wasPresent)
property = 'jdk.lang.Process.allowAmbiguousCommands';
if ~wasPresent
    java.lang.System.clearProperty(property);
else
    java.lang.System.setProperty(property, previous);
end
end

function remove_output(path)
if isfile(path), delete(path); end
end
