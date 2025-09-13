import os
import sys
from pathlib import Path

# Ensure `alfred_app` (under apps/api) is importable when running from repo root.
ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "apps" / "api"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

