function candidateNames = find_stale_partial_siblings(outputRoot)
%FIND_STALE_PARTIAL_SIBLINGS Find exact transaction-partial name prefixes.
outputRoot = string(outputRoot);
assert(isscalar(outputRoot) && ~ismissing(outputRoot), ...
    'Output root must be one nonmissing text scalar.');
parent = string(fileparts(outputRoot));
[~, name, extension] = fileparts(outputRoot);
prefix = string(name) + string(extension) + ".partial.";
entries = dir(parent);
names = string({entries.name});
candidateNames = sort(names(startsWith(names, prefix)));
end
