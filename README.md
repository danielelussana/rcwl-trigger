# rcwl-trigger

*[English](#english) | [Italiano](#italiano)*

---

## English

A physical switch based on the RCWL-0516 microwave sensor (GPIO17 by default).

When it detects a "press" (configurable debounce) it stops the `systemd --user` unit named in `rcwl-trigger.ini` (default `monitorpm.service`), runs the command given in the same file (default `/opt/scripts/nodstream/run.sh`) and waits for it to finish, then restarts the unit it stopped.

The ini file is re-read at every trigger, so the service/command/debounce can be changed without restarting the process (except the GPIO pin).

### Installation

It runs as `systemd --user` (a graphical session is required):

```bash
mkdir -p ~/.config/systemd/user
cp rcwl-trigger.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now rcwl-trigger
```

Requires a Python venv with `gpiozero` (default `/home/dlx/env`, see `ExecStart` in the unit).

### License

CC BY-NC 4.0, see `LICENSE`.

---

## Italiano

Interruttore fisico basato sul sensore a microonde RCWL-0516 (GPIO17 di default).

Quando rileva una "pressione" (debounce configurabile) ferma la unit `systemd --user` indicata in `rcwl-trigger.ini` (default `monitorpm.service`), esegue il comando indicato nello stesso file (default `/opt/scripts/nodstream/run.sh`) attendendo che termini, poi riavvia la unit fermata.

Il file ini viene riletto ad ogni trigger, quindi si può cambiare servizio/comando/debounce senza riavviare il processo (tranne il pin GPIO).

### Installazione

Gira come `systemd --user` (serve la sessione grafica):

```bash
mkdir -p ~/.config/systemd/user
cp rcwl-trigger.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now rcwl-trigger
```

Richiede un venv Python con `gpiozero` (default `/home/dlx/env`, vedi `ExecStart` nella unit).

### Licenza

CC BY-NC 4.0 — vedi `LICENSE`.
