"""Automazione del portale RDV Network (parte 3).

Contiene:
  - sessione.py     : gestione del browser e login assistito manuale
  - ricognizione.py : raccolta in SOLA LETTURA di causali, conti e guide

La scrittura delle registrazioni verra' aggiunta solo dopo aver mappato i form
reali del portale durante la ricognizione.

Richiede Playwright (vedi requirements.txt) e, sul PC dell'utente:
    pip install -r requirements.txt
    playwright install chromium
"""
