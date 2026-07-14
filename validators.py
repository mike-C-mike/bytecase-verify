def get_selected_algorithm_names(algorithms):
    """
    Returns selected hash algorithm display names from the algorithm checkbox dictionary.
    """
    selected = []

    if algorithms.get("md5"):
        selected.append("MD5")
    if algorithms.get("sha1"):
        selected.append("SHA-1")
    if algorithms.get("sha256"):
        selected.append("SHA-256")

    return selected


def validate_hash_request(selected_files, selected_folders, algorithms):
    """
    Validates whether hashing can begin.

    Returns:
        errors: list of blocking problems
        warnings: list of non-blocking concerns
    """
    errors = []
    warnings = []

    selected_algorithm_names = get_selected_algorithm_names(algorithms)

    if not selected_algorithm_names:
        errors.append("Select at least one hash algorithm before hashing.")

    if not selected_files and not selected_folders:
        errors.append("Add at least one file or folder before hashing.")

    return errors, warnings


def validate_manifest_for_export(manifest):
    """
    Validates whether a completed manifest can be exported.

    Returns:
        errors: list of blocking problems
        warnings: list of non-blocking concerns
    """
    errors = []
    warnings = []

    case_info = manifest.get("case_info", {})
    hash_settings = manifest.get("hash_settings", {})
    files = manifest.get("files", [])

    algorithms = hash_settings.get("algorithms", [])

    if not algorithms:
        errors.append("No hash algorithms are recorded in the manifest.")

    if not files:
        errors.append("No hash results are available to export.")

    if not case_info.get("case_number", "").strip():
        warnings.append("Case Number is blank.")

    if not case_info.get("technician", "").strip():
        warnings.append("Technician is blank.")

    if not case_info.get("source_description", "").strip():
        warnings.append("Source Description is blank.")

    summary = summarize_hash_results(files)

    if summary["error_count"] > 0:
        warnings.append(
            f"{summary['error_count']} file(s) could not be hashed and are listed with error status."
        )

    return errors, warnings


def summarize_hash_results(files):
    """
    Summarizes hash result records.

    Returns a dictionary useful for review windows and report output.
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


def format_bytes(size_bytes):
    """
    Human-readable file size formatter used by validation/review.
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