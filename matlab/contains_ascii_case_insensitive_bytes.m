function tf = contains_ascii_case_insensitive_bytes(haystack, needle)
%CONTAINS_ASCII_CASE_INSENSITIVE_BYTES Exact binary-safe byte search.
if ~isa(haystack, 'uint8') || ~isa(needle, 'uint8')
    error('SIMPLE:InvalidByteInput', 'Haystack and needle must both be uint8 arrays.');
end
haystack = reshape(haystack, 1, []);
needle = reshape(needle, 1, []);
haystack = ascii_lower(haystack);
needle = ascii_lower(needle);
if isempty(needle)
    tf = true;
    return;
end
lastStart = numel(haystack) - numel(needle) + 1;
if lastStart < 1
    tf = false;
    return;
end
starts = find(haystack(1:lastStart) == needle(1));
tf = false;
for i = 1:numel(starts)
    first = starts(i);
    if all(haystack(first:(first + numel(needle) - 1)) == needle)
        tf = true;
        return;
    end
end
end

function output = ascii_lower(input)
output = input;
mask = output >= uint8('A') & output <= uint8('Z');
output(mask) = output(mask) + uint8(32);
end
