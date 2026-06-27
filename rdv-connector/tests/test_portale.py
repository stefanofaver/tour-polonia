"""Test della parte portale che NON richiedono Playwright installato.

Verificano che il pacchetto resti importabile e degradi correttamente in
assenza della dipendenza opzionale, e che lo slug dei nomi file sia sicuro.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rdv_connector.portale.ricognizione import slug
from rdv_connector.portale.sessione import PlaywrightNonDisponibile, _PLAYWRIGHT_OK, SessionePortale


class TestSlug(unittest.TestCase):
    def test_slug_normalizza(self):
        self.assertEqual(slug("Elenco Causali"), "elenco-causali")
        self.assertEqual(slug("Piano dei Conti / 2026"), "piano-dei-conti-2026")
        self.assertEqual(slug("  "), "pagina")
        self.assertEqual(slug("Guida: Prima Nota!"), "guida-prima-nota")


class TestDegradazioneSenzaPlaywright(unittest.TestCase):
    def test_errore_chiaro_se_playwright_assente(self):
        if _PLAYWRIGHT_OK:
            self.skipTest("Playwright installato: test della degradazione non applicabile")
        with self.assertRaises(PlaywrightNonDisponibile):
            SessionePortale("https://esempio")


if __name__ == "__main__":
    unittest.main(verbosity=2)
