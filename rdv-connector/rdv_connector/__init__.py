"""Connettore RDV Network — lettura documenti contabili e proposta registrazioni.

Pacchetto suddiviso in tre responsabilita':
  - parsers/   : lettura dei documenti (FatturaPA XML, PDF)
  - proposta/  : trasformazione del documento in registrazione di prima nota proposta
  - (futuro) scrittura sul portale RDV tramite automazione del browser

Vedi README.md per architettura e flusso di lavoro.
"""

__version__ = "0.1.0"
