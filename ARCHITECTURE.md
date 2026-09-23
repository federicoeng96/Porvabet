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

**Betson (via diretta.it) e livescore.com sono stati valutati come fonti di
quote pre-match e restano entrambi non implementati, per motivi diversi** (v.
`DATA_SOURCES.md`): Betson/diretta.it ha un override esplicito dell'utente sui
ToS (categoria C, divieto assoluto, nessuna eccezione per uso personale), ma
resta bloccato da un limite tecnico di questo ambiente (nessun browser
headless funzionante attraverso il proxy di rete di questa sessione, verificato
contro host arbitrari, non solo diretta.it) — le quote esistono e sono state
confermate dal vivo, ma non c'è un percorso di codice funzionante per leggerle.
livescore.com (auditato indipendentemente come backup, gruppo societario
diverso) mostra le proprie quote solo dietro un sistema di widget
affiliati con gate paese/utente (`isAdult`/`notSelfExcluded`/`hasBetFeatures`)
mai osservato con dati reali in questa sessione. `FallbackOddsProvider`
(`app/providers/base/odds_provider_chain.py`) implementa la logica di
fallback tra le fonti in modo che, quando una verrà completata/verificata,
si inserisca senza modificare i chiamanti.

**Betfair Exchange cambia questo quadro** (v. DATA_SOURCES.md, categoria
`D_OFFICIAL_API_PERSONAL_ACCOUNT`): non è una fonte scraped, è l'API
ufficiale Betting di Betfair usata tramite l'account personale dell'utente —
nessun rischio ToS da valutare. `BetfairExchangeOddsProvider`
(`app/providers/betfair/provider.py`) è implementato, testato (contro un
client finto costruito con le classi di risorse reali di
`betfairlightweight`) e **ora collegato al Decision Layer**:
`run_analysis_for_match` (`analysis_runner.py`) interroga
`build_default_odds_provider_chain()` — Betfair per primo, come qui
raccomandato — per ogni partita non ancora `FINISHED`, e persiste quanto
trovato come `OddsQuote` (`ingest_live_odds_quotes` in
`match_ingestion.py`), creando `Market`/`MarketOutcome` al volo se
mancano. Le credenziali reali dell'utente sono configurate, ma **la
verifica contro l'API live resta da fare fuori da questa sandbox**: il
login stesso (non solo le chiamate autenticate) è bloccato da un WAF
Cloudflare geografico/anti-frode sull'IP di questo ambiente, stesso
risultato con credenziali finte e reali — confermato funzionante da un IP
italiano dall'utente (v. DATA_SOURCES.md, RUNNING_LOCALLY.md). Questo è un
limite di rete della sandbox, non del codice o delle credenziali.

**The Odds API aggiunge una seconda fonte quote reale e funzionante, questa
volta raggiungibile da questa stessa sandbox** (v. DATA_SOURCES.md,
categoria `E_COMMERCIAL_AGGREGATOR_API`): un aggregatore commerciale
di terze parti (relay di Betfair Exchange + altri bookmaker), non la fonte
ufficiale come Betfair — da qui la nuova categoria, distinta da D.
`TheOddsApiOddsProvider` (`app/providers/the_odds_api/provider.py`) è
collegato a `build_default_odds_provider_chain()` **dopo** Betfair (budget
gratuito limitato a 500 crediti/mese, riservato come fallback — v.
DATA_SOURCES.md per il calcolo completo). A differenza di Betfair,
`api.the-odds-api.com` **non è bloccato dalla rete di questa sandbox**
(verificato: risponde con un errore JSON pulito anche con una chiave non
valida, non un blocco Cloudflare) — manca solo una chiave gratuita reale
(richiede una registrazione con email propria, v. DATA_SOURCES.md per le
istruzioni esatte), non una verifica dal computer dell'utente.

Conseguenza architetturale, aggiornata: finché `EPlay24OddsProvider`,
`BetsonDirettaOddsProvider` e `LivescoreOddsProvider` restano interfacce
senza implementazione funzionante, e sia `BetfairExchangeOddsProvider` sia
`TheOddsApiOddsProvider` restano collegati ma non verificati dal vivo per
mancanza di credenziali/chiave (non per un blocco tecnico o ToS — v.
`app/providers/eplay24/`, `app/providers/betson_diretta/`,
`app/providers/livescore/`, `app/providers/betfair/`,
`app/providers/the_odds_api/`), questo progetto è, di fatto, **un motore di
stima (probabilità + quota fair), non ancora un motore di value betting
verificato contro un book reale in tempo reale** — ma per la prima volta ha
**due** fonti quote reali per cui manca "solo" una chiave/verifica dal vivo,
non anche un blocco tecnico o ToS, e una delle due (The Odds API) è
verificabile anche da questa stessa sandbox non appena esiste una chiave.
Il "value" e
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

## ⚠️ Limite d'ambiente: nessun browser headless funzionante in questa sessione

Verificato empiricamente in questa sessione (non un'assunzione): il proxy di
rete di questo ambiente sandboxato (`$HTTPS_PROXY`, v.
`/root/.ccr/README.md`) azzera l'handshake TLS per qualsiasi host esterno
raggiunto tramite un motore browser reale (Playwright/Chromium, il binario è
installato e disponibile) — non un blocco specifico di un sito: verificato
con la stessa identica firma di errore anche contro google.com e
accounts.google.com. Richieste HTTP semplici (`httpx`/`curl`) attraverso lo
stesso proxy funzionano normalmente — è solo l'handshake TLS del motore
browser a fallire.

Conseguenza pratica: ogni fonte dati la cui parte rilevante viene renderizzata
solo lato client (richiede JS eseguito da un browser reale, non solo un fetch
HTTP) **non è implementabile in questa sessione**, anche quando i ToS lo
permetterebbero — non per scelta di prodotto, ma per questo limite di
infrastruttura. Due casi reali di questa sessione: le quote pre-match di
Betson (via diretta.it) e i moduli/titolari/ballottaggi di FantaLab (v.
`DATA_SOURCES.md` per entrambi). Se in futuro questo limite viene rimosso
(un ambiente/sessione dove Playwright raggiunge davvero internet), queste
fonti vanno riverificate da capo prima di essere implementate — questo
documento non deve essere trattato come prova che siano permanentemente
irraggiungibili.

## LineupProvider/TacticalProvider — stato per FantaLab (**ACCANTONATO**)

**Decisione esplicita dell'utente: FantaLab è accantonato per complessità/
rischio di autenticazione (AWS Cognito + login Premium automatizzato), non
per un divieto ToS** — nessuna clausola ToS anti-scraping è mai stata trovata
per questa fonte (v. DATA_SOURCES.md). Questo lo distingue esplicitamente
dagli accantonamenti "categoria C per ToS" delle altre fonti (diretta.it/
Betson, legaseriea.it): qui il limite è tecnico/di rischio-account, non
legale. L'utente ha rifiutato di autorizzare l'automazione del login, non
la legittimità della fonte in sé.

L'interfaccia `LineupProvider` (`app/providers/base/lineup_provider.py`) è già
usata da `SosFantaLineupProvider`/`GazzettaLineupProvider` (probabili
formazioni, entrambi stub non implementati, confermati categoria C con
motivo concreto — v. sezione dedicata sotto) e ora anche da
`CorriereDelloSportLineupProvider` (implementazione reale, v. sotto).
**Nessuna classe FantaLab è stata aggiunta**: l'audit tecnico (v. `DATA_SOURCES.md`) ha trovato che i dati
reali (moduli, titolari, tiratori di rigori/punizioni — da collegare in
futuro al modulo palle inattive esistente, v. MODEL_SPEC.md set-piece —
ballottaggi, focus allenatori Premium) risiedono dietro un Firebase Realtime
Database autenticato, con un login utente che passa per un sistema di
identità diverso (AWS Cognito) il cui ponte verso Firebase non è verificabile
da analisi statica. Implementarlo richiederebbe login Premium reale
automatizzato via browser — bloccato anche dal limite della sezione sopra —
oltre a una decisione esplicita dell'utente sul rischio verso il proprio
account (categoria di rischio distinta, mai stata necessaria finora in questo
progetto). Nessuna implementazione è stata tentata; l'audit è stato segnalato
invece di essere risolto unilateralmente.

## CorriereDelloSportLineupProvider — reale, testato, non ancora collegato all'analisi live

`app/providers/corriere_dello_sport/provider.py` è un `LineupProvider` reale
(categoria B, Serie A) che legge `GET /probabili-formazioni/calcio/serie-a`
(HTML server-renderizzato, dati Opta, verificato dal vivo — v.
DATA_SOURCES.md) e restituisce il modulo tattico per squadra una volta che
la fonte lo ha annunciato — mai un placeholder prima di allora. **Limite
esplicito nel design**: `player_names_starting` è sempre `[]` — questa fonte
non espone nomi di giocatori, solo il modulo, quindi non deve essere trattata
come fonte per probabili titolari/tiratori/ballottaggi a livello di singolo
giocatore (v. docstring del modulo e DATA_SOURCES.md per il perché nessun'altra
fonte auditata in questa sessione copre quel livello di dettaglio in modo
affidabile). Come `SosFantaLineupProvider`/`GazzettaLineupProvider`, questo
provider non è ancora collegato a `run_analysis_for_match` — l'interfaccia
`LineupProvider` non è consumata da nessun punto dell'engine live in questo
progetto (la logica di riconciliazione in
`app/engine/decision/lineup_reconciliation.py` esiste ed è testata, ma non è
ancora chiamata da nessun runner) — collegarla è un passo successivo, non
fatto in questo turno perché non esplicitamente richiesto.

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
