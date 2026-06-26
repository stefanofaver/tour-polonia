"""Lettore di documenti PDF.

A differenza della fattura XML (struttura nota e precisa), un PDF non ha uno
schema garantito: estraiamo il testo grezzo e tentiamo di individuare i campi
principali con euristiche. Per i casi dubbi vengono lasciati avvisi: in questo
progetto il PDF e' pensato come supporto, mentre la fonte affidabile resta la
fattura elettronica XML quando disponibile.

Dipendenza opzionale: `pypdf` (vedi requirements.txt). Se non installata, la
lettura restituisce un Documento con avviso, senza far cadere il programma.
"""
from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from ..models import Documento, RigaIVA

try:  # dipendenza opzionale
    from pypdf import PdfReader  # type: ignore

    _PYPDF_OK = True
except BaseException:  # noqa: BLE001  (anche panic di estensioni native rotte)
    # Usiamo BaseException perche' un backend nativo malfunzionante puo'
    # sollevare eccezioni che non derivano da Exception: l'assenza/rottura di
    # una dipendenza opzionale non deve mai bloccare l'intero strumento.
    _PYPDF_OK = False


_RE_NUMERO = re.compile(r"(?:fattura|nr\.?|n\.?)\s*[:#]?\s*([A-Za-z0-9/\-]+)", re.I)
_RE_DATA = re.compile(r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})")
_RE_PIVA = re.compile(r"(?:p\.?\s*iva|partita iva)\D{0,10}(\d{11})", re.I)
_RE_TOTALE = re.compile(r"(?:totale(?:\s+documento)?)\D{0,15}([\d.,]+)", re.I)


def _estrai_testo(percorso: Path) -> str:
    reader = PdfReader(str(percorso))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def _importo(testo: str) -> Decimal | None:
    # Converte un importo in formato italiano (1.234,56) in Decimal.
    t = testo.strip().replace(".", "").replace(",", ".")
    try:
        return Decimal(t)
    except Exception:
        return None


def leggi_pdf(percorso: str | Path) -> list[Documento]:
    """Estrae i campi principali da un PDF. Best-effort, sempre con avvisi."""
    percorso = Path(percorso)
    doc = Documento(fonte=str(percorso), formato="pdf")

    if not _PYPDF_OK:
        doc.avvisi.append(
            "Libreria 'pypdf' non installata: impossibile leggere il PDF. "
            "Esegui: pip install -r requirements.txt"
        )
        return [doc]

    try:
        testo = _estrai_testo(percorso)
    except Exception as exc:  # pragma: no cover
        doc.avvisi.append(f"Errore nella lettura del PDF: {exc}")
        return [doc]

    if not testo.strip():
        doc.avvisi.append(
            "PDF senza testo estraibile (probabile scansione): servira' OCR."
        )
        return [doc]

    if m := _RE_NUMERO.search(testo):
        doc.numero = m.group(1)
    if m := _RE_DATA.search(testo):
        doc.data = m.group(1)
    if m := _RE_TOTALE.search(testo):
        doc.totale_documento = _importo(m.group(1))

    pive = _RE_PIVA.findall(testo)
    if pive:
        doc.cedente.partita_iva = pive[0]

    doc.descrizione_sintetica = "Documento PDF (lettura euristica)"
    doc.avvisi.append(
        "Dati estratti dal PDF in modo euristico: verificare prima di approvare."
    )
    return [doc]
