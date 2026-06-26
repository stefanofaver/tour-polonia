"""Test del lettore FatturaPA e del motore di proposta (solo stdlib)."""
import sys
import unittest
from decimal import Decimal
from pathlib import Path

# Rende importabile il pacchetto eseguendo i test dalla cartella del progetto.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rdv_connector.models import TipoMovimento
from rdv_connector.parsers.fattura_xml import leggi_fattura
from rdv_connector.proposta.motore import proponi_registrazione
from rdv_connector.proposta.regole import carica_regole

BASE = Path(__file__).resolve().parents[1]
SAMPLE = BASE / "samples" / "fattura_acquisto_esempio.xml"
REGOLE = BASE / "config" / "regole.example.json"


class TestLetturaFattura(unittest.TestCase):
    def setUp(self):
        self.docs = leggi_fattura(SAMPLE)
        self.doc = self.docs[0]

    def test_un_solo_body(self):
        self.assertEqual(len(self.docs), 1)

    def test_intestazione(self):
        self.assertEqual(self.doc.numero, "145")
        self.assertEqual(self.doc.data, "2026-05-12")
        self.assertEqual(self.doc.tipo_documento, "TD01")
        self.assertEqual(self.doc.cedente.denominazione, "Forniture Ufficio S.r.l.")
        self.assertEqual(self.doc.cedente.partita_iva, "IT02345678901")
        self.assertEqual(self.doc.cessionario.partita_iva, "IT01234567890")

    def test_importi(self):
        self.assertEqual(self.doc.imponibile_totale, Decimal("200.00"))
        self.assertEqual(self.doc.imposta_totale, Decimal("44.00"))
        self.assertEqual(self.doc.totale_documento, Decimal("244.00"))
        self.assertEqual(self.doc.totale_calcolato, Decimal("244.00"))

    def test_nessun_avviso_di_coerenza(self):
        self.assertEqual(self.doc.avvisi, [])


class TestProposta(unittest.TestCase):
    def setUp(self):
        self.regole = carica_regole(REGOLE)
        self.doc = leggi_fattura(SAMPLE)[0]
        self.reg = proponi_registrazione(self.doc, self.regole)

    def test_riconosce_acquisto(self):
        self.assertEqual(self.reg.tipo, TipoMovimento.ACQUISTO)

    def test_partita_doppia_quadra(self):
        self.assertTrue(self.reg.quadra)
        self.assertEqual(self.reg.totale_dare, Decimal("244.00"))
        self.assertEqual(self.reg.totale_avere, Decimal("244.00"))

    def test_usa_conto_specifico_fornitore(self):
        # Il fornitore 02345678901 ha una regola dedicata in regole.example.json
        conti_dare = {r.conto_codice for r in self.reg.righe if r.dare}
        self.assertIn("60.10.020", conti_dare)  # conto cancelleria
        self.assertIn("10.30.010", conti_dare)  # IVA a credito

    def test_riga_fornitore_in_avere(self):
        avere = [r for r in self.reg.righe if r.avere]
        self.assertEqual(len(avere), 1)
        self.assertEqual(avere[0].conto_codice, "20.05.001")
        self.assertEqual(avere[0].avere, Decimal("244.00"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
