# Codex Pet Ping

A Windows extension to [lolPing](https://github.com/darrenprx/lolPing): a green **Need Vision** ping captures the display you pinged, circles the point, and asks your existing Codex / ChatGPT desktop pet about it. The answer appears in the pet's own conversation bubble.

The screenshot-and-question workflow was inspired by [super-ping](https://github.com/norvancc/super-ping). This implementation uses lolPing's Windows input and overlay system, with a new native Windows bridge to the existing pet. See [UPSTREAM.md](UPSTREAM.md) for attribution and the exact base revision.

## Use

1. Start the desktop pet and sign in.
2. In the extended lolPing app, enable **Settings → Pings & sound → Ask your pet with a Need Vision ping**.
3. Hold **Alt**, drag down-left to the green **Need Vision** icon on the default wheel, then release the mouse and Alt.

The pet action follows the Need Vision icon if you customize its wheel position. The **? / Enemy Missing** ping now behaves as a normal ping.

The question asks what the item at the orange circle means or does. The extension sends the entire pinged display as an attachment to the pet. Temporary capture files are removed after handoff; the sent image and question remain in the pet conversation. Existing drafts block submission, and repeated pings during handoff are ignored. If a handoff fails, check the pet for a partial draft before trying again.

This setting defaults to off in fresh installations. It was enabled in the local installation tested on 2026-10-13.

## Source layout

This folder stores the integration as a small, reproducible addition to pinned lolPing **v0.5.1**:

- [`overlay/`](overlay/) contains the new TypeScript coordinator, native C# bridge, and question tests.
- [`patches/lolping-pet.patch`](patches/lolping-pet.patch) contains changes to existing lolPing files, including the settings UI, screenshot handoff, build configuration, and tests.
- [`upstream.json`](upstream.json) pins the base commit and records content hashes for all 16 changed or added files.
- [`prepare.mjs`](prepare.mjs) reconstructs a complete source checkout and checks those hashes.
- [`VALIDATION.md`](VALIDATION.md) records the implementation checks and live test.

Dependencies, installers, desktop screenshots, and local settings are excluded from this folder.

## Prepare and build

Requirements: Windows 11 x64, Git, Node.js 22.12 or later, Visual Studio 2022 or later with **Desktop development with C++**, and the Windows .NET Framework 4.x compiler. The existing desktop pet must support **Win+Alt+P**.

From this folder:

```powershell
node prepare.mjs
Set-Location .work/lolPing
npm ci
npx install-electron
npm run build:helper
npm run typecheck
npm test
npm run dev
```

To make an installer after building the helpers:

```powershell
npm run build
npx electron-builder --win nsis --config.nsis.artifactName=lolPing-Pet-Setup-0.5.1.exe --publish never
```

The installer is written under the reconstructed checkout's `release/` directory. Use the custom artifact name to distinguish it from an official lolPing release.

`prepare.mjs` creates `.work/lolPing` and refuses to overwrite an existing directory. To use an existing local upstream clone without downloading it, run `node prepare.mjs --source "path/to/lolPing"`. To prepare a second checkout, add `--destination "path/to/new-checkout"`. Local uncommitted changes are not imported: the script checks out the pinned commit and applies only the saved integration.

## Compatibility

The live test used desktop version **26.928.4866.0** on Windows with the existing Hikari pet. The bridge uses Windows accessibility and the normal pet shortcut; it does not use a private Codex API. Changes to the pet's shortcut or UI can require an update to the bridge. This integration has not been validated on other desktop versions or on macOS.

The upstream lolPing updater is still configured to the official lolPing repository. Installing an upstream update can replace this extension.

## Credits and license

- **[darrenprx/lolPing](https://github.com/darrenprx/lolPing)** — the application and source-code foundation. Copyright © 2026 Danrui Meng; the original [MIT license and asset notice](LICENSE.lolPing) are preserved.
- **[norvancc/super-ping](https://github.com/norvancc/super-ping)** — reference for asking a question with a screenshot and a marked ping point. No Swift source was copied.
- **DaryLu0v0's local integration** — the Windows screenshot-to-existing-pet bridge and its lolPing wiring.

Riot Games ping and emote assets in the upstream checkout are not covered by lolPing's MIT source-code license. See the upstream license and README for those notices.
