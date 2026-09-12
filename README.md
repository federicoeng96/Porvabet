# Porvabet

Motore quantitativo di analisi pre-match per scommesse sportive (Premier League,
Serie A). Vedi la documentazione di progetto prima di tutto:

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — stack, struttura, principio no-leakage, limiti dell'ambiente di sviluppo
- [`DATA_SOURCES.md`](./DATA_SOURCES.md) — valutazione verificata di ogni fonte dati, per categoria
- [`MODEL_SPEC.md`](./MODEL_SPEC.md) — modelli statistici, fair odds, value, risk score
- [`BACKTEST_SPEC.md`](./BACKTEST_SPEC.md) — metriche, garanzie anti-leakage, cosa manca
- [`ROADMAP.md`](./ROADMAP.md) — stato reale e prossimi passi
- [`RUNNING_LOCALLY.md`](./RUNNING_LOCALLY.md) — come eseguire il progetto sul
  tuo computer per una verifica end-to-end reale (necessario per Betfair
  Exchange: la sandbox di sviluppo è bloccata a livello di rete, v. `DATA_SOURCES.md`)

## Uso previsto

**Questo strumento è e resterà a uso esclusivamente personale dell'utente
proprietario del progetto.** Non verrà mai distribuito, venduto, condiviso con
terzi né reso disponibile ad altri utenti in nessuna forma. Questo è il
contesto reale in cui vanno lette tutte le valutazioni di rischio legale in
`DATA_SOURCES.md` e nella sezione sotto: dove un ToS distingue tra uso
personale e ridistribuzione/uso commerciale, questo progetto è sempre il
primo caso, mai il secondo. Questo abbassa il rischio pratico di violazione
(nessuna ridistribuzione, nessun terzo esposto), ma **non elimina il rischio
contrattuale residuo** se un domani un ToS vietasse esplicitamente anche il
solo uso personale a scopo di scommessa — v. `DATA_SOURCES.md` per il
dettaglio fonte per fonte.

## ⚠️ Nota sui dati

Il repository di per sé **non include un database precaricato**: quali dati ci
sono dipende da cosa esegui. Sono disponibili due percorsi, entrambi verificati
funzionanti in questo progetto:

- **Dati reali**: `backend/scripts/ingest_football_data.py` scarica da
  football-data.co.uk (nessuna chiave richiesta) risultati storici + quote di
  più bookmaker per Premier League e Serie A. Verificato in questa sessione con
  7.600 partite reali (10 stagioni per competizione, 2015/16–2024/25) — analisi,
  backtest, API e frontend testati con successo su questi dati (v.
  `BACKTEST_SPEC.md` per i risultati reali del backtest).
- **Dati sintetici** (`backend/scripts/seed_dev_fixture.py`): squadre fittizie
  ("FC Alpha/Beta/...", fonte `synthetic_dev_fixture` nel database), utili solo
  per uno smoke-test rapido della pipeline senza dover scaricare storico reale
  — non usare mai per un'analisi che verrà presa sul serio.

Il frontend mostra sempre la quota del bookmaker realmente presente nei dati
ingeriti (es. "Bet365", "1XBet", "Market Average" da football-data.co.uk) — mai
ePlay24, per cui non esiste accesso automatico noto (v. `DATA_SOURCES.md`).

## ⚠️ Rischi legali noti

Due fonti dati (`app/providers/whoscored/` e `app/providers/sofascore/`) sono
presenti nel codice **solo come interfaccia collegata a un rischio legale
esplicito**, non come integrazioni pronte all'uso. Questo va tenuto visibile
qui, non solo in un file di configurazione:

| Fonte | Clausola ToS specifica (verbatim) | Rischio |
|---|---|---|
| **WhoScored** | *"The use of WhoScored.com ratings by media, betting or fantasy platforms requires an official licence."* | Nomina esplicitamente le piattaforme di scommesse. Questo progetto è un motore di analisi scommesse — qualunque uso che ecceda l'uso privato personale dell'utente viola direttamente questa clausola. |
| **SofaScore** | *"SofaScore states that they do not supply sports data to bookmakers, and bookmakers should not rely on their site to verify bets."* (più: nessuna API pubblica esiste nemmeno a pagamento, per loro stessa FAQ) | Disclaimer esplicito contro l'uso da parte di bookmaker/piattaforme scommesse. |

Entrambe sono classificate **categoria B** in `DATA_SOURCES.md` ("solo uso
personale non commerciale — rischio accettato esplicitamente dall'utente") e
portano un flag `LICENSE_RISK = "personal_use_only_betting_platform_clause"`
leggibile a runtime sulla classe del provider (non un commento) — verificato
da test dedicati (`backend/tests/test_category_b_providers.py`). Nessuna delle
due ha uno scraping realmente implementato in questo repository: gli endpoint
tecnici non sono stati verificati, e implementarli senza prima leggerli
direttamente violerebbe il principio di questo progetto di non inventare
endpoint. Se in futuro verranno implementati, il rischio resta quello sopra:
va accettato consapevolmente dall'utente, non aggirato.

**Lettura nel contesto reale di uso personale (v. "Uso previsto" sopra)**:
l'uso reale di questo progetto — personale, non distribuito — abbassa il
rischio *pratico* di queste due clausole (nessun terzo esposto, nessuna
ridistribuzione avvenuta). Questo **non è la stessa cosa** che dire "il
rischio è basso": entrambe le clausole restano scritte, e resta un rischio
contrattuale residuo se un domani vietassero esplicitamente anche il solo uso
personale a scopo di scommessa (non solo la ridistribuzione a terzi) — in tal
caso il rischio tornerebbe pieno, indipendentemente da come viene usato oggi.
Il flag `LICENSE_RISK` e questa documentazione restano per questo motivo, non
vengono rimossi né la classificazione B viene declassata ad A solo perché
l'uso è personale.

**diretta.it / Flashscore (quote del bookmaker "Betson")** è stato valutato
in questa sessione come possibile fonte di quote reali per il Value/Odds
Engine e **classificato categoria C, non B**: a differenza di WhoScored/
SofaScore, qui i ToS vietano lo scraping/l'estrazione dati **senza
un'eccezione per uso personale**, e la quota mostrata è di un bookmaker terzo
concessa in licenza a diretta.it solo per la visualizzazione sul proprio
sito — non un dato che diretta.it stesso possa "prestare" a terzi, nemmeno
implicitamente. Nessun provider implementato — v. `DATA_SOURCES.md` per
l'audit completo.

## Setup — Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Postgres (locale): richiede un server Postgres 16 raggiungibile.
# Crea utente/db (una tantum):
#   sudo -u postgres psql -c "CREATE USER porvabet WITH PASSWORD 'porvabet_dev' SUPERUSER;"
#   sudo -u postgres psql -c "CREATE DATABASE porvabet OWNER porvabet;"
#   sudo -u postgres psql -c "CREATE DATABASE porvabet_test OWNER porvabet;"

alembic upgrade head

# Dati REALI (richiede accesso di rete verso football-data.co.uk):
python scripts/ingest_football_data.py --competitions EPL SERIE_A --seasons 2015 2024

# Oppure, dati SINTETICI di test (per verificare rapidamente che tutto funzioni,
# senza bisogno di rete — non usare per un'analisi reale):
python scripts/seed_dev_fixture.py

uvicorn app.main:app --reload --port 8000
```

Test:

```bash
cd backend && source .venv/bin/activate && pytest
ruff check app scripts tests
```

## Setup — Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL punta al backend
npm run dev   # http://localhost:3000
```

## Configurazione

`backend/.env` (opzionale, vedi `app/config.py`):

```
DATABASE_URL=postgresql+psycopg://porvabet:porvabet_dev@localhost:5432/porvabet
API_FOOTBALL_KEY=   # opzionale — senza chiave il provider API-Football è semplicemente disabilitato
```

## Cosa NON fa (onestamente, oggi)

- Non mostra quote reali di ePlay24 (nessun accesso pubblico noto — v. `DATA_SOURCES.md`).
  Le quote mostrate provengono dai dati storici ingeriti da football-data.co.uk
  (bookmaker reali come Bet365/1XBet/Pinnacle o media di mercato), etichettate
  come tali nell'interfaccia.
- Non copre corner, cartellini, falli o player props (mancano modelli e dati
  ingeriti per questi mercati — v. `MODEL_SPEC.md`/`ROADMAP.md`).
- Non ha un motore live (solo l'architettura lo prevede, per design).
- Non promette vincite: il backtest reale su EPL/Serie A 2019-2025 mostra ROI
  negativo su tutti i livelli di rischio con il modello attuale (v.
  `BACKTEST_SPEC.md`) — il ranking di rischio funziona (hit rate scende
  correttamente da livello 1 a 10), ma il modello base non batte ancora il
  mercato. Ogni probabilità mostrata è una stima di modello, non una garanzia.
