"""Install runtime dependencies that pip cannot fully materialize."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _chromium_is_installed() -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False

    try:
        with sync_playwright() as playwright:
            path = Path(str(playwright.chromium.executable_path)).expanduser()
            return path.exists() and path.is_file() and os.access(path, os.X_OK)
    except Exception:
        return False


def install_chromium(*, quiet: bool = False) -> bool:
    """Install Playwright's Chromium browser runtime when missing."""
    if _chromium_is_installed():
        if not quiet:
            print("Playwright Chromium runtime is already installed.")
        return True

    if not quiet:
        print("Installing Playwright Chromium runtime...")
    result = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
    return result.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Install BigA-Analysis-Agents runtime dependencies.")
    parser.add_argument("--quiet", action="store_true", help="Only print installer output when installation is needed.")
    args = parser.parse_args()
    if not install_chromium(quiet=args.quiet):
        raise SystemExit(1)
