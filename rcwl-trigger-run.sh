#!/usr/bin/env bash
# rcwl-trigger-run.sh
#
# Esegue manualmente la stessa azione di rcwl_trigger.py (ferma stop_service,
# lancia run_command in modo bloccante, riavvia stop_service), leggendo la
# configurazione da rcwl-trigger.ini, ma senza passare dalla rilevazione del
# sensore RCWL-0516: un lancio = un ciclo, subito.

set -euo pipefail

DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INI="$DIR/rcwl-trigger.ini"

if [[ ! -f "$INI" ]]; then
    echo "[ERRORE] impossibile leggere $INI" >&2
    exit 1
fi

leggi_ini() {
    # leggi_ini <sezione> <chiave>
    awk -F'=' -v sezione="[$1]" -v chiave="$2" '
        /^\[/ { in_sezione = ($0 == sezione); next }
        in_sezione && $1 ~ "^[[:space:]]*" chiave "[[:space:]]*$" {
            val = $0
            sub(/^[^=]*=/, "", val)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", val)
            print val
            exit
        }
    ' "$INI"
}

stop_service="$(leggi_ini azione stop_service)"
run_command="$(leggi_ini azione run_command)"

servizio_attivo() {
    systemctl --user is-active --quiet "$1"
}

systemctl_user() {
    local azione="$1" unit="$2"
    echo "[TRIGGER] systemctl --user $azione $unit"
    if ! systemctl --user "$azione" "$unit"; then
        echo "[WARN] systemctl --user $azione $unit fallito" >&2
    fi
}

era_attivo=0
if [[ -n "$stop_service" ]] && servizio_attivo "$stop_service"; then
    era_attivo=1
fi

if [[ -n "$stop_service" ]]; then
    systemctl_user stop "$stop_service"
fi

if [[ -n "$run_command" ]]; then
    echo "[TRIGGER] avvio '$run_command' (bloccante)"
    # eval per rispettare eventuali argomenti quotati nell'ini, come shlex.split
    eval "$run_command"
    echo "[TRIGGER] run_command terminato"
fi

if [[ -n "$stop_service" ]]; then
    systemctl_user start "$stop_service"
    if [[ "$era_attivo" -eq 1 ]]; then
        echo "[TRIGGER] $stop_service era attivo prima, riavviato"
    fi
fi
