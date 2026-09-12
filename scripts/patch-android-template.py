#!/usr/bin/env python3
"""Make Solar2D's Android Gradle template honour ``build.settings`` target SDK.

Why
---
Solar2D ships its Android Gradle template inside ``android-template.zip`` with
the target platform hardcoded::

    android {
        compileSdk = 35
        defaultConfig {
            targetSdk = 35
            ...

Only ``minSdkVersion`` is read from the project's ``build.settings``.  Projects
that declare ``android.targetSdkVersion`` therefore still produce APKs/AABs
that target the template's hardcoded level, which Google Play refuses for
updates once its minimum target rises (observed: ``Target SDK of artifact is
too low`` for an APK declaring ``targetSdkVersion:'35'`` after 2026-08-31).

What this does
--------------
Rewrites ``template/app/build.gradle.kts`` inside the extracted-from-DMG
``android-template.zip`` *in place* so the template:

* reads ``buildSettings.android.targetSdkVersion`` (falling back to the value
  the template shipped with, so behaviour is unchanged when absent),
* uses it for ``defaultConfig.targetSdk``,
* compiles against ``maxOf(shipped default, targetSdk)`` so AGP never compiles
  against a platform older than the declared target,
* leaves ``minSdkVersion`` handling untouched,
* publishes the resolved value as ``extra["targetSdkVersion"]`` for plugins.

Fail-closed
-----------
Every anchor must be found exactly once.  When upstream changes the template
layout the script exits non-zero *without* touching the zip, so the release
build stops instead of silently shipping an unpatchable/unpatched template.
Re-running on an already-patched template is a no-op (exit 0).

Usage
-----
    scripts/patch-android-template.py <android-template.zip>

Exit codes: ``0`` patched or already patched, ``1`` anchor/verification
failure, ``2`` usage error.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

TEMPLATE_ENTRY = "template/app/build.gradle.kts"

# ``extra["minSdkVersion"] = ...`` marks where Solar2D already reads
# build.settings; the target-SDK lookup is inserted right after it.
MIN_SDK_ANCHOR = (
    'extra["minSdkVersion"] = parsedBuildProperties.lookup<Any?>('
    '"buildSettings.android.minSdkVersion")'
)
TARGET_SDK_KEY = "buildSettings.android.targetSdkVersion"

# Marker written into the template so re-runs (and readers) can recognise it.
MARKER = "coronaTargetSdkVersion"

INSERT_BLOCK = """
// Cubeage/solar2d-linux: read the target platform from build.settings.
// Google Play rejects updates that target an API level below its current
// minimum, so the level must come from the project, not this template.
val {marker}: Int =
        parsedBuildProperties.lookup<Any?>("{key}").firstOrNull()?.toString()?.toIntOrNull()
                ?: {default}
// AGP requires compileSdk >= targetSdk; keep the template's own level as the
// floor so absent/older declarations keep working exactly as before.
val coronaCompileSdkVersion: Int = maxOf({default}, {marker})
extra["targetSdkVersion"] = {marker}
"""


class PatchError(RuntimeError):
    pass


def _single_match(pattern: str, text: str, what: str) -> re.Match[str]:
    matches = list(re.finditer(pattern, text, re.MULTILINE))
    if len(matches) != 1:
        raise PatchError(
            f"expected exactly one {what} in {TEMPLATE_ENTRY}, found {len(matches)}; "
            "upstream template layout changed — update scripts/patch-android-template.py"
        )
    return matches[0]


def patch_template_text(text: str) -> tuple[str, bool]:
    """Return ``(patched_text, changed)``; raises PatchError when anchors drift."""
    if MARKER in text or TARGET_SDK_KEY in text:
        # Already patched (ours, or upstream adopting the same lookup).
        if TARGET_SDK_KEY not in text:
            raise PatchError(
                f"marker {MARKER!r} present but no {TARGET_SDK_KEY!r} lookup; "
                "refusing to guess"
            )
        if re.search(r"^[ \t]*(compileSdk|targetSdk) = \d+[ \t]*$", text, re.MULTILINE):
            raise PatchError(
                "template declares "
                f"{TARGET_SDK_KEY!r} but still hardcodes a compileSdk/targetSdk level; "
                "update scripts/patch-android-template.py"
            )
        return text, False

    min_sdk = _single_match(
        re.escape(MIN_SDK_ANCHOR) + r".*\n(\s*\?: \d+)\n", text, "minSdkVersion lookup (anchor)"
    )
    compile_sdk = _single_match(
        r"^(?P<indent>[ \t]*)compileSdk = (?P<value>\d+)[ \t]*$", text, "compileSdk assignment"
    )
    target_sdk = _single_match(
        r"^(?P<indent>[ \t]*)targetSdk = (?P<value>\d+)[ \t]*$", text, "targetSdk assignment"
    )

    default_compile = int(compile_sdk.group("value"))
    default_target = int(target_sdk.group("value"))
    if default_compile != default_target:
        raise PatchError(
            "template ships compileSdk="
            f"{default_compile} but targetSdk={default_target}; refusing to guess the floor"
        )
    default = default_compile

    block = INSERT_BLOCK.format(marker=MARKER, key=TARGET_SDK_KEY, default=default)

    patched = text[: min_sdk.end()] + block + text[min_sdk.end():]
    patched, n_compile = re.subn(
        r"^([ \t]*)compileSdk = " + str(default) + r"([ \t]*)$",
        r"\1compileSdk = coronaCompileSdkVersion\2",
        patched,
        count=1,
        flags=re.MULTILINE,
    )
    patched, n_target = re.subn(
        r"^([ \t]*)targetSdk = " + str(default) + r"([ \t]*)$",
        r"\1targetSdk = " + MARKER + r"\2",
        patched,
        count=1,
        flags=re.MULTILINE,
    )
    if (n_compile, n_target) != (1, 1):
        raise PatchError(
            f"internal error: replacements compileSdk={n_compile} targetSdk={n_target}"
        )
    return patched, True


def verify_patched_text(text: str) -> None:
    """Assert the patch really is in place (used before writing the zip)."""
    required = [
        f'val {MARKER}: Int =',
        f'"{TARGET_SDK_KEY}"',
        "compileSdk = coronaCompileSdkVersion",
        f"targetSdk = {MARKER}",
        'extra["minSdkVersion"] = parsedBuildProperties.lookup',
    ]
    missing = [needle for needle in required if needle not in text]
    if missing:
        raise PatchError(f"patched template is missing expected code: {missing}")
    if re.search(r"^[ \t]*(compileSdk|targetSdk) = \d+[ \t]*$", text, re.MULTILINE):
        raise PatchError("patched template still contains a hardcoded SDK level")


def rewrite_zip(zip_path: Path, new_text: str) -> None:
    """Replace TEMPLATE_ENTRY inside ``zip_path`` atomically, keeping all else."""
    mode = zip_path.stat().st_mode
    with zipfile.ZipFile(zip_path) as zin:
        infos = zin.infolist()
        try:
            entry = next(i for i in infos if i.filename == TEMPLATE_ENTRY)
        except StopIteration:
            raise PatchError(f"{zip_path} has no {TEMPLATE_ENTRY}") from None
        data = {i.filename: zin.read(i.filename) for i in infos}

    data[TEMPLATE_ENTRY] = new_text.encode("utf-8")

    tmp_fd, tmp_name = tempfile.mkstemp(dir=str(zip_path.parent), suffix=".zip.tmp")
    try:
        with open(tmp_fd, "wb") as tmp_out, zipfile.ZipFile(tmp_out, "w") as zout:
            for info in infos:
                new_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                new_info.compress_type = info.compress_type
                new_info.external_attr = info.external_attr
                new_info.internal_attr = info.internal_attr
                new_info.create_system = info.create_system
                new_info.comment = info.comment
                zout.writestr(new_info, data[info.filename])
        shutil.move(tmp_name, zip_path)
        os.chmod(zip_path, mode)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("template_zip", type=Path, help="android-template.zip to patch in place")
    args = parser.parse_args(argv)

    zip_path: Path = args.template_zip
    if not zip_path.is_file():
        print(f"error: {zip_path} is not a file", file=sys.stderr)
        return 2

    try:
        with zipfile.ZipFile(zip_path) as zf:
            original = zf.read(TEMPLATE_ENTRY).decode("utf-8")
    except KeyError:
        print(f"error: {zip_path} has no {TEMPLATE_ENTRY}", file=sys.stderr)
        return 1

    try:
        patched, changed = patch_template_text(original)
        if changed:
            verify_patched_text(patched)
    except PatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not changed:
        print(f"patch-android-template: {zip_path} already patched (no-op)")
        return 0

    rewrite_zip(zip_path, patched)

    with zipfile.ZipFile(zip_path) as zf:
        written = zf.read(TEMPLATE_ENTRY).decode("utf-8")
    verify_patched_text(written)

    print(
        "patch-android-template: patched {} (sha256 {})".format(
            zip_path, hashlib.sha256(written.encode()).hexdigest()[:16]
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
