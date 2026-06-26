"""Modelli dati condivisi: documento letto e registrazione contabile proposta.

Usiamo solo la libreria standard (dataclasses) per non introdurre dipendenze
nel cuore del connettore.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional


class TipoMovimento(str, Enum):
    """Verso del documento rispetto all'azienda configurata."""

    ACQUISTO = "acquisto"  # fattura ricevuta da un fornitore
    VENDITA = "vendita"    # fattura emessa verso un cliente
    SCONOSCIUTO = "sconosciuto"


@dataclass
class Controparte:
    """Cedente/prestatore o cessionario/committente di un documento."""

    denominazione: str = ""
    partita_iva: Optional[str] = None
    codice_fiscale: Optional[str] = None

    @property
    def identificativo(self) -> Optional[str]:
        """Chiave usata per cercare regole specifiche (PIVA, poi CF)."""
        return self.partita_iva or self.codice_fiscale


@dataclass
class RigaIVA:
    """Una riga di riepilogo IVA del documento (per aliquota/natura)."""

    aliquota: Decimal = Decimal("0")
    imponibile: Decimal = Decimal("0")
    imposta: Decimal = Decimal("0")
    natura: Optional[str] = None  # es. N1..N7 per operazioni senza IVA


@dataclass
class Documento:
    """Documento contabile letto da una fonte (XML FatturaPA o PDF)."""

    fonte: str = ""                 # percorso del file di origine
    formato: str = ""               # "xml" | "pdf"
    tipo_documento: str = ""        # es. TD01
    numero: str = ""
    data: str = ""                  # ISO YYYY-MM-DD quando disponibile
    divisa: str = "EUR"
    cedente: Controparte = field(default_factory=Controparte)
    cessionario: Controparte = field(default_factory=Controparte)
    righe_iva: list[RigaIVA] = field(default_factory=list)
    totale_documento: Optional[Decimal] = None
    descrizione_sintetica: str = ""
    avvisi: list[str] = field(default_factory=list)  # problemi di lettura

    @property
    def imponibile_totale(self) -> Decimal:
        return sum((r.imponibile for r in self.righe_iva), Decimal("0"))

    @property
    def imposta_totale(self) -> Decimal:
        return sum((r.imposta for r in self.righe_iva), Decimal("0"))

    @property
    def totale_calcolato(self) -> Decimal:
        return self.imponibile_totale + self.imposta_totale


@dataclass
class RigaContabile:
    """Una riga della scrittura in partita doppia (dare/avere)."""

    conto_codice: str
    conto_descrizione: str
    dare: Decimal = Decimal("0")
    avere: Decimal = Decimal("0")


@dataclass
class RegistrazioneProposta:
    """Proposta di registrazione di prima nota da sottoporre ad approvazione."""

    documento: Documento
    tipo: TipoMovimento
    data_registrazione: str = ""
    causale: str = ""
    descrizione: str = ""
    righe: list[RigaContabile] = field(default_factory=list)
    avvisi: list[str] = field(default_factory=list)

    @property
    def totale_dare(self) -> Decimal:
        return sum((r.dare for r in self.righe), Decimal("0"))

    @property
    def totale_avere(self) -> Decimal:
        return sum((r.avere for r in self.righe), Decimal("0"))

    @property
    def quadra(self) -> bool:
        """La partita doppia e' bilanciata (dare == avere)."""
        return self.totale_dare == self.totale_avere
