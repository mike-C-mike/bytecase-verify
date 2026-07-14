import json
import sys
from pathlib import Path


APP_NAME = "Hash Manifest Generator"
APP_VERSION = "0.1.2"


def get_base_dir():
    """
    Returns the directory where the app should create local files.

    When running from source, this is the project folder.
    When running as a PyInstaller executable, this is the folder containing the exe.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent

    return Path(__file__).parent


BASE_DIR = get_base_dir()
SETTINGS_PATH = BASE_DIR / "settings.json"


DEFAULT_SETTINGS = {
    "department_name": "",
    "unit_name": "",
    "default_technician": "",
    "appearance": {
        "theme": "dark"
    },
    "output_paths": {
        "base_output_dir": "",
        "reports_folder_name": "output",
        "saved_manifests_folder_name": "saved_manifests"
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
    }
}


def deep_merge(default, loaded):
    """
    Recursively merges loaded settings into default settings.

    This allows older settings.json files to continue working when new settings are added.
    """
    result = default.copy()

    for key, value in loaded.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def load_or_create_settings():
    """
    Loads settings.json if it exists.

    If it does not exist, creates it using DEFAULT_SETTINGS.
    """
    if not SETTINGS_PATH.exists():
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as f:
            loaded = json.load(f)

        return deep_merge(DEFAULT_SETTINGS, loaded)

    except (json.JSONDecodeError, OSError):
        return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    """
    Saves settings.json next to the executable or source files.
    """
    with SETTINGS_PATH.open("w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def get_output_paths(settings):
    """
    Resolves output paths based on settings.

    If base_output_dir is blank, outputs are created next to the app.
    """
    output_settings = settings.get("output_paths", {})

    base_output_dir = output_settings.get("base_output_dir", "").strip()
    reports_folder_name = output_settings.get("reports_folder_name", "output").strip() or "output"
    saved_manifests_folder_name = output_settings.get("saved_manifests_folder_name", "saved_manifests").strip() or "saved_manifests"

    if base_output_dir:
        base_dir = Path(base_output_dir)
    else:
        base_dir = BASE_DIR

    reports_dir = base_dir / reports_folder_name
    saved_manifests_dir = base_dir / saved_manifests_folder_name

    return {
        "base_dir": base_dir,
        "reports_dir": reports_dir,
        "saved_manifests_dir": saved_manifests_dir
    }


def ensure_directories(settings):
    """
    Ensures output directories exist and returns the resolved paths.
    """
    paths = get_output_paths(settings)

    paths["base_dir"].mkdir(parents=True, exist_ok=True)
    paths["reports_dir"].mkdir(parents=True, exist_ok=True)
    paths["saved_manifests_dir"].mkdir(parents=True, exist_ok=True)

    return paths