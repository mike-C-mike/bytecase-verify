# ByteCase Verify

**ByteCase Verify**

**ByteCase Verify** is a Windows-friendly forensic utility for creating file-level hash manifests, verifying files against prior manifests, and comparing saved manifest files.

It is designed for digital evidence, incident response, administrative evidence handling, and other workflows where a user needs a clear record of file names, paths, sizes, timestamps, and hash values.

ByteCase Verify is part of the **ByteCase** toolset by **Forensics Byte**.

Product domain: `byte-case.com`.

---

## Current Version

```text
v0.9.1 - ByteCase Branding / Theme Update
```

This project is currently in a **pre-1.0 release track**. A v1.0 stable release is being held until Microsoft code signing options are evaluated.

---

## Release Status

Current public Windows builds are **unsigned**.

Because the executable is not currently Microsoft code signed, Windows SmartScreen or antivirus products may display a warning when the application is downloaded or opened.

This does not automatically mean the application is malicious. It means the executable has not been signed with a trusted code-signing certificate and may not yet have reputation with Microsoft SmartScreen.

Users should only download releases from the official GitHub repository and should verify downloaded files using the published SHA-256 checksums.

See:

```text
UNSIGNED_WINDOWS_NOTICE.md
```

---

## What This Tool Does

ByteCase Verify helps users create structured, readable, and reusable hash documentation for selected files and folders.

The application can:

- Hash selected files.
- Hash files inside selected folders.
- Recursively collect files from folders when enabled.
- Calculate MD5, SHA-1, and SHA-256 hash values.
- Generate readable hash manifest reports.
- Save structured JSON manifests for later verification.
- Verify current files against a prior JSON manifest.
- Compare two saved JSON manifests.
- Export reports in selectable TXT, CSV, DOCX, XLSX formats, with JSON always preserved for manifest/verification workflows.
- Store agency, unit, technician, output folder, branding, and report defaults.
- Include an optional report signature block.
- Use the shared ByteCase visual theme with Dark, Light, and System Default modes.

---

## What This Tool Does Not Do

ByteCase Verify is **not** a forensic imaging tool.

It does not:

- Acquire physical drives.
- Acquire logical volumes.
- Create E01 images.
- Create AFF4 images.
- Create RAW/DD images.
- Control write blockers.
- Detect write blocker status.
- Parse file systems at the block level.
- Interpret evidence.
- Parse forensic artifacts.
- Determine user intent.
- Determine file relevance.
- Make investigative conclusions.

This tool performs **file-level hashing and report generation only**.

---

## Primary Workflows

### 1. Generate a New Hash Manifest

Use this workflow when you want to create a new manifest for selected files or folders.

Basic workflow:

```text
1. Enter case and source information.
2. Select hash algorithms.
3. Add files and/or folders.
4. Hash selected items.
5. Review the manifest.
6. Export the manifest.
```

Normal manifest export always creates JSON. Optional report formats can be enabled or disabled in Settings to reduce folder clutter.

Optional formats:

```text
TXT
CSV
DOCX
XLSX
```

JSON remains permanent because it can be loaded later for verification or comparison.

---

### 2. Verification Mode

Verification Mode is one of the main reasons this tool exists.

Use this workflow when you already have a prior JSON manifest and want to check whether current files still match that manifest.

Basic workflow:

```text
1. Load a prior manifest JSON.
2. Select the current files or folders.
3. Hash the current selection.
4. Review verification results.
5. Export the verification report.
```

Verification results may include:

| Result | Meaning |
|---|---|
| Matched | Compared hash values matched. |
| Hash mismatch | At least one compared hash value did not match. |
| Missing from current selection | A file listed in the original manifest was not found in the current selection. |
| New file not in original manifest | A current file was not listed in the original manifest. |
| Error | The file could not be compared or the comparison was ambiguous. |

Verification export always creates JSON and can also create the selected optional formats:

```text
TXT
CSV
DOCX
XLSX
```

---

### 3. Manifest Compare Mode

Compare Mode is for comparing two saved JSON manifests without re-hashing current files.

Use this workflow when you have two manifests and want to see what changed between them.

Basic workflow:

```text
1. Open Compare Two Manifests.
2. Load Manifest A JSON.
3. Load Manifest B JSON.
4. Review compare results.
5. Export the compare report.
```

Compare results may include:

| Result | Meaning |
|---|---|
| Matched | Compared hash values matched. |
| Hash mismatch | At least one compared hash value did not match. |
| Only in Manifest A | A file exists in Manifest A but not Manifest B. |
| Only in Manifest B | A file exists in Manifest B but not Manifest A. |
| Error | The file could not be compared or the comparison was ambiguous. |

Compare export always creates JSON and can also create the selected optional formats:

```text
TXT
CSV
DOCX
XLSX
```

---

## Supported Hash Algorithms

ByteCase Verify supports:

- MD5
- SHA-1
- SHA-256

Default settings:

```text
MD5: enabled
SHA-1: disabled
SHA-256: enabled
```

MD5 and SHA-1 are included for compatibility with existing workflows and legacy hash sets. SHA-256 is recommended for stronger integrity comparison.

---

## Hash Generation Method

Hash values are generated by the application using Python's built-in `hashlib` library.

Files are opened in binary read mode and processed in chunks. The selected hash algorithms are updated during the same file-read process.

The application does **not** use external command-line hashing utilities, PowerShell hashing commands, CertUtil commands, or third-party hashing executables to generate the listed hash values.

---

## Report Outputs

### TXT

The TXT report is a plain-text, readable report intended for easy review, copying, printing, and attachment to a case packet.

### CSV

The CSV output is useful for spreadsheet import, filtering, sorting, and system-to-system review.

### DOCX

The DOCX report is intended for readable report packets. It can include optional agency branding and optional signature lines.

### XLSX

The XLSX workbook provides formatted worksheets, summary sheets, filters, frozen panes, and issue/difference sheets for easier review.

### JSON

The JSON file is the structured manifest or report data. JSON is the preferred format for loading back into the tool for verification and comparison.

---


## Export Format Preferences

ByteCase Verify always exports JSON because JSON is the structured format required for later verification and manifest comparison workflows.

Users can choose which optional formats are exported by default in Settings:

```text
TXT
CSV
DOCX
XLSX
```

This helps keep output folders cleaner when a case only needs a JSON manifest plus one readable report format.

## Optional Signature Block

Normal hash manifest reports can include an optional signature block.

When enabled, TXT and DOCX reports include:

```text
Technician
Reviewed By
Date
Technician Signature
Reviewer Signature
```

This option can be enabled or disabled per report. It can also be set as a default in Settings.

The XLSX Summary sheet records whether the signature block option was enabled, but it does not include physical signature lines.

---

## Settings

The Settings window supports:

- Department / agency name
- Unit name
- Technician list
- Default technician
- Output folder configuration
- Saved manifest folder configuration
- Report branding image path
- Default hash algorithm selections
- Default report explanation settings
- Optional signature block default
- Dark, Light, and System Default theme

Settings are stored in a local `settings.json` file.

By default, output is written under `C:\Users\<user>\ByteCase\<case_number>\verify\`. A custom ByteCase Output Root may be selected in Settings. When a custom root is selected, ByteCase creates case folders directly inside that location.

When running from source, `settings.json` is created near the Python files.

When running from a packaged executable, `settings.json` is created beside the executable.

Do not commit a real agency `settings.json` file to a public repository unless it has been sanitized.

---

## Release Folder Layout

A packaged release folder should look similar to this:

```text
HashManifestGenerator-v0.9.0/
  HashManifestGenerator.exe
  README.md
  BUILD.md
  DEPENDENCIES.md
  KNOWN_LIMITATIONS.md
  RELEASE_CHECKLIST.md
  RELEASE_NOTES.md
  UNSIGNED_WINDOWS_NOTICE.md
  settings.example.json
  HashManifestGenerator-v0.9.0-SHA256SUMS.txt
  ByteCase/<case_number>/verify/manifests/
  ByteCase/<case_number>/verify/verifications/
  ByteCase/<case_number>/verify/comparisons/
```

The top-level `release/` folder should also contain:

```text
HashManifestGenerator-v0.9.0.zip
HashManifestGenerator-v0.9.0-SHA256SUMS.txt
```

---

## Verifying SHA-256 Checksums

A release should include a checksum file named similar to:

```text
HashManifestGenerator-v0.9.0-SHA256SUMS.txt
```

To verify the ZIP on Windows PowerShell:

```powershell
Get-FileHash .\HashManifestGenerator-v0.9.0.zip -Algorithm SHA256
```

Compare the displayed hash to the value listed in the checksum file.

To verify the executable after extracting the ZIP:

```powershell
Get-FileHash .\HashManifestGenerator.exe -Algorithm SHA256
```

---

## Running From Source

Requirements:

- Windows 10 or Windows 11 recommended
- Python 3.10 or newer recommended
- PowerShell

Install runtime dependencies:

```powershell
py -m pip install -r requirements.txt
```

Run the application:

```powershell
py .\main.py
```

---

## Building a Windows Release

Install runtime dependencies:

```powershell
py -m pip install -r requirements.txt
```

Install build dependencies:

```powershell
py -m pip install -r requirements-build.txt
```

Run the release build script with a one-time execution policy bypass:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_release.ps1 -Version 0.9.0
```

Expected output:

```text
release/HashManifestGenerator-v0.9.0/
release/HashManifestGenerator-v0.9.0.zip
release/HashManifestGenerator-v0.9.0-SHA256SUMS.txt
```

---

## Dependencies

See:

```text
DEPENDENCIES.md
```

Runtime dependencies:

- Python standard library
- Tkinter
- python-docx
- openpyxl

Build dependency:

- PyInstaller

---

## Known Limitations

See:

```text
KNOWN_LIMITATIONS.md
```

Important limitations include:

- File-level hashing only
- No physical disk imaging
- No write blocker control
- No forensic artifact parsing
- Possible ambiguity when duplicate file names or duplicate relative paths exist in older manifests
- Windows-focused packaging and folder-opening behavior

---

## Recommended GitHub Release Assets

For a v0.9.0 GitHub pre-release, upload:

```text
HashManifestGenerator-v0.9.0.zip
HashManifestGenerator-v0.9.0-SHA256SUMS.txt
```

Mark the release as:

```text
Pre-release
```

Do not label this as v1.0 until code signing and final release expectations are addressed.

---

## Project Status

ByteCase Verify is currently a public pre-1.0 tool.

Planned before a future v1.0 release:

- Code signing evaluation
- Additional release testing
- Documentation review
- Possible UI polish
- Public screenshots
- Finalized stable release checklist

---

## License

This project is intended to be released under the MIT License.

Confirm that a `LICENSE` file is present before publishing a public release.