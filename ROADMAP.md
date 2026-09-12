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
11. ✅ **Corner e cartellini**: ingestione reale (colonne HC/AC/HY/AY/HR/AR/HF/AF,
    prima lette dal parser ma scartate silenziosamente — bug corretto),
    `PoissonCountModel` dedicato (attacco/difesa, senza correzione arbitro —
    nessun dato arbitro ancora ingerito), stime esposte via API/frontend come
    "solo probabilità, nessuna quota" (football-data.co.uk non pubblica quote
    per questi mercati — limite strutturale, non implementativo, v. MODEL_SPEC.md),
    backtest reale con hit rate 56-69% ma overconfidence marcata nelle code
    (v. BACKTEST_SPEC.md).
12. ✅ **Binomiale negativa testata contro Poisson** (`NegativeBinomialCountModel`),
    stesso backtest reale, stesso periodo: migliora marginalmente Brier/log
    loss ma **non risolve in modo consistente** l'overconfidence nelle code
    alte (v. BACKTEST_SPEC.md, confronto completo). Decisione basata sui dati:
    **Poisson resta il modello di produzione**, NB resta nel codice come
    alternativa testata, non attivata — non un'assunzione a priori.
13. ✅ **Persistenza reale dei risultati di backtest** (`app/backtest/persistence.py`
    + `scripts/persist_backtest_results.py`): 8 righe `ModelVersion`/`Backtest`
    scritte in DB per EPL+Serie A × {MATCH_RESULT, TOTAL_GOALS, CORNERS,
    CARDS}, dagli stessi backtest reali già in BACKTEST_SPEC.md (v. punto 1
    sotto per il dettaglio e per cosa resta aperto).
14. ✅ **`model_reliability` reale** (`app/engine/decision/reliability.py`):
    non più il placeholder 0.5, deriva dal gap di calibrazione della riga
    `Backtest` più recente per mercato/competizione, fail-conservative (0.0)
    quando non stimabile con confidenza — mai un numero indovinato.
15. ✅ **Calibrazione post-hoc (Platt/isotonica) testata, non attivata**
    (v. punto 3 sotto per il dettaglio): terzo tentativo indipendente che non
    risolve l'overconfidence nelle code alte in modo consistente.

## Prossimi passi concreti (in ordine di valore/dipendenza)

### 1. ✅ Persistere i risultati di backtest
`app/backtest/persistence.py` (`persist_backtest_run`) aggrega l'output già
prodotto da `run_walk_forward_backtest`/`run_count_market_backtest` con
`app/backtest/metrics.py` e scrive una riga `ModelVersion` + `Backtest` (test
in `tests/test_backtest_persistence.py`). Eseguito realmente con
`scripts/persist_backtest_results.py` sugli stessi dati/stagioni già in
BACKTEST_SPEC.md (EPL + Serie A, 2019/20–2024/25): 8 righe reali ora in DB
(`MATCH_RESULT`/`TOTAL_GOALS` con Dixon-Coles, `CORNERS`/`CARDS` con
`PoissonCountModel`, il modello di produzione — v. punto 12). Nessun numero
nuovo rispetto a BACKTEST_SPEC.md, solo la stessa evidenza ora interrogabile
dal DB invece che riportata solo a mano.

**Non ancora fatto** (fuori scope per questo item, esplicitamente rimandato):
collegare `model_reliability` reale (letto da queste righe `Backtest`)
nell'endpoint di analisi live — oggi `analysis_runner.py` usa ancora
`model_reliability=0.5` come placeholder neutro. Questo richiede decidere
quale riga `Backtest` è "quella corrente" per un dato mercato/competizione
(la più recente? quella con la finestra più ampia?) — una domanda di design
non ancora affrontata, non solo una query.

### 2. ✅ Ricalibrare il refit più frequente su tutte le stagioni
Eseguito: `refit_batch_days=7` (default) su tutte e 10 le stagioni disponibili
(3.800 partite per campionato, EPL+Serie A). Confronto completo in
BACKTEST_SPEC.md — **corretto un errore di etichettatura**: il confronto
isola solo l'effetto stagioni (6→10) a refit=7 fisso, non refit 21→7 come
scritto in una prima stesura (v. BACKTEST_SPEC.md per il dettaglio). Risultato
onesto: Brier/log loss migliorano leggermente su tutti i segmenti (atteso,
più stagioni di storia), il gap di calibrazione nel bin 0.9-1.0 si dimezza per
l'EPL ma resta ampio per la Serie A (n piccolo in entrambi i casi, 38-50 —
parte del miglioramento può essere rumore campionario) — la ricalibrazione
**non risolve da sola** l'overconfidence nelle code alte, coerente con la
conclusione già raggiunta per corner/cartellini (punto 4 sotto): serve
calibrazione post-hoc (punto 3 sotto) o feature aggiuntive, non solo più dati
di allenamento.

### 3. ✅ Calibrazione dei pesi/soglie/probabilità — Platt/isotonica testate, non attivate
Entrambe implementate (`app/engine/decision/calibration.py`) e backtestate
senza leakage su tutti gli 8 segmenti reali (v. BACKTEST_SPEC.md). Risultato
onesto: nessuna delle due migliora la calibrazione nelle fasce alte in modo
consistente tra segmenti — un miglioramento reale (Serie A MATCH_RESULT) e
peggioramenti netti altrove (EPL CARDS/TOTAL_GOALS) nello stesso esperimento.
**Decisione basata sui numeri**: nessuna delle due attivata in produzione;
`fair_odds()` continua a usare la probabilità grezza del modello. Terzo
tentativo indipendente (dopo NB e più stagioni) che non risolve
l'overconfidence — rafforza l'ipotesi che il problema sia nella struttura
media (feature mancanti), non nella forma/calibrazione della probabilità.
`risk_score.WEIGHTS` e `value.ALERT_THRESHOLD_*` restano punti di partenza
espliciti, non ancora ricalibrati sul backtest reale (nessuna analisi
tentata finora su questo punto specifico — resta aperto).

### 4. Corner/cartellini: la binomiale negativa non basta — serve la feature arbitro (e altre)
✅ Testata (v. punto 12 sopra): non risolve l'overconfidence nelle code alte in
modo consistente. **Conclusione aggiornata**: il problema non sembra essere
principalmente la forma Poisson-vs-NB della distribuzione, ma l'assenza di
feature esplicative nella struttura media attacco/difesa — in primis
l'arbitro per i cartellini (bloccato dall'assenza di dati arbitro, v. punto 5
sotto per AIA-FIGC/PGMOL) e feature tattiche per i corner (v. punto 6 sotto).
Un'ipotesi più mirata da testare in futuro: dispersione NB **per singola
squadra** invece che condivisa — non ancora provata, dato che il condiviso
non ha aiutato abbastanza.
Il mercato falli (dati già ingeriti, `TeamMatchStats.fouls_committed`) non
ha ancora un modello/mercato dedicato — i falli non sono tipicamente un
mercato scommesse standalone come corner/cartellini, priorità bassa.

### 5. ⚠️ Feature tattiche misurabili (Matchup Engine) — bloccato su entrambe le fonti candidate, verificato in questa sessione
Il data model (`TacticalFeature`) e la lista di feature del brief
(crosses_per_90, PPDA, progressive_passes, ecc.) sono già previsti nello
schema. Le due fonti candidate per l'estrazione reale sono state **testate
con rete reale in questa sessione, per la prima volta** (i loro provider
erano scritti ma mai eseguiti contro il sito vero — i rispettivi docstring lo
segnalavano esplicitamente):
- **understat.com**: il sito risponde (200), ma la sua struttura interna è
  cambiata — la pagina non incorpora più i dati come JSON in uno `<script>`
  (`UnderstatProvider.parse_dates_data` cerca `var datesData = JSON.parse(...)`,
  non più presente); il sito ora carica i dati via JavaScript lato client
  dopo il caricamento. Il parser attuale **non funziona**.
- **fbref.com**: bloccato da Cloudflare (403, sfida JavaScript anti-bot)
  prima ancora di arrivare al contenuto — il limite di 10 richieste/minuto
  dichiarato da fbref non è il problema, è un blocco a monte.
- **StatsBomb Open Data**: già verificato e già escluso in DATA_SOURCES.md —
  copre solo stagioni storiche isolate (2015/16 e più vecchie), non la
  stagione corrente, quindi utile solo per validazione metodologica futura,
  mai come feed reale.

**Nessuna fonte candidata produce oggi dati tattici reali estraibili senza
altro lavoro.** Sbloccare understat richiederebbe reverse-engineering del suo
nuovo meccanismo di caricamento dati (endpoint interno non documentato,
lavoro non banale e fragile). Sbloccare fbref richiederebbe un browser reale
(es. Playwright) per superare la sfida Cloudflare — una scelta tecnica più
pesante e più vicina al confine dell'elusione di anti-bot, che **non è stata
presa autonomamente**: richiede una decisione esplicita dell'utente su se e
come procedere. Fino ad allora, l'entity-resolution cross-provider
(`canonicalize_team_name`, oggi solo normalizzazione lessicale semplice) resta
un rafforzamento prematuro — non ha senso costruirla prima di avere una
seconda fonte reale da collegare.

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
- ✅ **Endpoint batch per "AGGIORNA ANALISI"**: `POST /matches/analyze-batch`
  (`app/api/routers/matches.py`) esegue `run_analysis_for_match` per un
  elenco di `match_id` (o su tutte le partite se omesso) in un'unica
  richiesta, con commit/rollback per singola partita — un fallimento
  (es. `InsufficientDataError`) non blocca le altre. Frontend aggiornato
  (`analyzeMatchesBatch` in `lib/api.ts`, usato da `page.tsx`) a fare una
  sola chiamata invece di N parallele. Testato end-to-end con dati reali
  (curl contro il DB dev, 3 partite reali) oltre che con test API sintetici
  (`tests/test_matches_api.py`, incluso il caso limite id sconosciuto).
  Verifica di rendering nel browser non eseguita (nessun Playwright/browser
  driver installato in questo repo) — verificato invece `tsc --noEmit` pulito
  e il contratto JSON confermato identico lato backend/frontend.
- ⚠️ **Persistenza lato server della schedina — non implementata, ambiguità
  reale non risolvibile leggendo la documentazione esistente.** Valutato in
  questa sessione: la "schedina" oggi non è una lista che l'utente compone
  (nessun pulsante "aggiungi"/"rimuovi") — è una vista **derivata** dallo
  stato client (`groupRisk`/`perMatchRisk` in `page.tsx`, "qual è la
  selezione principale per il livello di rischio scelto, per ogni partita
  visibile ora"). Persisterla lato server richiederebbe decisioni di
  prodotto non specificate da nessuna parte: cosa si salva esattamente (le
  preferenze di rischio? le selezioni risolte in quel momento, che possono
  cambiare a ogni "AGGIORNA ANALISI"?), e soprattutto **non esiste alcun
  modello utente/sessione in questo progetto** (nessuna tabella `User`,
  nessuna autenticazione) — servirebbe inventarne uno da zero solo per capire
  "di chi" è la schedina da salvare. Il brief non richiede una cronologia
  scommesse e ROADMAP.md lo trattava già come condizionale ("se servisse").
  Non implementato autonomamente: è esattamente il tipo di ambiguità che
  richiede una decisione esplicita, non un'assunzione.
