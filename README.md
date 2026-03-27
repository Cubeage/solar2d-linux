# solar2d-linux

Linux build of **Solar2DBuilder** for CI/CD Android APK builds.

Built from [Solar2D](https://github.com/coronalabs/corona) open source.  
Android templates extracted from the official macOS release DMG.

## Why?

Solar2D only publishes macOS + Windows binaries. This repo builds `Solar2DBuilder`  
for Linux so Android APKs can be built on self-hosted Linux CI runners.

## Usage

```bash
curl -L https://github.com/Cubeage/solar2d-linux/releases/download/2026.3728/solar2dbuilder-linux-3728.tar.gz | tar -xz
cd solar2d-linux-3728
./Solar2DBuilder build --lua recipe-android.lua
```

## Building a new version

Trigger the **Build Solar2DBuilder for Linux** workflow with the Solar2D build number.

Requires: `macos-k8s-0` self-hosted runner for Android template extraction.
