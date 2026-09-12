"""Guards for the Solar2DBuilder release build path.

Every scheduled run of the release workflow failed from 2026-03-27 to
2026-09-12 because the build configured the wrong CMake source directory
(``cmake ../..`` from ``platform/linux/build`` points at ``platform/``, which
has no ``CMakeLists.txt``), and because ``patches/01-*.patch`` rewrote the root
``CMakeLists.txt`` without the ``CORONA_ROOT``/``ALSOFT_NATIVE_TOOLS_PATH``
variables that ``platform/linux/CMakeList.txt`` needs.  These tests keep both
regressions out.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SH = REPO_ROOT / "scripts" / "build.sh"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build.yml"
PATCH_DIR = REPO_ROOT / "patches"


def _stale_source_dir(text: str) -> re.Match[str] | None:
    """Find an actual `cmake ../..` command (comments may mention it)."""
    return re.search(r"^\s*cmake\s+\.\./\.\.", text, re.MULTILINE)


class ReleaseBuildPathTests(unittest.TestCase):
    def test_build_script_configures_repo_root(self) -> None:
        text = BUILD_SH.read_text()
        self.assertIn("cmake -S . -B platform/linux/build", text)
        self.assertIsNone(_stale_source_dir(text), "build.sh still configures platform/ as source")

    def test_workflow_configures_repo_root(self) -> None:
        text = WORKFLOW.read_text()
        self.assertIn("cmake -S . -B platform/linux/build", text)
        self.assertIsNone(_stale_source_dir(text), "workflow still configures platform/ as source")

    def test_release_builds_pass_build_number_and_year_as_env(self) -> None:
        # The upstream root CMakeLists.txt reads $ENV{BUILD_NUMBER}/$ENV{YEAR}
        # and its plain set() shadows -D cache values, so the env must be set.
        for path in (BUILD_SH, WORKFLOW):
            text = path.read_text()
            self.assertIn('BUILD_NUMBER="${BUILD}" YEAR="${YEAR}" cmake', text, path)

    def test_patch_set_does_not_rewrite_root_cmakelists(self) -> None:
        # platform/linux/CMakeList.txt needs CORONA_ROOT and
        # ALSOFT_NATIVE_TOOLS_PATH, which only the upstream root file defines.
        offenders = []
        for patch in sorted(PATCH_DIR.glob("*.patch")):
            for line in patch.read_text().splitlines():
                if re.match(r"^(---|\+\+\+) [ab]/CMakeLists\.txt\s*$", line):
                    offenders.append(patch.name)
                    break
        self.assertEqual(offenders, [], f"patches rewriting the root CMakeLists.txt: {offenders}")

    def test_release_workflow_verifies_the_patched_template(self) -> None:
        text = WORKFLOW.read_text()
        self.assertIn("scripts/patch-android-template.py", text)
        self.assertIn("buildSettings.android.targetSdkVersion", text)

    def test_package_includes_processed_and_shared_resources(self) -> None:
        # The template loads Native/Corona/shared/resource/json.lua through the
        # bundled lua binary, and the Android ant flow needs ant.jar etc. from
        # the processed resource tree; both were missing from the assembly.
        for path in (BUILD_SH, WORKFLOW):
            text = path.read_text()
            self.assertIn("platform/linux/build/Resources", text, path)
            self.assertIn("Native/Corona/shared/resource", text, path)

    def test_revision_check_covers_already_packaged_builds(self) -> None:
        # Comparing only against the latest release would rebuild and overwrite
        # the published asset every day once a revision is the latest release.
        text = WORKFLOW.read_text()
        self.assertIn("releases?per_page=100", text)
        self.assertNotIn("${{ github.repository }}/releases/latest", text)


if __name__ == "__main__":
    unittest.main()
