import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from report_templates import HASH_GENERATION_METHOD, HASHING_EXPLANATION
from settings_service import APP_NAME, APP_VERSION, ensure_directories


CHUNK_SIZE = 1024 * 1024  # 1 MB


def safe_filename(value: str, fallback: str = "manifest") -> str:
    """
    Creates a filesystem-safe filename component.
    """
    value = (value or "").strip()

    if not value:
        value = fallback

    invalid_chars = '<>:"/\\|?*'

    for char in invalid_chars:
        value = value.replace(char, "_")

    value = value.replace(" ", "_")

    while "__" in value:
        value = value.replace("__", "_")

    return value.strip("_") or fallback


def get_file_modified_time(path: Path) -> str:
    """
    Returns file modified time as ISO-like local timestamp.
    """
    try:
        timestamp = path.stat().st_mtime
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except OSError:
        return ""


def collect_files(
    selected_files: Iterable[str],
    selected_folders: Iterable[str],
    recursive: bool
) -> List[Path]:
    """
    Collects selected files and files from selected folders.

    Duplicate file paths are removed while preserving order.
    """
    collected = []
    seen = set()

    for file_path in selected_files:
        path = Path(file_path)

        if path.is_file():
            resolved = str(path.resolve())

            if resolved not in seen:
                collected.append(path)
                seen.add(resolved)

    for folder_path in selected_folders:
        folder = Path(folder_path)

        if not folder.is_dir():
            continue

        pattern = "**/*" if recursive else "*"

        for path in folder.glob(pattern):
            if path.is_file():
                resolved = str(path.resolve())

                if resolved not in seen:
                    collected.append(path)
                    seen.add(resolved)

    return collected


def get_total_size_bytes(files: List[Path]) -> int:
    """
    Returns the total size in bytes for all accessible files.
    """
    total = 0

    for path in files:
        try:
            total += path.stat().st_size
        except OSError:
            continue

    return total


def normalize_algorithms(algorithms: Dict[str, bool]) -> Dict[str, bool]:
    """
    Ensures expected algorithm keys exist.
    """
    return {
        "md5": bool(algorithms.get("md5", False)),
        "sha1": bool(algorithms.get("sha1", False)),
        "sha256": bool(algorithms.get("sha256", False))
    }


def get_selected_algorithm_names(algorithms: Dict[str, bool]) -> List[str]:
    """
    Returns display names for selected algorithms.
    """
    algorithms = normalize_algorithms(algorithms)

    selected = []

    if algorithms["md5"]:
        selected.append("MD5")
    if algorithms["sha1"]:
        selected.append("SHA-1")
    if algorithms["sha256"]:
        selected.append("SHA-256")

    return selected


def hash_file(
    path: Path,
    algorithms: Dict[str, bool],
    progress_callback: Optional[Callable[[int], None]] = None
) -> Dict[str, object]:
    """
    Hashes one file using the selected algorithms.

    The file is read once, and all selected hash algorithms are updated during the same read loop.
    """
    algorithms = normalize_algorithms(algorithms)

    hashers = {}

    if algorithms["md5"]:
        hashers["md5"] = hashlib.md5()
    if algorithms["sha1"]:
        hashers["sha1"] = hashlib.sha1()
    if algorithms["sha256"]:
        hashers["sha256"] = hashlib.sha256()

    record = {
        "file_name": path.name,
        "file_path": str(path),
        "relative_path": path.name,
        "file_size_bytes": None,
        "modified_time": "",
        "md5": None,
        "sha1": None,
        "sha256": None,
        "hash_status": "Pending",
        "error": ""
    }

    try:
        stat = path.stat()
        record["file_size_bytes"] = stat.st_size
        record["modified_time"] = get_file_modified_time(path)

        with path.open("rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)

                if not chunk:
                    break

                for hasher in hashers.values():
                    hasher.update(chunk)

                if progress_callback:
                    progress_callback(len(chunk))

        if "md5" in hashers:
            record["md5"] = hashers["md5"].hexdigest()
        if "sha1" in hashers:
            record["sha1"] = hashers["sha1"].hexdigest()
        if "sha256" in hashers:
            record["sha256"] = hashers["sha256"].hexdigest()

        record["hash_status"] = "Completed"

    except OSError as e:
        record["hash_status"] = "Error"
        record["error"] = str(e)

    return record


def hash_files(
    files: List[Path],
    algorithms: Dict[str, bool],
    status_callback: Optional[Callable[[Dict[str, object]], None]] = None,
    progress_callback: Optional[Callable[[int], None]] = None
) -> List[Dict[str, object]]:
    """
    Hashes multiple files and returns file records.
    """
    results = []
    total_files = len(files)

    for index, path in enumerate(files, start=1):
        if status_callback:
            status_callback({
                "current_index": index,
                "total_files": total_files,
                "current_file": str(path)
            })

        record = hash_file(path, algorithms, progress_callback=progress_callback)
        results.append(record)

    return results


def build_manifest(
    settings: Dict[str, object],
    case_number: str,
    agency_case_number: str,
    technician: str,
    source_description: str,
    recursive: bool,
    algorithms: Dict[str, bool],
    include_hashing_explanation: bool,
    include_hash_generation_method: bool,
    notes: str,
    files: List[Dict[str, object]]
) -> Dict[str, object]:
    """
    Builds the full manifest object for JSON and report exports.
    """
    selected_algorithm_names = get_selected_algorithm_names(algorithms)
    summary = calculate_file_summary(files)

    manifest = {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "department": {
            "department_name": settings.get("department_name", ""),
            "unit_name": settings.get("unit_name", "")
        },
        "case_info": {
            "case_number": case_number.strip(),
            "agency_case_number": agency_case_number.strip(),
            "technician": technician.strip(),
            "source_description": source_description.strip()
        },
        "hash_settings": {
            "algorithms": selected_algorithm_names,
            "recursive": bool(recursive),
            "include_hashing_explanation": bool(include_hashing_explanation),
            "include_hash_generation_method": bool(include_hash_generation_method)
        },
        "hash_generation_method": {
            "implementation": "Python hashlib",
            "file_read_mode": "Binary read mode",
            "chunk_size_bytes": CHUNK_SIZE,
            "external_tools_used": False,
            "external_tool_description": "No external command-line, PowerShell, CertUtil, or third-party hashing executable was used."
        },
        "file_summary": summary,
        "files": files,
        "notes": notes.strip()
    }

    return manifest


def calculate_file_summary(files: List[Dict[str, object]]) -> Dict[str, int]:
    """
    Calculates summary counts for manifest output.
    """
    total_files = len(files)
    completed_count = 0
    error_count = 0
    total_size_bytes = 0

    for record in files:
        status = record.get("hash_status", "")

        if status == "Completed":
            completed_count += 1
        elif status == "Error":
            error_count += 1

        size = record.get("file_size_bytes")

        if isinstance(size, int):
            total_size_bytes += size

    return {
        "total_files": total_files,
        "completed_count": completed_count,
        "error_count": error_count,
        "total_size_bytes": total_size_bytes
    }


def format_bytes(size_bytes: Optional[int]) -> str:
    """
    Human-readable file size.
    """
    if size_bytes is None:
        return "Unknown"

    size = float(size_bytes)

    for unit in ["bytes", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            if unit == "bytes":
                return f"{int(size)} {unit}"

            return f"{size:.2f} {unit}"

        size /= 1024

    return f"{size_bytes} bytes"


def build_txt_manifest(manifest: Dict[str, object]) -> str:
    """
    Builds a plain text hash manifest report.
    """
    department = manifest.get("department", {})
    case_info = manifest.get("case_info", {})
    hash_settings = manifest.get("hash_settings", {})
    file_summary = manifest.get("file_summary", {})
    files = manifest.get("files", [])

    lines = []

    lines.append("HASH MANIFEST")
    lines.append("=" * 80)
    lines.append("")

    department_name = department.get("department_name", "")
    unit_name = department.get("unit_name", "")

    if department_name:
        lines.append(f"Department / Agency: {department_name}")
    if unit_name:
        lines.append(f"Unit: {unit_name}")

    if department_name or unit_name:
        lines.append("")

    lines.append("MANIFEST INFORMATION")
    lines.append("-" * 80)
    lines.append(f"Generated By: {manifest.get('app_name', '')} v{manifest.get('app_version', '')}")
    lines.append(f"Created At: {manifest.get('created_at', '')}")
    lines.append("")

    lines.append("CASE INFORMATION")
    lines.append("-" * 80)
    lines.append(f"Case Number: {case_info.get('case_number', '')}")
    lines.append(f"Agency Case Number: {case_info.get('agency_case_number', '')}")
    lines.append(f"Technician: {case_info.get('technician', '')}")
    lines.append(f"Source Description: {case_info.get('source_description', '')}")
    lines.append("")

    lines.append("HASH SETTINGS")
    lines.append("-" * 80)
    algorithms = hash_settings.get("algorithms", [])
    lines.append(f"Algorithms: {', '.join(algorithms) if algorithms else 'None selected'}")
    lines.append(f"Recursive Folder Selection: {'Yes' if hash_settings.get('recursive') else 'No'}")
    lines.append("")

    if hash_settings.get("include_hash_generation_method"):
        lines.append("HASH GENERATION METHOD")
        lines.append("-" * 80)
        lines.append(HASH_GENERATION_METHOD)
        lines.append("")

    lines.append("FILE SUMMARY")
    lines.append("-" * 80)
    lines.append(f"Total Files Listed: {file_summary.get('total_files', len(files))}")
    lines.append(f"Completed: {file_summary.get('completed_count', 0)}")
    lines.append(f"Errors: {file_summary.get('error_count', 0)}")
    lines.append(f"Total Size: {format_bytes(file_summary.get('total_size_bytes', 0))}")
    lines.append("")

    if hash_settings.get("include_hashing_explanation"):
        lines.append("HASHING EXPLANATION")
        lines.append("-" * 80)
        lines.append(HASHING_EXPLANATION)
        lines.append("")

    notes = manifest.get("notes", "")

    if notes:
        lines.append("NOTES")
        lines.append("-" * 80)
        lines.append(notes)
        lines.append("")

    lines.append("HASHED FILES")
    lines.append("-" * 80)
    lines.append("")

    for index, record in enumerate(files, start=1):
        lines.append(f"File {index}")
        lines.append("-" * 40)
        lines.append(f"Name: {record.get('file_name', '')}")
        lines.append(f"Path: {record.get('file_path', '')}")
        lines.append(f"Size: {format_bytes(record.get('file_size_bytes'))}")
        lines.append(f"Modified Time: {record.get('modified_time', '')}")
        lines.append(f"Status: {record.get('hash_status', '')}")

        if record.get("error"):
            lines.append(f"Error: {record.get('error')}")

        lines.append(f"MD5: {record.get('md5') or 'Not calculated'}")
        lines.append(f"SHA-1: {record.get('sha1') or 'Not calculated'}")
        lines.append(f"SHA-256: {record.get('sha256') or 'Not calculated'}")
        lines.append("")

    lines.append("=" * 80)
    lines.append("End of Hash Manifest")
    lines.append("=" * 80)

    return "\n".join(lines)


def save_manifest_outputs(
    manifest: Dict[str, object],
    settings: Dict[str, object]
) -> Tuple[Path, Path, Path]:
    """
    Saves TXT, CSV, and JSON outputs.
    """
    paths = ensure_directories(settings)

    case_number = manifest.get("case_info", {}).get("case_number", "")
    source_description = manifest.get("case_info", {}).get("source_description", "")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    safe_case = safe_filename(case_number, "NO_CASE")
    safe_source = safe_filename(source_description, "hash_manifest")
    base_filename = f"{safe_case}_{safe_source}_{timestamp}_hash_manifest"

    txt_path = paths["reports_dir"] / f"{base_filename}.txt"
    csv_path = paths["reports_dir"] / f"{base_filename}.csv"
    json_path = paths["saved_manifests_dir"] / f"{base_filename}.json"

    txt_report = build_txt_manifest(manifest)

    with txt_path.open("w", encoding="utf-8") as f:
        f.write(txt_report)

    save_csv_manifest(manifest, csv_path)

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return txt_path, csv_path, json_path


def save_csv_manifest(manifest: Dict[str, object], csv_path: Path) -> None:
    """
    Saves a CSV file with one row per hashed file.
    """
    files = manifest.get("files", [])
    case_info = manifest.get("case_info", {})

    fieldnames = [
        "case_number",
        "agency_case_number",
        "technician",
        "source_description",
        "file_name",
        "file_path",
        "file_size_bytes",
        "modified_time",
        "md5",
        "sha1",
        "sha256",
        "hash_status",
        "error"
    ]

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for record in files:
            writer.writerow({
                "case_number": case_info.get("case_number", ""),
                "agency_case_number": case_info.get("agency_case_number", ""),
                "technician": case_info.get("technician", ""),
                "source_description": case_info.get("source_description", ""),
                "file_name": record.get("file_name", ""),
                "file_path": record.get("file_path", ""),
                "file_size_bytes": record.get("file_size_bytes", ""),
                "modified_time": record.get("modified_time", ""),
                "md5": record.get("md5") or "Not calculated",
                "sha1": record.get("sha1") or "Not calculated",
                "sha256": record.get("sha256") or "Not calculated",
                "hash_status": record.get("hash_status", ""),
                "error": record.get("error", "")
            })