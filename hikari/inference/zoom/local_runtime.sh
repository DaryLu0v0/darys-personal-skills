#!/usr/bin/env bash
# Windows launcher bridge; all meeting operations run as the WSL desktop user.
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
export PULSE_SERVER="unix:$XDG_RUNTIME_DIR/hikari-pulse/native"
export DISPLAY="${DISPLAY:-:0}"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

action="${1:-check}"
shift || true
case "$action" in
  check|status|join|speak|leave|project-prepare|project-select|join-project) ;;
  *) printf 'Unknown Hikari action.\n' >&2; exit 2 ;;
esac

systemctl --user start pipewire.socket pipewire-pulse.socket wireplumber.service
systemctl --user set-environment "DISPLAY=$DISPLAY" "PULSE_SERVER=$PULSE_SERVER"
if [ -n "${OPENAI_API_KEY:-}" ]; then
  systemctl --user import-environment OPENAI_API_KEY
fi
if ! systemctl --user is-active --quiet hikari-gateway.service; then
  # Keep WSL's desktop session alive after the short Windows command exits.
  # WSL 2.6 can otherwise idle-stop even with a lingering systemd user service.
  dbus-launch true
fi
systemctl --user start hikari-gateway.service
ready=0
for attempt in {1..45}; do
  if curl --silent --fail http://127.0.0.1:18989/healthz >/dev/null; then
    ready=1
    break
  fi
  if systemctl --user is-failed --quiet hikari-gateway.service; then
    printf 'Hikari could not start. Inspect: journalctl --user -u hikari-gateway.service\n' >&2
    exit 1
  fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  printf 'Hikari is still starting. Use Check again before joining.\n' >&2
  exit 1
fi
if [ "$action" = check ]; then
  exec python3 "$script_dir/zoom_assistant.py" --timeout 180 "$action" "$@"
fi
if [ "$action" = project-prepare ]; then
  exec python3 "$script_dir/project_agent.py" prepare "$@"
fi
if [ "$action" = project-select ]; then
  exec python3 "$script_dir/project_agent.py" select "$@"
fi
if [ "$action" = join-project ]; then
  if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    printf 'Join a project with a project folder and Zoom link.\n' >&2
    exit 2
  fi
  project="$1"
  meeting_url="$2"
  shift 2
  python3 "$script_dir/project_agent.py" select "$project" --meeting "$meeting_url" "$@"
  action=join
  set -- "$meeting_url"
fi
systemctl --user start hikari-session.service
for attempt in {1..30}; do
  if [ -S "$XDG_RUNTIME_DIR/hikari/meeting.sock" ]; then break; fi
  sleep 1
done
exec node "$script_dir/local_session.mjs" "$action" "$@"
