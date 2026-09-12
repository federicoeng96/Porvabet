# Architettura

## Stack e motivazione

| Livello | Scelta | Perché |
|---|---|---|
| Backend | Python 3.11 + FastAPI | Ecosistema statistico (numpy/scipy/pandas) nello stesso linguaggio del motore quantitativo — nessun confine linguaggio tra ingestion, modeling e API. FastAPI dà validazione Pydantic e OpenAPI gratis. |
| Database | PostgreSQL 16 | Relazionale, transazionale, maturo per un data model con ~25 entità fortemente collegate (partite, mercati, quote, predizioni, versioni). SQLAlchemy 2.0 (typed) + Alembic per le migrazioni. |
| Statistica | numpy, scipy, pandas, scikit-learn (pianificato) | Standard de-facto; scipy.optimize per la stima Dixon-Coles via massima verosimiglianza. |
| Frontend | Next.js 15 (App Router) + React 19, TypeScript | SSR/CSR ibrido, routing per pagina partita, nessuna dipendenza esotica. Stile scritto a mano (nessuna libreria UI) per restare leggero nel vertical slice. |

Ogni scelta è stata verificata eseguibile in questo ambiente (Postgres 16 e Node 22 sono risultati già installati; le dipendenze Python/JS si installano da PyPI/npm, entrambi raggiungibili).

## ⚠️ Limite attivo: nessun value/edge reale contro ePlay24

**Il sistema oggi stima probabilità e quote fair, ma NON può calcolare un
value/edge reale rispetto al mercato ePlay24.** Non è un dettaglio implementativo
rimandato: è stato verificato tecnicamente (v. `DATA_SOURCES.md`, sezione
ePlay24) che il sito blocca ogni richiesta automatizzata a livello di
infrastruttura edge (Akamai) — homepage, robots.txt e persino la pagina dei
propri termini di servizio restituiscono tutti HTTP 403, sia da rete diretta
sia tramite `WebFetch`. Non esiste inoltre alcuna API pubblica o feed
documentato, né un aggregatore di quote di terze parti che copra ePlay24.

**Anche diretta.it/Flashscore (quote del bookmaker "Betson" mostrate sul
sito) è stato valutato come possibile alternativa e scartato** (v.
`DATA_SOURCES.md`, categoria C): tecnicamente raggiungibile (a differenza di
ePlay24), ma i ToS vietano esplicitamente scraping/estrazione senza consenso,
e la quota mostrata appartiene al bookmaker terzo licenziatario, non a
diretta.it stesso — un doppio motivo di rischio, non solo un blocco tecnico.

Conseguenza architetturale: finché `EPlay24OddsProvider` resta
un'interfaccia senza implementazione (v. `app/providers/eplay24/provider.py`),
questo progetto è, di fatto, **un motore di stima (probabilità + quota fair),
non un motore di value betting contro ePlay24 specificamente**. Il "value" e
gli alert mostrati oggi nell'interfaccia sono sempre calcolati contro le
quote della fonte realmente disponibile (football-data.co.uk — quote reali di
altri bookmaker, mai simulate), e sono **etichettati esplicitamente con il nome
del bookmaker reale** (mai "ePlay24") sia nell'API (`bookmaker_name` in ogni
`Prediction`/`SelectionOut`) sia nel frontend (colonna quota + banner
dedicato). Nessuna quota di un altro bookmaker viene mai presentata come "quota
ePlay24" o usata come sostituto silenzioso — se in futuro servisse un proxy per
testare il Value Engine con dati storici, andrebbe comunque etichettato
esplicitamente come tale (es. "TEST — quota non ePlay24"), non semplicemente
attribuito a "quota bookmaker" generica.

**Lo stesso limite si applica, per una ragione diversa, a corner e
cartellini**: qui non è ePlay24 a essere irraggiungibile — è che **nessuna
fonte dati integrata (nemmeno football-data.co.uk) pubblica quote per questi
due mercati** (verificato contro lo schema colonne reale — solo 1X2, O/U 2.5
gol e handicap asiatico hanno prezzi). Il modello (`PoissonCountModel`, v.
MODEL_SPEC.md) produce comunque una probabilità reale, esposta via API/
frontend come stima esplicitamente "senza quota" (`additional_estimates`,
mai nella risk ladder) — stesso principio del punto sopra: mostrare il lavoro
di stima senza fingere un value che nessun prezzo di mercato reale supporta.

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

## Backtest → DB → risk score live: il loop è chiuso

`scripts/persist_backtest_results.py` scrive righe `Backtest`/`ModelVersion`
reali in DB (non più solo un report testuale in BACKTEST_SPEC.md — v. ROADMAP.md
punto 1). `app/engine/decision/reliability.py` le legge da lì all'analisi live:
`run_analysis_for_match` → `_build_candidates_and_predictions` →
`model_reliability_for(db, family, market_category, competition_id, probability)`
→ fattore `model_reliability` in `RiskFactors`. Non c'è un servizio/cache
separato: è una query diretta sulla riga `Backtest` più recente per quel
segmento, eseguita ad ogni "AGGIORNA ANALISI" — accettabile a questo volume
(poche righe `Backtest` per competizione/mercato), da rivedere solo se il
numero di segmenti backtestati crescesse di ordini di grandezza. Se per un
segmento non esiste ancora un backtest persistito, o nessun bin della sua
curva di calibrazione ha abbastanza osservazioni, la funzione ritorna "non
stimabile" esplicitamente (mai un numero indovinato) e il chiamante applica un
valore di caso peggiore — v. MODEL_SPEC.md "Incertezza, qualità dati,
affidabilità modello".

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
      statistical/    # Dixon-Coles Poisson (1X2/O-U/BTTS) + PoissonCountModel (corner/cartellini)
      decision/       # fair odds, value, risk score, selezione, riconciliazione formazioni,
                      # count_market_estimates.py (stime corner/cartellini SENZA value — v. sotto)
      intelligence/   # segnali qualitativi (interfaccia, non ancora popolata — v. ROADMAP)
    backtest/         # runner walk-forward + metriche (gol) + count_market_runner.py (corner/cartellini)
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

## ⚠️ Dipendenza aperta: accesso di rete dell'ambiente di ESECUZIONE reale

Quanto sopra riguarda **solo l'ambiente sandbox di sviluppo** usato per
scrivere e verificare questo codice. **Non è stato verificato — e non può
esserlo da questa sessione — se l'ambiente dove il sistema girerà
effettivamente in uso normale** (il server/macchina/container che l'utente
sceglierà per il deploy: locale, VPS, servizio cloud, ecc.) abbia accesso di
rete in uscita verso football-data.co.uk, understat.com, fbref.com o le altre
fonti. Questo dipende interamente da come e dove l'utente decide di eseguire
il sistema in produzione, una scelta non ancora fatta/comunicata in questo
progetto. Non va quindi dato per scontato che "funziona in sandbox dopo il
cambio di policy" implichi "funzionerà ovunque verrà deployato" — sono due
ambienti distinti con policy di rete potenzialmente diverse (un server
aziendale con firewall restrittivo, un container CI, un servizio PaaS con
allowlist propria, ecc. possono tutti bloccare l'uscita verso questi domini
indipendentemente da cosa succede qui).

**Azione raccomandata prima di considerare l'ingestione "pronta per la
produzione"**: eseguire un semplice test di connettività
(`curl -sSL -o /dev/null -w "%{http_code}" https://www.football-data.co.uk/`)
dall'ambiente di deploy scelto, prima di fare affidamento
sull'ingestione automatica pianificata (es. un cron job) — se quell'ambiente
blocca l'uscita, l'ingestione fallirà silenziosamente in produzione anche se
ha funzionato qui. Questo è un rischio operativo aperto, non un problema di
codice: nessuna riga di questo progetto può risolverlo da sola.
