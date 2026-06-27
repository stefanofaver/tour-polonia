"""Gestione della sessione browser verso il portale RDV, con login assistito.

Scelte di sicurezza:
  - **Login manuale**: il browser si apre in modo visibile, tu accedi a mano
    (gestendo password, 2FA, eventuali captcha). Lo strumento NON memorizza le
    credenziali.
  - Lo stato autenticato viene salvato in un file locale (`auth_state.json`,
    escluso dal versionamento) per riusare la sessione senza rifare il login a
    ogni esecuzione.

Playwright e' importato in modo protetto: il pacchetto resta importabile anche
dove Playwright non e' installato (es. ambienti che usano solo le parti 1-2).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT_OK = True
except BaseException:  # noqa: BLE001 - assenza dipendenza opzionale
    _PLAYWRIGHT_OK = False


class PlaywrightNonDisponibile(RuntimeError):
    """Sollevata quando si usa la sessione senza Playwright installato."""

    def __init__(self) -> None:
        super().__init__(
            "Playwright non e' installato. Esegui:\n"
            "    pip install -r requirements.txt\n"
            "    playwright install chromium"
        )


class SessionePortale:
    """Incapsula browser, contesto e pagina del portale RDV.

    Uso tipico:
        with SessionePortale(base_url, stato_path) as sess:
            sess.login_manuale()          # solo la prima volta
            page = sess.nuova_pagina()
            page.goto(...)
    """

    def __init__(
        self,
        base_url: str,
        stato_path: str | Path = "auth_state.json",
        headless: bool = False,
    ) -> None:
        if not _PLAYWRIGHT_OK:
            raise PlaywrightNonDisponibile()
        self.base_url = base_url
        self.stato_path = Path(stato_path)
        self.headless = headless
        self._pw = None
        self._browser = None
        self._context = None

    # --- ciclo di vita -----------------------------------------------------
    def __enter__(self) -> "SessionePortale":
        self.avvia()
        return self

    def __exit__(self, *exc) -> None:
        self.chiudi()

    def avvia(self) -> None:
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        # Riusa lo stato salvato se presente (sessione gia' autenticata).
        if self.stato_path.exists():
            self._context = self._browser.new_context(storage_state=str(self.stato_path))
        else:
            self._context = self._browser.new_context()

    def chiudi(self) -> None:
        if self._context is not None:
            self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()

    # --- operazioni --------------------------------------------------------
    @property
    def autenticata(self) -> bool:
        """Vero se esiste uno stato di sessione salvato."""
        return self.stato_path.exists()

    def nuova_pagina(self):
        if self._context is None:
            raise RuntimeError("Sessione non avviata: usa 'with' o chiama avvia().")
        return self._context.new_page()

    def login_manuale(self, conferma=input) -> None:
        """Apre il portale e attende che l'utente acceda manualmente.

        `conferma` e' iniettabile per i test; di default usa input() per
        mettere in pausa finche' l'utente non ha completato il login.
        """
        page = self.nuova_pagina()
        page.goto(self.base_url)
        print("\n" + "=" * 64)
        print("  ACCEDI MANUALMENTE nel browser appena aperto.")
        print("  Completa login, eventuale 2FA e arriva alla home del")
        print("  gestionale. Quando sei dentro, torna qui e premi INVIO.")
        print("=" * 64)
        conferma("  Premi INVIO quando hai completato l'accesso... ")
        self.salva_stato()
        print(f"  Sessione salvata in {self.stato_path}. Non rifarai il login.")
        page.close()

    def salva_stato(self) -> None:
        if self._context is None:
            raise RuntimeError("Sessione non avviata.")
        self._context.storage_state(path=str(self.stato_path))
