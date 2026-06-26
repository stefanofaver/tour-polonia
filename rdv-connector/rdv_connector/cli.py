"""Interfaccia a riga di comando del connettore RDV.

Per ora copre il flusso "leggi documenti -> proponi registrazioni" (parti 1 e 2).
La scrittura sul portale (parte 3) verra' aggiunta dopo aver mappato i form di RDV.

Esempi:
    python -m rdv_connector.cli proponi --documenti samples/ --regole config/regole.example.json
    python -m rdv_connector.cli proponi --documenti fatture/ --regole config/regole.json --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .models import Documento, RegistrazioneProposta
from .parsers.fattura_xml import leggi_fattura
from .parsers.pdf import leggi_pdf
from .proposta.motore import proponi_registrazione
from .proposta.regole import Regole, carica_regole


def _raccogli_documenti(percorso: Path) -> list[Documento]:
    """Legge un file o tutti i documenti supportati in una cartella."""
    file_list: list[Path]
    if percorso.is_dir():
        file_list = sorted(
            p for p in percorso.iterdir()
            if p.suffix.lower() in (".xml", ".pdf")
        )
    else:
        file_list = [percorso]

    documenti: list[Documento] = []
    for f in file_list:
        try:
            if f.suffix.lower() == ".xml":
                documenti.extend(leggi_fattura(f))
            elif f.suffix.lower() == ".pdf":
                documenti.extend(leggi_pdf(f))
        except Exception as exc:
            doc = Documento(fonte=str(f), formato=f.suffix.lstrip("."))
            doc.avvisi.append(f"Errore di lettura: {exc}")
            documenti.append(doc)
    return documenti


def _stampa_proposta(reg: RegistrazioneProposta) -> None:
    doc = reg.documento
    print("=" * 72)
    print(f"Documento : {Path(doc.fonte).name}  [{doc.formato.upper()}]")
    print(f"Tipo      : {reg.tipo.value}   Causale: {reg.causale or '-'}")
    print(f"Data reg. : {reg.data_registrazione or '-'}")
    print(f"Descrizione: {reg.descrizione}")
    if reg.righe:
        print("-" * 72)
        print(f"  {'Conto':<14} {'Descrizione':<32} {'Dare':>10} {'Avere':>10}")
        for r in reg.righe:
            dare = f"{r.dare:.2f}" if r.dare else ""
            avere = f"{r.avere:.2f}" if r.avere else ""
            print(f"  {r.conto_codice:<14} {r.conto_descrizione[:32]:<32} {dare:>10} {avere:>10}")
        print("-" * 72)
        stato = "OK quadra" if reg.quadra else "NON QUADRA"
        print(f"  {'':<14} {'TOTALI':<32} {reg.totale_dare:>10.2f} {reg.totale_avere:>10.2f}   [{stato}]")
    for a in reg.avvisi:
        print(f"  ! {a}")
    print()


def _proposta_to_dict(reg: RegistrazioneProposta) -> dict:
    return {
        "documento": Path(reg.documento.fonte).name,
        "formato": reg.documento.formato,
        "tipo": reg.tipo.value,
        "causale": reg.causale,
        "data_registrazione": reg.data_registrazione,
        "descrizione": reg.descrizione,
        "righe": [
            {
                "conto_codice": r.conto_codice,
                "conto_descrizione": r.conto_descrizione,
                "dare": str(r.dare),
                "avere": str(r.avere),
            }
            for r in reg.righe
        ],
        "totale_dare": str(reg.totale_dare),
        "totale_avere": str(reg.totale_avere),
        "quadra": reg.quadra,
        "avvisi": reg.avvisi,
    }


def comando_proponi(args: argparse.Namespace) -> int:
    regole: Regole = carica_regole(args.regole)
    documenti = _raccogli_documenti(Path(args.documenti))
    if not documenti:
        print("Nessun documento .xml o .pdf trovato.", file=sys.stderr)
        return 1

    proposte = [proponi_registrazione(d, regole) for d in documenti]

    if args.json:
        print(json.dumps([_proposta_to_dict(p) for p in proposte], indent=2, ensure_ascii=False))
    else:
        print(f"\nTrovati {len(documenti)} documenti, generate {len(proposte)} proposte.\n")
        for p in proposte:
            _stampa_proposta(p)
        n_avvisi = sum(1 for p in proposte if p.avvisi)
        print(f"Proposte con avvisi da verificare: {n_avvisi}/{len(proposte)}")
        print("Nessuna registrazione e' stata scritta su RDV (richiede approvazione).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rdv_connector", description="Connettore RDV Network")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("proponi", help="Leggi documenti e proponi registrazioni")
    p.add_argument("--documenti", required=True, help="File o cartella con .xml/.pdf")
    p.add_argument("--regole", required=True, help="File JSON delle regole di mappatura")
    p.add_argument("--json", action="store_true", help="Output in formato JSON")
    p.set_defaults(func=comando_proponi)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
