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
9. ✅ **Ingestione reale**: 7.600 partite reali (10 stagioni EPL + 10 Serie A,
   2015/16–2024/25) da football-data.co.uk via `scripts/ingest_football_data.py`,
   con correzione del parser per distinguere quote pre-chiusura da chiusura vera
   (scoperta verificando lo schema colonne reale, non ipotizzato).
10. ✅ **Backtest walk-forward su dati reali** (EPL + Serie A, 2019/20–2024/25):
    risultati completi in `BACKTEST_SPEC.md` — proprietà di ranking del rischio
    confermata (hit rate 60%→20% dal Risk 1 al 10), ROI onestamente negativo con
    il modello attuale, calibrazione buona nelle fasce centrali ma overconfident
    nelle code alte.

## Prossimi passi concreti (in ordine di valore/dipendenza)

### 1. Persistere i risultati di backtest
Il backtest reale (punto 10 sopra) è stato eseguito con uno script ad-hoc e i
risultati riportati manualmente in BACKTEST_SPEC.md — manca ancora il codice
che aggrega l'output di `run_walk_forward_backtest` con
`app/backtest/metrics.py` e lo scrive in una riga `Backtest` (tabella già nello
schema). Necessario prima di poter collegare `model_reliability` reale (da
backtest, non valore neutro) nell'endpoint di analisi live.

### 2. Ricalibrare il refit più frequente su tutte le stagioni
Il backtest reale eseguito usa `refit_batch_days=21` su 6 stagioni per
restare in tempi ragionevoli in questa sessione; un run con la finestra di
refit di default (7 giorni) su tutte le 10 stagioni disponibili darebbe una
stima leggermente più precisa. Richiede solo tempo di calcolo (nessun limite
tecnico), da eseguire su un ambiente con più tempo/risorse a disposizione.

### 3. Calibrazione dei pesi/soglie/probabilità
Il backtest reale mostra overconfidence nelle probabilità alte (bin 0.9-1.0:
predetto 92.6%, osservato 71.4%) — una calibrazione post-hoc (Platt
scaling/isotonic regression) applicata dopo `fair_odds()` la correggerebbe.
`risk_score.WEIGHTS` e `value.ALERT_THRESHOLD_*` restano punti di partenza
espliciti, ora con un backtest reale (punto 10 sopra) su cui ricalibrarli.

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
✅ Già ingerita e analizzata insieme a Premier League (v. punti 9-10 sopra) —
il codice era già competition-agnostic (`competition_code` come parametro
ovunque), quindi non ha richiesto alcuna modifica al motore.

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
