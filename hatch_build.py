"""Build the React frontend into backend/static/ when packaging a wheel.

This is what lets `uvx craybee serve` work with no Node on the user's machine:
the compiled bundle travels inside the wheel as ordinary package data.
"""

import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

ROOT = Path(__file__).parent
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist"
STATIC = ROOT / "backend" / "static"


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        if version != "standard":  # editable installs skip the build
            return
        if not (FRONTEND / "package.json").exists():
            return

        npm = shutil.which("npm")
        if npm is None:
            raise RuntimeError(
                "Node/npm is required to build the craybee wheel "
                "(the frontend bundle is compiled into it)."
            )

        self.app.display_waiting("Building frontend...")
        subprocess.run([npm, "ci"], cwd=FRONTEND, check=True)
        subprocess.run([npm, "run", "build"], cwd=FRONTEND, check=True)

        if STATIC.exists():
            shutil.rmtree(STATIC)
        shutil.copytree(DIST, STATIC)
        self.app.display_success(f"Frontend bundled into {STATIC.relative_to(ROOT)}")
