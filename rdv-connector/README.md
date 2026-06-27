# Connettore RDV Network

Strumento per ridurre il lavoro manuale delle registrazioni contabili ripetitive
sul gestionale **RDV Network** (gruppo CGN). Legge i documenti contabili
(fatture elettroniche **XML / FatturaPA** e **PDF**), **propone** la registrazione
di prima nota e — dopo la tua **approvazione** — la scrive sul portale.

> Filosofia: lo strumento **propone**, tu **approvi**, poi viene **scritto**.
> Nessuna registrazione finisce su RDV senza un tuo via libera.

---

## Stato del progetto

| Parte | Cosa fa | Stato |
|------|---------|-------|
| 1. Lettura documenti | FatturaPA XML (completo) + PDF (euristico) | ✅ Funzionante |
| 2. Motore di proposta | Documento → registrazione di prima nota in partita doppia | ✅ Funzionante |
| 3a. Login + ricognizione portale | Login assistito e raccolta in sola lettura di causali/conti/guide | ✅ Pronto da eseguire* |
| 3b. Scrittura sul portale | Compilazione automatica dei form di prima nota | ⏳ Dopo la ricognizione |

\* Richiede Playwright installato sul tuo PC e il login al tuo account
(vedi [Portale RDV](#portale-rdv-login-e-ricognizione)). Io non ho accesso al
tuo portale: la scrittura (3b) verra' costruita sui form reali raccolti in 3a.

---

## Perché gira sul tuo computer

Lo strumento tratta **credenziali di accesso** e **documenti fiscali**: per
sicurezza è pensato per essere eseguito **in locale, sul tuo PC**, non in cloud.
Le password e i documenti non lasciano la tua macchina.

---

## Requisiti

- **Python 3.10+**
- Per la sola lettura XML + proposta: **nessuna dipendenza** (solo libreria standard).
- Per i PDF: `pip install -r requirements.txt` (installa `pypdf`).
- Per la futura scrittura sul portale: `playwright` (incluso in requirements).

---

## Uso rapido

Leggere i documenti di una cartella e vedere le registrazioni proposte:

```bash
python -m rdv_connector.cli proponi \
    --documenti samples/ \
    --regole config/regole.example.json
```

Output di esempio:

```
Documento : fattura_acquisto_esempio.xml  [XML]
Tipo      : acquisto   Causale: FATTURA ACQUISTO
Data reg. : 2026-05-12
Descrizione: Ft. 145 - Forniture Ufficio S.r.l.
------------------------------------------------------------------------
  Conto          Descrizione                            Dare      Avere
  60.10.020      Cancelleria e materiale di consu     200.00
  10.30.010      IVA a credito                         44.00
  20.05.001      Debiti verso fornitori                          244.00
------------------------------------------------------------------------
                 TOTALI                               244.00     244.00   [OK quadra]
```

Output in JSON (utile per integrazioni / per la fase di scrittura):

```bash
python -m rdv_connector.cli proponi --documenti samples/ --regole config/regole.example.json --json
```

---

## Configurare le tue regole

1. Copia `config/regole.example.json` in `config/regole.json`.
2. Inserisci:
   - **`azienda`**: la tua denominazione e **P.IVA** (serve a capire se un
     documento è un acquisto o una vendita).
   - **`conti`**: i **codici reali del tuo piano dei conti RDV** (debiti
     fornitori, crediti clienti, IVA a credito/debito, conti di costo/ricavo
     predefiniti). Quelli nell'esempio sono fittizi.
   - **`causali`**: le causali da usare.
   - **`controparti`**: qui codifichi le **regole ricorrenti** — per ogni
     fornitore/cliente (chiave = P.IVA o C.F.) il conto di costo/ricavo e la
     causale da applicare automaticamente. È il cuore dell'automazione: più
     regole inserisci, meno correzioni dovrai fare.

`config/regole.json` è escluso dal versionamento (`.gitignore`) perché può
contenere dati aziendali.

---

## Schema delle scritture generate

**Acquisto** (fattura da fornitore):

| | Conto | Dare | Avere |
|--|-------|------|-------|
| | Costo (per controparte o predefinito) | imponibile | |
| | IVA a credito | imposta | |
| | Debiti v/fornitori | | totale |

**Vendita** (fattura a cliente):

| | Conto | Dare | Avere |
|--|-------|------|-------|
| | Crediti v/clienti | totale | |
| | Ricavo (per controparte o predefinito) | | imponibile |
| | IVA a debito | | imposta |

Ogni proposta riporta **avvisi** quando qualcosa va verificato (controparte
sconosciuta, totale incoerente, partita doppia non quadrata, PDF illeggibile…).

---

## Struttura del codice

```
rdv-connector/
├── rdv_connector/
│   ├── models.py              # Documento, RegistrazioneProposta, ...
│   ├── parsers/
│   │   ├── fattura_xml.py     # lettore FatturaPA (solo stdlib)
│   │   └── pdf.py             # lettore PDF (pypdf, best-effort)
│   ├── proposta/
│   │   ├── regole.py          # caricamento regole di mappatura
│   │   └── motore.py          # documento → registrazione proposta
│   └── cli.py                 # interfaccia a riga di comando
├── config/regole.example.json # modello di configurazione
├── samples/                   # fattura di esempio per i test
└── tests/                     # test (python -m unittest)
```

Eseguire i test:

```bash
python -m unittest discover -s tests
```

---

## Portale RDV: login e ricognizione

Questa fase gira **sul tuo PC** e parte in **sola lettura**: prima di scrivere
qualunque cosa, raccoglie il materiale per capire il programma e configurarlo
sul tuo ambiente reale (causali, piano dei conti, guida alla prima nota).

**Sicurezza — login manuale.** Il browser si apre in modo visibile e **accedi
tu a mano** (password, eventuale 2FA, captcha). Lo strumento **non memorizza la
password**: salva solo lo stato di sessione in `auth_state.json` (escluso dal
versionamento) per non rifare il login ogni volta.

Preparazione (una tantum):

```bash
pip install -r requirements.txt
playwright install chromium
cp config/portale.example.json config/portale.json   # poi adattalo
```

1) Login assistito (salva la sessione):

```bash
python -m rdv_connector.cli login --portale config/portale.json
```

2) Ricognizione. Modalità **manuale** (consigliata all'inizio: navighi tu e
catturi le pagine che ti interessano, senza dover conoscere gli URL):

```bash
python -m rdv_connector.cli ricognizione --portale config/portale.json --manuale
```

Oppure modalità **automatica** (visita gli URL elencati in `config/portale.json`).

Per ogni pagina vengono salvati, nella cartella `output_ricognizione`, tre file:
`<nome>.html` (sorgente), `<nome>.txt` (testo leggibile) e `<nome>.png`
(screenshot). Questo materiale serve a configurare conti/causali reali e a
costruire la successiva fase di scrittura.

## Prossimi passi (scrittura, parte 3b)

Dopo la ricognizione, sui form reali raccolti costruirò la compilazione
automatica della prima nota, che scriverà **solo dopo la tua approvazione**
(una per una o a blocchi, come preferisci) e terrà un registro di tutto ciò che
viene inserito.

---

## Avvertenza

Strumento di supporto operativo: **non sostituisce il controllo di un
professionista**. Le registrazioni proposte vanno sempre verificate prima
dell'approvazione e dell'invio definitivo.
