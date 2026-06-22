# Cubeage Solar2D Linux

Cubeage Solar2D Linux builds Linux Solar2DBuilder artifacts for Android APK builds on CI. It owns the Solar2D source patch set, Linux build script, GitHub Actions release workflow, and published tarball artifacts consumed by downstream game build pipelines.

Lifecycle: `production`
Layer: `tooling`

## Goals

- Produce Linux Solar2DBuilder packages for self-hosted or GitHub Actions Android build pipelines.
- Track upstream Solar2D releases and apply the repository patch set needed for Linux Android builds.
- Publish reproducible release artifacts with smoke evidence and release readback.

## Non-Goals

- This repository does not own the upstream Solar2D runtime, game source code, or Android app release behavior.
- This repository does not own consumer CI workflows beyond the published Solar2DBuilder package contract.
- This repository does not own central CI runner, enterprise release bot, or platform preview behavior.

## Boundaries

The machine-readable source of truth is [.doctrine/project.json](.doctrine/project.json). Agents must keep this repository as a build-tool artifact producer and route game-specific build behavior to consuming game repositories.

## Public Surfaces

- Linux build script in `scripts/build.sh`.
- Solar2D Linux patch set under `patches/`.
- Release workflow in `.github/workflows/build.yml`.
- GitHub Release tarball `solar2dbuilder-linux-<BUILD>.tar.gz`.

## Delivery

Release changes require upstream Solar2D version evidence, patch application proof, package smoke output, GitHub Release asset readback, and downstream compatibility notes. Published artifacts are externally consumable; recovery is normally a forward-fix release, release deletion/deprecation when safe, or staged channel halt rather than source revert alone.
