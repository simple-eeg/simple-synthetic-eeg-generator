function tests = test_binary_audit_runtime
% Runtime coverage for the production binary-safe ASCII token search.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
matlabDir = fullfile(root, 'matlab');
addpath(matlabDir);
testCase.addTeardown(@() rmpath(matlabDir));
end

function testFoundWithASCIICaseFold(testCase)
haystack = uint8(['prefix-PeTaL-suffix']);
verifyTrue(testCase, contains_ascii_case_insensitive_bytes(haystack, uint8('petal')));
verifyTrue(testCase, contains_ascii_case_insensitive_bytes(haystack, uint8('PETAL')));
end

function testProductionHelperResolvesUniquely(testCase)
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
expected = string(fullfile(root, 'matlab', 'contains_ascii_case_insensitive_bytes.m'));
verifyEqual(testCase, string(which('contains_ascii_case_insensitive_bytes', '-all')), expected);
end

function testAbsentAndNearMatches(testCase)
haystack = uint8('xxpetax-peta-petallxx');
verifyFalse(testCase, contains_ascii_case_insensitive_bytes(haystack, uint8('petal-')));
verifyFalse(testCase, contains_ascii_case_insensitive_bytes(haystack, uint8('hospital')));
end

function testNulAndHighBitRemainBinarySafe(testCase)
haystack = uint8([0 255 double('AbC') 0 128 254]);
verifyTrue(testCase, contains_ascii_case_insensitive_bytes(haystack, uint8([255 double('aBc') 0 128])));
verifyFalse(testCase, contains_ascii_case_insensitive_bytes(haystack, uint8([255 double('aBd')])));
verifyTrue(testCase, contains_ascii_case_insensitive_bytes(haystack, uint8([0 255])));
end

function testBoundariesAndShapeNormalisation(testCase)
haystack = uint8('needle---middle---NEEDLE').';
verifyTrue(testCase, contains_ascii_case_insensitive_bytes(haystack, uint8('needle')));
verifyTrue(testCase, contains_ascii_case_insensitive_bytes(haystack, uint8('needle').'));
verifyFalse(testCase, contains_ascii_case_insensitive_bytes(uint8('short'), uint8('longer')));
verifyTrue(testCase, contains_ascii_case_insensitive_bytes(uint8('anything'), uint8([])));
end

function testRejectsNonByteInputs(testCase)
verifyError(testCase, @() contains_ascii_case_insensitive_bytes('abc', uint8('a')), ...
    'SIMPLE:InvalidByteInput');
verifyError(testCase, @() contains_ascii_case_insensitive_bytes(uint8('abc'), 'a'), ...
    'SIMPLE:InvalidByteInput');
end
