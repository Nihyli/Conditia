from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = (BACKEND_ROOT / "conditia.db").resolve()
DEFAULT_STORAGE_DIR = (BACKEND_ROOT / "storage").resolve()
