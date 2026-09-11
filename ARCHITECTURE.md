# Architettura

## Stack e motivazione

| Livello | Scelta | Perché |
|---|---|---|
| Backend | Python 3.11 + FastAPI | Ecosistema statistico (numpy/scipy/pandas) nello stesso linguaggio del motore quantitativo — nessun confine linguaggio tra ingestion, modeling e API. FastAPI dà validazione Pydantic e OpenAPI gratis. |
| Database | PostgreSQL 16 | Relazionale, transazionale, maturo per un data model con ~25 entità fortemente collegate (partite, mercati, quote, predizioni, versioni). SQLAlchemy 2.0 (typed) + Alembic per le migrazioni. |
| Statistica | numpy, scipy, pandas, scikit-learn (pianificato) | Standard de-facto; scipy.optimize per la stima Dixon-Coles via massima verosimiglianza. |
| Frontend | Next.js 15 (App Router) + React 19, TypeScript | SSR/CSR ibrido, routing per pagina partita, nessuna dipendenza esotica. Stile scritto a mano (nessuna libreria UI) per restare leggero nel vertical slice. |

Ogni scelta è stata verificata eseguibile in questo ambiente (Postgres 16 e Node 22 sono risultati già installati; le dipendenze Python/JS si installano da PyPI/npm, entrambi raggiungibili).

## Principio cardine: separazione Provider → Ingestion → Engine → API

```
┌──────────────┐   DTO puri    ┌────────────┐   righe ORM   ┌──────────────┐
│  Providers   │ ─────────────▶│ Ingestion  │ ─────────────▶│  PostgreSQL  │
│ (5 interfacce│                │ (upsert    │                │  (26 tabelle)│
│  astratte)   │                │ idempotente)│                └──────┬───────┘
└──────────────┘                └────────────┘                       │
                                                                       │ solo dati
                                                                       │ precedenti
                                                                       ▼
                                                        ┌───────────────────────┐
                                                        │ Statistical Engine     │
                                                        │ (Dixon-Coles Poisson)  │
                                                        └──────────┬────────────┘
                                                                   ▼
                                                        ┌───────────────────────┐
                                                        │ Decision Layer         │
                                                        │ fair odds/value/risk/  │
                                                        │ selection ladder 1-10  │
                                                        └──────────┬────────────┘
                                                                   ▼
                                                     AnalysisVersion + Prediction +
                                                     RiskSelection + Alert (persistiti)
                                                                   ▼
                                                        ┌───────────────────────┐
                                                        │ FastAPI               │
                                                        └──────────┬────────────┘
                                                                   ▼
                                                        ┌───────────────────────┐
                                                        │ Next.js frontend      │
                                                        └───────────────────────┘
```

Nessun livello dipende da un provider concreto: `app/providers/base/*.py` definisce
5 interfacce astratte (`SportsDataProvider`, `OddsProvider`, `NewsProvider`,
`LineupProvider`, `WeatherProvider`); il motore e l'API lavorano solo su righe DB
o DTO, mai su un client HTTP specifico. Sostituire/aggiungere una fonte dati non
richiede toccare `engine/` né `api/`.

## No data leakage — dove è imposto nel codice

1. **Fit del modello**: `analysis_runner._load_training_matches` seleziona solo
   partite con `Match.kickoff_utc < match.kickoff_utc` nella stessa competizione.
   Lo stesso vincolo è nel backtest (`backtest/runner.py`): il modello per un batch
   è addestrato solo su partite di batch precedenti.
2. **Nessuna fuga tramite feature "attuali"**: `TacticalFeature` ha `as_of_date`
   proprio per permettere, in futuro, lo stesso filtro temporale su feature
   tattiche/infortuni.
3. **Versioning esplicito**: ogni predizione referenzia un `ModelVersion` con
   `training_data_cutoff` esplicito — un backtest può sempre verificare che nessuna
   predizione abbia usato un modello addestrato "nel futuro" rispetto alla partita.

## AnalysisVersion / RiskSelection — perché cambiare rischio non ricalcola nulla

`run_analysis_for_match` (in `app/engine/decision/analysis_runner.py`) è l'unica
funzione che scrive `Prediction`/`RiskSelection`/`Alert`. Ad ogni esecuzione crea
una nuova `AnalysisVersion` (marcando la precedente `is_current=False`, mai
cancellata — storia limitata implicitamente da quante versioni si tengono, non
serve una cronologia infinita) e per ognuno dei 10 livelli di rischio scrive 1
riga `rank=1` (principale) + fino a 2 `rank=2/3` (alternative). L'endpoint
`GET /matches/{id}` restituisce **tutti e 10 i livelli già calcolati**: il
frontend cambia solo quale livello mostra, mai chiamando l'endpoint di analisi.
Il pulsante "AGGIORNA ANALISI" è l'unico trigger di `POST /matches/{id}/analyze`.

## Motore Live (non implementato, solo predisposto)

Nessuna tabella o funzione qui assume che una partita sia "pre-match": `Match.status`
è un enum che include `IN_PLAY`; `AnalysisVersion` è già pensata per essere generata
più volte nel tempo. Un motore live futuro aggiungerebbe:
- un `LiveOddsProvider` (stessa interfaccia `OddsProvider`, polling più frequente);
- un secondo modello statistico (es. aggiornamento bayesiano in-play) dietro la
  stessa interfaccia del Decision Layer;
- una tabella `live_events` collegata a `Match` per i minuti/eventi;

senza toccare lo schema esistente né il codice pre-match.

## Struttura repository

```
backend/
  app/
    models/         # SQLAlchemy ORM — il data model completo (26 tabelle)
    providers/       # 5 interfacce astratte + implementazioni per categoria (v. DATA_SOURCES.md)
    ingestion/        # mapping DTO provider -> righe DB, idempotente
    engine/
      statistical/    # Dixon-Coles Poisson
      decision/       # fair odds, value, risk score, selezione, riconciliazione formazioni
      intelligence/   # segnali qualitativi (interfaccia, non ancora popolata — v. ROADMAP)
    backtest/         # runner walk-forward + metriche
    api/              # FastAPI routers
  alembic/            # migrazioni
  tests/              # pytest, dati sintetici etichettati esplicitamente
  scripts/
    seed_dev_fixture.py     # dati SINTETICI per smoke-test locale (mai per analisi reale)
    ingest_football_data.py # ingestione REALE bulk da football-data.co.uk (multi-stagione)
frontend/
  app/                # Next.js App Router: tabella, dettaglio partita, schedina
```

## Nota storica sull'accesso di rete durante lo sviluppo

L'ambiente sandbox in cui questo progetto è stato inizialmente sviluppato
bloccava l'accesso di rete in uscita verso l'internet generico (proxy con
allowlist limitata a registri pacchetti npm/PyPI e all'API Anthropic) — la
prima ingestione è stata quindi verificata solo con dati sintetici
(`scripts/seed_dev_fixture.py`). A metà sviluppo la policy di rete
dell'ambiente è stata cambiata dall'utente, e da quel momento è stato
verificato un accesso reale a football-data.co.uk: sono state ingerite 7.600
partite reali (10 stagioni Premier League + 10 stagioni Serie A, 2015/16–
2024/25) tramite `scripts/ingest_football_data.py`, e sull'ingestione reale
sono stati eseguiti con successo l'analisi (`run_analysis_for_match`), un
backtest walk-forward reale (v. BACKTEST_SPEC.md) e verifiche end-to-end di
API e frontend. Le altre fonti (API-Football, understat, fbref) restano
verificate solo strutturalmente (codice + test unitari), non con una vera
ingestione in questa sessione — v. DATA_SOURCES.md per lo stato preciso di
ciascuna.
