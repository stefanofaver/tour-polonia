"""Ricognizione in SOLA LETTURA del portale RDV.

Obiettivo: prima di scrivere qualunque cosa, raccogliere il materiale che mi
serve per capire il programma e configurarlo sul tuo ambiente reale:
  - elenco delle causali di registrazione;
  - piano dei conti;
  - pagine della guida sul flusso di prima nota.

Per ogni pagina visitata salva tre file nella cartella di output:
  - <nome>.html  (sorgente, per analisi)
  - <nome>.txt   (testo visibile, leggibile)
  - <nome>.png   (screenshot a pagina intera)

Due modalita':
  - automatica: visita gli URL elencati in config (`pagine`);
  - manuale (--manuale): navighi tu nel browser e catturi le pagine che vuoi,
    utile quando non conosciamo ancora gli URL esatti dei menu.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Optional

from .sessione import SessionePortale


def slug(nome: str) -> str:
    """Trasforma un nome libero in un nome file sicuro."""
    s = nome.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "pagina"


def salva_pagina(page, nome: str, cartella: str | Path) -> Path:
    """Salva HTML, testo e screenshot della pagina corrente."""
    out = Path(cartella)
    out.mkdir(parents=True, exist_ok=True)
    base = slug(nome)

    (out / f"{base}.html").write_text(page.content(), encoding="utf-8")

    try:
        testo = page.inner_text("body")
    except Exception:
        testo = ""
    (out / f"{base}.txt").write_text(testo, encoding="utf-8")

    try:
        page.screenshot(path=str(out / f"{base}.png"), full_page=True)
    except Exception:
        pass  # lo screenshot e' un di piu', non bloccare la raccolta

    return out / f"{base}.txt"


def carica_config(percorso: str | Path) -> dict:
    return json.loads(Path(percorso).read_text(encoding="utf-8"))


def esegui_ricognizione(
    config: dict,
    manuale: bool = False,
    prompt: Callable[[str], str] = input,
) -> list[Path]:
    """Esegue la ricognizione. Ritorna i percorsi dei file di testo salvati."""
    base_url = config["base_url"]
    stato = config.get("stato_sessione", "auth_state.json")
    out_dir = config.get("output_ricognizione", "ricognizione_output")
    salvati: list[Path] = []

    with SessionePortale(base_url, stato_path=stato, headless=False) as sess:
        if not sess.autenticata:
            sess.login_manuale(conferma=prompt)

        page = sess.nuova_pagina()

        if manuale:
            print("\nMODALITA' MANUALE: naviga nel browser dove vuoi.")
            while True:
                nome = prompt(
                    "\nNome per la pagina corrente (INVIO vuoto per terminare): "
                ).strip()
                if not nome:
                    break
                f = salva_pagina(page, nome, out_dir)
                salvati.append(f)
                print(f"  Salvata: {f}")
        else:
            pagine = [p for p in config.get("pagine", []) if not str(p.get("nome", "")).startswith("_")]
            if not pagine:
                print("Nessuna pagina elencata in config['pagine']. Usa --manuale.")
            for voce in pagine:
                nome = voce["nome"]
                url = voce["url"]
                print(f"  Visito '{nome}' -> {url}")
                try:
                    page.goto(url, wait_until="networkidle")
                    f = salva_pagina(page, nome, out_dir)
                    salvati.append(f)
                    print(f"    Salvata: {f}")
                except Exception as exc:
                    print(f"    ! Errore su '{nome}': {exc}")

        page.close()

    print(f"\nRicognizione completata: {len(salvati)} pagine in '{out_dir}'.")
    return salvati
