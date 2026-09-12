#!/usr/bin/env bash
# repack-revision.sh — publish a packaging revision of an already released
# Solar2DBuilder package.
#
# The binary and the resource tree stay exactly as published; only the Android
# Gradle template inside android-template.zip is patched (build.settings
# targetSdkVersion support).  This is the low-risk way to ship a template fix
# without recompiling Solar2DBuilder.
#
# Usage:
#   scripts/repack-revision.sh <base-release-tag|base-build> <build> [--out DIR] [--from FILE]
#
# e.g. scripts/repack-revision.sh 2026.3728 3728 --out dist
#
# Prints the base and result sha256 so the release notes can record provenance.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_SLUG="${REPO_SLUG:-Cubeage/solar2d-linux}"

BASE_TAG="${1:?Usage: $0 <base-release-tag|base-build> <build> [--out DIR] [--from FILE]}"
BUILD="${2:?Usage: $0 <base-release-tag|base-build> <build> [--out DIR] [--from FILE]}"
shift 2

OUT=""
FROM=""
while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    --from) FROM="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

case "$BASE_TAG" in
  *.*) ;;
  *) BASE_TAG="$(date +%Y).${BASE_TAG}" ;;
esac

PKG="solar2d-linux-${BUILD}"
TARBALL="solar2dbuilder-linux-${BUILD}.tar.gz"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

if [ -n "$FROM" ]; then
  cp "$FROM" "$WORK/$TARBALL"
else
  URL="https://github.com/${REPO_SLUG}/releases/download/${BASE_TAG}/${TARBALL}"
  echo "==> Downloading base release ${BASE_TAG}: ${URL}"
  curl -fsSL "$URL" -o "$WORK/$TARBALL"
fi
BASE_SHA="$(sha256sum "$WORK/$TARBALL" | cut -d' ' -f1)"
echo "    base sha256: ${BASE_SHA}"

tar -xzf "$WORK/$TARBALL" -C "$WORK"
[ -d "$WORK/$PKG" ] || { echo "base archive has no ${PKG}/ directory" >&2; exit 1; }

echo "==> Patching android-template.zip"
python3 "$REPO_ROOT/scripts/patch-android-template.py" "$WORK/$PKG/Resources/android-template.zip"
python3 "$REPO_ROOT/scripts/patch-android-template.py" "$WORK/$PKG/Resources/Native/Corona/android/resource/android-template.zip"

echo "==> Repacking"
( cd "$WORK" && tar -czf "$TARBALL" "$PKG" )

if [ -n "$OUT" ]; then
  mkdir -p "$OUT"
  cp "$WORK/$TARBALL" "$OUT/$TARBALL"
  TARGET="$OUT/$TARBALL"
else
  cp "$WORK/$TARBALL" "./$TARBALL"
  TARGET="./$TARBALL"
fi

RESULT_SHA="$(sha256sum "$TARGET" | cut -d' ' -f1)"
echo "==> Done: ${TARGET}"
echo "    base   sha256: ${BASE_SHA}  (${BASE_TAG})"
echo "    repack sha256: ${RESULT_SHA}"
