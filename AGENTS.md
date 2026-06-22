# Repository Instructions

Follow the enterprise doctrine in `SylphxAI/doctrine` and the local project boundary in [PROJECT.md](PROJECT.md). The machine-readable control-plane manifest is [.doctrine/project.json](.doctrine/project.json).

This repository owns the Linux Solar2DBuilder package producer only. Do not add game-specific build policy, app release behavior, central CI, release-bot, or platform-preview behavior here.

For package changes, record upstream Solar2D version evidence, patch/build proof, smoke output, release asset readback, and downstream compatibility impact. Published artifacts are forward-fix recovery unless a repo-local release runbook proves a safer rollback.
