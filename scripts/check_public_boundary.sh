#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

violations=()
legacy_exceptions=()

legacy_allowed_paths=()

public_script_paths=(
  "scripts/build_assets.mjs"
  "scripts/check_public_boundary.sh"
)

contains_path() {
  local needle="$1"
  shift

  local item
  for item in "$@"; do
    if [[ "$item" == "$needle" ]]; then
      return 0
    fi
  done

  return 1
}

add_violation() {
  local path="$1"
  local reason="$2"

  violations+=("$path :: $reason")
}

while IFS= read -r path; do
  if [[ ! -e "$path" ]]; then
    continue
  fi

  if contains_path "$path" "${legacy_allowed_paths[@]}"; then
    legacy_exceptions+=("$path")
    continue
  fi

  case "$path" in
    .devin/*|.windsurf/*|AGENTS.md)
      add_violation "$path" "agent-local files do not belong in the public app repository"
      ;;
    raw_data/*|data/raw/*|data/interim/*|data/processed/*|db_dump/*|logs/*)
      add_violation "$path" "raw/interim data, dumps, and logs belong outside the public app repository"
      ;;
    docs/03_operations/sql/*)
      add_violation "$path" "one-off operations SQL belongs in the private ops/data repository"
      ;;
    scripts/*)
      if ! contains_path "$path" "${public_script_paths[@]}"; then
        add_violation "$path" "scripts/ is limited to public contributor tooling"
      fi
      ;;
  esac

  if [[ "$path" != */* && "$path" =~ \.(sql|xlsx?|xlsm|pdf|csv|json|geojson|gpkg|shp|zip|dump|backup|sqlite)$ ]]; then
    add_violation "$path" "root-level data or repair artifacts belong outside the public app repository"
  fi

  if [[ "$path" =~ ^sources/.*/management/commands/import_.*\.py$ ]]; then
    add_violation "$path" "source-specific ETL importers belong in the private data repository"
  fi
done < <(git ls-files --cached --others --exclude-standard)

if ((${#violations[@]})); then
  printf 'Public repository boundary check failed:\n\n' >&2
  printf '  - %s\n' "${violations[@]}" >&2
  printf '\nMove these files to BRIT-data/BRIT-ops or update the boundary rules if they are public app assets.\n' >&2
  exit 1
fi

if ((${#legacy_exceptions[@]})); then
  printf 'Public boundary check passed with %d legacy exception(s) pending extraction.\n' "${#legacy_exceptions[@]}"
else
  printf 'Public boundary check passed.\n'
fi
