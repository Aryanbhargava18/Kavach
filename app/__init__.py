"""Kavach. Loads .env (if present) before anything reads the environment."""
import os
from pathlib import Path

_env = Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            if _v.strip() and _k.strip() not in os.environ:
                os.environ[_k.strip()] = _v.strip().strip('"').strip("'")
