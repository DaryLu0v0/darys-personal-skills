# Validation record

Test date: **2026-10-13**. Platform: **Windows x64**. Desktop app version: **26.928.4866.0**.

## Windows sign-in startup configuration — 2026-10-14

- Enabled the installed app's `launchAtStartup` setting. `enabledOnStart` and `petAskEnabled` remained enabled, and all other saved settings were preserved.
- Verified the current user's Windows Run entry named `com.lolping.app` points to the installed `lolPing.exe` with the `--hidden` argument.
- Confirmed there was no existing Windows StartupApproved entry disabling this item.
- Restarted lolPing and verified that the application and its input helper were running with the saved setting enabled.
- Retained a local settings backup outside the repository. No machine-specific settings or user paths were added to this repository.

The startup preference and registration were checked directly. A Windows sign-out/sign-in cycle was not performed. This configuration uses lolPing's existing startup support; no application source or binary changed.

## Current revision: green Need Vision trigger

On 2026-10-13, the pet action moved from `missing` / `?` to `needvision`, matching the green icon supplied by the user. Settings labels, English and Chinese question text, documentation, and regression checks were updated.

- **72 tests across 3 affected files passed**, including rejection of `?` pings, acceptance of Need Vision pings, and exclusion of remote pings and settings previews.
- Type checking and production build passed.
- The saved package reconstructed successfully; all **16 integration files** matched the updated content hashes.
- The updated installer completed with exit code 0. The installed application hash matched the new package; `petAskEnabled`, the Alt trigger, and enabled-on-start were retained.
- The app was restarted with the new mapping. The pet interaction was not repeated in this revision; the earlier live result below used the original `?` trigger.

| Current artifact | SHA-256 |
| --- | --- |
| `lolPing-Pet-NeedVision-Setup-0.5.1.exe` | `B0E43B7D92355CF7B0BCBFE74F2A2BC5DDB9599CC589E1C277011B02920A370A` |
| Installed `app.asar` | `2D07C97B172E891DA89754AF36CD5C22B1F9E7E4AA440588B247C2D4D97F1E97` |

The native pet bridge and official input helper were unchanged from the earlier build below.

## Initial implementation checks (? trigger)

- TypeScript suite: **720 tests passed across 45 files**.
- Type checking: passed.
- Patch whitespace check: passed.
- Real input-helper simulation/protocol tests: 7 passed using the unchanged official helper executable.
- Installer completed with exit code 0; installed application and helper hashes matched the packaged outputs.

The machine did not have the Visual Studio C++ compiler. The unchanged original input helper was reused from the verified official lolPing v0.5.1 installation. The new C# pet bridge was compiled locally. A clean build of the original C++ helper was therefore not performed on this machine.

## Repository package checks

- `prepare.mjs` successfully reconstructed a fresh checkout from the local upstream clone at the pinned commit.
- All **16 changed or added files** matched the saved implementation hashes after applying the patch and new files.
- A repeat invocation refused to overwrite the existing checkout and preserved its contents.
- The retained upstream license matched the original file byte for byte.
- The reconstructed checkout is ignored by the parent repository. Only the integration source, patch, manifest, and documentation are included for version control.

These checks verify source reconstruction. The application tests and live behavior below describe the earlier tested installation; they were not rerun just to package the same source.

## Initial live behavior (? trigger)

- An actual **Alt + left-drag to ?** gesture triggered the screenshot handoff.
- The existing **Hikari** pet identified the circled **Zoom Workplace** desktop shortcut and answered in its own native activity bubble.
- A test draft in the pet blocked submission and was preserved. The test draft was subsequently cleared.
- Temporary screenshot request directories were removed after the handoff.

Desktop screenshots and local settings from these checks are intentionally not part of the repository package. This record describes one observed desktop version; compatibility with other versions is unverified.

## Initial build binary hashes (? trigger)

SHA-256 values identify the locally tested build. Compiling again may produce different binary bytes.

| Artifact | SHA-256 |
| --- | --- |
| Custom installer `lolPing-Pet-Setup-0.5.1.exe` | `CE1CFF0ED5F88E57CEF8FF938593E750946FD799059BA712E8EC3772E57A42AC` |
| New native `pet-bridge.exe` | `423E8B30F48CFE0DB71B9FF1C6B340D6862B28D1087381A3A0AADC18D31B5BBE` |
| Installed `app.asar` | `38FC1F86F6890385ABBA8AA2720BF75876498F62B75DEA4D1CAA7F98AB4649A4` |
| Unchanged official `hook-helper.exe` | `163A05D580047D161D30F3D4FBBBBEF15E5319A2CB621D4D5CD92036DC60A6C3` |

The original official `lolPing-Setup-0.5.1.exe` used as the input-helper source had SHA-256 `42B88183E07999E305AB9D2E7CE150797D2B94CFE6F60A0D237FBA469523AD4A`.
