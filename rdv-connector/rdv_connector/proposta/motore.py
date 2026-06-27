"""Trasforma un Documento letto in una RegistrazioneProposta di prima nota.

Schema delle scritture generate (IVA ordinaria):

  ACQUISTO (fattura da fornitore)
      DARE   conto di costo            imponibile
      DARE   IVA a credito             imposta
      AVERE  debiti v/fornitori        totale

  VENDITA (fattura a cliente)
      DARE   crediti v/clienti         totale
      AVERE  conto di ricavo           imponibile
      AVERE  IVA a debito              imposta

Le righe senza IVA (Natura N1..N7) generano solo imponibile, senza riga IVA.
Il verso (acquisto/vendita) si deduce confrontando la P.IVA dell'azienda
configurata con cedente/cessionario del documento.
"""
from __future__ import annotations

from decimal import Decimal

from ..models import (
    Documento,
    RegistrazioneProposta,
    RigaContabile,
    TipoMovimento,
)
from .regole import Conto, Regole


def _norm_piva(valore: str | None) -> str:
    """Normalizza una P.IVA per il confronto (rimuove un eventuale IT iniziale)."""
    if not valore:
        return ""
    v = valore.strip().upper()
    if len(v) > 2 and v[:2].isalpha():
        v = v[2:]
    return v


def _determina_tipo(doc: Documento, regole: Regole) -> TipoMovimento:
    azienda = _norm_piva(regole.azienda_partita_iva)
    if not azienda:
        return TipoMovimento.SCONOSCIUTO
    if _norm_piva(doc.cessionario.partita_iva) == azienda:
        return TipoMovimento.ACQUISTO  # l'azienda e' la committente -> acquisto
    if _norm_piva(doc.cedente.partita_iva) == azienda:
        return TipoMovimento.VENDITA   # l'azienda e' la cedente -> vendita
    return TipoMovimento.SCONOSCIUTO


def _conto_controparte(doc: Documento, regole: Regole, default_key: str) -> tuple[Conto, list[str]]:
    """Conto di costo/ricavo: specifico della controparte se configurato."""
    avvisi: list[str] = []
    controparte = doc.cedente if _determina_tipo(doc, regole) == TipoMovimento.ACQUISTO else doc.cessionario
    regola = regole.regola_controparte(controparte.identificativo)
    if regola and regola.conto:
        return regola.conto, avvisi
    avvisi.append(
        f"Nessuna regola per '{controparte.denominazione}' "
        f"({controparte.identificativo or 'senza P.IVA'}): uso conto predefinito."
    )
    return regole.conto(default_key), avvisi


def proponi_registrazione(doc: Documento, regole: Regole) -> RegistrazioneProposta:
    tipo = _determina_tipo(doc, regole)
    reg = RegistrazioneProposta(
        documento=doc,
        tipo=tipo,
        data_registrazione=doc.data,
        descrizione=_descrizione(doc, tipo),
    )
    reg.avvisi.extend(doc.avvisi)

    if tipo == TipoMovimento.SCONOSCIUTO:
        reg.avvisi.append(
            "Impossibile capire se acquisto o vendita: P.IVA azienda non "
            "corrisponde ne' al cedente ne' al cessionario. Registrazione non generata."
        )
        return reg

    imponibile = doc.imponibile_totale
    imposta = doc.imposta_totale
    totale = doc.totale_documento if doc.totale_documento is not None else doc.totale_calcolato

    conto_cr, avvisi = _conto_controparte(doc, regole, "costo_default" if tipo == TipoMovimento.ACQUISTO else "ricavo_default")
    reg.avvisi.extend(avvisi)

    if tipo == TipoMovimento.ACQUISTO:
        reg.causale = _causale(doc, regole, "acquisto")
        reg.righe.append(RigaContabile(conto_cr.codice, conto_cr.descrizione, dare=imponibile))
        if imposta > 0:
            iva = regole.conto("iva_credito")
            reg.righe.append(RigaContabile(iva.codice, iva.descrizione, dare=imposta))
        fornitori = regole.conto("debiti_fornitori")
        reg.righe.append(RigaContabile(fornitori.codice, fornitori.descrizione, avere=totale))
    else:  # VENDITA
        reg.causale = _causale(doc, regole, "vendita")
        clienti = regole.conto("crediti_clienti")
        reg.righe.append(RigaContabile(clienti.codice, clienti.descrizione, dare=totale))
        reg.righe.append(RigaContabile(conto_cr.codice, conto_cr.descrizione, avere=imponibile))
        if imposta > 0:
            iva = regole.conto("iva_debito")
            reg.righe.append(RigaContabile(iva.codice, iva.descrizione, avere=imposta))

    if not reg.quadra:
        reg.avvisi.append(
            f"ATTENZIONE: partita doppia non quadra "
            f"(dare {reg.totale_dare} != avere {reg.totale_avere})."
        )
    return reg


def _descrizione(doc: Documento, tipo: TipoMovimento) -> str:
    controparte = doc.cedente.denominazione if tipo != TipoMovimento.VENDITA else doc.cessionario.denominazione
    pezzi = [p for p in (f"Ft. {doc.numero}" if doc.numero else "", controparte) if p]
    return " - ".join(pezzi) if pezzi else (doc.descrizione_sintetica or "Documento")


def _causale(doc: Documento, regole: Regole, chiave: str) -> str:
    controparte = doc.cedente if chiave == "acquisto" else doc.cessionario
    regola = regole.regola_controparte(controparte.identificativo)
    if regola and regola.causale:
        return regola.causale
    return regole.causali.get(chiave, chiave.upper())
