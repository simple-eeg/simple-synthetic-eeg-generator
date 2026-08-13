# Dependency locking

`producing.in` and `test.in` are the approved direct-version anchors, not
complete locks. Before any candidate data are generated, resolve them under
CPython 3.13.6 on macOS 26.6.1 arm64 into reviewed lock files that pin every
transitive distribution and include SHA-256 hashes. Install into a new local
virtual environment using pip's `--require-hashes` mode.

The reviewed producing and test locks are byte-identical: exactly 19
distributions and SHA-256
`ed84d519fd102843c2da38e7174d829a352eabfb4babdb8321018dbb9cce6b05`.
The generator refuses any other lock bytes or package/version map, even if an
alternative lock is complete and fully hashed. It also requires the installed
distribution set to equal that reviewed map exactly.
