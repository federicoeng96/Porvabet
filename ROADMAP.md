# Roadmap

Stato reale al termine di questo primo vertical slice (non un piano ideale —
riflette cosa è già fatto e cosa manca davvero).

## Fatto in questo slice

1. ✅ Architettura + analisi di fattibilità fonti dati (`ARCHITECTURE.md`,
   `DATA_SOURCES.md`), incluso l'accesso a ePlay24 (non disponibile).
2. ✅ Data model completo (26 tabelle) + migrazioni Alembic, Postgres.
3. ✅ 5 interfacce provider astratte + implementazioni reali per le fonti di
   categoria A raggiungibili senza rischio legale (football-data.co.uk,
   API-Football, understat, fbref, Open-Meteo, RSS generico) + stub
   esplicitamente flaggati per le fonti di categoria B (WhoScored, SofaScore) e
   C (ePlay24, legaseriea.it, SOS Fanta, Gazzetta).
4. ✅ Statistical Engine: Dixon-Coles Poisson (1X2, O/U, BTTS), pesatura
   temporale, vettorizzato per scalare su migliaia di partite.
5. ✅ Decision Layer: fair odds, value/EV, alert a soglia (provvisoria),
   risk score 1–10 come combinazione dinamica, selezione 1 principale + 2
   alternative per livello.
6. ✅ Backtest walk-forward senza leakage, con metriche complete per segmento.
7. ✅ Frontend: tabella con le colonne richieste, rischio di gruppo e per
   partita senza ricalcolo, schedina automatica con quota totale, popover
   alert.
8. ✅ Test automatici (38, tutti su dati sintetici chiaramente etichettati) +
   lint pulito.

## Prossimi passi concreti (in ordine di valore/dipendenza)

### 1. Ingestione reale (bloccante per tutto il resto)
Eseguire `FootballDataCoUkProvider` da un ambiente con accesso di rete normale
contro le stagioni storiche reali di Premier League e Serie A, verificare
manualmente il primo lotto (conteggio righe, spot-check quote), poi scrivere
uno script di ingestione bulk analogo a `scripts/seed_dev_fixture.py` ma contro
dati reali (`scripts/ingest_football_data.py`, da creare).

### 2. Persistere i risultati di backtest
Oggi `run_walk_forward_backtest` produce predizioni in memoria; manca il
codice che le aggrega con `app/backtest/metrics.py` e scrive una riga
`Backtest` (tabella già nello schema). Necessario prima di poter collegare
`model_reliability` reale (da backtest, non valore neutro) nell'endpoint di
analisi live.

### 3. Calibrazione dei pesi/soglie
`risk_score.WEIGHTS`, `value.ALERT_THRESHOLD_*`, `dixon_coles.xi` sono tutti
punti di partenza espliciti — da ricalibrare sul backtest reale (punto 1+2),
non prima.

### 4. Corner, cartellini, falli (mercati team)
Richiede: (a) dati storici corner/cartellini per partita (già nel data model,
`TeamMatchStats`, non ancora ingeriti da nessuna fonte reale), (b) un modello
dedicato (binomiale negativa, corretto per avversario e — per i cartellini —
per arbitro tramite `RefereeStats`). Vedi MODEL_SPEC.md.

### 5. Feature tattiche misurabili (Matchup Engine)
Il data model (`TacticalFeature`) e la lista di feature del brief
(crosses_per_90, PPDA, progressive_passes, ecc.) sono già previsti nello
schema; l'estrazione reale richiede fbref/understat/StatsBomb (per validazione
metodologica) collegati con join corretto sul nome squadra/giocatore — oggi
`canonicalize_team_name` fa solo una normalizzazione lessicale semplice, non
una vera risoluzione di entità cross-provider (da rafforzare quando si
aggiunge una seconda fonte oltre a football-data.co.uk).

### 6. Intelligence Engine
Interfaccia predisposta (`app/engine/intelligence/`, oggi vuota) — deve
produrre segnali/feature qualitativi (tattica, allenatori, news) che il layer
quantitativo valida con dati osservabili, mai probabilità dirette. Dipende dal
punto 5 per avere feature misurabili su cui ancorare le ipotesi qualitative.

### 7. Player props
Richiede: formazioni reali (probabile prima ufficiale, poi da fonti
concordi/discordanti — riconciliazione già implementata in
`lineup_reconciliation.py`, ma senza una fonte reale collegata oggi è
inutilizzata), un modello di minutaggio atteso, e un modello di produzione
individuale condizionato al minutaggio. Vedi MODEL_SPEC.md per la motivazione
di un modello dedicato invece di riusare Dixon-Coles per singolo giocatore.

### 8. Serie A
Il codice è già competition-agnostic (`competition_code` come parametro
ovunque) — aggiungere Serie A è principalmente un problema di ingestione dati
(football-data.co.uk copre già `I1`), non di riscrittura del motore.

### 9. Live Engine (solo architettura, non implementazione — come richiesto)
Vedi la sezione dedicata in `ARCHITECTURE.md`: `Match.status` include già
`IN_PLAY`, `AnalysisVersion` è già ripetibile nel tempo. Un vero motore live
aggiungerebbe un `LiveOddsProvider` e un modello in-play dietro le stesse
interfacce, senza refactoring del pre-match.

### 10. Frontend: rifiniture
- Endpoint dedicato per "AGGIORNA ANALISI" su tutte le partite in una singola
  chiamata batch invece di N chiamate parallele dal client (oggi funziona ma
  genera N round-trip).
- Persistenza lato server della schedina (oggi è stato automaticamente
  derivato dallo stato client, mai salvato — coerente col fatto che il brief
  non richiede una cronologia scommesse, ma se servisse andrebbe aggiunta una
  tabella dedicata).
