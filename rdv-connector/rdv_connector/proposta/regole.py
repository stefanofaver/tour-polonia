"""Caricamento e modello delle regole di mappatura contabile.

Le regole sono in JSON (libreria standard, nessuna dipendenza) e descrivono:
  - l'azienda (per capire se un documento e' acquisto o vendita);
  - il piano dei conti minimo usato dalle scritture;
  - le causali predefinite;
  - regole per singolo fornitore/cliente (conto di costo/ricavo ricorrente).

Vedi config/regole.example.json per un modello commentato.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Conto:
    codice: str
    descrizione: str

    @classmethod
    def da_dict(cls, d: dict) -> "Conto":
        return cls(codice=str(d.get("codice", "")), descrizione=str(d.get("descrizione", "")))


@dataclass
class RegolaControparte:
    """Regola specifica per un fornitore o cliente (chiave = PIVA/CF)."""

    conto: Optional[Conto] = None
    causale: Optional[str] = None


def normalizza_identificativo(valore: Optional[str]) -> str:
    """Normalizza P.IVA/CF per il confronto.

    Rimuove un eventuale prefisso paese (es. "IT01234567890" -> "01234567890")
    solo quando il resto e' tutto numerico, per non corrompere i codici fiscali
    alfanumerici.
    """
    if not valore:
        return ""
    v = valore.strip().upper()
    if len(v) > 2 and v[:2].isalpha() and v[2:].isdigit():
        v = v[2:]
    return v


@dataclass
class Regole:
    azienda_denominazione: str
    azienda_partita_iva: str
    conti: dict[str, Conto]
    causali: dict[str, str]
    controparti: dict[str, RegolaControparte] = field(default_factory=dict)

    def conto(self, chiave: str) -> Conto:
        if chiave not in self.conti:
            raise KeyError(
                f"Conto '{chiave}' mancante nelle regole. "
                f"Disponibili: {sorted(self.conti)}"
            )
        return self.conti[chiave]

    def regola_controparte(self, identificativo: Optional[str]) -> Optional[RegolaControparte]:
        chiave = normalizza_identificativo(identificativo)
        if not chiave:
            return None
        return self.controparti.get(chiave)


def carica_regole(percorso: str | Path) -> Regole:
    dati = json.loads(Path(percorso).read_text(encoding="utf-8"))

    azienda = dati.get("azienda", {})
    # Le chiavi che iniziano con "_" sono commenti nel JSON e vanno ignorate.
    conti = {
        k: Conto.da_dict(v)
        for k, v in dati.get("conti", {}).items()
        if not k.startswith("_")
    }

    controparti: dict[str, RegolaControparte] = {}
    for chiave, val in dati.get("controparti", {}).items():
        if chiave.startswith("_"):
            continue
        conto = Conto.da_dict(val["conto"]) if val.get("conto") else None
        controparti[normalizza_identificativo(str(chiave))] = RegolaControparte(
            conto=conto, causale=val.get("causale")
        )

    return Regole(
        azienda_denominazione=azienda.get("denominazione", ""),
        azienda_partita_iva=str(azienda.get("partita_iva", "")),
        conti=conti,
        causali=dati.get("causali", {}),
        controparti=controparti,
    )
