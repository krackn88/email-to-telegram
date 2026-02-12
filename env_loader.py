"""Base directory and .env loading. Works when run as script or as PyInstaller binary."""
import os
import sys
from pathlib import Path


def get_base_dir() -> Path:
    """Directory for .env, token.json, state.json, credentials.json (next to exe when frozen)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def load_dotenv() -> None:
    """Load .env from get_base_dir() into os.environ (only set if not already set)."""
    base = get_base_dir()
    env_file = base / ".env"
    if not env_file.exists():
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and v:
                    os.environ.setdefault(k, v)
