"""Lettore di fatture elettroniche in formato FatturaPA (XML).

Usa solo la libreria standard. Per essere robusto verso le varianti di
namespace presenti nei file reali, la ricerca degli elementi avviene per
*nome locale* (ignorando il prefisso/namespace).

Limitazioni note (gestite con avvisi, non con eccezioni):
  - i file firmati `.xml.p7m` (CAdES) vanno prima estratti in XML semplice;
    questo modulo legge XML gia' in chiaro.
  - una fattura puo' contenere piu' <FatturaElettronicaBody>: vengono letti
    tutti e restituiti come documenti separati.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ..models import Controparte, Documento, RigaIVA


def _local(tag: str) -> str:
    """Restituisce il nome locale di un tag, senza namespace."""
    return tag.rsplit("}", 1)[-1]


def _find(elem: ET.Element | None, *names: str) -> ET.Element | None:
    """Naviga per nomi locali successivi (primo figlio che corrisponde)."""
    cur = elem
    for name in names:
        if cur is None:
            return None
        cur = next((c for c in cur if _local(c.tag) == name), None)
    return cur


def _find_all(elem: ET.Element | None, name: str) -> list[ET.Element]:
    if elem is None:
        return []
    return [c for c in elem if _local(c.tag) == name]


def _text(elem: ET.Element | None, *names: str) -> str:
    found = _find(elem, *names)
    return (found.text or "").strip() if found is not None and found.text else ""


def _dec(value: str) -> Decimal:
    if not value:
        return Decimal("0")
    try:
        return Decimal(value.replace(",", "."))
    except InvalidOperation:
        return Decimal("0")


def _leggi_controparte(blocco: ET.Element | None) -> Controparte:
    dati = _find(blocco, "DatiAnagrafici")
    cp = Controparte()
    id_iva = _find(dati, "IdFiscaleIVA")
    if id_iva is not None:
        paese = _text(id_iva, "IdPaese")
        codice = _text(id_iva, "IdCodice")
        cp.partita_iva = f"{paese}{codice}" if paese else codice
    cf = _text(dati, "CodiceFiscale")
    if cf:
        cp.codice_fiscale = cf
    # Denominazione (persona giuridica) oppure Nome + Cognome (persona fisica)
    denom = _text(dati, "Anagrafica", "Denominazione")
    if denom:
        cp.denominazione = denom
    else:
        nome = _text(dati, "Anagrafica", "Nome")
        cognome = _text(dati, "Anagrafica", "Cognome")
        cp.denominazione = " ".join(p for p in (nome, cognome) if p)
    return cp


def _leggi_righe_iva(dati_beni: ET.Element | None) -> list[RigaIVA]:
    righe: list[RigaIVA] = []
    for riepilogo in _find_all(dati_beni, "DatiRiepilogo"):
        righe.append(
            RigaIVA(
                aliquota=_dec(_text(riepilogo, "AliquotaIVA")),
                imponibile=_dec(_text(riepilogo, "ImponibileImporto")),
                imposta=_dec(_text(riepilogo, "Imposta")),
                natura=_text(riepilogo, "Natura") or None,
            )
        )
    return righe


def leggi_fattura(percorso: str | Path) -> list[Documento]:
    """Legge un file FatturaPA e restituisce un Documento per ogni body."""
    percorso = Path(percorso)
    radice = ET.parse(percorso).getroot()

    header = _find(radice, "FatturaElettronicaHeader")
    cedente = _leggi_controparte(_find(header, "CedentePrestatore"))
    cessionario = _leggi_controparte(_find(header, "CessionarioCommittente"))

    documenti: list[Documento] = []
    for body in _find_all(radice, "FatturaElettronicaBody"):
        generali = _find(body, "DatiGenerali", "DatiGeneraliDocumento")
        dati_beni = _find(body, "DatiBeniServizi")

        descrizioni = [
            _text(linea, "Descrizione")
            for linea in _find_all(dati_beni, "DettaglioLinee")
        ]
        descrizioni = [d for d in descrizioni if d]

        totale_txt = _text(generali, "ImportoTotaleDocumento")
        doc = Documento(
            fonte=str(percorso),
            formato="xml",
            tipo_documento=_text(generali, "TipoDocumento"),
            numero=_text(generali, "Numero"),
            data=_text(generali, "Data"),
            divisa=_text(generali, "Divisa") or "EUR",
            cedente=cedente,
            cessionario=cessionario,
            righe_iva=_leggi_righe_iva(dati_beni),
            totale_documento=_dec(totale_txt) if totale_txt else None,
            descrizione_sintetica="; ".join(descrizioni[:3]),
        )

        # Controllo di coerenza: il totale dichiarato deve combaciare con
        # imponibile + imposta calcolati dal riepilogo IVA.
        if doc.totale_documento is not None:
            scarto = abs(doc.totale_documento - doc.totale_calcolato)
            if scarto > Decimal("0.01"):
                doc.avvisi.append(
                    f"Totale documento {doc.totale_documento} diverso dal "
                    f"calcolato {doc.totale_calcolato} (scarto {scarto})."
                )
        if not doc.righe_iva:
            doc.avvisi.append("Nessun dato di riepilogo IVA trovato.")

        documenti.append(doc)

    return documenti
