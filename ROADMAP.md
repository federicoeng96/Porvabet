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
16. ✅ **Audit fonti quote reali (diretta.it/Betson) e fonti xG gratuite**:
    diretta.it/Betson valutato per il Value/Odds Engine e classificato
    categoria C (v. DATA_SOURCES.md) — ToS vieta lo scraping senza eccezione
    per uso personale, quota di un bookmaker terzo in licenza display-only,
    non implementato. understat riparato (nuovo endpoint reale) e
    riclassificato categoria B (robots.txt disallow-all) — prima estrazione
    xG/PPDA reale eseguita, 10.640 righe `TacticalFeature` (v. punto 5 sotto).
    Aggiunta nota permanente "uso esclusivamente personale" in
    README.md/DATA_SOURCES.md.
17. ✅ **Intelligence Engine — livello di validazione** (`app/engine/
    intelligence/signals.py` + `validation.py`, v. punto 6 sotto per il
    dettaglio): confronta un'ipotesi qualitativa con un cambiamento
    misurabile reale nelle `TacticalFeature`, fail-conservative quando non
    stimabile. Nessuna fonte reale di segnali ancora collegata — solo il
    meccanismo di validazione, non il generatore.

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

### 5. ✅ Feature tattiche misurabili (xG/PPDA via understat) — sbloccato, prima estrazione reale fatta
Il data model (`TacticalFeature`) e la lista di feature del brief
(crosses_per_90, PPDA, progressive_passes, ecc.) sono già previsti nello
schema. Stato reale, dopo un audit completo delle fonti gratuite di xG
(decisione esplicita dell'utente: non aggirare Cloudflare/fbref; verificare
se understat è riparabile prima di scartarlo; controllare ClubElo e cercare
altre fonti reali):

- **understat.com — riparato e riclassificato B, ora la fonte reale.** Il
  cambio struttura del sito era **riparabile**, non un blocco definitivo: la
  pagina lega ora carica i dati via `GET /getLeagueData/{league}/{season}`
  (sessione via cookie, nessuna chiave) invece di incorporarli nell'HTML —
  `UnderstatProvider` riscritto per usare il nuovo endpoint, verificato con
  richieste reali (EPL+Serie A, 2023/24: 380 partite, 760 righe di stats
  tattiche). **Ma**: `robots.txt` disallowa tutto il sito (`Disallow: /`,
  nessuna eccezione) — fatto mai controllato quando fu classificato A in
  origine. Riclassificato **categoria B** (rischio accettato, uso personale),
  non più A — v. DATA_SOURCES.md per il dettaglio e il perché non è come le
  clausole ToS di WhoScored/SofaScore.
- **fbref.com**: bloccato da Cloudflare. **Decisione esplicita dell'utente:
  non aggirarlo** — resta non utilizzabile, non solo "in sospeso".
- **ClubElo**: verificato cosa offre davvero — rating Elo, non xG. Il
  sottodominio API pubblico non è stato raggiungibile in questa sessione
  (connessione TLS interrotta, ripetibile) — inconcludente se sia un blocco
  reale o un problema di questo ambiente sandboxato. Comunque non
  risolverebbe il gap xG anche se raggiungibile.
- **Nessuna altra fonte xG gratuita reale trovata** con una ricerca vera (non
  solo Kaggle/scraper di terze parti che ri-pubblicano gli stessi dati di
  understat, o servizi a pagamento) — understat resta, per fonti indipendenti,
  "una delle ultime fonti gratuite di xG" per questi campionati.

**Entity-resolution cross-provider**: mismatch reali trovati confrontando i
nomi squadra football-data.co.uk vs understat (Man City/Manchester City, Man
United/Manchester United, Newcastle/Newcastle United, Nott'm Forest/
Nottingham Forest, Wolves/Wolverhampton Wanderers, Milan/AC Milan) — risolti
con una mappa di alias esplicita e verificata (`UNDERSTAT_TEAM_NAME_ALIASES`
in `app/ingestion/match_ingestion.py`), non un matcher fuzzy generico: il
numero di club di massima serie è basso e finito, un alias hand-curated è più
onesto di un'euristica che potrebbe sbagliare silenziosamente. Un nome non
risolvibile (squadra mai ingerita da football-data.co.uk) viene saltato e
riportato esplicitamente (`scripts/ingest_understat_tactical_features.py`),
mai indovinato.

**Prima estrazione reale eseguita**: `scripts/ingest_understat_tactical_features.py`
ha scritto **10.640 righe reali** `TacticalFeature` (xG, xGA, npxG, npxGA,
PPDA, deep completions/deep completions allowed — window_matches=1, valore
grezzo per singola partita, non ancora una media mobile) per EPL+Serie A,
stagione 2023/24, 0 nomi squadra irrisolti. Scalare a tutte le 10 stagioni è
meccanico (stesso script, altre stagioni in `SEASONS`) ma non ancora eseguito
per tempo in questa sessione.

**Collegate al Decision Engine, backtestate, decisione basata sui numeri**
(v. MODEL_SPEC.md/BACKTEST_SPEC.md per il dettaglio):
- Correzione xG su Dixon-Coles: migliora davvero l'EPL, non aiuta la Serie A
  → non attivata di default per nessuno dei due.
- Correzione corner da deep completions (correlazione reale confermata prima
  di costruire nulla: r=+0.447 con i corner) su `PoissonCountModel`: peggiora
  la previsione su ogni metrica, entrambi i campionati → scartata, non
  attivata.
Entrambe restano nel codice, testate, non collegate al layer di analisi live.

**Cosa resta esplicitamente aperto** (non fatto in questa sessione):
- Aggregazione a finestra mobile no-leakage (window_matches>1) — quale
  finestra, quale aggregazione, è una vera decisione di design, meglio presa
  quando un consumatore reale (Matchup/Intelligence Engine, punto 6 sotto) ne
  ha bisogno che indovinata ora.
- Estensione alle altre 9 stagioni disponibili.
- crosses_per_90/progressive_passes (non in understat, servirebbero fbref o
  un'altra fonte — bloccati dagli stessi motivi sopra).

### 6. ✅ Intelligence Engine — livello di validazione costruito, ancora senza una fonte di segnali reale
`app/engine/intelligence/` non è più vuoto: `signals.py` definisce
`IntelligenceSignal` (una ipotesi qualitativa su una squadra — soggetto,
categoria, testo libero, data, fonte) e `validation.py` implementa
`validate_tactical_shift_signal`, che confronta la media di una feature
`TacticalFeature` reale (xG/PPDA/deep completions da understat, v. punto 5)
in una finestra prima/dopo la data del segnale, e dice se il cambiamento
supera una soglia — **mai indovinato**: sotto una soglia minima di
osservazioni per finestra (3) o con media-prima pari a zero, ritorna
esplicitamente "non stimabile" (`supported=None`), stesso pattern
fail-conservative di `reliability.py`. Deliberatamente **non** interpreta la
direzione attesa del cambiamento (es. "più pressing → PPDA più basso") — quella
lettura resta di chi legge il testo del claim, non della funzione.

**Cosa NON è stato costruito, esplicitamente**: nessuna fonte reale produce
`IntelligenceSignal` oggi — non un feed news, non una pipeline di analisi
LLM, non un'interfaccia di inserimento manuale. `IntelligenceSignal` è
volutamente una dataclass in memoria, non una tabella persistita: persistere
una forma mai esercitata da un vero produttore di segnali sarebbe uno schema
DB indovinato, non progettato. Nessuna nuova migrazione Alembic in questo
slice. Solo una categoria (`TACTICAL_SHIFT`) ha un percorso di validazione —
`NEWS_EVENT`/cambio allenatore, menzionati nel brief, non hanno ancora un
controllo a dati osservabili implementato, quindi non sono nemmeno elencati
come categorie valide finché non ne esiste uno.

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
- ⚠️ **Rivalutazione colonna ALERT (Data/Ora | Partita | Risk | Selezione |
  Quota | Probabilità | Quota Modello | Info | Value | 🚨) — ancora non
  sbloccata.** Verificato in questa sessione dopo il tentativo di
  implementare Betson (via diretta.it) e livescore.com come fonti di quote
  pre-match reali per partite future (v. DATA_SOURCES.md, ARCHITECTURE.md):
  **nessuna delle due fornisce oggi quote reali** — entrambe sono stub
  verificati-bloccati (non "non ancora implementati per pigrizia"), per un
  limite tecnico di questo ambiente (nessun browser headless funzionante
  attraverso il proxy di rete di questa sessione) e, per livescore.com, anche
  per la natura dei dati stessi (widget di quote gated dietro consenso,
  bookmaker mai osservato dal vivo). Di conseguenza **la premessa del punto 3
  del brief di questo turno non si è verificata**: non ci sono quote
  pre-match reali disponibili per calcolare edge/value su partite future, e
  la colonna ALERT resta nello stesso stato di prima — vuota/non popolabile
  con dati reali per partite non ancora giocate, mai con dati finti. Se in
  futuro uno dei due `OddsProvider` verrà davvero completato (richiede prima
  che il limite del browser headless sia risolto — v. ARCHITECTURE.md), va
  ripreso da qui: a quel punto costruire il frontend per la colonna ALERT
  avrebbe un motivo concreto, cosa che oggi ancora non ha.
