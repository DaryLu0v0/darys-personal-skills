# GPT-Live participant for Zoom

Use GPT-Live as a named, speaking Zoom participant and delegate project questions
to an **existing OpenClaw agent**. This directory adds a small Python command-line
wrapper around OpenClaw's official `zoom-meetings` plugin. The plugin handles
Chrome, Zoom admission, native audio, and the GPT-Live connection.

The implementation targets **OpenClaw and `@openclaw/zoom-meetings` 2026.10.9**.
The generic workflow's original checks are documented in
[Validation](docs/VALIDATION.md). This copy contains portable code and generic
configuration. Existing host-specific live receipts are not published here.

For a separately provisioned Windows/WSL host, see the
[Windows prerequisites](docs/LOCAL_WINDOWS.md). `Start-Hikari.cmd` lives in this
repository's `hikari/` subfolder. The optional skill source is `$hikari-meeting`;
cloning does not install it, create services or join a meeting.

## How it works

| Component | Responsibility |
| --- | --- |
| Zoom Web App in OpenClaw Chrome | Displays the AI participant and carries meeting audio. |
| OpenClaw meeting audio engine | Captures other participants separately from the virtual microphone carrying AI speech. |
| GPT-Live in `bidi` mode | Listens, speaks, handles interruptions, and delegates deeper work. |
| Existing OpenClaw agent | Uses its already configured project workspace and tools to answer delegated questions. |
| This wrapper | Builds a scoped configuration patch from a short meeting brief and invokes the existing OpenClaw CLI. |

The brief is embedded in `realtime.instructions` together with
[meeting_instructions.txt](meeting_instructions.txt). Detailed project files stay
in the existing agent's workspace. Listing a file in the brief does not upload
it or grant the agent access to it.

### Voice routes

| Route | Model | Voice | Authentication on the Gateway host |
| --- | --- | --- | --- |
| `api` — default | `gpt-live-1` | `marin` | OpenAI Platform API credentials with model access. |
| `codex` — optional | `gpt-live-1-codex` | `cove` | Supported OpenClaw OpenAI sign-in and account access. |

For the optional Codex route, upstream documents
`openclaw models auth login --provider openai`. The wrapper does not sign in,
collect keys, or change model credentials. Configure API credentials in the
environment/provider configuration used by the **Gateway**, which may differ
from the shell running this wrapper. The two model/voice pairs are deliberate;
`cove` belongs to the Codex route.

## Requirements

- Python 3.10 or later. The wrapper uses only the standard library.
- An installed OpenClaw host and the official Zoom plugin, with a running
  Gateway. The reviewed version is `2026.10.9` for both.
- An existing agent ID whose workspace contains the relevant project context.
- Chrome and native audio on a supported desktop host, either alongside the
  Gateway or on an OpenClaw paired node.
- A Zoom meeting that permits browser participation, with any required account
  access and host admission.

If the Zoom plugin is missing, install it separately:

```bash
openclaw plugins install npm:@openclaw/zoom-meetings@2026.10.9 --pin
```

Follow the installation's application/start instructions and verify the running
Gateway before joining. The wrapper never installs OpenClaw, installs a plugin,
starts a Gateway, or creates an agent automatically.

### Where Chrome and audio run

The pinned upstream path documents **macOS with BlackHole 2ch and SoX**, or a
**Linux desktop with PipeWire-Pulse and its command-line tools**. Run the audio
processes as the same desktop user as Chrome. A headless/root service without
that user's audio session is insufficient.

For a paired Chrome node, allow `browser.proxy` and `zoommeetings.chrome` through
the node's existing OpenClaw permissions. Model credentials and the project agent
remain on the Gateway host. Select the audio backend for the machine that runs
Chrome, not the machine that runs this Python wrapper.

**Windows-native meeting audio is unverified for this integration.** Running the
wrapper on Windows does not establish a supported Windows audio path. Use a
documented macOS/Linux desktop or paired node for the initial end-to-end test.
See the pinned [upstream audio setup](https://github.com/openclaw/openclaw/blob/v2026.10.9/docs/plugins/meeting-plugins.md#prepare-chrome-and-audio).

Offline `prepare` and `validate` can run on Windows. Commands that invoke
OpenClaw deliberately reject native Windows `.cmd` and `.bat` launchers,
including npm's usual Windows shim. Run those commands on macOS/Linux or in a
suitable WSL environment with its own OpenClaw executable. WSL still needs a
working supported Chrome/audio host; it does not by itself verify meeting audio.

## Quick start

Run these commands from the `hikari/` subfolder. If your interpreter is named
`python3`, substitute it for `python`.

### 1. Write the meeting brief

Copy [MEETING_BRIEF.example.md](MEETING_BRIEF.example.md) to a working file, replace
the placeholders, and save it. The maximum brief length is **6,000 characters**.
Include the meeting objective, a few verified facts, and pointers to project
files already accessible to the existing agent.

### 2. Prepare and inspect the patch

Replace `path/to/meeting-brief.md` and `YOUR_EXISTING_AGENT_ID` below:

```console
python inference/zoom/zoom_assistant.py prepare --brief path/to/meeting-brief.md --agent YOUR_EXISTING_AGENT_ID --name "Hikari - AI assistant" --output inference/zoom/.local/zoom.patch.json
python inference/zoom/zoom_assistant.py validate --patch inference/zoom/.local/zoom.patch.json
```

`prepare` writes a local JSON patch. It does not call OpenClaw or join a meeting.
It refuses to overwrite an existing output unless you add `--force`. `validate`
checks this wrapper's allowed schema and configuration scope locally; it does
not verify an installed OpenClaw runtime or model access.

The wrapper selects the existing agent by ID and limits its meeting tool policy
to `safe-read-only` project questions. It does not create or reconfigure that
agent.

Use `--route codex` for the optional Codex voice route. For a paired node, add
`--chrome-node YOUR_NODE_ID` and, when needed, either
`--audio-backend blackhole-2ch` or `--audio-backend pipewire-pulse` to `prepare`.
Omitting `--chrome-node` preserves any existing paired-node setting during the
recursive patch; it does not switch an existing remote configuration to local.

[openclaw.zoom.example.json](openclaw.zoom.example.json) shows the patch shape.
The generated patch is specific to your brief and selected agent.

### 3. Let OpenClaw validate, then apply

```console
python inference/zoom/zoom_assistant.py apply --patch inference/zoom/.local/zoom.patch.json --dry-run
python inference/zoom/zoom_assistant.py apply --patch inference/zoom/.local/zoom.patch.json
python inference/zoom/zoom_assistant.py check
```

`apply` always runs OpenClaw's native configuration dry run first. With
`--dry-run`, it stops there. Without that flag, it applies the patch after the
dry run succeeds. This changes only the Zoom plugin configuration; it does not
replace the whole OpenClaw configuration or reconfigure the project agent.
OpenClaw may reserialize the configuration file, so preservation of unrelated
values does not imply preservation of JSON5 comments or formatting.

The patch enables both the plugin entry and its runtime, and sets the selected
model at both configuration levels. This prevents an older disabled setting or
provider-specific model from silently overriding the new route.

The patch deliberately sets `chrome.audioInputCommand` to `null`, removing an
existing custom input override. GPT-Live requires OpenClaw's managed isolated
browser capture so it can hear people while speaking without hearing its own
injected output. Review that change if you previously configured custom audio.

`check` prints the installed host version and runs
`openclaw zoommeetings setup --mode bidi`. A version mismatch is reported;
the reviewed baseline does not imply compatibility with arbitrary versions.
Resolve failed setup checks before using the speaking participant.

### 4. Join and inspect

Replace the quoted placeholder with the actual Zoom invite URL:

```console
python inference/zoom/zoom_assistant.py join "YOUR_ZOOM_INVITE_URL"
python inference/zoom/zoom_assistant.py status
```

To explicitly select a paired-node transport, add `--transport chrome-node` to
`join`; `--transport chrome` selects the local Chrome transport. Join executes
when invoked. It is not a dry run.

Zoom may report `manualAction` for sign-in, a passcode, verification, CAPTCHA,
browser permissions, or host admission. Complete that step in the same OpenClaw
Chrome profile and check status again. A normal guest account or a new Zoom
account does not override the host's access requirements.

Check `session.chrome.health.inCall` in the returned status. An allocated or
active session alone does not prove admission or usable audio. If a command
times out, the meeting join may still be running; inspect status before retrying
and explicitly leave any session you no longer want.

### 5. Speak or leave a session

Use the session identifier returned by OpenClaw:

```console
python inference/zoom/zoom_assistant.py status SESSION_ID
python inference/zoom/zoom_assistant.py speak SESSION_ID "This is a short audio test."
python inference/zoom/zoom_assistant.py leave SESSION_ID
```

These are live operations when invoked. Verify audible speech from a second
participant, interruption behavior, project delegation, and cleanup using the
[controlled meeting check](docs/VALIDATION.md#controlled-meeting-check).

Inspect the returned JSON as well as the process exit status. A `status` or
`leave` result containing `found: false` means the requested session was not
found; it is not confirmation that the browser participant left. For a leave
result, `browserLeft: true` is the strongest explicit departure indication.
Also confirm that Zoom no longer shows the participant and that audio cleanup
did not report an error.

## Command reference

| Command | Effect |
| --- | --- |
| `prepare --brief FILE --agent ID` | Writes a local patch; default output is `inference/zoom/.local/zoom.patch.json`, located beside the wrapper regardless of the working directory. |
| `validate --patch FILE` | Performs local validation without OpenClaw. |
| `apply --patch FILE --dry-run` | Runs upstream validation without writing configuration. |
| `apply --patch FILE` | Runs upstream validation, then applies the scoped patch. |
| `check` | Checks the installed version and upstream `bidi` setup. |
| `join URL` | Requests a live Zoom join. |
| `status [SESSION]` | Inspects session state. |
| `speak SESSION MESSAGE` | Requests speech in the selected meeting session. |
| `leave SESSION` | Requests browser departure and audio cleanup; inspect the returned result. |

Global options go **before** the command: `--openclaw PATH` chooses the OpenClaw
executable and `--timeout SECONDS` changes the default 120-second command timeout.
For example:

```console
python inference/zoom/zoom_assistant.py --openclaw /path/to/openclaw --timeout 180 check
```

## Tests and validation scope

From the `hikari/` subfolder:

```console
python -m unittest discover -s inference/zoom/tests -v
```

These are local wrapper tests. They do not start Chrome, join Zoom, send meeting
audio, or prove model access. Live validation remains a separate check on the
actual meeting host.

The upstream meeting plugins can persist caption-derived transcripts and notes
under the existing OpenClaw transcript settings. This wrapper leaves that
configuration intact. The Zoom plugin does not itself record meeting audio or
video; caption availability and notes are not guaranteed substitutes for a full
recording.

## Upstream and reuse

OpenClaw supplies the meeting runtime; this directory calls its installed CLI.
The vendor metadata records the pinned upstream version and license references.
It does not contain a vendored copy of the OpenClaw runtime.

- [Pinned Zoom plugin](https://github.com/openclaw/openclaw/tree/v2026.10.9/extensions/zoom-meetings)
- [Zoom behavior and manual actions](https://github.com/openclaw/openclaw/blob/v2026.10.9/docs/plugins/zoom-meetings.md)
- [Shared meeting audio and verification](https://github.com/openclaw/openclaw/blob/v2026.10.9/docs/plugins/meeting-plugins.md)
- [GPT-Live configuration and public API route](https://github.com/openclaw/openclaw/blob/v2026.10.9/docs/plugins/google-meet/config.md#gpt-live-with-cove)
- [Configuration patch semantics](https://github.com/openclaw/openclaw/blob/v2026.10.9/docs/cli/config.md)
