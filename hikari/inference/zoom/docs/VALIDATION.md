# Validation

## What has and has not been verified

This integration is based on the OpenClaw source and documentation at
`v2026.10.9`. Source inspection confirms that the official Zoom plugin exposes
browser participation and that its shared `bidi` path supports GPT-Live with
delegation to a configured OpenClaw agent.

Source inspection and local wrapper tests do not establish that a particular
machine can join a Zoom meeting, use its audio devices, authenticate to OpenAI,
or produce speech audible to other participants. No live meeting, model call,
or native audio round trip was exercised while preparing this package.

The delivered wrapper passed **21 offline unit tests on Python 3.12**. The tests
mock OpenClaw calls and cover scoped configuration, model selection, brief
handling, CLI arguments, apply preflight, failed results, and timeout recovery.

| Layer | Evidence needed |
| --- | --- |
| Wrapper | Offline tests pass; generated configuration matches the selected route and existing agent. |
| OpenClaw installation | Pinned host and Zoom plugin are installed; the Gateway runs successfully. |
| Model access | The Gateway can authenticate to the selected public API or Codex voice route. |
| Browser and native audio | The upstream setup check succeeds for the actual Chrome host. |
| Meeting admission | Status shows an in-call session after any required host or account action. |
| Local speech injection | Status reports verified speech output, not merely an increasing byte counter. |
| Remote audibility | A second participant hears the assistant's speech in the actual meeting. |
| Conversation and delegation | The assistant hears questions, yields when interrupted, and consults the intended project agent. |

## Controlled meeting check

Use a short test meeting and a second participant or device with headphones.
Run the setup and status commands in the README before starting this check.

1. **Admission and identity.** Join under the configured AI display name. Confirm
   that the intended participant is in the meeting and that its camera is off.
   Resolve any reported `manualAction` in the same OpenClaw browser profile.
2. **Incoming audio.** Ask a simple question from the second participant. Confirm
   that the answer addresses what was actually said.
3. **Outgoing audio.** Confirm that the second participant can hear the reply.
   A successful output process or locally verified microphone injection alone
   does not prove that Zoom transmitted the audio to another person.
4. **Interruption and echo.** Interrupt a longer reply. Confirm that the assistant
   yields and follows the new request, and that it does not respond repeatedly
   to its own speech. Keep the managed isolated browser input enabled for Live.
5. **Speaking policy.** Let humans exchange several ordinary turns without
   addressing the assistant, then ask it a question by name. Check for unwanted
   backchannels or interruptions. Prompt instructions express the desired
   behavior; they are not a guaranteed microphone gate.
6. **Project context.** Ask one question answered in the meeting brief and one
   requiring an accessible project file. Check the latter against the source
   and confirm that delegation used the intended existing agent. A plausible
   spoken answer alone is not evidence of successful retrieval.
7. **Missing evidence.** Ask for a result absent from both the brief and accessible
   project files. Confirm that it reports the gap instead of inventing a result.
8. **Cleanup.** Leave the meeting. Confirm that Zoom removes the participant and
   OpenClaw stops the session and audio bridge. Inspect `browserLeft: true` as
   the strongest explicit departure field in the leave result. A `found: false`
   result from status or leave is a session lookup miss, not proof of departure.
   If cleanup is reported as failed, inspect status and retry leaving that
   session before starting a replacement.

Record the host OS, Chrome host, OpenClaw and plugin versions, model/voice route,
configured agent, and results. Keep meeting passcodes and credentials out of
the record.

## Platform boundaries

- The pinned upstream documentation describes macOS with BlackHole/SoX and a
  Linux desktop with PipeWire-Pulse. The audio processes must run as the desktop
  user who owns the Chrome/audio session.
- A paired node may run Chrome and native audio while the Gateway retains model
  credentials and the existing project agent.
- Windows-native audio for this OpenClaw path has not been verified. A working
  Windows Python wrapper does not establish Windows meeting-audio support.
  Offline preparation and validation can run on Windows; operations invoking
  OpenClaw reject native `.cmd`/`.bat` shims. A WSL CLI still needs a working
  supported Chrome/audio host.
- Zoom host settings can disable browser participation or require an account,
  verification, a passcode, CAPTCHA completion, or host admission. These are
  reported as manual actions; the integration does not bypass them.
- Captions and durable notes depend on upstream transcript configuration and
  Zoom availability. Do not treat them as a guaranteed full meeting record.

## Upstream references

- [Meeting modes, audio setup, verification, and transcript behavior](https://github.com/openclaw/openclaw/blob/v2026.10.9/docs/plugins/meeting-plugins.md)
- [Zoom browser participation and manual actions](https://github.com/openclaw/openclaw/blob/v2026.10.9/docs/plugins/zoom-meetings.md)
- [Shared GPT-Live configuration and public API route](https://github.com/openclaw/openclaw/blob/v2026.10.9/docs/plugins/google-meet/config.md)
- [Pinned Zoom plugin package metadata](https://github.com/openclaw/openclaw/blob/v2026.10.9/extensions/zoom-meetings/package.json)
