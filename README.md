# rcwl-trigger

Interruttore fisico basato sul sensore a microonde RCWL-0516 (GPIO17 di default).

Quando rileva una "pressione" (debounce configurabile) ferma la unit `systemd --user` indicata in `rcwl-trigger.ini` (default `monitorpm.service`), esegue il comando indicato nello stesso file (default `/opt/scripts/nodstream/run.sh`) attendendo che termini, poi riavvia la unit fermata.

Il file ini viene riletto ad ogni trigger, quindi si può cambiare servizio/comando/debounce senza riavviare il processo (tranne il pin GPIO).

## Installazione

Gira come `systemd --user` (serve la sessione grafica):

```bash
mkdir -p ~/.config/systemd/user
cp rcwl-trigger.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now rcwl-trigger
```

Richiede un venv Python con `gpiozero` (default `/home/dlx/env`, vedi `ExecStart` nella unit).

## Licenza

CC BY-NC 4.0 — vedi `LICENSE`.
