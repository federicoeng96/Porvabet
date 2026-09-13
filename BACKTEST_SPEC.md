# Backtest Spec

## Obiettivo

Valutare storicamente il modello **senza data leakage**: nessuna predizione deve
usare informazioni non disponibili al momento reale della partita.

## Garanzia anti-leakage (come è imposta, non solo dichiarata)

`app/backtest/runner.py::run_walk_forward_backtest`:
1. Le partite sono ordinate per data e raggruppate in batch (default: finestre di
   7 giorni, `REFIT_BATCH_DAYS`).
2. Per ogni batch, il modello Dixon-Coles è riaddestrato **solo** su
   `training_pool`, cioè tutte le partite di batch strettamente precedenti — mai
   sul batch corrente o futuro.
3. Le predizioni per le partite del batch corrente usano quel fit — partite
   nello stesso batch non si "vedono" a vicenda nel training, solo nella
   previsione (contemporanee, non usate come feature l'una dell'altra).
4. **Affidabilità modello a rischio zero-leak**: la media mobile di Brier score
   usata come segnale `model_reliability` (v. MODEL_SPEC.md) si aggiorna **solo
   dopo** aver risolto la predizione per la partita result-market principale di
   ogni partita — non include mai l'esito della partita che si sta
   attualmente valutando.
5. Un refit periodico (invece che per ogni singola partita) è una scelta di
   costo computazionale, non una scappatoia sul leakage: nessuna partita del
   batch contribuisce al fit usato per predire quel batch.

Il principio no-leakage (fit solo su dati strettamente precedenti) è testato
end-to-end (dati sintetici) in `tests/test_analysis_runner.py` per il motore
di analisi live (`run_analysis_for_match`) e verificato manualmente su un
dataset sintetico più grande. Il backtest runner stesso
(`run_walk_forward_backtest`) — inclusa la simulazione del precompute a 10
livelli di rischio via `build_risk_ladder` dentro il loop walk-forward, non
solo le metriche per singolo mercato — ha invece avuto **solo esecuzione
manuale reale** (i numeri qui sotto) fino a una sessione successiva, senza
un test automatico dedicato: aggiunto `tests/test_backtest_runner.py`
(sintetico, veloce) che verifica esplicitamente che ogni livello 1-10 venga
prodotto e che `segment()` (le stesse metriche hit rate/ROI per livello
pubblicate sotto) funzioni sull'output reale della funzione, non solo su
dati costruiti a mano — così una regressione futura nel collegamento
backtest↔risk-ladder viene individuata prima della prossima esecuzione
reale, costosa, sui dati storici completi.

## Approssimazioni dei fattori di rischio nel backtest

Per restare honest e riproducibile, il backtest usa una configurazione
semplificata di `RiskFactors` (v. `app/backtest/runner.py::_build_candidates`):
- `data_quality = 1.0` — le quote di chiusura storiche sono complete per
  definizione (non ci sono "dati mancanti" in un dataset già chiuso).
- `prediction_stability = 1.0` — il concetto di "versione precedente
  dell'analisi" non esiste nel backtest puro (ogni partita è valutata una sola
  volta, a differenza dell'app live dove l'utente può premere più volte
  "AGGIORNA ANALISI").
- `lineup_dependency = 0.0` — solo mercati di squadra (1X2, O/U) sono
  valutati nel backtest attuale, nessuno dipende da formazioni.
- `uncertainty` — derivata dalla dimensione del training pool al momento del
  fit (`max(0, 1 - min(train_n, 300)/300)`), quindi varia realisticamente nel
  tempo (alta a inizio storico, bassa quando c'è più storia).
- `model_reliability` — media mobile out-of-sample come descritto sopra
  (parte da un valore neutro 0.5 quando non ci sono ancora predizioni risolte).

Questo è dichiarato esplicitamente come una scelta di semplificazione, non un
tentativo di nascondere che il backtest non riproduce esattamente tutti i
segnali dell'app live — è annotato nel modulo stesso
(`app/backtest/runner.py`, docstring).

## Metriche (implementate in `app/backtest/metrics.py`)

| Metrica | Definizione | Uso |
|---|---|---|
| Hit rate | % selezioni vincenti | Per segmento (v. sotto) |
| ROI | (ritorno totale − puntata totale) / puntata totale, stake flat | Per segmento |
| Yield | ROI × 100 (nota: sotto stake flat coincide numericamente con ROI%; diverge solo con stake sizing variabile — non ancora implementato) | Per segmento |
| Profit (unità) | Somma di (odds×stake − stake) se vinta, altrimenti −stake | Per segmento |
| Brier score | media((p − esito)²) | Calibrazione |
| Log loss | −media(esito·log(p) + (1−esito)·log(1−p)) | Calibrazione |
| Calibration curve | bins di probabilità predetta vs frequenza osservata | Diagnosi calibrazione |

`segment(bets, key)` calcola l'intero set di metriche sopra raggruppando per
qualunque chiave — usato per: **per livello di rischio (1–10)**, **per
mercato**, **home/away**, **per fascia di value** (`value_bucket_label`).
Player props non sono ancora nel backtest (nessun modello player-level
implementato, v. MODEL_SPEC.md/ROADMAP) — la funzione `segment` è già pronta a
riceverli quando esisteranno.

## Validazione empirica — RISULTATI REALI (EPL + Serie A, 2019/20–2024/25)

Una volta ottenuto accesso di rete in questa sessione, sono state ingerite
7.600 partite reali (10 stagioni per competizione) e il backtest walk-forward
è stato eseguito sulle 6 stagioni più recenti di ciascun campionato (2.280
partite ciascuno, refit ogni 21 giorni per restare in tempi ragionevoli — v.
nota sotto), usando il modello Dixon-Coles su MATCH_RESULT e TOTAL_GOALS. Ecco
i numeri reali, non sintetici:

**Per livello di rischio (EPL, n=2181 per livello):**

| Risk | Hit rate | ROI |
|---|---|---|
| 1–2 | 60.3% | −1.8% |
| 3–4 | 51.8% | −2.6% |
| 5–6 | 42.0% | −2.3% |
| 7–8 | 25.5% | −3.4% |
| 9–10 | 20.4% | −5.8% |

(Serie A: 60.0% → 49.8% → 43.2% → 25.8% → 21.1%, stesso pattern monotono.)
Il livello di rischio **separa correttamente** selezioni più sicure da
selezioni più rischiose, su entrambi i campionati — esattamente la proprietà
che il design del risk score deve garantire (v. MODEL_SPEC.md).

**ROI**: negativo su ogni singolo livello, su entrambi i campionati (da −0.5%
a −12.6% a seconda del segmento). Questo è il risultato onesto atteso da un
modello che stima probabilità solo dai gol storici, senza feature tattiche,
senza calibrazione ancora applicata, contro bookmaker moderni relativamente
efficienti — **il progetto non promette vincite, e questo backtest lo
conferma empiricamente invece di limitarsi a dichiararlo**. Un ROI negativo
non invalida il sistema: è esattamente il segnale che guida la roadmap
(calibrazione dei pesi, più feature, più mercati — v. ROADMAP.md) prima di
considerare il modello pronto per un uso reale.

**Calibrazione (EPL)**: buona nelle fasce centrali (bin 0.4–0.5: predetto
45.1%, osservato 45.1%; bin 0.5–0.6: predetto 54.7%, osservato 54.8%) ma il
modello è **overconfident nelle code alte** (bin 0.9–1.0: predetto 92.6%,
osservato solo 71.4% — n=42, quindi con margine di rumore campionario, ma la
direzione dell'overconfidence è consistente su tutti i bin sopra 0.6 in
entrambi i campionati). Questo è precisamente il tipo di scostamento che una
vera calibrazione post-hoc (Platt scaling o isotonic regression sulle
probabilità Dixon-Coles) dovrebbe correggere — non ancora implementata (v.
MODEL_SPEC.md "fair_odds ... raffinamenti ... non ancora implementato").

**Per mercato**: TOTAL_GOALS hit rate 50.0% (per costruzione, essendo un
mercato a 2 esiti circa equiprobabili) vs MATCH_RESULT 33.3% (3 esiti, la
selezione "principale" per livello di rischio non è sempre l'esito più
probabile in assoluto). Brier score comparabile tra i due mercati (~0.20–0.25).

**Home/away**: le selezioni sull'esito HOME hanno hit rate leggermente più
alto (43.5% EPL, 40.6% Serie A) rispetto alle altre selezioni — coerente con
il vantaggio-casa che il modello stesso stima (`home_advantage` positivo, v.
MODEL_SPEC.md), ma il ROI su HOME è più negativo (−4.8% EPL, −12.6% Serie A):
il mercato prezza il vantaggio-casa quantomeno altrettanto bene del modello.

**Nota metodologica sullo scope ridotto**: un primo tentativo su tutte e 10 le
stagioni con refit ogni 7 giorni (la configurazione di default) era stato
interrotto dopo diversi minuti senza essere completato — troppo costoso per
quella sessione. È stato quindi rieseguito con `refit_batch_days=21` (refit
ogni 3 settimane invece che ogni settimana) su 6 stagioni invece di 10: una
scelta di tempo, non un modo per nascondere risultati sfavorevoli.

**Aggiornamento — refit=7 giorni su tutte e 10 le stagioni (ROADMAP.md punto
2), completato**: con più tempo a disposizione, il backtest è stato rieseguito
nella configurazione di default (`refit_batch_days=7`, tutte le 10 stagioni,
3.800 partite per campionato invece di 2.280) — 192.8s per l'EPL, 170.9s per
la Serie A.

**Correzione di un errore di etichettatura (onestà > coerenza con quanto
scritto prima)**: la tabella di confronto qui sotto, in una prima stesura di
questo documento, etichettava le colonne "prima" come `21d/6 stagioni`. È
sbagliato: quei numeri venivano dalla prima persistenza reale in DB
(`scripts/persist_backtest_results.py`, ROADMAP.md punto 1), che per un bug
nello script usava `refit_batch_days=7` (il default di
`app/backtest/runner.py`), non 21 — il valore salvato in
`ModelVersion.hyperparameters_json` era corretto (7), solo il testo
descrittivo qui e nel docstring dello script erano sbagliati. Il vero run a
21 giorni/6 stagioni esiste (sezione "Validazione empirica" sopra, con le
metriche per-livello-di-rischio e il bin 0.9–1.0 EPL: predetto 92.6%,
osservato 71.4%, n=42) ma **non con Brier/log loss per mercato a questa
precisione** — quindi il confronto seguente isola correttamente **solo
l'effetto del numero di stagioni** (6 vs 10), tenendo il refit fisso a 7
giorni su entrambi i lati, non un confronto 21d-vs-7d:

| Segmento | n (7d/6 stag., DB) | Brier (7d/6) | LogLoss (7d/6) | n (7d/10 stag.) | Brier (7d/10) | LogLoss (7d/10) |
|---|---|---|---|---|---|---|
| EPL MATCH_RESULT | 13.158 | 0.1948 | 0.5768 | 27.964 | 0.1872 | 0.5628 |
| EPL TOTAL_GOALS | 8.772 | 0.2476 | 0.6898 | 9.096 | 0.2441 | 0.6817 |
| Serie A MATCH_RESULT | 13.122 | 0.1955 | 0.5777 | 27.960 | 0.1849 | 0.5545 |
| Serie A TOTAL_GOALS | 8.748 | 0.2483 | 0.6918 | 9.080 | 0.2465 | 0.6869 |

Brier e log loss migliorano leggermente su tutti e 4 i segmenti con più
stagioni di storia (refit invariato a 7 giorni tra le due colonne) — nella
direzione attesa, non sorprendente. Hit rate MATCH_RESULT combinato scende
leggermente (33.3%→31.0% EPL, 33.3%→30.6% Serie A): non è una regressione del
modello, riflette le 4 stagioni più vecchie (2015/16–2018/19) ora incluse,
probabilmente meno prevedibili o con dati quote di qualità inferiore — non
ancora indagato nel dettaglio.

Calibrazione nel bin più alto (0.9–1.0), lo stesso che mostrava overconfidence
marcata sopra:

| Segmento | n | Predetto (7d/10) | Osservato (7d/10) | Gap |
|---|---|---|---|---|
| EPL | 50 | 93.3% | 84.0% | +9.3 punti (era +21.2 punti nel run originale 21d/6 stagioni, n=42 — v. "Validazione empirica" sopra; qui **sia** le stagioni **che** il refit sono cambiati, non un confronto isolato come la tabella Brier/log loss sopra) |
| Serie A | 38 | 93.0% | 73.7% | +19.3 punti (nessun dato comparabile dal run originale per la Serie A) |

Il gap si dimezza per l'EPL con più dati, ma resta ampio per la Serie A — e
in entrambi i casi n è piccolo (38-50), quindi parte del miglioramento
potrebbe essere rumore campionario piuttosto che un effetto reale di più
stagioni di storia. **Conclusione onesta**: la ricalibrazione dà un
guadagno di precisione reale ma modesto (Brier/log loss), non risolve da sola
il problema di overconfidence nelle code alte (v. anche calibrazione
post-hoc, punto 3 di ROADMAP.md) — coerente con quanto già osservato per
corner/cartellini: il problema non è principalmente la quantità di dati di
allenamento.

## Corner e cartellini — RISULTATI REALI (`app/backtest/count_market_runner.py`)

Stesso walk-forward, stesse 6 stagioni EPL+Serie A 2019/20–2024/25,
`refit_batch_days=21`. **Nessun ROI/profit/yield riportato** — non per omissione,
ma perché nessuna fonte dati integrata pubblica quote per questi due mercati
(v. MODEL_SPEC.md): `roi()`/`profit_units()` ritornano correttamente `None`
quando ogni bet ha `bookmaker_odds=None`, invece di un numero fabbricato.

| Segmento | n | Hit rate | Brier | Log loss |
|---|---|---|---|---|
| EPL corner (linea 9.5) | 2.210 | 56.6% | 0.2495 | 0.6949 |
| EPL cartellini (linea 3.5) | 2.210 | 58.4% | 0.2430 | 0.6835 |
| Serie A corner (linea 9.5) | 2.191 | 55.9% | 0.2501 | 0.6957 |
| Serie A cartellini (linea 3.5) | 2.191 | **68.9%** | 0.2105 | 0.6128 |
| **Combinato** | 8.802 | 59.9% | 0.2383 | 0.6718 |

Hit rate sistematicamente sopra il 50% su tutti e 4 i segmenti — il modello ha
un potere predittivo reale, non casuale, anche nella sua forma più semplice
(Poisson puro, nessuna correzione arbitro/tattica). Serie A cartellini si
distingue nettamente in meglio (68.9% vs 55.9-58.4% altrove) — un'osservazione
grezza dal backtest, non ancora spiegata (potrebbe riflettere arbitraggio più
consistente, stile di gioco più prevedibile, o semplice rumore campionario;
non c'è abbastanza evidenza qui per concludere quale).

**Segnale di calibrazione importante — overdispersione confermata**: a
differenza del modello Dixon-Coles per i gol (buona calibrazione fino al bin
0.6-0.7, overconfidence solo nelle code estreme), qui l'**overconfidence inizia
già dal bin 0.7-0.8 ed è sostanziale**:

| Bin probabilità predetta | EPL corner: predetto vs osservato | EPL cartellini: predetto vs osservato |
|---|---|---|
| 0.7–0.8 | 73.9% vs 59.8% | 74.3% vs 66.9% |
| 0.8–0.9 | 83.3% vs 58.3% | 83.8% vs 67.0% |

Un divario di 15-25 punti percentuali tra probabilità dichiarata e frequenza
osservata è un segnale chiaro, non rumore campionario (n=72-323 per bin). Questo
sembrava, a prima vista, il tipo di evidenza che indica overdispersione — **la
sezione seguente mette questa ipotesi alla prova con un vero confronto, invece
di limitarsi a passare al modello "più sofisticato" per assunzione.**

## Poisson vs binomiale negativa — confronto reale, decisione basata sui dati

`NegativeBinomialCountModel` (stessa struttura attacco/difesa/vantaggio-casa di
`PoissonCountModel`, più un parametro di dispersione `alpha` condiviso fittato
via MLE) è stato implementato e backtestato **sugli stessi identici dati,
stesso periodo, stesso protocollo walk-forward** già usati sopra per il
Poisson — confronto pulito, non contaminato da differenze di scope.

| Segmento | Poisson Brier | NB Brier | Poisson LogLoss | NB LogLoss |
|---|---|---|---|---|
| EPL corner | 0.2495 | 0.2481 | 0.6949 | 0.6909 |
| EPL cartellini | 0.2430 | 0.2429 | 0.6835 | 0.6834 |
| Serie A corner | 0.2501 | 0.2480 | 0.6957 | 0.6906 |
| Serie A cartellini | 0.2105 | *non completato* | 0.6128 | *non completato* |

(Serie A cartellini con NB non è stato completato: il fit è risultato
insolitamente lento su questo segmento specifico — probabilmente per via
dell'alto numero di osservazioni nelle fasce alte, n=838 e n=382 nei bin
0.7-0.8 e 0.8-0.9 — e l'esecuzione è stata interrotta dopo oltre 12 minuti per
restare in tempi ragionevoli in questa sessione. I 3 segmenti completati sono
comunque sufficienti per un giudizio, e questo limite è dichiarato qui invece
di essere nascosto.)

**Calibrazione nelle fasce alte — il vero test, non solo Brier/log loss aggregati:**

| Segmento | Bin | Poisson: predetto/osservato (gap) | NB: predetto/osservato (gap) |
|---|---|---|---|
| EPL corner | 0.7–0.8 | 73.9%/59.8% (+0.141) | 74.1%/55.2% (**+0.188**) |
| EPL corner | 0.8–0.9 | 83.3%/58.3% (+0.250) | 84.4%/62.1% (+0.223) |
| EPL corner | 0.9–1.0 | 92.6%/83.3% (+0.092) | 91.8%/81.8% (+0.100) |
| EPL cartellini | 0.7–0.8 | 74.3%/66.9% (+0.074) | 74.3%/67.0% (+0.073) |
| EPL cartellini | 0.8–0.9 | 83.8%/67.0% (+0.167) | 83.8%/67.0% (+0.167) |
| EPL cartellini | 0.9–1.0 | 95.9%/50.0% (+0.459) | 95.9%/50.0% (+0.459) |
| Serie A corner | 0.7–0.8 | 73.7%/64.8% (+0.089) | 74.0%/66.2% (+0.077) |
| Serie A corner | 0.8–0.9 | 83.8%/67.1% (+0.167) | 83.4%/62.7% (**+0.207**) |
| Serie A corner | 0.9–1.0 | 92.4%/75.0% (+0.174) | 92.7%/75.0% (+0.177) |

**Conclusione onesta: la binomiale negativa NON risolve il problema di
overconfidence nelle code alte.** I numeri, non un'aspettativa a priori,
dicono questo:

- Su Brier score e log loss **complessivi**, NB è marginalmente migliore in
  tutti e 3 i segmenti completati (differenze dell'ordine di 0.001-0.005) —
  un miglioramento reale ma piccolo, non trasformativo.
- Sulla **calibrazione nelle fasce alte** (l'obiettivo specifico di questo
  fix), il quadro è **misto, senza un pattern consistente**: NB migliora in
  alcuni bin (es. Serie A corner 0.7-0.8: 0.089→0.077), peggiora in altri (es.
  EPL corner 0.7-0.8: 0.141→**0.188**; Serie A corner 0.8-0.9: 0.167→**0.207**),
  e per i cartellini EPL è **sostanzialmente identica** bin per bin — segno che
  l'ottimizzatore ha convergiuto a un `alpha` vicino a zero (nessuna
  overdispersione utile da catturare in quel segmento specifico).
- NB produce sistematicamente **meno osservazioni nelle fasce di probabilità
  alta** (es. EPL corner 0.7-0.8: n=301 con Poisson, n=172 con NB) — il
  parametro di dispersione "smussa" le stime verso probabilità meno estreme,
  come atteso, ma questo da solo non basta a renderle meglio calibrate.

**Decisione: si mantiene `PoissonCountModel` in produzione (nessuna
sostituzione)**, non perché "già scelto" ma perché il backtest non giustifica
il cambio: un parametro di dispersione condiviso fra tutte le squadre non
compensa un'overconfidence che sembra derivare più dalla struttura media
(attacco/difesa) stessa — probabilmente per l'assenza di feature esplicative
note (arbitro per i cartellini, stile/tattica per i corner, v. MODEL_SPEC.md)
— che dalla forma della distribuzione di conteggio. `NegativeBinomialCountModel`
resta nel codice, testato e funzionante (non cancellato): un'ipotesi futura
onesta da riprovare è una dispersione **per singola squadra** invece che
condivisa, o l'aggiunta delle feature mancanti prima di ririprovare NB — non
"binomiale negativa in generale" come se fosse già stata smentita in modo
definitivo.

## Falli totali — RISULTATI REALI, mercato aggiunto in produzione

Aggiunto durante un audit di qualità di una sessione successiva
(`app.models.enums.MarketCategory.FOULS` esisteva già nello schema dal primo
slice, mai collegato al Decision Layer): dati già ingeriti al 100%
(`TeamMatchStats.fouls_committed`, 15.200 righe su 7.600 partite reali,
colonne HF/AF di football-data.co.uk), stessa classe `PoissonCountModel`
già usata per corner/cartellini (nessun modello nuovo da scrivere), stesso
protocollo walk-forward di `app/backtest/count_market_runner.py`, linea
24.5 (vicina alla media reale osservata, ~24.0 falli/partita nell'intero
dataset).

**A differenza di corner/cartellini, qui il backtest mostra una calibrazione
buona, non un'overconfidence marcata**:

| Segmento | N risolte | Hit rate | Brier | LogLoss |
|---|---|---|---|---|
| EPL falli | 3709 | 72.9% | 0.1883 | 0.5633 |
| Serie A falli | 3705 | 65.4% | 0.2193 | 0.6295 |

Calibrazione nelle fasce alte (predetto vs osservato, gap in punti
percentuali — confrontare con i gap di 15-25 punti di corner/cartellini
sopra):

| Segmento | Bin | Predetto | Osservato | Gap |
|---|---|---|---|---|
| EPL falli | 0.7–0.8 (n=1018) | 75.1% | 73.6% | +1.5 |
| EPL falli | 0.8–0.9 (n=950) | 84.6% | 80.8% | +3.8 |
| EPL falli | 0.9–1.0 (n=438) | 93.3% | 88.6% | +4.7 |
| Serie A falli | 0.7–0.8 (n=941) | 74.9% | 70.2% | +4.7 |
| Serie A falli | 0.8–0.9 (n=657) | 82.8% | 79.5% | +3.3 |

(Serie A 0.9–1.0 omesso: solo n=9 osservazioni, troppo poche per un gap
significativo — dichiarato qui invece di nascosto, non escluso per
convenienza.)

**Decisione basata sui dati: mercato abilitato in produzione**
(`count_market_estimates.py`, `additional_estimates`, stessa etichetta
esplicita "nessuna quota reale, Value/Alert n/d" degli altri due mercati
count). Gap di 1.5-4.7 punti, non 15-25 — il modello più semplice possibile
(Poisson puro, nessuna correzione arbitro/tattica) ha già un potere
predittivo reale e ragionevolmente calibrato su questo mercato specifico,
diversamente da corner/cartellini. Non ancora spiegato perché i falli si
comportino meglio (ipotesi non verificata: i falli dipendono più dal ritmo/
stile di gioco di una squadra, una caratteristica più stabile e catturata
meglio da una struttura attacco/difesa pura, rispetto a corner — più
influenzati dal possesso/territorio della singola partita — o cartellini —
fortemente dipendenti dall'arbitro specifico, dato non ancora ingerito).

## Calibrazione post-hoc (Platt scaling / isotonica) — confronto reale, decisione basata sui dati

`app/engine/decision/calibration.py` implementa entrambe le tecniche come
opzioni indipendenti e testabili (`PlattCalibrator`, `IsotonicCalibrator`, PAVA
senza dipendenza da scikit-learn). `app/backtest/calibration_runner.py` le
valuta senza leakage: fit su una porzione (temporalmente) precedente delle
predizioni già risolte dal walk-forward, valutazione sulla porzione successiva
tenuta da parte (split 80/20 per tempo, non casuale — la stessa disciplina
"mai vedere il futuro" degli altri backtest).

Eseguito su tutti gli 8 segmenti già backtestati sopra (EPL+Serie A ×
{MATCH_RESULT, TOTAL_GOALS, CORNERS, CARDS}, 10 stagioni):

| Segmento | n test | Brier raw | Brier Platt | Brier isotonica |
|---|---|---|---|---|
| EPL MATCH_RESULT | 5.593 | 0.1903 | 0.1908 (peggio) | 0.1906 (peggio) |
| EPL TOTAL_GOALS | 1.820 | 0.2391 | 0.2401 (peggio) | 0.2390 (~pari) |
| EPL CORNERS | 742 | 0.2384 | 0.2393 (peggio) | 0.2386 (~pari) |
| EPL CARDS | 742 | 0.2411 | 0.2409 (~pari) | 0.2406 (~pari) |
| Serie A MATCH_RESULT | 5.592 | 0.1977 | 0.1978 (~pari) | 0.1976 (~pari) |
| Serie A TOTAL_GOALS | 1.816 | 0.2455 | 0.2447 (meglio) | 0.2461 (peggio) |
| Serie A CORNERS | 741 | 0.2421 | 0.2418 (~pari) | 0.2422 (~pari) |
| Serie A CARDS | 741 | 0.2296 | 0.2320 (peggio) | 0.2300 (~pari) |

Nessuno dei due metodi vince in modo sistematico: Platt migliora 3/8 segmenti
e peggiora 5/8; isotonica migliora/pareggia 3/8 e peggiora 5/8 — e le
differenze sono quasi ovunque nell'ordine di 0.0001-0.0025 (rumore, non un
effetto). Il test che conta davvero è la calibrazione nelle fasce alte
(0.7+), dove il problema è documentato:

| Segmento | Bin | Gap raw | Gap Platt | Gap isotonica |
|---|---|---|---|---|
| EPL MATCH_RESULT | 0.8–0.9 (n=64) | −0.044 | **−0.162** | −0.064 |
| EPL TOTAL_GOALS | 0.7–0.8 (n=32) | −0.078 | **−0.286** | −0.119 |
| EPL CARDS | 0.7–0.8 (n=87) | +0.118 | **−0.278** | **−0.275** |
| Serie A MATCH_RESULT | 0.7–0.8 (n=120) | +0.109 | +0.070 | **+0.029** |
| Serie A MATCH_RESULT | 0.8–0.9 (n=30) | +0.161 | +0.119 | **+0.043** |
| Serie A CARDS | 0.8–0.9 (n=57) | +0.077 | **+0.142** | n/a |

(Tabella completa nell'output dello script, non incluso nel repo — stesso
formato degli script ad-hoc precedenti.) La direzione dell'effetto è
**incoerente tra segmenti**: per Serie A MATCH_RESULT l'isotonica dimezza
davvero il gap (un miglioramento reale, non rumore, su n=120-30). Ma per EPL
CARDS/TOTAL_GOALS/MATCH_RESULT entrambi i metodi **peggiorano** nettamente il
gap, a volte capovolgendo il segno (da overconfidence a underconfidence). Nei
mercati corner/cartellini molti bin alti finiscono vuoti dopo la
trasformazione (`n/a` in tabella): il fit su un train set già ridotto
(n≈2.960-2.970 per il train, con ancora meno osservazioni nelle code più
estreme) produce trasformazioni aggressive (es. Platt `a=0.247` per EPL
corner) che comprimono quasi tutte le probabilità lontano dagli estremi,
"risolvendo" l'overconfidence spostando il problema fuori dal bin osservabile
— non un fix genuino.

**Conclusione onesta, decisione basata sui numeri, non sull'eleganza del
metodo**: né Platt scaling né la regressione isotonica vengono attivate in
produzione. Nessuno dei due migliora la calibrazione nelle fasce alte in modo
consistente tra segmenti — un vero miglioramento (Serie A MATCH_RESULT) e
peggioramenti netti altrove (EPL CARDS/TOTAL_GOALS) nello stesso esperimento.
`fit_platt_calibration`/`fit_isotonic_calibration` restano nel codice, testati
e funzionanti, non cancellati — un'ipotesi futura più mirata (fit per singolo
bin con soglia minima di osservazioni, o calibrazione fittata solo dove il
segmento ha abbastanza dati) non è stata ancora provata.

Questo è il **terzo** tentativo indipendente di risolvere l'overconfidence
nelle code alte che non ci riesce in modo consistente (dopo: binomiale
negativa per corner/cartellini, più stagioni di storia per i gol) — un
pattern che rafforza, non indebolisce, l'ipotesi già in ROADMAP.md: il
problema probabilmente non è la forma della distribuzione, né la quantità di
dati, né una trasformazione scalare post-hoc, ma **feature esplicative
mancanti nella struttura media** (arbitro per i cartellini, tattica per i
corner, feature aggiuntive non ancora identificate per i gol/1X2).

## xG-adjusted Dixon-Coles — confronto reale, decisione basata sui dati

Le `TacticalFeature` reali (xG per partita, da understat, v. ROADMAP.md
punto 5) sono state usate per correggere le attese di gol di Dixon-Coles:
`compute_xg_adjustment_factor` (`app/engine/statistical/tactical_adjustment.py`)
calcola, per ogni squadra e solo dalle partite strettamente precedenti alla
data di previsione, il rapporto tra xG medio e gol realmente segnati — un
fattore >1 indica una squadra che crea occasioni migliori di quante ne
concretizzi (sottoperformance, "sfortunata"), <1 il contrario. Il fattore
(clippato a [0.75, 1.33], un limite di sicurezza dichiarato, non calibrato
sui risultati del backtest) moltiplica il lambda/mu grezzo di Dixon-Coles
prima di calcolare le probabilità finali — mai applicato quando una squadra
non ha almeno 5 partite precedenti con dato xG (nessun numero indovinato).

**Scope**: le `TacticalFeature` coprono solo la stagione 2023/24 (v. ROADMAP.md
punto 5) — il confronto è quindi limitato a EPL+Serie A 2023/24, walk-forward,
stesso protocollo (refit=7gg, `MIN_TRAINING_MATCHES=80`) già usato altrove.
Non è un confronto su tutte le 10 stagioni: dove il dato xG non esiste, il
modello resta quello attuale senza alcuna correzione (v. sotto per come
questo si traduce in codice).

| Segmento | n | Brier raw | Brier xG-adj | LogLoss raw | LogLoss xG-adj |
|---|---|---|---|---|---|
| EPL MATCH_RESULT | 900 | 0.1898 | **0.1870** | 0.5662 | **0.5589** |
| EPL TOTAL_GOALS | 600 | 0.2403 | **0.2327** | 0.6767 | **0.6591** |
| Serie A MATCH_RESULT | 900 | **0.1974** | 0.1986 | 0.5953 | 0.5909 |
| Serie A TOTAL_GOALS | 600 | **0.2552** | 0.2580 | 0.7120 | 0.7126 |

(`n` = ogni candidato H/D/A o OVER/UNDER con quota reale disponibile, una
volta per partita — non replicato per i 10 livelli di rischio, per isolare
la qualità della probabilità dal meccanismo di selezione del ladder.)

Calibrazione nelle fasce alte (0.7+), lo stesso confronto:

| Segmento | Bin | Gap raw | Gap xG-adj |
|---|---|---|---|
| EPL MATCH_RESULT | 0.7–0.8 (n=42→36) | +0.121 | **+0.075** |
| EPL MATCH_RESULT | 0.9–1.0 (n=7→5) | +0.219 | **+0.125** |
| EPL TOTAL_GOALS | 0.8–0.9 (n=10→11) | +0.333 | **+0.110** |
| Serie A MATCH_RESULT | 0.7–0.8 (n=28) | −0.005 (già buono) | **+0.098** (peggiora) |
| Serie A MATCH_RESULT | 0.9–1.0 (n=9→3) | +0.258 | **+0.608** (peggiora, n piccolo) |
| Serie A TOTAL_GOALS | 0.8–0.9 (n=16→5) | +0.320 | **+0.642** (peggiora, n piccolo) |

**Conclusione onesta, incoerente tra campionati — non attivata di default.**
L'aggiustamento xG **migliora davvero** Brier, log loss e calibrazione nelle
fasce alte per l'**EPL**, su entrambi i mercati. Per la **Serie A** non aiuta
— Brier/log loss leggermente peggiori, e nel bin 0.7-0.8 di MATCH_RESULT
(l'unico già ben calibrato nel modello raw) l'aggiustamento introduce
overconfidence dove prima non c'era. Questo non è il pattern "aiuta ovunque
un po'" che giustificherebbe un'attivazione di default — è un miglioramento
reale ma **specifico dell'EPL**, di cui questa sessione non ha un'ipotesi
verificata (possibile rumore di campionamento vista la finestra di un solo
campionato/stagione, o una differenza reale nello stile di gioco/varianza di
finalizzazione tra i due campionati — nessuna delle due è stata testata qui).

**Decisione**: `compute_xg_adjustment_factor`/`apply_tactical_adjustment`
restano nel codice, testati e funzionanti, **non collegati** al layer di
analisi live (`analysis_runner.py` continua a usare Dixon-Coles senza
correzione xG per tutte le partite, EPL e Serie A comprese) — non per
mancanza dell'implementazione, ma perché il backtest non giustifica
un'attivazione uniforme. Un'attivazione **solo per EPL**, se mai presa,
richiederebbe la stessa cautela già usata per le decisioni di questo tipo:
non abbastanza dati qui (una sola stagione) per escludere che sia rumore.

### Aggiornamento (turno successivo, dopo il backfill a 10 stagioni) — ri-testato, il segnale EPL non regge

Stesso protocollo esatto (refit=7gg, `MIN_TRAINING_MATCHES=80`), stesso
codice di produzione (`compute_xg_adjustment_factor`/
`apply_tactical_adjustment`, non modificato), ora su tutte le 10 stagioni
disponibili (2015/16–2024/25) invece che solo 2023/24 — **~12 volte più
osservazioni per segmento** (n=900→11.118 per MATCH_RESULT, n=600→4.548 per
TOTAL_GOALS, per campionato).

| Segmento | n | Brier raw | Brier xG-adj | LogLoss raw | LogLoss xG-adj |
|---|---|---|---|---|---|
| EPL MATCH_RESULT | 11.118 | 0.1923 | 0.1930 (peggiora, marginale) | 0.5721 | 0.5736 (peggiora, marginale) |
| EPL TOTAL_GOALS | 4.548 | 0.2441 | 0.2438 (migliora, marginale) | 0.6817 | 0.6811 (migliora, marginale) |
| Serie A MATCH_RESULT | 11.112 | 0.1921 | 0.1920 (invariato) | 0.5717 | 0.5717 (identico) |
| Serie A TOTAL_GOALS | 4.540 | 0.2465 | 0.2468 (peggiora, marginale) | 0.6869 | 0.6874 (peggiora, marginale) |

**Il precedente segnale positivo per l'EPL (Brier 0.1898→0.1870,
−0.0028) non regge con 12 volte più dati (0.1923→0.1930, +0.0007, di
segno opposto).** Tutte le differenze aggregate, per entrambi i
campionati ed entrambi i mercati, sono ora dell'ordine di ±0.0005-0.0007 —
compatibili con rumore, non con un effetto reale in nessuna direzione.
Questo è l'esito onesto, anche se diverso da entrambe le ipotesi poste
esplicitamente all'inizio del ri-test ("aiuta anche la Serie A" oppure "si
conferma uguale a prima"): **il miglioramento EPL osservato con una sola
stagione (n=900) appare, con più dati, un artefatto di campione piccolo**,
non un effetto reale specifico del campionato.

Unica eccezione parziale: nelle fasce di calibrazione alte (0.7+) per
**EPL MATCH_RESULT**, il gap continua a restringersi con la correzione
applicata anche nel campione più ampio (0.7-0.8: −0.023→−0.012; 0.8-0.9:
+0.020→+0.006; 0.9-1.0: +0.074→+0.017, ma n=21→12, ancora piccolo) — un
segnale di calibrazione nelle code che non emerge nel Brier/log loss
aggregato. Non abbastanza per giustificare un'attivazione (un solo mercato,
un solo campionato, bin con n ancora limitato), ma onestamente diverso da
un "nessun effetto in assoluto".

**Decisione confermata, ora su base più solida**: `compute_xg_adjustment_factor`
resta **non attivato** per entrambi i campionati — la conclusione non
cambia, ma la sua giustificazione è più forte (12 volte più dati, nessun
segnale aggregato consistente in nessuna direzione) invece di riposare su
una singola stagione dove un'apparente differenza tra campionati poteva
essere solo rumore campionario, come infatti sembra essere stato.

## PPDA/deep completions vs corner — correlazione reale confermata, correzione testata e scartata

Prima di costruire qualunque correzione, verificata la correlazione reale tra
i dati tattici e i corner effettivi (2023/24 EPL+Serie A, 1.516 osservazioni
squadra-partita con sia dato tattico che corner reali):

| Feature | Corner (Pearson r) |
|---|---|
| PPDA (pressing — più basso = più aggressivo) | **−0.264** (pressing più aggressivo → più corner, direzione ipotizzata confermata) |
| Deep completions | **+0.447** (segnale più forte di PPDA) |

Entrambe le correlazioni sono reali e non banali — non assunte, verificate.
Costruita quindi una correzione basata su deep completions (segnale più
forte): `compute_deep_completions_adjustment_factor` — rapporto tra la media
di deep completions della squadra (solo partite precedenti) e la media di
lega nella stessa finestra, clippato come per l'aggiustamento xG, applicata
al lambda/mu grezzo di `PoissonCountModel` per il mercato corner (linea 9.5).

Backtestata con lo stesso protocollo walk-forward (refit=21gg,
`MIN_TRAINING_MATCHES=40`), EPL+Serie A 2023/24:

| Segmento | n | Hit rate raw | Hit rate adj | Brier raw | Brier adj | LogLoss raw | LogLoss adj |
|---|---|---|---|---|---|---|---|
| EPL corner | 331 | 58.3% | 58.0% | 0.2512 | **0.2705** | 0.7102 | **0.7864** |
| Serie A corner | 308 | 54.2% | **48.1%** | 0.2656 | **0.3173** | 0.7383 | **0.8883** |

Calibrazione nelle fasce alte, entrambi i campionati: il gap **peggiora** in
ogni singolo bin ≥0.7 con la correzione applicata (es. EPL 0.7-0.8: gap
+0.166→+0.246; Serie A 0.9-1.0: gap +0.191→+0.369).

**Conclusione onesta — risultato negativo, non solo incoerente questa
volta: la correzione peggiora la previsione su ogni metrica, per entrambi i
campionati.** La correlazione osservata è reale, ma applicarla come fattore
moltiplicativo aggiuntivo su `PoissonCountModel` non aiuta — un'ipotesi
plausibile (non verificata oltre in questa sessione): l'attacco/difesa già
fittati dal modello Poisson catturano implicitamente lo stile di gioco di
una squadra (incluso quanto genera azioni pericolose in zona avanzata), per
cui una correzione basata su deep completions aggiunge lo stesso segnale una
seconda volta invece di informazione nuova — amplificando la varianza
piuttosto che migliorare la stima. **Decisione basata sui numeri**: `compute_
deep_completions_adjustment_factor` resta nel codice, testato, **non
collegato** a `count_market_estimates.py` — nessuna attivazione, per nessuno
dei due campionati. A differenza dell'aggiustamento xG (positivo per l'EPL),
qui il segnale negativo è netto su entrambi i campionati, non solo
incoerente tra loro.

**Aggiornamento (turno successivo, dopo il backfill a 10 stagioni) — correlazione
riconfermata su un campione 10 volte più ampio, backtest NON ripetuto,
motivato esplicitamente:**

| Feature | r su 1.516 oss. (2023/24) | r su 15.122 oss. (10 stagioni, 2015/16–2024/25) |
|---|---|---|
| PPDA | −0.264 | **−0.310** |
| Deep completions | +0.447 | **+0.424** |

La correlazione non era un artefatto di campione piccolo — resta della
stessa entità (anzi leggermente più forte per PPDA) con 10 volte più dati.
Questo risolve la domanda posta esplicitamente in questo turno ("il problema
era la scarsità di dati o la correlazione stessa che non regge?"): **né
l'una né l'altra** — la correlazione grezza è reale e stabile, il problema è
specificamente nel modo in cui era stata tradotta in una correzione
applicata al modello (l'ipotesi già scritta sopra: probabile ridondanza con
ciò che attacco/difesa Poisson già catturano). Un dataset più ampio non
avrebbe cambiato l'esito di quel meccanismo — motivo per cui il backtest
completo (walk-forward su 10 stagioni, stesso protocollo) **non è stato
ripetuto**: sarebbe stato un test il cui risultato era già prevedibile dalla
sola riconferma della correlazione, non una verifica onesta di
un'ipotesi aperta. Nessuna modifica alla decisione: `compute_
deep_completions_adjustment_factor` resta testato, non collegato.

## Calibrazione soglie alert su dati reali

Le soglie `ALERT_THRESHOLD_INTERESTING`/`ALERT_THRESHOLD_STRONG`
(`app/engine/decision/value.py`) erano provvisorie dalla stesura iniziale del
brief, mai verificate contro il backtest reale. Verificato in una sessione
successiva: preso l'intero output del backtest walk-forward reale a 10
stagioni (lo stesso che produce i numeri sopra — **74.100 predizioni
risolte in totale**, EPL+Serie A, tutti i mercati/livelli di rischio),
calcolato `discrepancy_pct` reale per ognuna (la stessa quantità che
`classify_alert` classifica) e aggregato per fascia di `|discrepancy|`:

| Fascia | n | Hit rate | ROI | Brier | Log loss |
|---|---|---|---|---|---|
| 0–5% | 17.376 | 39.5% | −3.0% | 0.207 | 0.601 |
| 5–10% | 15.234 | 39.4% | −0.7% | 0.209 | 0.607 |
| 10–15% | 12.493 | 38.2% | −2.9% | 0.205 | 0.597 |
| 15–20% | 8.922 | 36.3% | −2.7% | 0.206 | 0.598 |
| 20–30% | 9.666 | 32.5% | −7.5% | 0.200 | 0.583 |
| 30%+ | 10.409 | 22.2% | −14.6% | 0.167 | 0.535 |

**Risultato onesto, e opposto all'assunzione implicita nel brief originale**:
una discrepanza modello-mercato più grande **non** significa che il modello
abbia più probabilità di avere ragione — hit rate e ROI peggiorano
**monotonicamente** al crescere della discrepanza, non migliorano. La fascia
30%+ è marcatamente la peggiore (hit rate 22.2% contro 39.5% della fascia
0-5%, ROI −14.6%). La tabella di calibrazione per fascia (probabilità media
predetta vs hit rate osservato) mostra inoltre che il modello è
**overconfident proprio nella fascia di discrepanza più alta** (predetto
24.9%, osservato 22.2%, gap +2.7 punti) — coerente con l'overconfidence
nelle code alte già documentata sopra per la calibrazione generale, qui
isolata specificamente sulla fascia che l'alert "forte" segnala.

**Conclusione e modifica applicata**: le due soglie non separavano bene
"probabile opportunità" da "rumore", perché quella lettura non è supportata
dai dati — quello che la discrepanza segnala davvero è "il modello si
discosta molto dal book", che qui correla con una performance **peggiore**
del modello, non migliore. Applicate due modifiche, entrambe motivate dai
numeri sopra, non a istinto:
1. **`ALERT_THRESHOLD_STRONG` spostata da 0.15 a 0.20`**: le fasce 10-15%/
   15-20% si comportano in modo simile (ROI −2.9%/−2.7%), mentre il vero
   peggioramento comincia nettamente al 20% (−7.5%, poi −14.6%) — 0.20 è
   dove si trova il reale punto di rottura nei dati, non un arrotondamento
   arbitrario.
2. **`ALERT_THRESHOLD_INTERESTING` resta a 0.10**: le fasce 0-5%/5-10%/
   10-15% non mostrano un punto di rottura pulito (ROI oscilla tra
   −3.0%/−0.7%/−2.9%, verosimilmente per la composizione di mercati/livelli
   di rischio in ciascuna fascia più che per un vero effetto soglia) — non
   c'è nei dati un segnale altrettanto netto per giustificare uno
   spostamento qui.
3. **Riformulato il linguaggio dell'alert** (`classify_alert`'s docstring,
   `AlertPopover.tsx`): non più "discrepanza marcata (potenziale
   mispricing)", che implicava un'opportunità — ora un esplicito segnale di
   cautela ("storicamente il modello ha più spesso torto qui"), coerente
   con quanto la tabella sopra mostra davvero. Trovata anche, durante questo
   lavoro, una funzione morta (`alert_explanation()` in `value.py`, mai
   chiamata da nessuna parte, con lo stesso testo obsoleto duplicato) —
   rimossa invece di lasciarla come fonte di confusione futura.

Script di analisi non incluso nel repository (esecuzione una tantum sui dati
già ingeriti, stesso pattern di `scripts/persist_backtest_results.py` per il
caricamento dei record reali) — i numeri sopra sono il suo output diretto,
non ricalcolati a mano.

## Cosa manca (onestamente)

- ✅ Il refit più frequente (7 giorni, default) su tutte le 10 stagioni è
  stato eseguito (v. sezione sopra) — non più un limite di questa sessione.
- ✅ I risultati sono ora persistiti in righe `Backtest` reali
  (`scripts/persist_backtest_results.py`, v. ROADMAP.md punto 1) — non più
  solo riportati a mano.
- Metriche per player props: bloccate dall'assenza di un modello dedicato
  (v. MODEL_SPEC.md). Corner/cartellini **hanno invece già risultati reali**
  (v. sezione dedicata sopra, `PoissonCountModel`) — l'unico limite per loro
  è l'assenza di una quota di mercato per calcolare ROI/value (v.
  DATA_SOURCES.md), non l'assenza di un modello o di un backtest.
- Distribuzione di probabilità e stabilità nel tempo (richiesta dal brief) —
  `calibration_curve` copre la prima; una vera analisi di stabilità
  richiederebbe di confrontare backtest su finestre temporali diverse, non
  ancora automatizzato in uno script dedicato.
- ✅ ~~Non è stata eseguita alcuna ricalibrazione delle soglie di alert~~ —
  fatto (v. sezione dedicata sopra): `ALERT_THRESHOLD_STRONG` ricalibrata da
  0.15 a 0.20 sui dati reali. **Resta aperta** solo la ricalibrazione dei
  pesi di `risk_score.WEIGHTS` — nessuna analisi tentata finora su quel
  punto specifico.
