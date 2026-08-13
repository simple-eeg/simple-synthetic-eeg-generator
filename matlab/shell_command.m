function command = shell_command(executable, arguments)
%SHELL_COMMAND Build one POSIX-shell command with literal scalar arguments.
executable = string(executable);
arguments = reshape(string(arguments), 1, []);
assert(isscalar(executable) && ~ismissing(executable), ...
    'Executable must be one nonmissing text scalar.');
assert(~any(ismissing(arguments)), 'Command arguments must not be missing.');
pieces = [shell_quote(executable), arrayfun(@shell_quote, arguments)];
command = char(join(pieces, ' '));
end

function quoted = shell_quote(value)
value = string(value);
assert(isscalar(value) && ~ismissing(value), ...
    'Shell argument must be one nonmissing text scalar.');
singleQuote = string(char(39));
doubleQuote = string(char(34));
embeddedSingleQuote = singleQuote + doubleQuote + singleQuote + doubleQuote + singleQuote;
quoted = singleQuote + replace(value, singleQuote, embeddedSingleQuote) + singleQuote;
end
