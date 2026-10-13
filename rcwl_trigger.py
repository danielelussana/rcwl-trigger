#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
rcwl_trigger.py

Interruttore fisico basato sul sensore di movimento a microonde RCWL-0516
(uscita digitale su GPIO, numerazione BCM - pin configurato in
rcwl-trigger.ini, default GPIO17 / pin fisico 11).

Ad ogni "pressione" (presenza confermata da letture ravvicinate consecutive,
stesso schema di debounce di sensortest.py) esegue, nell'ordine, le due
azioni lette da rcwl-trigger.ini:

  1. ferma la unit systemd --user indicata da stop_service;
  2. lancia run_command e attende (bloccante) che termini;
  3. riavvia stop_service.

Il trigger si riarma solo quando il sensore torna inattivo (debounce
simmetrico a "conferme" letture) E sono trascorsi almeno --cooldown
secondi dalla fine del comando: se il sensore resta attivo (presenza
prolungata, falsi positivi da interferenze) il ciclo non riparte da solo.
"""

import configparser
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path

from gpiozero import DigitalInputDevice

INI_PATH = Path(__file__).with_name("rcwl-trigger.ini")

CW1602_SEND = "/home/dlx/Public/scripts/notifly/cw1602-send.sh"  # display LCD 16x2
LCD_COLS = 16
LCD_SPINNER_FRAMES = 4    # passi della barra di caricamento mostrata sulla seconda riga


def notifica_lcd_async(messaggio):
    """Mostra 'messaggio' sulla prima riga del CW1602 e una barra di
    caricamento sulla seconda, come notifica_lcd_async in monitorpm.py.
    Non bloccante: gira in un thread separato cosi' il loop del sensore
    non aspetta i tempi del display seriale."""

    def worker():
        larghezza_barra = LCD_COLS - 2
        etichetta = f"{messaggio:<{LCD_COLS}}"[:LCD_COLS]
        for i in range(LCD_SPINNER_FRAMES + 1):
            pieno = i * larghezza_barra // LCD_SPINNER_FRAMES
            if pieno >= larghezza_barra:
                corpo = "=" * larghezza_barra
            else:
                corpo = "=" * pieno + ">" + " " * (larghezza_barra - pieno - 1)
            barra = "[" + corpo + "]"
            testo = etichetta + f"{barra:<{LCD_COLS}}"[:LCD_COLS]
            try:
                subprocess.run([CW1602_SEND, testo], check=False,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                return  # display/script non disponibile: nessuna notifica, nessun crash

    threading.Thread(target=worker, daemon=True).start()


def servizio_attivo(unit):
    r = subprocess.run(["systemctl", "--user", "is-active", "--quiet", unit])
    return r.returncode == 0


def carica_config():
    parser = configparser.ConfigParser()
    letti = parser.read(INI_PATH)
    if not letti:
        print(f"[ERRORE] impossibile leggere {INI_PATH}", file=sys.stderr)
        sys.exit(1)
    return {
        "pin": parser.getint("gpio", "pin", fallback=17),
        "conferme": max(1, parser.getint("gpio", "conferme", fallback=3)),
        "intervallo": parser.getfloat("gpio", "intervallo", fallback=0.2),
        "cooldown": parser.getfloat("gpio", "cooldown", fallback=2.0),
        "stop_service": parser.get("azione", "stop_service", fallback="").strip(),
        "run_command": parser.get("azione", "run_command", fallback="").strip(),
        "timeout_massimo": parser.getfloat("azione", "timeout_massimo", fallback=1800.0),
    }


def systemctl_user(azione, unit):
    print(f"[TRIGGER] systemctl --user {azione} {unit}")
    r = subprocess.run(["systemctl", "--user", azione, unit])
    if r.returncode != 0:
        print(f"[WARN] systemctl --user {azione} {unit} uscito con codice {r.returncode}",
              file=sys.stderr)


def esegui_run_command(comando, timeout_massimo):
    """Avvia 'comando' e attende che termini, imponendo un tetto massimo
    alla durata: se lo supera invia prima SIGTERM (fade-out pulito, come
    da exit_on_key di nodstream) e solo se non basta SIGKILL. Senza
    questo limite un sensore bloccato "attivo" terrebbe il comando (es.
    nodstream, rendering OpenGL fullscreen) in esecuzione a tempo
    indefinito, con relativo consumo di CPU/GPU."""
    try:
        processo = subprocess.Popen(comando)
    except (FileNotFoundError, PermissionError) as e:
        print(f"[ERRORE] impossibile avviare run_command: {e}", file=sys.stderr)
        return

    try:
        processo.wait(timeout=timeout_massimo if timeout_massimo > 0 else None)
    except subprocess.TimeoutExpired:
        print(f"[WARN] run_command oltre il timeout di {timeout_massimo}s: invio SIGTERM",
              file=sys.stderr)
        processo.terminate()
        try:
            processo.wait(timeout=10)
        except subprocess.TimeoutExpired:
            print("[WARN] run_command non terminato dopo SIGTERM: invio SIGKILL",
                  file=sys.stderr)
            processo.kill()
            processo.wait()
    print("[TRIGGER] run_command terminato")


def esegui_azione(stop_service, run_command, timeout_massimo):
    nome_breve = stop_service.removesuffix(".service") if stop_service else ""
    era_attivo = bool(stop_service) and servizio_attivo(stop_service)

    if stop_service:
        if era_attivo:
            notifica_lcd_async(f"Ferma {nome_breve}")
        systemctl_user("stop", stop_service)

    if run_command:
        comando = shlex.split(run_command)
        print(f"[TRIGGER] avvio {comando!r} (bloccante, timeout={timeout_massimo}s)")
        esegui_run_command(comando, timeout_massimo)

    if stop_service:
        systemctl_user("start", stop_service)
        if era_attivo:
            notifica_lcd_async(f"Riavvia {nome_breve}")


def main():
    cfg = carica_config()
    sensore = DigitalInputDevice(cfg["pin"], pull_up=False)

    contatore = 0
    contatore_rilascio = 0
    armato = True
    azione_terminata_a = 0.0
    ultimo_attivo = None

    print(f"rcwl-trigger avviato su GPIO{cfg['pin']} "
          f"(conferme={cfg['conferme']}, cooldown={cfg['cooldown']}s)")

    try:
        while True:
            cfg = carica_config()

            attivo = sensore.is_active
            if attivo != ultimo_attivo:
                print(f"[SENSORE] raw={int(sensore.value)} active={attivo} "
                      f"contatore={contatore} armato={armato}")
                ultimo_attivo = attivo

            if attivo:
                contatore = min(contatore + 1, cfg["conferme"])
                contatore_rilascio = 0
            else:
                contatore = max(contatore - 1, 0)
                contatore_rilascio = min(contatore_rilascio + 1, cfg["conferme"])

            # Riarmo solo a sensore confermato inattivo (stesso debounce del
            # trigger, sul rilascio) e trascorso almeno cooldown dalla fine
            # dell'azione: un sensore rimasto attivo non puo' riarmarsi da solo.
            if (not armato and contatore_rilascio >= cfg["conferme"]
                    and (time.time() - azione_terminata_a) >= cfg["cooldown"]):
                armato = True

            confermato = contatore >= cfg["conferme"]

            if confermato and armato:
                armato = False
                esegui_azione(cfg["stop_service"], cfg["run_command"], cfg["timeout_massimo"])
                azione_terminata_a = time.time()
                contatore = 0
                contatore_rilascio = 0

            time.sleep(cfg["intervallo"])
    except KeyboardInterrupt:
        pass
    finally:
        sensore.close()
        print("rcwl-trigger terminato.")


if __name__ == "__main__":
    main()
