#!/usr/bin/env bash
# Resolve all Compose files independently of the caller's working directory.
set -euo pipefail
checkout_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
mode=base
if [[ "${1:-}" == --mode ]]; then
  [[ $# -ge 2 ]] || { echo 'Missing simulator mode.' >&2; exit 2; }
  mode="$2"
  shift 2
fi
compose_args=(--project-directory "$checkout_dir" -f "$checkout_dir/compose.simulator.yml")
case "$mode" in
  base) ;;
  speech|audio|full)
    if [[ -z "${LUXOPI_AI_CHECKOUT:-}" ]]; then
      ai_candidate="$(dirname "$checkout_dir")/luxopi-ai"
      if [[ ! -d "$ai_candidate" ]]; then
        common_git_dir="$(git -C "$checkout_dir" rev-parse --path-format=absolute --git-common-dir)"
        ai_candidate="$(dirname "$(dirname "$common_git_dir")")/luxopi-ai"
      fi
      [[ -d "$ai_candidate" ]] || { echo 'Set LUXOPI_AI_CHECKOUT to the luxopi-ai checkout.' >&2; exit 2; }
      export LUXOPI_AI_CHECKOUT="$ai_candidate"
    fi
    compose_args+=(-f "$checkout_dir/compose.speech-simulator.yml")
    if [[ "$mode" != speech ]]; then compose_args+=(-f "$checkout_dir/compose.audio-simulator.yml"); fi
    if [[ "$mode" == full ]]; then compose_args+=(-f "$checkout_dir/compose.full-simulator.yml"); fi
    ;;
  physics) compose_args+=(-f "$checkout_dir/compose.physics-simulator.yml") ;;
  *) echo "Unknown simulator mode: $mode (base, speech, audio, physics, full)." >&2; exit 2 ;;
esac
exec docker compose "${compose_args[@]}" "$@"
