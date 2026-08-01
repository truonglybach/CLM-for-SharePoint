"""
Shared test setup.
Makes src/ importable when the package isn't pip-installed and supplies dummy
environment variables so config.Settings() constructs without real credentials.
Forces USE_DUMMY_AI so the pipeline never makes a network call during tests.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Minimal, non-secret config so importing config/auth/sharepoint_io succeeds.
os.environ.setdefault("TENANT_ID", "test-tenant")
os.environ.setdefault("CLIENT_ID", "test-client")
os.environ.setdefault("SITE_ID", "test-site")
os.environ.setdefault("DRIVE_ID", "test-drive")
os.environ.setdefault("CLIENT_SECRET", "test-secret")
os.environ.setdefault("USE_DUMMY_AI", "true")
