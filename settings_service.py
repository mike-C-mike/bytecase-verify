import json
import sys
from pathlib import Path

from bytecase_theme import normalize_theme_preference, THEME_SYSTEM


APP_NAME = "ByteCase Verify"
APP_SUBTITLE = "Hash Manifest Generator"
APP_VERSION = "0.9.1"

SUITE_NAME = "ByteCase"
PUBLISHER_NAME = "Forensics Byte"
PRODUCT_DOMAIN = "byte-case.com"
TOOL_FOLDER_NAME = "verify"
DEFAULT_ROOT_FOLDER_NAME = "ByteCase"


def get_base_dir():
    """
    Returns the directory where the app should create local settings files.

    When running from source, this is the project folder.
    When running as a PyInstaller executable, this is the folder containing the exe.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent

    return Path(__file__).parent


BASE_DIR = get_base_dir()
SETTINGS_PATH = BASE_DIR / "settings.json"


DEFAULT_SETTINGS = {
    "suite_name": SUITE_NAME,
    "publisher": PUBLISHER_NAME,
    "department_name": "",
    "unit_name": "",
    "default_technician": "",
    "technicians": [],
    "appearance": {
        "theme": THEME_SYSTEM
    },
    "output_paths": {
        "base_output_dir": "",
        "use_shared_bytecase_root": True
    },
    "report_branding": {
        "patch_image_path": ""
    },
    "hash_defaults": {
        "md5": True,
        "sha1": False,
        "sha256": True,
        "include_hashing_explanation": True,
        "include_hash_generation_method": True
    },
    "report_defaults": {
        "include_signature_block": True,
        "export_txt": True,
        "export_csv": False,
        "export_docx": True,
        "export_xlsx": False,
        "export_json": True
    }
}


def deep_merge(default, loaded):
    result = default.copy()

    for key, value in loaded.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def safe_case_folder_name(case_number):
    value = str(case_number or "").strip()

    if not value:
        value = "NO_CASE"

    for char in '<>:"/\\|?*':
        value = value.replace(char, "_")

    value = value.replace(" ", "_")

    while "__" in value:
        value = value.replace("__", "_")

    return value.strip("_") or "NO_CASE"


def get_default_output_root():
    return Path.home() / DEFAULT_ROOT_FOLDER_NAME


def get_output_root(settings):
    output_settings = settings.get("output_paths", {})
    base_output_dir = str(output_settings.get("base_output_dir", "")).strip()

    if base_output_dir:
        return Path(base_output_dir)

    return get_default_output_root()


def get_case_tool_paths(settings, case_number="", mode_folder=None):
    """
    Return the shared ByteCase output paths.

    Blank output root:
        C:\\Users\\<user>\\ByteCase\\<case_number>\\verify\\

    Custom output root:
        <custom_root>\\<case_number>\\verify\\
    """
    root_dir = get_output_root(settings)
    case_folder_name = safe_case_folder_name(case_number)
    case_dir = root_dir / case_folder_name
    tool_dir = case_dir / TOOL_FOLDER_NAME

    paths = {
        "root_dir": root_dir,
        "case_dir": case_dir,
        "tool_dir": tool_dir,
        "base_dir": tool_dir,
        "reports_dir": tool_dir,
        "saved_manifests_dir": tool_dir,
    }

    if mode_folder:
        mode_dir = tool_dir / str(mode_folder).strip().lower()
        paths["mode_dir"] = mode_dir
        paths["reports_dir"] = mode_dir
        paths["saved_manifests_dir"] = mode_dir

    return paths


def get_output_paths(settings, case_number="", mode_folder=None):
    return get_case_tool_paths(settings, case_number=case_number, mode_folder=mode_folder)


def ensure_directories(settings, case_number="", mode_folder=None):
    paths = get_case_tool_paths(settings, case_number=case_number, mode_folder=mode_folder)

    paths["root_dir"].mkdir(parents=True, exist_ok=True)
    paths["case_dir"].mkdir(parents=True, exist_ok=True)
    paths["tool_dir"].mkdir(parents=True, exist_ok=True)

    if mode_folder:
        paths["mode_dir"].mkdir(parents=True, exist_ok=True)
    else:
        for folder_name in ["manifests", "verifications", "comparisons"]:
            (paths["tool_dir"] / folder_name).mkdir(parents=True, exist_ok=True)

    return paths


def normalize_settings(settings):
    appearance = settings.get("appearance", {})

    if not isinstance(appearance, dict):
        appearance = {}

    settings["appearance"] = {
        "theme": normalize_theme_preference(appearance.get("theme", THEME_SYSTEM))
    }

    technicians = settings.get("technicians", [])

    if not isinstance(technicians, list):
        technicians = []

    cleaned_technicians = []
    seen = set()

    for technician in technicians:
        technician = str(technician).strip()

        if not technician:
            continue

        key = technician.lower()

        if key not in seen:
            cleaned_technicians.append(technician)
            seen.add(key)

    default_technician = str(settings.get("default_technician", "")).strip()

    if default_technician:
        key = default_technician.lower()

        if key not in seen:
            cleaned_technicians.insert(0, default_technician)

    settings["technicians"] = cleaned_technicians
    settings["default_technician"] = default_technician

    output_paths = settings.get("output_paths", {})

    if not isinstance(output_paths, dict):
        output_paths = {}

    settings["output_paths"] = {
        "base_output_dir": str(output_paths.get("base_output_dir", "")).strip(),
        "use_shared_bytecase_root": bool(output_paths.get("use_shared_bytecase_root", True))
    }

    report_defaults = settings.get("report_defaults", {})

    if not isinstance(report_defaults, dict):
        report_defaults = {}

    settings["report_defaults"] = {
        "include_signature_block": bool(report_defaults.get("include_signature_block", True)),
        "export_txt": bool(report_defaults.get("export_txt", True)),
        "export_csv": bool(report_defaults.get("export_csv", False)),
        "export_docx": bool(report_defaults.get("export_docx", True)),
        "export_xlsx": bool(report_defaults.get("export_xlsx", False)),
        "export_json": True
    }

    hash_defaults = settings.get("hash_defaults", {})

    if not isinstance(hash_defaults, dict):
        hash_defaults = {}

    settings["hash_defaults"] = {
        "md5": bool(hash_defaults.get("md5", True)),
        "sha1": bool(hash_defaults.get("sha1", False)),
        "sha256": bool(hash_defaults.get("sha256", True)),
        "include_hashing_explanation": bool(hash_defaults.get("include_hashing_explanation", True)),
        "include_hash_generation_method": bool(hash_defaults.get("include_hash_generation_method", True))
    }

    report_branding = settings.get("report_branding", {})

    if not isinstance(report_branding, dict):
        report_branding = {}

    settings["report_branding"] = {
        "patch_image_path": str(report_branding.get("patch_image_path", "")).strip()
    }

    settings["suite_name"] = str(settings.get("suite_name", SUITE_NAME)).strip() or SUITE_NAME
    settings["publisher"] = str(settings.get("publisher", PUBLISHER_NAME)).strip() or PUBLISHER_NAME
    settings["department_name"] = str(settings.get("department_name", "")).strip()
    settings["unit_name"] = str(settings.get("unit_name", "")).strip()

    return settings


def get_report_export_options(settings):
    """
    Return normalized report export preferences.

    JSON is always enabled because ByteCase Verify needs JSON manifests for
    later verification and comparison workflows.
    """
    report_defaults = settings.get("report_defaults", {})

    if not isinstance(report_defaults, dict):
        report_defaults = {}

    return {
        "txt": bool(report_defaults.get("export_txt", True)),
        "csv": bool(report_defaults.get("export_csv", False)),
        "docx": bool(report_defaults.get("export_docx", True)),
        "xlsx": bool(report_defaults.get("export_xlsx", False)),
        "json": True
    }


def format_export_path_list(outputs):
    """
    Build readable export path lines for user-facing messages.
    """
    labels = [
        ("TXT", outputs.get("txt")),
        ("CSV", outputs.get("csv")),
        ("DOCX", outputs.get("docx")),
        ("XLSX", outputs.get("xlsx")),
        ("JSON", outputs.get("json")),
    ]

    lines = []

    for label, path in labels:
        if path:
            lines.append(f"{label}:\n{path}")

    return "\n\n".join(lines)


def load_or_create_settings():
    if not SETTINGS_PATH.exists():
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as f:
            loaded = json.load(f)

        settings = deep_merge(DEFAULT_SETTINGS, loaded)
        settings = normalize_settings(settings)
        save_settings(settings)
        return settings

    except (json.JSONDecodeError, OSError):
        return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    settings = normalize_settings(settings)

    with SETTINGS_PATH.open("w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def get_settings_path():
    return SETTINGS_PATH


def get_base_path():
    return BASE_DIR
