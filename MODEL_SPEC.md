# Model Spec

## Scelta dei modelli per mercato

| Mercato | Modello scelto | Perché | Stato |
|---|---|---|---|
| 1X2 / Doppia chance | Dixon-Coles Poisson bivariato | Standard per i mercati a gol nel calcio, interpretabile (rating attacco/difesa per squadra), corregge la sotto-stima dei punteggi bassi correlati (0-0, 1-1) rispetto a due Poisson indipendenti (Dixon & Coles, 1997). | **Implementato** (`app/engine/statistical/dixon_coles.py`) |
| Over/Under gol | Stessa distribuzione di punteggio del modello Dixon-Coles, sommata sulla matrice di score | Nessun motivo di usare un modello diverso: O/U è una proiezione della stessa distribuzione congiunta dei gol. | **Implementato** |
| Both Teams To Score | Idem, proiezione della stessa matrice | Idem | **Implementato** |
| Handicap asiatico | Stessa matrice di score, soglia sulla differenza gol | Stessa distribuzione, cambia solo l'evento aggregato | Non ancora esposto nel Decision Layer (v. ROADMAP) |
| Corner | Poisson log-lineare attacco/difesa (Maher-style, senza il termine `rho` di Dixon-Coles — non pertinente ai conteggi corner) | I corner non condividono il problema di correlazione a basso punteggio dei gol; una struttura attacco/difesa log-lineare separata, fittata sui dati storici corner reali, è sufficiente come primo modello. | **Implementato** (`app/engine/statistical/count_market_model.py`) — dati storici reali ingeriti da football-data.co.uk (colonne HC/AC), 15.200 righe `TeamMatchStats` popolate su 7.600 partite reali EPL+Serie A. Overdispersione non ancora modellata (Poisson puro, non binomiale negativa) — v. nota sotto. |
| Cartellini | Stessa struttura Poisson attacco/difesa, **senza correzione arbitro** | I cartellini dipendono fortemente dall'arbitro, ma nessun dato arbitro è ancora ingerito (v. DATA_SOURCES.md su AIA-FIGC/PGMOL) — un modello che lo ignori è deliberatamente incompleto, non mal specificato per omissione: la varianza spiegata dall'arbitro resta fuori dal modello finché quella feature non esiste, ed è documentato così invece di essere nascosto. | **Implementato** (stessa classe `PoissonCountModel`, cartellini = gialli+rossi combinati), dati storici reali ingeriti (colonne HY/AY/HR/AR). |
| Falli | Dati ingeriti (colonne HF/AF, `TeamMatchStats.fouls_committed`) | — | Dati disponibili, nessun modello/mercato ancora costruito su di essi (i falli non sono tipicamente un mercato scommesse standalone come corner/cartellini) — v. ROADMAP. |
| Player props (tiri, assist, cartellini) | Modelli specifici per giocatore (es. Poisson per tiri/gol individuali, corretto per minutaggio atteso), NON lo stesso modello di squadra applicato al singolo giocatore | Il volume di un giocatore dipende da minutaggio, ruolo, sistema di gioco — serve un layer che stimi prima il minutaggio atteso (dipendente da formazione, v. `lineup_reconciliation.py`) e poi la produzione condizionata. | Non implementato (richiede dati minutaggio/formazioni affidabili, v. ROADMAP) |

Nessun "unico modello monolitico": ogni famiglia di mercato ha (o avrà) il proprio
modello, selezionato in base a cosa è statisticamente ragionevole per quel tipo di
evento — coerente con l'indicazione del brief.

## Dixon-Coles: dettaglio

- Parametri: `attack_i`, `defense_i` per ogni squadra, `home_advantage` (γ),
  correlazione `rho` per le celle (0,0),(0,1),(1,0),(1,1).
- `λ_home = exp(attack_home + defense_away + home_advantage)`,
  `μ_away = exp(attack_away + defense_home)`.
- Stima per massima verosimiglianza pesata (`scipy.optimize.minimize`,
  L-BFGS-B), con penalità che vincola la media degli `attack` a zero
  (identificabilità, invece di fissare una squadra di riferimento).
- **Pesatura temporale**: peso `exp(-xi * days)`, `xi=0.0018/giorno` di default
  (valore di partenza dal paper originale, esplicitamente da ricalibrare via
  backtest — v. BACKTEST_SPEC.md).
- **Limite esplicito**: il modello stima solo dai gol segnati/subiti; non
  incorpora ancora trasferibilità per squadre promosse, continuità
  allenatore/sistema, o correzione H2H selettiva — queste sono responsabilità
  del layer di feature engineering "a monte" del modello (ingestion +
  Intelligence Engine), non del modello stesso. Il modello oggi tratta la
  storia recente allo stesso modo per qualunque squadra; il fattore di
  trasferibilità per le neopromosse (menzionato nel brief) è pianificato come
  un peso aggiuntivo sui match di stagioni precedenti in categorie diverse
  (v. ROADMAP), non ancora implementato.
- **Correzione xG di Dixon-Coles — testata sui dati reali, non attivata di
  default.** xG, xGA, npxG, PPDA e deep completions per partita (da
  understat.com, v. DATA_SOURCES.md categoria B) sono stati estratti e
  persistiti in `TacticalFeature` per EPL+Serie A 2023/24 (`scripts/
  ingest_understat_tactical_features.py`, 10.640 righe reali). `app/engine/
  statistical/tactical_adjustment.py` usa il rapporto xG/gol-reali di una
  squadra (solo partite precedenti, mai leakage) per correggere il lambda/mu
  di Dixon-Coles prima di calcolare le probabilità finali — un fattore
  esplicitamente clippato a [0.75, 1.33] (limite di sicurezza dichiarato, non
  tarato sui risultati del backtest), applicato solo quando esistono >= 5
  partite precedenti con dato xG per quella squadra (altrimenti il modello
  resta quello attuale, senza correzione — v. BACKTEST_SPEC.md "xG-adjusted
  Dixon-Coles" per il perché di questo comportamento).
  **Risultato del backtest reale (EPL+Serie A 2023/24, unica stagione
  coperta)**: migliora Brier/log loss/calibrazione nelle fasce alte per
  l'**EPL** su entrambi i mercati, ma **non aiuta la Serie A** (leggermente
  peggio, e introduce overconfidence in un bin che nel modello raw era già
  ben calibrato). **Decisione basata sui numeri**: non attivata di default
  per nessuno dei due campionati — un beneficio specifico a un solo
  campionato, su una sola stagione di dati, non è una base solida per
  un'attivazione uniforme. Il codice resta testato e pronto, non cancellato.
- **Correzione corner da PPDA/deep completions — correlazione reale
  confermata, correzione scartata.** Verificato prima di costruire nulla: PPDA
  e deep completions correlano davvero con i corner reali (Pearson r=−0.264 e
  +0.447 su 1.516 osservazioni 2023/24), non un'assunzione. La correzione
  costruita su deep completions (stesso meccanismo dell'aggiustamento xG:
  rapporto squadra/media-lega, clippato, mai applicato senza >= 5 partite di
  dato) **peggiora** però Brier, log loss e calibrazione su **ogni** metrica,
  per **entrambi** i campionati (v. BACKTEST_SPEC.md "PPDA/deep completions vs
  corner" per la tabella completa) — un risultato negativo netto, non solo
  incoerente tra segmenti. Ipotesi (non verificata oltre): l'attacco/difesa
  già fittati da `PoissonCountModel` catturano implicitamente lo stesso
  segnale, per cui la correzione aggiunge rumore, non informazione. `compute_
  deep_completions_adjustment_factor` resta nel codice, testato, non
  collegato a `count_market_estimates.py`.
- **Intelligence Engine — solo il livello di validazione, non un generatore
  di segnali**: `app/engine/intelligence/validation.py` confronta
  un'ipotesi qualitativa (`IntelligenceSignal`, es. "pressing più aggressivo
  da quando è arrivato il nuovo allenatore") con un cambiamento misurabile
  reale in una `TacticalFeature` prima/dopo la data del segnale —
  fail-conservative (nessun giudizio forzato sotto una soglia minima di
  osservazioni). Nessuna fonte reale produce ancora un `IntelligenceSignal`
  (nessun feed news, nessuna pipeline LLM, nessun inserimento manuale
  collegato) — il layer quantitativo di validazione esiste ed è testato, il
  layer qualitativo che dovrebbe alimentarlo no.

## Corner e cartellini: modello e limite strutturale sul value

`PoissonCountModel` (`app/engine/statistical/count_market_model.py`) fitta,
separatamente per corner e per cartellini, un rating attacco/difesa/vantaggio
casa via massima verosimiglianza Poisson — stessa idea di Dixon-Coles ma senza
il termine di correlazione `rho` (specifico alla sotto-stima dei punteggi
bassi nei gol, non pertinente a un conteggio come i corner). Proprietà usata:
la somma di due Poisson indipendenti è essa stessa Poisson(λ+μ), quindi il
mercato "totale partita" (es. Over/Under 9.5 corner) non richiede costruire
una matrice congiunta come per i gol.

**Limite strutturale, non implementativo**: football-data.co.uk (l'unica fonte
di quote reali in questo progetto) **non pubblica quote per corner o
cartellini** — solo 1X2, Over/Under 2.5 gol e handicap asiatico hanno colonne
quota nel CSV (verificato contro lo schema colonne reale). Di conseguenza:
- Il modello produce una **probabilità reale**, stimata su dati storici reali
  (15.200 righe `TeamMatchStats`, 7.600 partite EPL+Serie A).
- Ma **non esiste un prezzo di mercato con cui calcolare value/edge** per
  questi due mercati in nessuna fonte dati oggi integrata.
- Queste stime (`app/engine/decision/count_market_estimates.py`) sono quindi
  **volutamente escluse dalla risk ladder** (che richiede sempre probabilità
  + quota reale) e esposte separatamente via API (`additional_estimates`) e
  frontend, etichettate esplicitamente come "stima statistica, nessuna quota
  di mercato disponibile" — mai presentate come una selezione scommettibile
  con value calcolato.
- Le linee usate (9.5 corner, 3.5 cartellini) sono le **linee convenzionali
  note nel mercato delle scommesse sportive** (dominio pubblico, non il prezzo
  proprietario di un bookmaker), scelte solo per esprimere la probabilità del
  modello a un livello riconoscibile — non sono una quota inventata.

**Poisson vs binomiale negativa — testato, non solo ipotizzato.** Un primo
backtest reale aveva mostrato overconfidence marcata nelle probabilità sopra
0.7 (v. BACKTEST_SPEC.md), suggerendo overdispersione non catturata da un
Poisson puro. `NegativeBinomialCountModel`
(`app/engine/statistical/count_market_model.py`, stessa struttura
attacco/difesa + un parametro di dispersione `alpha` condiviso, fittato via
MLE) è stato implementato e backtestato sugli stessi dati/periodo per
verificarlo — **risultato: la binomiale negativa migliora marginalmente
Brier/log loss aggregati, ma NON risolve in modo consistente la
calibrazione nelle fasce alte** (in alcuni bin migliora, in altri peggiora, in
un segmento converge quasi esattamente a Poisson) — v. BACKTEST_SPEC.md per
la tabella completa. **`PoissonCountModel` resta il modello in produzione**;
`NegativeBinomialCountModel` resta nel codice come alternativa testata e
funzionante, non come modello "in attesa di essere attivato" — l'ipotesi più
plausibile ora è che l'overconfidence osservata venga più dalla struttura
media (mancanza di feature come l'arbitro per i cartellini) che dalla forma
Poisson vs NB della distribuzione stessa.

## Probabilità → quota fair → value

- `fair_odds = 1 / probability` (`app/engine/decision/fair_odds.py`) — formula
  pura, nessun aggiustamento nascosto. Un blend con la probabilità implicita
  di mercato resta un passo esplicito e separato, non ancora implementato.
- **Calibrazione post-hoc (Platt/isotonica) — testata, non attivata.**
  `app/engine/decision/calibration.py` implementa entrambe
  (`PlattCalibrator`, `IsotonicCalibrator` via PAVA) e sono state
  backtestate senza leakage (`app/backtest/calibration_runner.py`, split
  temporale 80/20) su tutti gli 8 segmenti reali già backtestati
  (EPL+Serie A × MATCH_RESULT/TOTAL_GOALS/CORNERS/CARDS). Risultato: nessuna
  delle due migliora la calibrazione nelle fasce alte in modo consistente —
  un miglioramento reale su Serie A MATCH_RESULT, ma peggioramenti netti su
  EPL CARDS/TOTAL_GOALS/MATCH_RESULT nello stesso esperimento (v.
  BACKTEST_SPEC.md per la tabella completa). **Decisione basata sui numeri**:
  la pipeline usa ancora la probabilità grezza del modello, non calibrata —
  non per mancanza di un'implementazione, ma perché quella implementazione,
  testata, non ha dimostrato di migliorare le cose. Questo è il terzo
  tentativo indipendente (dopo binomiale negativa e più stagioni di storia)
  che non risolve l'overconfidence nelle code alte in modo consistente —
  prova indiretta ma convergente che il problema è nella struttura media
  (feature mancanti), non nella forma della distribuzione o in una
  trasformazione scalare post-hoc.
- `value = probability * bookmaker_odds - 1` (EV per unità puntata) — scelta
  sugli altri possibili indicatori (es. rapporto tra quote) perché è la
  grandezza che ROI/yield del backtest già usano nativamente: un'unica
  definizione di "quanto vale una scommessa" attraversa tutto il sistema.
- `discrepancy_pct = (probabilità modello − probabilità implicita mercato) /
  probabilità implicita mercato` — usata per la soglia di alert, espressa in
  termini relativi apposta (un divario di 5 punti percentuali non è la stessa
  cosa a probabilità 90% o 20%).

## Alert: soglie (provvisorie)

`<10%` nessun alert, `10–15%` interessante, `>15%` forte — esattamente i valori
indicati nel brief, marcati esplicitamente come provvisori
(`app/engine/decision/value.py`, `ALERT_THRESHOLD_*`) fino a una calibrazione
sui risultati del backtest.

## Incertezza, qualità dati, affidabilità modello

`RiskFactors` (`app/engine/decision/risk_score.py`) raccoglie 7 segnali:
probabilità, quota, incertezza, qualità dati, affidabilità modello, stabilità
predizione, dipendenza da formazioni non ufficiali. Nel vertical slice:
- **incertezza**: derivata dalla dimensione del campione di allenamento
  disponibile (`max(0, 1 − min(train_n, 300)/300)`) — più storia, meno
  incertezza; è un proxy dichiarato, non una vera quantificazione bayesiana
  della varianza posteriore (che richiederebbe un modello gerarchico/bayesiano,
  v. ROADMAP per PyMC).
- **qualità dati**: fissa a 1.0 quando la quota di chiusura è presente (dati
  completi); scenderebbe con dati mancanti/proiettati.
- **affidabilità modello**: **non più un placeholder**. `app/engine/decision/
  reliability.py` (`model_reliability_for`) legge la riga `Backtest` più
  recente per (model_family, market_category, competition) — le stesse righe
  reali persistite da `scripts/persist_backtest_results.py` (v. ROADMAP.md
  punto 1) — e ne deriva l'affidabilità dal **gap di calibrazione**
  (`|predicted_mean − observed_frequency|` nel bin della curva di calibrazione
  in cui cade la probabilità del candidato corrente), non da Brier
  score/log loss/hit rate: questi ultimi mescolano discriminazione e
  calibrazione, mentre "l'affidabilità di questa probabilità specifica" è
  esattamente ciò che il gap di calibrazione misura — ed è precisamente il
  problema che BACKTEST_SPEC.md documenta (overconfidence concentrata nelle
  fasce alte). Se il bin specifico ha troppe poche osservazioni
  (`MIN_BIN_COUNT=30`), la stima ricade su una media pesata dei bin del
  segmento con dati sufficienti; se **nessun** bin del segmento ne ha
  abbastanza, la funzione ritorna esplicitamente "non stimabile" invece di
  forzare un numero — nel qual caso `analysis_runner.py` applica **0.0** (il
  caso peggiore, non 0.5 neutro): il mercato resta comunque visibile
  all'utente (ha comunque una quota reale e un EV), ma penalizzato al massimo
  su questo fattore del rischio — fail-conservative, non un'esclusione
  silenziosa. Se in futuro esistono più `ModelVersion` per lo stesso segmento,
  viene sempre usata la riga `Backtest` più recente (`run_at` più alto).
- **stabilità predizione**: confronto tra `AnalysisVersion` consecutive per la
  stessa partita — nel vertical slice è 1.0 alla prima analisi (nessun confronto
  possibile) e andrebbe popolato reale al secondo "AGGIORNA ANALISI".
- **dipendenza da formazioni**: 0 per i mercati di squadra (1X2/O-U/BTTS) che
  non dipendono da chi gioca titolare; diventa rilevante per i player props.

## Rischio 1–10: combinazione dinamica, non soglia di probabilità

`compute_risk_raw` (pesi documentati in `risk_score.py`) combina tutti i
segnali sopra in un unico punteggio continuo 0–1; `build_risk_ladder`
(`app/engine/decision/selection.py`) lo trasforma in un livello 1–10 per
**ranking relativo tra i candidati della stessa partita**, non per soglia
assoluta su una singola variabile — esattamente il vincolo del brief. I pesi
attuali (`WEIGHTS` in `risk_score.py`) sono un punto di partenza esplicito, da
ricalibrare quando il backtest per-livello-di-rischio (v. BACKTEST_SPEC.md)
avrà abbastanza volume per giudicare se, es., il Risk 3 batte davvero il Risk 7
su hit rate/ROI.

## Limite onesto sul numero di mercati nel vertical slice

Con solo 1X2 + O/U 2.5 + BTTS implementati, una partita ha tipicamente ~7
candidati — non i 30 slot distinti che 10 livelli × 3 selezioni
richiederebbero senza alcun riuso. `build_risk_ladder` gestisce questo caso
esplicitamente (preferendo mercati non ancora usati come "principale" per un
altro livello, quando possibile) invece di fingere un'indipendenza che i dati
non supportano ancora. Aggiungere corner/cartellini/player props (v. ROADMAP)
risolve strutturalmente questo limite.

## Formazioni e player props — gestione conflitto

`app/engine/decision/lineup_reconciliation.py` implementa esattamente la
regola del brief: formazione ufficiale → confidence 1.0; due fonti probabili
concordi → confidence 0.85; fonti in conflitto → confidence 0.35 e
`is_conflicting=True`. `Candidate.lineup_conflict=True` impedisce a un mercato
player-dependent di diventare la selezione principale di un livello quando
esiste un'alternativa non-player idonea (`selection.py::is_eligible_main` +
fallback a ricerca globale, testato in
`tests/test_decision_layer.py::test_player_market_with_lineup_conflict_never_main_when_alternative_exists`).
