# Porvabet

Motore quantitativo di analisi pre-match per scommesse sportive (Premier League,
Serie A). Vedi la documentazione di progetto prima di tutto:

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — stack, struttura, principio no-leakage, limiti dell'ambiente di sviluppo
- [`DATA_SOURCES.md`](./DATA_SOURCES.md) — valutazione verificata di ogni fonte dati, per categoria
- [`MODEL_SPEC.md`](./MODEL_SPEC.md) — modelli statistici, fair odds, value, risk score
- [`BACKTEST_SPEC.md`](./BACKTEST_SPEC.md) — metriche, garanzie anti-leakage, cosa manca
- [`ROADMAP.md`](./ROADMAP.md) — stato reale e prossimi passi

## ⚠️ Nota importante sui dati in questo repository

Questo progetto **non contiene dati reali**. L'ambiente in cui è stato
sviluppato inizialmente non ha accesso di rete verso le fonti dati reali (v.
`ARCHITECTURE.md`). Il codice dei provider (`app/providers/`) è scritto per
funzionare con dati reali in un ambiente con accesso a internet normale; per
verificare che l'intera pipeline (DB → statistica → decisione → API →
frontend) funzioni end-to-end è stato usato **solo**
`backend/scripts/seed_dev_fixture.py`, che genera dati **sintetici**
chiaramente etichettati (squadre fittizie "FC Alpha/Beta/...", fonte
`synthetic_dev_fixture` nel database) — mai da confondere con un'analisi reale.

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

# Dati REALI (richiede un ambiente con accesso di rete normale):
#   python -c "from app.providers.football_data_co_uk import FootballDataCoUkProvider; ..."
#   (vedi ARCHITECTURE.md — nessuno script di ingestione bulk reale è incluso
#   ancora, v. ROADMAP.md punto 1)

# Dati SINTETICI di test (per verificare che tutto funzioni, in qualunque ambiente):
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
  Le quote mostrate provengono dai dati storici ingeriti (es. media di mercato
  da football-data.co.uk), etichettate come tali nell'interfaccia.
- Non copre corner, cartellini, falli o player props (mancano modelli e dati
  ingeriti per questi mercati — v. `MODEL_SPEC.md`/`ROADMAP.md`).
- Non ha un motore live (solo l'architettura lo prevede, per design).
- Non promette vincite: ogni probabilità è una stima di modello, da validare
  col backtest — v. `BACKTEST_SPEC.md`.
