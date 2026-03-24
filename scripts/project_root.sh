#!/usr/bin/env bash

tcptransgui_looks_like_project_root() {
    local dir="$1"
    [[ -d "$dir" ]] || return 1
    [[ -d "$dir/Client" ]] || return 1
    [[ -d "$dir/Server" ]] || return 1
    [[ -d "$dir/common" ]] || return 1
    [[ -d "$dir/packaging" ]] || return 1
    [[ -d "$dir/scripts" ]] || return 1
    [[ -f "$dir/requirements.txt" ]] || return 1
    return 0
}

tcptransgui_resolve_project_root() {
    local source_file="$1"
    local candidate=""
    local script_root=""

    if [[ -n "${TCPTRANSGUI_PROJECT_ROOT:-}" ]]; then
        candidate="${TCPTRANSGUI_PROJECT_ROOT}"
        if tcptransgui_looks_like_project_root "$candidate"; then
            printf '%s\n' "$candidate"
            return 0
        fi
    fi

    if [[ -n "${PWD:-}" ]]; then
        candidate="${PWD}"
        if tcptransgui_looks_like_project_root "$candidate"; then
            printf '%s\n' "$candidate"
            return 0
        fi
    fi

    if candidate="$(pwd 2>/dev/null)"; then
        if tcptransgui_looks_like_project_root "$candidate"; then
            printf '%s\n' "$candidate"
            return 0
        fi
    fi

    script_root="$(cd "$(dirname "$source_file")/.." && pwd -P)"
    printf '%s\n' "$script_root"
}
