#!/usr/bin/env bash
# smoke-target-sdk-build.sh — prove a Solar2DBuilder package honours
# build.settings android.targetSdkVersion end to end.
#
# It builds the tiny fixture project in tests/fixture-project (which declares
# targetSdkVersion = "36") with the given Solar2DBuilder package, then reads
# the produced APK back with aapt2 and fails unless the artifact declares the
# requested target SDK.  This is the regression check for
# scripts/patch-android-template.py.
#
# Usage:
#   scripts/smoke-target-sdk-build.sh <solar2d-linux-package-dir> [--target 36] [--work DIR]
#
# Environment:
#   ANDROID_SDK_ROOT  Android SDK with the requested platform + build-tools
#                     (auto-detected from $ANDROID_HOME / $ANDROID_SDK_ROOT)
#   AAPT2             aapt2 binary (default: newest build-tools aapt2)
#
# Exits non-zero when the artifact's targetSdkVersion != --target.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

PKG_DIR="${1:?Usage: $0 <solar2d-linux-package-dir> [--target N] [--work DIR]}"
shift

TARGET=36
WORK=""
while [ $# -gt 0 ]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --work)   WORK="$2";   shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

PKG_DIR="$(cd "$PKG_DIR" && pwd)"
[ -x "$PKG_DIR/Solar2DBuilder" ] || { echo "no Solar2DBuilder in $PKG_DIR" >&2; exit 2; }

ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
if [ -z "$ANDROID_SDK_ROOT" ] || [ ! -d "$ANDROID_SDK_ROOT" ]; then
  echo "ANDROID_SDK_ROOT/ANDROID_HOME must point at an Android SDK" >&2
  exit 2
fi
export ANDROID_SDK_ROOT ANDROID_HOME="$ANDROID_SDK_ROOT"

AAPT2="${AAPT2:-$(ls "$ANDROID_SDK_ROOT"/build-tools/*/aapt2 2>/dev/null | sort -V | tail -1)}"
[ -x "$AAPT2" ] || { echo "aapt2 not found under $ANDROID_SDK_ROOT/build-tools" >&2; exit 2; }

WORK="${WORK:-$(mktemp -d)}"
mkdir -p "$WORK/project" "$WORK/out"
cp "$REPO_ROOT"/tests/fixture-project/main.lua "$WORK/project/"
cp "$REPO_ROOT"/tests/fixture-project/build.settings "$WORK/project/"

# Fixture project declares the target SDK under test.
python3 - "$WORK/project/build.settings" "$TARGET" <<'PY'
import sys, pathlib
path, target = pathlib.Path(sys.argv[1]), sys.argv[2]
path.write_text(path.read_text().replace("__TARGET_SDK__", target))
PY

# Throwaway signing key for the fixture build.
if [ ! -f "$WORK/debug.keystore" ]; then
  keytool -genkeypair -keystore "$WORK/debug.keystore" -alias androiddebugkey \
    -storepass android -keypass android -keyalg RSA -keysize 2048 -validity 30 \
    -dname "CN=Cubeage SDK Smoke,O=Cubeage,C=HK" >/dev/null 2>&1
fi

cat > "$WORK/recipe.lua" <<EOF
return {
	appName = "targetsdk-smoke",
	androidAppPackage = "com.cubeage.targetsdksmoke",
	androidStore = "google",
	platform = "android",
	appVersion = "1.0.0",
	androidVersionCode = "1",
	projectPath = "$WORK/project",
	dstPath = "$WORK/out",
	certificatePath = "$WORK/debug.keystore",
	keystorePassword = "android",
	keystoreAlias = "androiddebugkey",
	keystoreAliasPassword = "android",
}
EOF

echo "==> Building fixture project targeting API $TARGET with $PKG_DIR"
export LD_LIBRARY_PATH="$PKG_DIR/lib:${LD_LIBRARY_PATH:-}"
if command -v xvfb-run >/dev/null 2>&1; then
  xvfb-run -a "$PKG_DIR/Solar2DBuilder" build --lua "$WORK/recipe.lua"
else
  "$PKG_DIR/Solar2DBuilder" build --lua "$WORK/recipe.lua"
fi

APK="$(find "$WORK/out" -name '*.apk' | head -1)"
[ -n "$APK" ] || { echo "FAIL: no APK produced in $WORK/out" >&2; ls -la "$WORK/out" >&2; exit 1; }

echo "==> aapt2 dump badging $APK"
"$AAPT2" dump badging "$APK" | grep -E "^(package|sdkVersion|targetSdkVersion)" || true

DECLARED="$("$AAPT2" dump badging "$APK" | sed -n "s/^targetSdkVersion:'\([0-9]*\)'.*/\1/p")"
if [ "$DECLARED" != "$TARGET" ]; then
  echo "FAIL: APK targetSdkVersion='$DECLARED', expected '$TARGET' ($APK)" >&2
  exit 1
fi
echo "PASS: APK declares targetSdkVersion='$DECLARED' (requested $TARGET)"
echo "APK: $APK"
