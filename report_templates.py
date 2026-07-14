HASH_GENERATION_METHOD = """Hash values in this manifest were calculated by Hash Manifest Generator using Python's built-in hashlib library. Files were opened in binary read mode and processed in chunks. The selected hash algorithms were updated during the same file read process.

No external command-line hashing utility, PowerShell hashing command, CertUtil command, or third-party hashing executable was used by this application to generate the listed hash values."""


HASHING_EXPLANATION = """Hash values are fixed-length digital fingerprints generated from file contents using cryptographic hash algorithms. When the contents of a file remain unchanged, the same algorithm should produce the same hash value. If the file contents change, the resulting hash value should also change.

This manifest includes the selected hash values for the listed files at the time the manifest was generated. Hash values may be used to support file identification, integrity checks, duplicate identification, and later comparison. The presence of a matching hash value does not independently explain the meaning, relevance, source, or user activity associated with a file."""