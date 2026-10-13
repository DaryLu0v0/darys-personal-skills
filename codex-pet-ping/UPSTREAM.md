# Upstream attribution

## Application foundation: lolPing

- Repository: [darrenprx/lolPing](https://github.com/darrenprx/lolPing)
- Author: Danrui Meng / darrenprx
- Base release: [v0.5.1](https://github.com/darrenprx/lolPing/tree/v0.5.1)
- Exact base commit: [`b1181e9ea53972992a503d078fdb06792ffa087e`](https://github.com/darrenprx/lolPing/tree/b1181e9ea53972992a503d078fdb06792ffa087e)
- License: MIT for source code; original text and separate Riot Games asset notice retained in [LICENSE.lolPing](LICENSE.lolPing).

lolPing supplies the desktop ping wheel, input helper, overlay rendering, settings, localization, and Electron packaging. The saved patch adds an opt-in Windows question action to local `needvision` / green Need Vision pings and connects it to the new native pet bridge. Remote pings and settings previews do not trigger questions. The initial implementation used `missing` / `?`; it was moved to Need Vision on 2026-10-13 at the user's request.

## Workflow reference: super-ping

- Repository: [norvancc/super-ping](https://github.com/norvancc/super-ping)
- Role: reference for capturing a screenshot, highlighting the ping point, and passing the image with a question to an assistant.
- Inspected components: `Sources/PingAgent/ActionRunner.swift`, `Sources/PingCore/MarkedScreenshot.swift`, and `Sources/PingCore/CaptureSequence.swift`.

super-ping's implementation targets macOS and launches a Codex CLI flow. This folder does not vendor, translate, or depend on its Swift source. It is credited for the workflow reference; the Windows bridge was implemented separately. No super-ping revision is required to build this extension.

## Local implementation

Prepared for DaryLu0v0 on 2026-10-13. The new code captures and annotates the pinged Windows display, invokes the existing desktop pet with Win+Alt+P, pastes the image and question, and submits through the normal pet UI. It preserves existing drafts and cleans up temporary capture files.

This is a local extension, not an official release of lolPing, super-ping, or the Codex desktop app. The original upstream author and project metadata remain intact in the reconstructed application.
