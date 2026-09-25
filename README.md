# solar2d-linux

<p align="center">
  <img src="https://mark.sylphx.com/api/v1/mark/hero?type=constellation&theme=tokyonight&text=solar2d+linux&desc=Linux+build+of+Solar2DBuilder+for+Android+APK+builds+in+CI&height=200&animation=rise" alt="solar2d-linux — Sylphx Mark banner" width="100%" />
</p>

Linux builds of **Solar2DBuilder** for CI/CD Android APK builds.

Built from [Solar2D](https://github.com/coronalabs/corona) open source. Automatically updated when Solar2D releases a new version.

> Solar2D only publishes macOS + Windows binaries. This repo patches and builds `Solar2DBuilder` for Linux so Android APKs can be built on self-hosted Linux CI runners.

## Usage

```bash
# Download latest release
S2D_BUILD=3728
S2D_YEAR=2026

curl -fsSL "https://github.com/Cubeage/solar2d-linux/releases/download/${S2D_YEAR}.${S2D_BUILD}/solar2dbuilder-linux-${S2D_BUILD}.tar.gz" \
  | tar -xz

cd "solar2d-linux-${S2D_BUILD}"

# Build your APK (wrapper handles LD_LIBRARY_PATH + virtual display)
./Solar2DBuilder.sh build --lua path/to/recipe-android.lua
```

### GitHub Actions

```yaml
- name: Install Solar2DBuilder
  env:
    S2D_BUILD: '2026.3728'
  run: |
    curl -fsSL "https://github.com/Cubeage/solar2d-linux/releases/download/${S2D_BUILD}/solar2dbuilder-linux-${S2D_BUILD#*.}.tar.gz" \
      | tar -xz -C /opt
    echo "/opt/solar2d-linux-${S2D_BUILD#*.}" >> $GITHUB_PATH

- name: Build APK
  run: Solar2DBuilder.sh build --lua client/ci/recipe-android.lua
```

## Releases

Builds are published automatically when Solar2D releases a new version (daily check). See [Releases](https://github.com/Cubeage/solar2d-linux/releases).

Release tags are `YEAR.BUILD` (first packaging of an upstream Solar2D build) or
`YEAR.BUILD.REV` (a later packaging revision of the *same* upstream build —
for example the Android template fix below). The tarball inside always keeps
the upstream build number in its name (`solar2dbuilder-linux-<BUILD>.tar.gz`,
extracting to `solar2d-linux-<BUILD>/`), so downstream pins point at a
different release tag without changing their asset path:

```bash
# first packaging:   https://github.com/Cubeage/solar2d-linux/releases/download/2026.3728/solar2dbuilder-linux-3728.tar.gz
# packaging revision: https://github.com/Cubeage/solar2d-linux/releases/download/2026.3728.1/solar2dbuilder-linux-3728.tar.gz
```

Dispatch a revision with **Actions → Build Solar2DBuilder for Linux → Run
workflow** (`solar2d_build=3728`, `solar2d_year=2026`, `package_revision=1`).

### Packaging revisions (`repack_from`)

A revision that only changes packaging (like the Android template patch below) can reuse the
already published binary instead of recompiling: set `repack_from` to the base release tag (for
example `2026.3728`) and the workflow downloads that package, patches the Android template, verifies
it, re-tars the package under the same asset name and publishes it under the new tag. The release
notes record the base release, and the same repack can be reproduced locally:

```bash
scripts/repack-revision.sh 2026.3728 3728 --out dist
# → dist/solar2dbuilder-linux-3728.tar.gz (prints base + result sha256)
```

The daily check treats a build as already packaged when **any** release for `YEAR.BUILD` exists
(first packaging or revision), so it will not rebuild and overwrite a published asset; publish
another revision with `package_revision=<N>` or rebuild explicitly with `force=true`.

## Android target SDK (`build.settings`)

Solar2D ships its Android Gradle template with the platform level hardcoded
(`compileSdk = 35`, `targetSdk = 35` in `template/app/build.gradle.kts`) and
only reads `minSdkVersion` from the project's `build.settings`. Projects that
declare `android.targetSdkVersion` therefore still produced an artifact
targeting the hardcoded level, which Google Play refuses once its minimum
target rises (`Target SDK of artifact is too low: <versionCode>`).

Every package built here patches the template (inside the
DMG-extracted `android-template.zip`) so it:

* reads `buildSettings.android.targetSdkVersion` and uses it for
  `defaultConfig.targetSdk`,
* compiles against `maxOf(template default, targetSdk)` so AGP never compiles
  against a platform older than the declared target,
* falls back to the template default when the project does not declare a
  target (behaviour unchanged), and leaves `minSdkVersion` alone.

The patch is applied by `scripts/patch-android-template.py`; it fails closed
when upstream changes the template layout, so a release never ships an
unpatched (or silently unpatchable) template.

### Verifying it end to end

```bash
# unit tests for the template patch (fail-closed + idempotency)
python3 -m unittest discover -s tests -t . -v

# build tests/fixture-project (declares targetSdkVersion = "36") with a
# package directory and read the produced APK back with aapt2
ANDROID_SDK_ROOT=/path/to/android-sdk \
  scripts/smoke-target-sdk-build.sh /path/to/solar2d-linux-3728 --target 36
# → PASS: APK declares targetSdkVersion='36' (requested 36)
```

## Package contents

```
solar2d-linux-<BUILD>/
├── Solar2DBuilder        # compiled binary
├── Solar2DBuilder.sh     # wrapper (sets LD_LIBRARY_PATH + xvfb-run)
├── lib/                  # bundled shared libraries (works on any distro)
└── Resources/            # Lua scripts + Android templates
    ├── AndroidValidation.lua
    ├── Corona.aar
    ├── android-template.zip
    ├── ant.jar / AntInvoke.jar / ...
    └── Native/
        └── Corona/android/...
```

## Patches

4 fixes applied to the Solar2D source to enable Linux Android builds:

| Patch | Fix |
|-------|-----|
| `02-linux-cmake-flags.patch` | Add `Rtt_AndroidSupportTools.c` to Solar2DBuilder + `CORONABUILDER_ANDROID` flag |
| `03-android-validation-linux-path.patch` | Add Linux branch to `AndroidValidation.lua` path lookup |
| `04-get-resource-directory-linux.patch` | Implement `GetResourceDirectory()` for Linux via `/proc/self/exe` |
| `05-tmp-dir-linux.patch` | Use `$TMPDIR` (not `/TemporaryFiles` which is root-owned on Linux) |

The former `01-add-android-support-tools.patch` was removed on 2026-09-12. It replaced the upstream
root `CMakeLists.txt` with a three-line file that dropped `CORONA_ROOT` and `ALSOFT_NATIVE_TOOLS_PATH`
(both required by `platform/linux/CMakeList.txt`), and the workflow configured `cmake ../..` from
`platform/linux/build` — i.e. `platform/`, which has no `CMakeLists.txt`. Together they made every
scheduled build fail; builds now configure the repository root, which is what the upstream root file
expects.

The Android Gradle template is patched at package time (it ships inside the
official DMG, not in the patch set): see **Android target SDK** above and
`scripts/patch-android-template.py`.

## Building locally

```bash
./scripts/build.sh 3728 2026
```

Requires: `cmake`, `ninja`, `jdk-17`, OpenGL dev libs, `7zip`, `xvfb`.
The script configures the repository root (`cmake -S . -B platform/linux/build`), applies
`patches/`, downloads the official DMG for `Corona.aar`/`android-template.zip`, patches the Android
template, and writes `solar2dbuilder-linux-<BUILD>.tar.gz` in the repository root.
