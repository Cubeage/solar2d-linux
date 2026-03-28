# solar2d-linux

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

5 fixes applied to the Solar2D source to enable Linux Android builds:

| Patch | Fix |
|-------|-----|
| `01-add-android-support-tools.patch` | Simplify root CMakeLists.txt (was mis-including wrong platform file) |
| `02-linux-cmake-flags.patch` | Add `Rtt_AndroidSupportTools.c` to Solar2DBuilder + `CORONABUILDER_ANDROID` flag |
| `03-android-validation-linux-path.patch` | Add Linux branch to `AndroidValidation.lua` path lookup |
| `04-get-resource-directory-linux.patch` | Implement `GetResourceDirectory()` for Linux via `/proc/self/exe` |
| `05-tmp-dir-linux.patch` | Use `$TMPDIR` (not `/TemporaryFiles` which is root-owned on Linux) |

## Building locally

```bash
./scripts/build.sh 3728 2026
```

Requires: `cmake`, `ninja`, `jdk-17`, OpenGL dev libs, `7zip`, `xvfb`.
