"""Tests for scripts/patch-android-template.py.

Run: ``python3 -m unittest discover -s tests -v`` (or
``python3 tests/test_patch_android_template.py -v``).
"""

from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "app-build.gradle.kts.3728"
SCRIPT = REPO_ROOT / "scripts" / "patch-android-template.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("patch_android_template", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


pat = _load_module()


class PatchTextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original = FIXTURE.read_text()

    def test_upstream_template_is_the_expected_fixture(self) -> None:
        self.assertIn(
            'extra["minSdkVersion"] = parsedBuildProperties.lookup<Any?>("buildSettings.android.minSdkVersion")',
            self.original,
        )
        self.assertIn("compileSdk = 35", self.original)
        self.assertIn("targetSdk = 35", self.original)
        self.assertNotIn(pat.TARGET_SDK_KEY, self.original)

    def test_patch_rewrites_both_sdk_levels(self) -> None:
        patched, changed = pat.patch_template_text(self.original)
        self.assertTrue(changed)
        pat.verify_patched_text(patched)
        self.assertIn("compileSdk = coronaCompileSdkVersion", patched)
        self.assertIn("targetSdk = coronaTargetSdkVersion", patched)
        self.assertIn("maxOf(35, coronaTargetSdkVersion)", patched)
        # minSdk handling untouched.
        self.assertIn("minSdk = (extra[\"minSdkVersion\"] as Int)", patched)

    def test_patch_is_idempotent(self) -> None:
        patched, _ = pat.patch_template_text(self.original)
        again, changed = pat.patch_template_text(patched)
        self.assertFalse(changed)
        self.assertEqual(patched, again)

    def test_fails_closed_when_compile_sdk_anchor_disappears(self) -> None:
        mutated = self.original.replace("    compileSdk = 35\n", "", 1)
        with self.assertRaises(pat.PatchError):
            pat.patch_template_text(mutated)

    def test_fails_closed_when_target_is_declared_twice(self) -> None:
        mutated = self.original.replace(
            "        targetSdk = 35\n", "        targetSdk = 35\n        targetSdk = 35\n", 1
        )
        with self.assertRaises(pat.PatchError):
            pat.patch_template_text(mutated)

    def test_fails_closed_when_marker_present_without_lookup(self) -> None:
        mutated = self.original.replace(
            'extra["minSdkVersion"]', 'val coronaTargetSdkVersion = 36\nextra["minSdkVersion"]', 1
        )
        with self.assertRaises(pat.PatchError):
            pat.patch_template_text(mutated)

    def test_fails_closed_when_lookup_present_but_level_still_hardcoded(self) -> None:
        mutated = self.original.replace(
            'extra["minSdkVersion"]',
            'val unused = parsedBuildProperties.lookup<Any?>('
            '"buildSettings.android.targetSdkVersion")\n'
            'extra["minSdkVersion"]',
            1,
        )
        with self.assertRaises(pat.PatchError):
            pat.patch_template_text(mutated)


class PatchZipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="s2d-patch-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.zip_path = self.tmp / "android-template.zip"
        with zipfile.ZipFile(self.zip_path, "w") as zf:
            zf.writestr("template/app/build.gradle.kts", FIXTURE.read_text())
            zf.writestr("template/gradle/wrapper/gradle-wrapper.jar", b"\x00binary\xff" * 32)
            zf.writestr("template/app/src/main/AndroidManifest.xml", "<manifest/>")

    def test_cli_patches_zip_and_preserves_other_entries(self) -> None:
        rc = pat.main([str(self.zip_path)])
        self.assertEqual(rc, 0)

        with zipfile.ZipFile(self.zip_path) as zf:
            self.assertIsNone(zf.testzip())
            patched = zf.read("template/app/build.gradle.kts").decode()
            self.assertIn("targetSdk = coronaTargetSdkVersion", patched)
            self.assertEqual(
                zf.read("template/gradle/wrapper/gradle-wrapper.jar"), b"\x00binary\xff" * 32
            )
            self.assertEqual(zf.read("template/app/src/main/AndroidManifest.xml"), b"<manifest/>")
            self.assertEqual(
                zf.namelist(),
                [
                    "template/app/build.gradle.kts",
                    "template/gradle/wrapper/gradle-wrapper.jar",
                    "template/app/src/main/AndroidManifest.xml",
                ],
            )

    def test_cli_is_idempotent(self) -> None:
        self.assertEqual(pat.main([str(self.zip_path)]), 0)
        first = self.zip_path.read_bytes()
        self.assertEqual(pat.main([str(self.zip_path)]), 0)
        self.assertEqual(first, self.zip_path.read_bytes())

    def test_cli_reports_missing_file(self) -> None:
        self.assertEqual(pat.main([str(self.tmp / "nope.zip")]), 2)

    def test_cli_reports_zip_without_template_entry(self) -> None:
        broken = self.tmp / "no-template.zip"
        with zipfile.ZipFile(broken, "w") as zf:
            zf.writestr("something/else.txt", "hi")
        before = broken.read_bytes()
        self.assertEqual(pat.main([str(broken)]), 1)
        self.assertEqual(before, broken.read_bytes())

    def test_cli_preserves_file_mode(self) -> None:
        self.zip_path.chmod(0o640)
        self.assertEqual(pat.main([str(self.zip_path)]), 0)
        self.assertEqual(self.zip_path.stat().st_mode & 0o777, 0o640)

    def test_cli_fails_closed_and_leaves_zip_untouched(self) -> None:
        broken = self.tmp / "broken.zip"
        with zipfile.ZipFile(broken, "w") as zf:
            zf.writestr("template/app/build.gradle.kts", "// no anchors here\n")
        before = broken.read_bytes()
        self.assertEqual(pat.main([str(broken)]), 1)
        self.assertEqual(before, broken.read_bytes())


if __name__ == "__main__":
    unittest.main()
