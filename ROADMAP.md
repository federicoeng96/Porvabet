# Roadmap

Stato reale al termine di questo primo vertical slice (non un piano ideale —
riflette cosa è già fatto e cosa manca davvero).

## Quadro onesto: verificato con dati reali vs costruito vs bloccato

Richiesto esplicitamente dall'utente per capire dove siamo davvero, non solo
cosa esiste nel codice. Tre categorie, nessuna ambiguità tra "esiste" e
"verificato dal vivo":

**✅ Verificato end-to-end con dati reali** (non solo unit test/mock):
- Ingestione storica football-data.co.uk: 7.600 partite reali (EPL+Serie A,
  2015/16–2024/25), analisi/backtest/API/frontend testati su questi dati.
- Motore statistico (Dixon-Coles, `PoissonCountModel`): fit e predizioni
  reali su queste 7.600 partite **e, dal 13/09, su fixture reali future**
  (Man United–Man City, Napoli–Bologna: probabilità 1X2/O-U sensate, v.
  `VERIFICATION_LOG.md`).
- Backtest walk-forward a 10 stagioni, incluso il precompute a 10 livelli di
  rischio (`build_risk_ladder` dentro il loop, non solo metriche isolate per
  mercato) — hit rate/ROI/calibrazione reali in `BACKTEST_SPEC.md`.
- Soglie alert: ricalibrate sul backtest reale (74.100 predizioni risolte),
  non più valori provvisori dal brief — v. `BACKTEST_SPEC.md`.
- **`FootballDataOrgFixtureProvider`, 13/09**: prima ingestione autenticata
  reale (9 fixture EPL+Serie A della prossima giornata) — v. punto 1 sotto
  per il mismatch nomi squadra trovato e corretto in diretta.
- **Tentativo quota Betfair su una fixture reale, 13/09**: confermato di
  nuovo dal vivo (non riletto da documentazione precedente) lo stesso 403 —
  v. `VERIFICATION_LOG.md`.
- Corriere dello Sport (moduli tattici Serie A): verificato dal vivo contro
  la pagina reale, provider funzionante e testato — ma non ancora collegato
  a `run_analysis_for_match`/`lineup_reconciliation.py` (v. punto 7 sotto).
- **Decision Layer "n/d" anche quando NESSUN mercato ha una quota, 13/09**:
  il primo vero giro end-to-end con una fixture futura reale (Man United–Man
  City, Napoli–Bologna) aveva trovato che l'analisi si interrompeva con un
  errore invece di mostrare "n/d" quando letteralmente nessun mercato ha una
  quota da nessuna fonte (il caso normale per ogni fixture futura reale in
  questa sandbox) — comportamento preesistente e deliberatamente testato,
  non un bug introdotto quella notte, ma mai visto in azione prima. Decisione
  esplicita dell'utente: estendere lo stesso principio già in uso per "alcuni
  mercati senza quota" anche a questo caso limite, nessuna eccezione speciale.
  Implementato e ri-verificato con le stesse due fixture reali: la risk ladder
  a 10 livelli ora si costruisce sempre, Value/Alert "n/d" ovunque manchi una
  quota, mai un prezzo inventato — v. `VERIFICATION_LOG.md` sezione 7 per il
  dettaglio completo (redistribuzione del peso rischio quando l'odds non
  esiste, `additional_estimates` ridotto a CORNERS/CARDS per non duplicare,
  audit dell'intero codebase per assunzioni simili).
- `BetfairExchangeOddsProvider`: login/richiesta reale confermati di nuovo
  il 13/09 contro una fixture reale — bloccato dalla rete della sandbox
  (v. bloccato sotto), non dal codice.

**🔨 Costruito e testato con mock/dati sintetici, mai verificato dal vivo**:
- Intelligence Engine (`app/engine/intelligence/`): livello di validazione
  costruito e testato, nessuna fonte reale di segnali collegata.

**⛔ Bloccato, con motivo verificato (non solo "non ancora fatto")**:
- Copertura Betfair per corner/cartellini: **ri-audit — i mercati Exchange
  esistono davvero** (confermato con fonti reali indipendenti, non più solo
  un indizio circostanziale — v. `DATA_SOURCES.md`), ma il codice esatto del
  market type resta bloccato dalla stessa documentazione ufficiale
  irraggiungibile da qui. Costruito invece un meccanismo di discovery reale
  (`discover_market_types_for_match` + `scripts/discover_betfair_market_types.py`)
  che chiede a Betfair stesso quali mercati esistono per ogni fixture, senza
  indovinare nulla — resta da eseguire dal computer dell'utente per ottenere
  il codice reale e collegarlo.
- Player props: nessuna fonte gratuita trovata con formazioni a livello di
  singolo giocatore in forma strutturata e a rischio accettabile (Gazzetta/
  BBC categoria C con divieto esplicito; Sky Italia bloccata tecnicamente;
  Sky UK/SOS Fanta senza struttura affidabile) — v. punto 7 sotto per il
  dettaglio completo, riverificato stanotte su richiesta esplicita.
- ePlay24, fbref.com, Gazzetta dello Sport, BBC Sport, legaseriea.it:
  bloccati/vietati, per motivi diversi e già documentati per ciascuno in
  `DATA_SOURCES.md` — nessuna decisione presa di aggirarli.
- Feature arbitro per il modello cartellini (AIA-FIGC, `pgmol.com`):
  riverificata dal vivo stanotte, entrambe bloccate a livello di rete da
  questa sandbox (sfida Cloudflare / connessione azzerata, stesso pattern
  di fbref.com/betfair.com) — v. punto 4 sotto e `DATA_SOURCES.md` per il
  dettaglio, incluso perché la SPA di premierleague.com non è stata
  perseguita come alternativa (richiederebbe un audit ToS dedicato della
  sua API interna, mai fatto finora).
- xG-adjusted Dixon-Coles e correzione corner da deep completions: testate
  su dati reali (10 stagioni), **correttamente non attivate** perché i
  numeri reali non giustificano l'attivazione — non "bloccate", una
  decisione presa sui dati.

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
18. ✅ **Betfair Exchange collegato al Decision Layer** (categoria D,
    credenziali reali configurate) — 1X2 e O/U 2.5, rinnovo automatico
    sessione, mai testato dal vivo per un blocco di rete dell'intera
    sandbox (non un problema di credenziali/codice — v. `DATA_SOURCES.md`/
    `RUNNING_LOCALLY.md`). Corner/cartellini restano "n/d": indagati a
    fondo, non verificabili da questa sandbox (v. punto sotto).
19. ✅ **"n/d" esplicito invece di riga saltata, anche quando NESSUN mercato
    ha una quota + fixture future reali**: il Decision Layer mostra sempre
    probabilità/quota-modello per MATCH_RESULT/TOTAL_GOALS (mai una riga
    assente, mai un prezzo inventato — v. `NoOddsEstimateOut`/`SelectionOut`).
    Un giro reale il 13/09 aveva trovato un caso limite non coperto: quando
    NESSUN mercato ha una quota da nessuna fonte, l'analisi si interrompeva
    con un errore invece di mostrare "n/d" ovunque — comportamento
    preesistente reso visibile per la prima volta da una fixture vera, non
    un bug di quella notte. Su decisione esplicita dell'utente, generalizzato:
    ora la risk ladder si costruisce sempre, priced o no, con lo stesso
    principio già in uso — v. `VERIFICATION_LOG.md` sezione 7 per il dettaglio
    completo (implementazione, audit di coerenza, ri-verifica con le stesse
    fixture reali). `FootballDataOrgFixtureProvider`
    (categoria A) popola la prossima giornata reale Premier League/Serie A —
    **testato dal vivo con una chiamata autenticata reale il 13/09** (9
    fixture EPL+Serie A ingerite, chiave risolta — v. `VERIFICATION_LOG.md`
    per la causa del mismatch di nome che l'aveva bloccata prima). Il
    precompute dei 10 livelli di rischio (1 principale + 2 alternative,
    `build_risk_ladder`) e la sua simulazione nel backtest walk-forward
    (hit rate/ROI per livello, v. `BACKTEST_SPEC.md`) **erano già entrambi
    implementati e testati prima di questa nota** — verificato di nuovo
    direttamente nel codice, non solo a memoria, prima di dichiararli
    "fatti".
20. ✅ **Soglie alert ricalibrate sul backtest reale**: bucket di
    `discrepancy_pct` sulle 74.100 predizioni risolte del backtest a 10
    stagioni mostrano hit rate/ROI **monotonicamente peggiori** al crescere
    della discrepanza (39,5%→22,2% hit rate, ROI da -3,0% a -14,6%) — il
    contrario dell'assunzione implicita del brief originale (discrepanza
    grande = opportunità). `ALERT_THRESHOLD_STRONG` spostata da 0.15 a 0.20
    (punto di rottura reale nei dati), `ALERT_THRESHOLD_INTERESTING`
    confermata a 0.10 (nessun punto di rottura pulito), testo di
    `classify_alert`/`AlertPopover.tsx` corretto per non parlare più di
    "opportunità"/mispricing ma di segnale di cautela — v. `BACKTEST_SPEC.md`
    "Calibrazione soglie alert su dati reali" per la tabella completa.

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
`value.ALERT_THRESHOLD_*` **ricalibrate stanotte** sul backtest reale
(74.100 predizioni risolte): STRONG spostata da 0.15 a 0.20 dove i dati
mostrano il vero punto di rottura, INTERESTING confermata a 0.10 (nessun
punto di rottura pulito nei bucket più bassi) — v. `BACKTEST_SPEC.md`
"Calibrazione soglie alert su dati reali" per la tabella completa. Il
significato di STRONG è anche stato corretto: il backtest mostra che una
discrepanza maggiore correla con hit rate/ROI **peggiori**, non con
un'opportunità — è un segnale di cautela, non di value, sia nel testo
che nel codice/frontend. `risk_score.WEIGHTS` resta invece un punto di
partenza esplicito, non ancora ricalibrato sul backtest reale (nessuna
analisi tentata finora su questo punto specifico — resta aperto).

### 4. Corner/cartellini: la binomiale negativa non basta — serve la feature arbitro (e altre)
✅ Testata (v. punto 12 sopra): non risolve l'overconfidence nelle code alte in
modo consistente. **Conclusione aggiornata**: il problema non sembra essere
principalmente la forma Poisson-vs-NB della distribuzione, ma l'assenza di
feature esplicative nella struttura media attacco/difesa — in primis
l'arbitro per i cartellini e feature tattiche per i corner (v. punto 6 sotto).

**Feature arbitro: riverificata in questa sessione, resta bloccata per un
motivo di rete, non solo "dati non ingeriti".** AIA-FIGC (designazioni Serie
A) e `pgmol.com` (Premier League) sono le due fonti candidate (categoria A,
`app/ingestion/source_registry.py`), ma entrambe risultano bloccate a
livello di rete da questa sandbox: `www.aia-figc.it` dietro una sfida
Cloudflare "Just a moment..." (stesso blocco di fbref.com/betfair.com),
`pgmol.com` con connessione TCP azzerata (stesso blocco geografico
dell'intero dominio betfair.com). `premierleague.com` stesso è raggiungibile
e con `robots.txt` permissivo, ma è una SPA React lato client (nessun
contenuto articolo nell'HTML grezzo) — richiederebbe un browser reale
(Playwright) più un audit ToS/rischio dedicato della sua API interna
(`footballapi.pulselive.com`, raggiungibile ma mai auditata come fonte),
non tentato qui per non introdurre una fonte dati nuova senza lo stesso
rigore di audit già applicato a tutte le altre — v. `DATA_SOURCES.md` per
il dettaglio completo. Resta quindi bloccato con motivo verificato, non un
gap di lavoro non ancora fatto.

✅ **Ipotesi dispersione NB per singola squadra — retestata in una sessione
successiva.** `NegativeBinomialPerTeamCountModel` implementato e
backtestato sui 4 segmenti reali: migliora Brier/log loss in modo più netto
della NB condivisa e migliora la calibrazione nelle fasce alte in modo
consistente (non più un pattern misto) — ma il gap residuo resta
sostanziale (4-18 punti percentuali) e il costo computazionale è reale
(10-25x più lento per singolo fit, minuti invece di secondi per un intero
backtest). Decisione basata sui dati: `PoissonCountModel` resta in
produzione — miglioramento reale ma parziale, non ancora sufficiente a
giustificare il costo. V. `BACKTEST_SPEC.md` per la tabella completa.
✅ **Mercato falli — implementato in una sessione successiva** (audit di
qualità/performance, non un nuovo modello: stessa `PoissonCountModel` già
usata per corner/cartellini, `MarketCategory.FOULS` esisteva già
nello schema dal primo slice, mai collegato). Backtestato prima di
abilitarlo (stesso standard di CORNERS/CARDS): a differenza di
corner/cartellini, la calibrazione nelle fasce alte è **buona** (gap di
1.5-4.7 punti percentuali, non 15-25) — v. `BACKTEST_SPEC.md` sezione
dedicata per i numeri completi. Linea standard 24.5, vicina alla media
reale osservata (~24.0 falli/partita).

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

**Estrazione reale ora completa su tutte le 10 stagioni disponibili**
(aggiornamento in un turno successivo — era rimasta scoped a un'unica
stagione "per tempo"): `scripts/ingest_understat_tactical_features.py` ha
scritto **106.400 righe reali** `TacticalFeature` (xG, xGA, npxG, npxGA,
PPDA, deep completions/deep completions allowed — window_matches=1, valore
grezzo per singola partita, non ancora una media mobile) per EPL+Serie A,
**tutte e 10 le stagioni 2015/16–2024/25**, verificato 15.200/15.200
apparizioni squadra-partita attese (100%, 0 nomi irrisolti residui) contro
il roster reale di ogni stagione. Tre nuovi alias squadra trovati e
verificati durante il backfill (stesso pattern hand-curated già in uso,
mai una fuzzy match): `West Bromwich Albion`→`West Brom`,
`SPAL 2013`→`Spal`, `Parma Calcio 1913`→`Parma` — nomi ufficiali/storici
usati da understat per squadre che football-data.co.uk registra
diversamente.

**Nota operativa emersa durante il backfill**: richieste ripetute a
understat in rapida sequenza (un ciclo di retry troppo aggressivo dopo i
primi errori di rete) hanno iniziato a fallire con una quota crescente di
`RemoteProtocolError` — un pattern coerente con un rate-limit/soft-block,
non semplice instabilità casuale. Corretto lo script: pausa tra richieste
alzata da 2s a 10s, e soprattutto aggiunto un controllo solo-DB che salta
del tutto la richiesta live a understat per una stagione già completamente
persistita (prima la rifaceva comunque a ogni esecuzione, anche per dati
già presenti) — una singola esecuzione pulita, non un loop di retry
stretto, ha poi completato il resto senza altri errori.

**Collegate al Decision Engine, backtestate, decisione basata sui numeri**
(v. MODEL_SPEC.md/BACKTEST_SPEC.md per il dettaglio):
- Correzione xG su Dixon-Coles: su 2023/24 sembrava aiutare l'EPL, non la
  Serie A — **ri-testata su tutte e 10 le stagioni (turno successivo): il
  segnale EPL non regge**, differenze aggregate marginali e incoerenti per
  entrambi i campionati con 12 volte più dati (v. BACKTEST_SPEC.md) → non
  attivata, conclusione confermata su base più solida.
- Correzione corner da deep completions (correlazione reale confermata prima
  di costruire nulla: r=+0.447 con i corner, **riconfermata su 10 stagioni
  a r=+0.424** — non un artefatto di campione piccolo) su `PoissonCountModel`:
  peggiora la previsione su ogni metrica, entrambi i campionati → scartata,
  non attivata; backtest completo non ripetuto sulle 10 stagioni perché la
  riconferma della correlazione già isola il problema nel meccanismo di
  correzione, non nella scarsità di dati.
Entrambe restano nel codice, testate, non collegate al layer di analisi live.

**Cosa resta esplicitamente aperto**:
- Aggregazione a finestra mobile no-leakage (window_matches>1) — quale
  finestra, quale aggregazione, è una vera decisione di design, meglio presa
  quando un consumatore reale (Matchup/Intelligence Engine, punto 6 sotto) ne
  ha bisogno che indovinata ora.
- ✅ ~~Estensione alle altre 9 stagioni disponibili~~ — fatto (v. sopra).
- crosses_per_90/progressive_passes (non in understat, servirebbero fbref o
  un'altra fonte — bloccati dagli stessi motivi sopra).
- ✅ ~~Le due correzioni già testate (xG su Dixon-Coles, deep completions sui
  corner) non sono state ri-backtestate contro le 9 stagioni aggiuntive~~ —
  fatto in un turno successivo (v. sopra, "Collegate al Decision Engine..."):
  entrambe ri-testate sulle 10 stagioni complete, stessa conclusione
  (non attivare) ora su base molto più solida invece che su una sola
  stagione. Questa voce era rimasta qui per una svista — corretta durante
  la sessione notturna di coerenza documentale.

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
Richiede: formazioni **a livello di singolo giocatore** (probabile prima
ufficiale, poi da fonti concordi/discordanti — riconciliazione già
implementata in `lineup_reconciliation.py`), un modello di minutaggio
atteso, e un modello di produzione individuale condizionato al minutaggio.
Vedi MODEL_SPEC.md per la motivazione di un modello dedicato invece di
riusare Dixon-Coles per singolo giocatore.

**Verificato in una sessione successiva** (l'utente ha chiesto di
controllare se Gazzetta/Sky/BBC — auditate mesi fa — fossero mai state
davvero implementate come provider, non solo classificate): non c'era
alcun gap da colmare. L'audit in `DATA_SOURCES.md` aveva già dato verdetto
**negativo** per tutte tranne una: Gazzetta (categoria C, Data Mining
Policy esplicita), SOS Fanta (rischio di affiliazione + prosa non
strutturata), Sky Sport Italia (bloccata tecnicamente da un WAF Akamai),
BBC Sport (categoria C, il divieto più esplicito del progetto), Sky Sports
UK (nessuna struttura equivalente trovata) — tutte correttamente **non
implementate**, con `GazzettaLineupProvider`/`SosFantaLineupProvider` che
esistono comunque come stub espliciti (`app/providers/probable_lineups/`,
`NotImplementedError`, mai un dato inventato). L'unica con verdetto
positivo, **Corriere dello Sport**, è realmente implementata
(`CorriereDelloSportLineupProvider`, con test) — ma copre solo il modulo
tattico di squadra (es. "4-3-3"), mai i nomi dei giocatori, quindi non
sblocca comunque il player-props qui sopra, che ha bisogno proprio di
quel livello di dettaglio. **Nota separata, non legata a questa
verifica**: `CorriereDelloSportLineupProvider` stesso non risulta ancora
collegato a `lineup_reconciliation.py`/`run_analysis_for_match` da nessuna
parte nel codice (confermato con una ricerca diretta) — coerente con
quanto ARCHITECTURE.md già dichiara ("reale, testato, non ancora collegato
all'analisi live"), quindi non una scoperta nuova, solo una conferma che
resta vero. Anche se lo fosse, non sbloccherebbe comunque i player props
per il motivo sopra (solo modulo, mai nomi giocatore).

**Ri-verificato di nuovo dal vivo il 13/09** (l'utente ha chiesto conferma
esplicita che non fosse solo una rilettura della sessione precedente):
chiamata reale a `https://www.corrieredellosport.it/probabili-formazioni/
calcio/serie-a` in questo momento — HTTP 200, 6 fixture reali della
prossima giornata Serie A correttamente estratte (Lecce–Monza,
Napoli–Bologna, Sassuolo–Juventus, Como–Parma, Torino–Roma, Inter–Udinese
— le stesse 6 appena ingerite da football-data.org), formazioni ancora
vuote (normale, OPTA non le ha ancora pubblicate a 1-2 giorni dal match) e
correttamente **nessun record restituito** per queste (mai un placeholder).
Confermato di nuovo: `CorriereDelloSportLineupProvider` è codice reale e
funzionante, non uno stub — le uniche due classi stub nel progetto restano
`GazzettaLineupProvider`/`SosFantaLineupProvider` (`is_available() → False`,
`NotImplementedError` sul fetch), coerenti con il verdetto negativo
dell'audit per quelle due fonti. Nessuna classe provider esiste per Sky/BBC
(mai state implementate, coerente con l'audit: nessuna fonte viabile
trovata per loro).

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
- ✅ ~~Rivalutazione colonna ALERT — ancora non sbloccata~~ **— SBLOCCATA in
  una sessione successiva, v. il punto Betfair subito sotto.** Cronaca
  originale (per contesto): Betson (via diretta.it) e livescore.com erano
  stati valutati come fonti di quote pre-match reali per partite future e
  **nessuna delle due forniva quote reali** — entrambe stub
  verificati-bloccati per un limite tecnico dell'ambiente (browser headless
  non funzionante attraverso il proxy di rete di questa sessione), non per
  pigrizia. La colonna ALERT restava quindi vuota/non popolabile per
  partite future. **Questo non è più lo stato attuale**: Betfair Exchange
  (fonte ufficiale, non scraped — v. sotto) fornisce ora quote reali quando
  disponibili, e la colonna ALERT funziona per qualunque `Candidate` con
  quota reale, partita futura inclusa.
- ✅ **Betfair collegato al Decision Layer — credenziali configurate, ma
  ancora non verificato dal vivo (blocco di rete della sandbox, non un
  problema di codice o di credenziali).** `run_analysis_for_match`
  (`analysis_runner.py`) ora chiama `build_default_odds_provider_chain()`
  (Betfair per primo) per ogni partita non `FINISHED` prima di costruire i
  `Candidate`, e persiste quanto trovato come nuove righe `OddsQuote` tramite
  `ingest_live_odds_quotes` (`match_ingestion.py`) — creando `Market`/
  `MarketOutcome` al volo se non esistono ancora (necessario per una
  partita futura senza quote storiche). `BetfairExchangeOddsProvider` ora
  interroga sia `MATCH_ODDS` (1X2) sia `OVER_UNDER_25` (O/U 2.5 gol, non
  solo 1X2 come prima); corner/cartellini restano non implementati —
  indagine approfondita in una sessione successiva (v. sotto) ha confermato
  che non è verificabile da questa sandbox nemmeno leggendo la
  documentazione ufficiale (blocco di rete su tutto il dominio betfair.com,
  non solo login/Betting API), quindi restano "n/d" per decisione esplicita
  dell'utente, non per pigrizia. Aggiunti anche: fix
  di un bug reale trovato leggendo il sorgente di `betfairlightweight`
  (`client.login()` è l'endpoint cert-based, non quello interattivo — va
  usato `client.login_interactive()`), locale `"italy"` per l'endpoint
  identity, e rinnovo automatico della sessione (`session_expired` +
  `keep_alive()`, fallback a re-login completo) così l'utente non deve mai
  reinserire nulla manualmente. **Le credenziali reali sono ora configurate**
  (`BETFAIR_USERNAME`/`BETFAIR_PASSWORD`/`BETFAIR_APP_KEY`, quest'ultima una
  Delayed key generata manualmente dall'utente da un IP italiano), ma il
  login da questa sandbox resta bloccato con lo stesso `HTTP 403` Cloudflare
  già trovato con credenziali placeholder — confermato dall'utente che
  funziona da un IP italiano/residenziale. **Verifica end-to-end reale
  (copertura mercati 1X2/O-U/corner/cartellini su partite vere, quote
  effettivamente ricevute) resta da fare dal computer dell'utente — v.
  `RUNNING_LOCALLY.md`.**
- ✅ **I due blocchi sotto sono stati RISOLTI in una sessione successiva** (la
  cronaca originale del blocco è mantenuta qui sotto per contesto storico —
  la decisione di design che allora era stata segnalata invece di presa
  unilateralmente è stata poi esplicitamente autorizzata dall'utente, che ha
  scelto l'opzione (b) descritta sotto).
  1. **"n/d" invece di riga saltata (opzione (b) scelta all'epoca — poi
     superata, v. sotto)**: `_build_candidates_and_predictions` fa
     get-or-create di `Market`/`MarketOutcome` per MATCH_RESULT/TOTAL_GOALS
     (non dipende più da righe già esistenti) e persiste **sempre** una
     `Prediction` per ogni esito con probabilità calcolabile dal modello: con
     quota reale quando esiste un `OddsQuote` liquido, altrimenti
     `bookmaker_odds=None`/`value=None` — mai una riga assente, mai un
     prezzo inventato. All'epoca la scelta fu la (b) "tipo di riga
     separato" (`NoOddsEstimateOut`), non la (a): `RiskFactors`/`Candidate`
     restavano obbligatori su `bookmaker_odds`, la stima "n/d" viveva fuori
     dalla risk ladder. **Questo è cambiato il 13/09**, dopo che un vero
     giro end-to-end aveva mostrato che, quando NESSUN mercato ha una quota
     (il caso normale per ogni fixture futura reale qui), l'intera analisi
     si interrompeva con un errore invece di mostrare "n/d". Su decisione
     esplicita dell'utente, `Candidate.bookmaker_odds`/
     `RiskFactors.bookmaker_odds`/`ScoredCandidate.value` sono ora `float |
     None` (di fatto anche l'opzione (a), ma solo per MATCH_RESULT/
     TOTAL_GOALS): un esito senza quota entra comunque nella risk ladder,
     ranked su probabilità/incertezza/affidabilità (mai un prezzo
     sostitutivo inventato — il peso del fattore quota viene redistribuito
     sugli altri). `NoOddsEstimateOut`/`additional_estimates` restano, ma
     ristretti a CORNERS/CARDS (mai parte del meccanismo ladder) — v.
     `VERIFICATION_LOG.md` sezione 7 per il dettaglio completo.
  2. **Fixture future reali**: `FootballDataOrgFixtureProvider`
     (`app/providers/football_data_org/provider.py`, categoria A) +
     `ingest_upcoming_fixture` chiudono il secondo blocco — vedi la sezione
     dedicata più sotto per il dettaglio (non ancora testato dal vivo: manca
     una chiave gratuita da registrare, ma la rete di questa sandbox non è
     bloccata verso questa API, a differenza di Betfair).

  Cronaca originale del blocco (per contesto, non più lo stato attuale):
  *Scaffolding frontend (colonne Probabilità/Quota Modello senza quota
  reale) — fermato prima di implementare, ambiguità architetturale reale
  trovata investigando, non solo un'attività rimandata.* L'idea proposta
  ("la tabella mostra già probabilità e quota modello, che non dipendono da
  Betfair") era vera per le partite già giocate — ma era stato verificato
  nel codice che `_build_candidates_and_predictions` saltava del tutto un
  mercato quando non esisteva una riga `OddsQuote` reale per quel market
  outcome, e che `RiskFactors.bookmaker_odds` era un campo obbligatorio
  usato direttamente nel calcolo del risk score. In pratica: per una
  partita futura senza alcuna quota ingerita, il motore non produceva
  nessuna riga in tabella, punto. **Secondo blocco, indipendente dal
  primo**: non esisteva alcuna partita futura non ancora giocata nei dati
  reali ingeriti (7.600 partite totali, 0 con kickoff futuro). Costruire
  quanto chiesto richiedeva una vera decisione di design: o (a) rendere
  `bookmaker_odds`/value/alert opzionali dentro `Candidate`/`RiskFactors`,
  oppure (b) introdurre un tipo di riga separato e più semplice ("stima di
  modello, nessun mercato quotato"). Non presa autonomamente in quel turno:
  segnalato invece di forzare una soluzione rapida (v. sopra come è stata
  poi risolta).
- ✅ **Fixture future reali: football-data.org, non diretta.it — correzione
  esplicita dell'utente rispetto a un piano precedente.** Un primo tentativo
  di chiudere il "secondo blocco" sopra aveva considerato diretta.it (stessa
  fonte già autorizzata per le quote Betson), ma verificato dal vivo che
  anche il suo calendario è caricato via JS lato client (stesso blocco
  tecnico delle quote — v. `DATA_SOURCES.md`). Corretto dall'utente:
  `FootballDataOrgFixtureProvider` (categoria A, API REST pubblica e
  documentata) copre esattamente il caso d'uso richiesto — solo la
  **prossima giornata** per Premier League/Serie A, non un calendario
  stagionale completo. Verificato dal vivo in questa sessione (non assunto):
  endpoint reale `GET /v4/competitions/{PL|SA}/matches?matchday=N`, header
  `X-Auth-Token`, piano gratuito confermato per PL+SA a 10 richieste/minuto.
  La rete di questa sandbox NON è bloccata verso questa API (confermato con
  una chiamata pubblica reale e con un test a token non valido, che ha
  correttamente risposto "token invalido" invece di un blocco di rete) — a
  differenza di Betfair, quindi una volta ottenuta una chiave gratuita
  questo può essere verificato dal vivo anche da questa sandbox, non solo
  dal computer dell'utente. **Non ancora testato dal vivo**: nessuna chiave
  `FOOTBALL_DATA_ORG_API_KEY` disponibile in questa sessione — testato
  contro lo schema JSON v4 reale verificato, tramite `httpx.MockTransport`.
  `ingest_upcoming_fixture` (`app/ingestion/match_ingestion.py`) persiste
  ogni fixture come `Match` `SCHEDULED`, idempotente, e non tocca mai una
  partita già `FINISHED` da un'ingestione storica. Prossimo passo concreto:
  l'utente registra una chiave gratuita su football-data.org e la imposta
  in `.env`, poi `python scripts/ingest_upcoming_fixtures.py` popola
  davvero la prossima giornata.
- ✅ **Copertura Betfair corner/cartellini: ri-audit, esito aggiornato — i
  mercati esistono davvero, il codice esatto resta da confermare dal vivo.**
  Richiesta esplicita (due volte, sessioni diverse): verificare se Betfair
  Exchange offra davvero mercati corner/cartellini per il calcio. Primo giro
  (invariato): `docs.developer.betfair.com`/`developer.betfair.com`
  bloccati (stesso Cloudflare "Restricted" del login, l'intero dominio
  betfair.com, non solo login/Betting API); `betfairlightweight` senza
  catalogo di market type code, solo l'indizio circostanziale del modello
  dati In-Play Service. **Secondo giro**: confermato con fonti web reali e
  indipendenti (materiale educativo Betfair sull'Exchange stesso, siti di
  trading/recensioni indipendenti) che corner e cartellini/bookings **sono
  mercati Exchange reali e liquidi** per le partite principali — non più solo
  un indizio, ma nemmeno il codice letterale del market type, ancora
  bloccato dalla stessa documentazione ufficiale irraggiungibile. Costruito
  invece `BetfairExchangeOddsProvider.discover_market_types_for_match`
  (chiama `listMarketTypes`, un'operazione reale e documentata dell'API-NG,
  per scoprire cosa Betfair offre davvero per ogni fixture, mai indovinare
  un codice) + `scripts/discover_betfair_market_types.py` per l'utente.
  Corner/cartellini restano "n/d" fino alla conferma reale del codice e
  della convenzione di naming dei runner — v. `DATA_SOURCES.md` per il
  dettaglio completo.

### 11. Audit qualità generale (test/errori/performance) — richiesto esplicitamente, completato
Passata critica sull'intero codebase su tre assi, con lo stesso standard di
rigore (misurato, non stimato, ogni volta che possibile):

- **Copertura test**: report reale (`pytest-cov`, ora dipendenza dev
  dichiarata), 86% → 96%. Colmati i gap reali (non gli stub deliberati già
  accettati in sessioni precedenti): `lineup_reconciliation.py` (logica di
  decisione reale, 0% → 100%), `rate_limiter.py`, `db/session.py`,
  `api/routers/matches.py` (69% → 98%, incluso `GET /matches` mai testato
  prima), e i 4 provider reali ma mai testati (`open_meteo`, `rss_news`,
  `api_football`, `fbref`). Scrivere i test per `fbref` ha scoperto un bug
  reale (non ipotetico): il provider era completamente non funzionante in
  questo stesso ambiente installato (`lxml` mancante come dipendenza,
  `pandas.read_html` su una stringa letterale). Vedi `CHANGELOG.md` per il
  dettaglio completo, incluso l'elenco onesto dei gap residui non chiusi.
- **Gestione errori**: trovati e corretti 4 punti dove un singolo elemento
  malformato interrompeva bruscamente un intero batch di ingestione reale
  (10 stagioni × 2 competizioni) invece di degradare in modo controllato —
  `ingest_football_data.py`/`ingest_upcoming_fixtures.py` (isolamento per
  record via SAVEPOINT), `ingest_understat_tactical_features.py`
  (isolamento per stagione), `football_data_co_uk/provider.py::parse_csv`
  (isolamento per riga CSV). Verificato anche cosa non necessitava
  correzione (fallback provider già isolato, un `RuntimeError` difensivo
  reso irraggiungibile da un guard a monte, FastAPI già degrada in un 500
  pulito).
- **Performance su molte partite reali insieme** (la domanda esplicita
  dell'utente): trovato e corretto un N+1 severo in `GET /matches` — l'intera
  tabella principale scansionava OGNI partita mai ingerita (10 stagioni di
  storico) invece che solo quelle con analisi corrente, misurato **7733
  query SQL per 18 righe reali**, corretto a 124 (62 volte meno) con un
  JOIN diretto. Un secondo N+1 reale in `count_market_estimates.py`
  (corner/cartellini) dimezzato (7.68s → 3.67s/partita). Aggiunta una
  cache di fit opzionale (`model_fit_cache`, mai attiva di default) che
  permette a `analyze-batch` di riusare lo stesso modello già fittato tra
  partite della stessa competizione con lo stesso identico orario di calcio
  d'inizio, invece di rifittare da zero per ognuna (~10s/partita altrimenti).
  Tutto misurato contro i dati reali già nel database di sviluppo, non solo
  stimato — v. `CHANGELOG.md` per i numeri completi e cosa NON è stato
  corretto (un N+1 minore in `GET /matches/{id}`, a priorità più bassa
  perché non peggiora con la crescita dello storico).

246 test passano, lint pulito, 3 commit separati e pushati.

### Setup locale e verifica Betfair dal vivo — priorità esplicita dell'utente
`setup.ps1`/`start.ps1` (Windows) e `setup.sh`/`start.sh` (macOS/Linux)
automatizzano prerequisiti, database, migrazioni, `.env`, dipendenze e primo
avvio (ingestione fixture reali + apertura browser inclusi).
`RUNNING_LOCALLY.md` riscritto per un utente al primo terminale, con una
sezione "Problemi comuni" per gli errori più probabili. Resta da fare
dall'utente: il primo avvio reale sul proprio computer, la verifica che
Betfair restituisca quote vere (non più bloccato dalla rete della sandbox),
ed eventualmente l'esecuzione di `scripts/discover_betfair_market_types.py`
per scoprire se/come corner e cartellini sono davvero disponibili come
market type — v. `RUNNING_LOCALLY.md` per i passi esatti.
