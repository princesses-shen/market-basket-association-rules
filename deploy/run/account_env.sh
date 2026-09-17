#!/bin/bash
# Source from a startup script. This file never evaluates configuration as shell code.
account_load_env() {
    local config_path="${ACCOUNT_SECURITY_ENV:-$HOME/day08/config/account-security.env}"
    local name value line jwt_value
    umask 077
    mkdir -p "$(dirname "$config_path")" || return 1
    touch "$config_path" || return 1
    chmod 600 "$config_path" || return 1
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%$'\r'}"
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        [[ "$line" == *=* ]] || { echo 'Invalid account configuration entry.' >&2; return 1; }
        name="${line%%=*}"; value="${line#*=}"
        case "$name" in
            ZK_QUORUM|JWT_SECRET|ADMIN_INITIAL_PASSWORD|SMTP_HOST|SMTP_PORT|SMTP_USERNAME|SMTP_PASSWORD|SMTP_FROM|SMTP_STARTTLS|SMTP_SSL) ;;
            *) echo 'Invalid account configuration key.' >&2; return 1 ;;
        esac
        if [[ -z "${!name}" ]]; then printf -v "$name" '%s' "$value"; export "$name"; fi
    done < "$config_path"
    if [[ -z "${JWT_SECRET:-}" ]]; then
        jwt_value=$(openssl rand -hex 48) || return 1
        # Remove only an empty JWT entry; never replace a configured secret.
        sed -i '/^JWT_SECRET=\r\?$/d' "$config_path" || return 1
        printf '\nJWT_SECRET=%s\n' "$jwt_value" >> "$config_path" || return 1
        export JWT_SECRET="$jwt_value"
    fi
    [[ ${#JWT_SECRET} -ge 32 ]] || { echo 'JWT_SECRET must contain at least 32 bytes.' >&2; return 1; }
}
account_load_env
