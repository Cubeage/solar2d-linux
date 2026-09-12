# Test fixtures

`app-build.gradle.kts.3728` is a **verbatim copy** of the Android Gradle
template that Solar2D 2026.3728 ships inside `android-template.zip`
(`template/app/build.gradle.kts`).

- Upstream source: <https://github.com/coronalabs/corona/blob/3728/platform/android/app/build.gradle.kts>
- sha256: `f10bf3b5feb5da0446986ce1cc8fc3c2670ee8cb04481e8db3e2d33d8616dbc4`
- It is byte-identical to the copy extracted from
  `Solar2D-macOS-2026.3728.dmg` → `android-template.zip` (verified 2026-09-12),
  which is the input the release build patches.

`scripts/patch-android-template.py` must keep working on real upstream input,
which is why the fixture is the real 43 KB file rather than a trimmed excerpt:
the tests patch it, assert the anchors were found exactly once, and assert the
template still has no hardcoded `compileSdk`/`targetSdk` afterwards.
