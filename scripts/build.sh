#!/usr/bin/env bash
# build.sh — Build Solar2DBuilder for Linux (Android CI use)
#
# Usage: ./scripts/build.sh <BUILD> <YEAR>
# e.g.   ./scripts/build.sh 3728 2026
#
# Produces: solar2dbuilder-linux-<BUILD>.tar.gz
# Contents:
#   solar2d-linux-<BUILD>/Solar2DBuilder   (binary)
#   solar2d-linux-<BUILD>/Solar2DBuilder.sh (wrapper — sets LD_LIBRARY_PATH + xvfb-run)
#   solar2d-linux-<BUILD>/lib/             (bundled shared libs)
#   solar2d-linux-<BUILD>/Resources/       (Lua scripts + Android templates)
#
set -euo pipefail

BUILD="${1:?Usage: $0 <BUILD> <YEAR>}"
YEAR="${2:?Usage: $0 <BUILD> <YEAR>}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK_DIR="$(mktemp -d)"
PKG_NAME="solar2d-linux-${BUILD}"
PKG_DIR="${WORK_DIR}/${PKG_NAME}"

echo "==> Building Solar2DBuilder Linux ${YEAR}.${BUILD}"
echo "    WORK_DIR: ${WORK_DIR}"
echo "    REPO_ROOT: ${REPO_ROOT}"

# ── 1. Install dependencies ──────────────────────────────────────────
echo "==> Installing build dependencies..."
sudo apt-get update -qq
sudo apt-get install -y \
  cmake ninja-build git \
  openjdk-17-jdk-headless \
  libcurl4-openssl-dev libfreetype6-dev \
  libgl1-mesa-dev libglu1-mesa-dev libgl1-mesa-dri libglx-mesa0 \
  libopenal-dev libpng-dev libjpeg-dev libssl-dev \
  libvorbis-dev libogg-dev uuid-dev zlib1g-dev \
  libsdl2-dev p7zip-full xvfb \
  patchelf 2>/dev/null || true

# ── 2. Clone Solar2D source at tag ───────────────────────────────────
echo "==> Cloning coronalabs/corona @ tag ${BUILD}..."
git clone --recursive --depth 1 --branch "${BUILD}" \
  https://github.com/coronalabs/corona.git "${WORK_DIR}/src"

# ── 3. Apply patches ─────────────────────────────────────────────────
echo "==> Applying patches..."
cd "${WORK_DIR}/src"
for PATCH in "${REPO_ROOT}/patches/"*.patch; do
  echo "    Applying: $(basename "$PATCH")"
  git apply "$PATCH"
done

# ── 4. Build Solar2DBuilder ──────────────────────────────────────────
echo "==> Building Solar2DBuilder..."
mkdir -p platform/linux/build
cd platform/linux/build
cmake ../.. \
  -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_NUMBER="${BUILD}" \
  -DYEAR="${YEAR}"
ninja Solar2DBuilder
echo "    Binary size: $(du -sh Solar2DBuilder | cut -f1)"

# ── 5. Get Android templates from official release ───────────────────
echo "==> Downloading Android templates from Solar2D ${YEAR}.${BUILD}..."
mkdir -p "${WORK_DIR}/templates"

# Corona.aar from CoronaCards-Android release asset
CARDS_URL="https://github.com/coronalabs/corona/releases/download/${BUILD}/CoronaCards-Android-${YEAR}.${BUILD}.zip"
echo "    Downloading CoronaCards-Android..."
curl -fsSL "${CARDS_URL}" -o "${WORK_DIR}/CoronaCards-Android.zip"
cd "${WORK_DIR}/templates"
unzip -q "${WORK_DIR}/CoronaCards-Android.zip"
# Extract Corona.aar from the nested zip
unzip -q CoronaCardsAndroidAAR.zip
mv CoronaCards.aar Corona.aar
echo "    Corona.aar: $(du -sh Corona.aar | cut -f1)"

# android-template.zip from macOS DMG (only official source)
echo "    Downloading macOS DMG for android-template.zip..."
DMG_URL="https://github.com/coronalabs/corona/releases/download/${BUILD}/Solar2D-macOS-${YEAR}.${BUILD}.dmg"
curl -fsSL "${DMG_URL}" -o "${WORK_DIR}/Solar2D.dmg"
mkdir -p "${WORK_DIR}/dmg"
cd "${WORK_DIR}/dmg"
7z x "${WORK_DIR}/Solar2D.dmg" -o./outer 2>&1 | tail -3
HFS=$(find outer -type f -size +50M 2>/dev/null | head -1)
[ -n "$HFS" ] && 7z x "$HFS" -o./inner 2>&1 | tail -3 || mv outer inner
TEMPLATE=$(find . -name "android-template.zip" 2>/dev/null | head -1)
if [ -z "$TEMPLATE" ]; then
  echo "ERROR: android-template.zip not found in DMG" >&2
  exit 1
fi
cp "$TEMPLATE" "${WORK_DIR}/templates/android-template.zip"
echo "    android-template.zip: $(du -sh "${WORK_DIR}/templates/android-template.zip" | cut -f1)"
# Free up disk
rm -f "${WORK_DIR}/Solar2D.dmg"
rm -rf "${WORK_DIR}/dmg"

# ── 6. Assemble package ──────────────────────────────────────────────
echo "==> Assembling package..."
mkdir -p "${PKG_DIR}/lib" "${PKG_DIR}/Resources"

# Binary
cp "${WORK_DIR}/src/platform/linux/build/Solar2DBuilder" "${PKG_DIR}/"
chmod +x "${PKG_DIR}/Solar2DBuilder"

# Wrapper script (sets LD_LIBRARY_PATH + xvfb-run)
cat > "${PKG_DIR}/Solar2DBuilder.sh" << 'EOF'
#!/usr/bin/env bash
# Wrapper: bundles shared libs + virtual display for headless CI builds
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
export LD_LIBRARY_PATH="${DIR}/lib:${LD_LIBRARY_PATH:-}"
exec xvfb-run -a "${DIR}/Solar2DBuilder" "$@"
EOF
chmod +x "${PKG_DIR}/Solar2DBuilder.sh"

# Bundle shared libs (so it works on any distro, not just ubuntu-22.04)
echo "    Bundling shared libraries..."
ldd "${PKG_DIR}/Solar2DBuilder" \
  | awk '/=>/ && $3 ~ /^\// {print $3}' \
  | sort -u \
  | xargs -I{} cp -n {} "${PKG_DIR}/lib/" 2>/dev/null || true
echo "    Bundled $(ls "${PKG_DIR}/lib/" | wc -l) libs"

# Resources: Lua scripts from source
SRC="${WORK_DIR}/src"
echo "    Copying Lua resources from source..."
cp -r "${SRC}/platform/resources/." "${PKG_DIR}/Resources/"
# Additional CoronaBuilder Lua scripts
cp "${SRC}/tools/CoronaBuilder/CoronaBuilder.lua"              "${PKG_DIR}/Resources/" 2>/dev/null || true
cp "${SRC}/tools/CoronaBuilder/BuilderPluginDownloader.lua"    "${PKG_DIR}/Resources/" 2>/dev/null || true

# Resources: jar files from source
echo "    Copying jar files from source..."
cp "${SRC}/platform/android/project/AntInvoke/AntInvoke.jar"          "${PKG_DIR}/Resources/" 2>/dev/null || true
cp "${SRC}/platform/android/project/ListKeyStore/ListKeyStore.jar"     "${PKG_DIR}/Resources/" 2>/dev/null || true
cp "${SRC}/platform/android/AntLiveManifest/AntLiveManifest.jar"      "${PKG_DIR}/Resources/" 2>/dev/null || true
cp "${SRC}/platform/android/resources/_coronatest.jar"                 "${PKG_DIR}/Resources/" 2>/dev/null || true

# Resources: Android templates
cp "${WORK_DIR}/templates/Corona.aar"           "${PKG_DIR}/Resources/"
cp "${WORK_DIR}/templates/android-template.zip" "${PKG_DIR}/Resources/"

# Resources: Native subdir structure (for AndroidValidation.lua path)
mkdir -p "${PKG_DIR}/Resources/Native/Corona/android/resource"
mkdir -p "${PKG_DIR}/Resources/Native/Corona/android/lib/gradle"
cp "${WORK_DIR}/templates/android-template.zip" "${PKG_DIR}/Resources/Native/Corona/android/resource/"
cp "${WORK_DIR}/templates/Corona.aar"           "${PKG_DIR}/Resources/Native/Corona/android/lib/gradle/"

echo "    Resources: $(find "${PKG_DIR}/Resources" -type f | wc -l) files"

# ── 7. Create tarball ─────────────────────────────────────────────────
echo "==> Creating tarball..."
cd "${WORK_DIR}"
tar -czf "solar2dbuilder-linux-${BUILD}.tar.gz" "${PKG_NAME}"
TARBALL="${WORK_DIR}/solar2dbuilder-linux-${BUILD}.tar.gz"
echo "    Tarball: $(du -sh "$TARBALL" | cut -f1)"

# Copy to current directory
cp "$TARBALL" "${REPO_ROOT}/"
echo ""
echo "✅ Done: solar2dbuilder-linux-${BUILD}.tar.gz"
echo ""
echo "Test with:"
echo "  tar -xzf solar2dbuilder-linux-${BUILD}.tar.gz"
echo "  cd ${PKG_NAME}"
echo "  ./Solar2DBuilder.sh --help"
