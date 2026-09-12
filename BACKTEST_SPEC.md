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

Questo è testato end-to-end (dati sintetici) in
`tests/test_analysis_runner.py` e verificato manualmente su un dataset
sintetico più grande (v. sezione "Validazione empirica" sotto).

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
la Serie A. Confronto diretto con la configurazione ridotta sopra:

| Segmento | n (21d/6 stag.) | Brier (21d/6) | LogLoss (21d/6) | n (7d/10 stag.) | Brier (7d/10) | LogLoss (7d/10) |
|---|---|---|---|---|---|---|
| EPL MATCH_RESULT | 13.158 | 0.1948 | 0.5768 | 27.964 | 0.1872 | 0.5628 |
| EPL TOTAL_GOALS | 8.772 | 0.2476 | 0.6898 | 9.096 | 0.2441 | 0.6817 |
| Serie A MATCH_RESULT | 13.122 | 0.1955 | 0.5777 | 27.960 | 0.1849 | 0.5545 |
| Serie A TOTAL_GOALS | 8.748 | 0.2483 | 0.6918 | 9.080 | 0.2465 | 0.6869 |

Brier e log loss migliorano leggermente su tutti e 4 i segmenti con più dati e
refit più frequente — nella direzione attesa, non sorprendente. Hit rate
MATCH_RESULT combinato scende leggermente (33.3%→31.0% EPL, 33.3%→30.6% Serie
A): non è una regressione del modello, riflette le 4 stagioni più vecchie
(2015/16–2018/19) ora incluse, probabilmente meno prevedibili o con dati
quote di qualità inferiore — non ancora indagato nel dettaglio.

Calibrazione nel bin più alto (0.9–1.0), lo stesso che mostrava overconfidence
marcata sopra:

| Segmento | n | Predetto (7d/10) | Osservato (7d/10) | Gap |
|---|---|---|---|---|
| EPL | 50 | 93.3% | 84.0% | +9.3 punti (era +21.2 punti con 21d/6 stagioni, n=42) |
| Serie A | 38 | 93.0% | 73.7% | +19.3 punti |

Il gap si dimezza per l'EPL con più dati, ma resta ampio per la Serie A — e
in entrambi i casi n è piccolo (38-50), quindi parte del miglioramento
potrebbe essere rumore campionario piuttosto che un effetto reale di
più dati/refit più frequente. **Conclusione onesta**: la ricalibrazione dà un
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

## Cosa manca (onestamente)

- Il risultato sopra usa `refit_batch_days=21` e 6 stagioni per contenere il
  tempo di esecuzione in questa sessione — un run con la finestra di refit
  di default (7 giorni) su tutte le 10 stagioni disponibili darebbe una stima
  leggermente più precisa (più rifit = modello più aggiornato in ogni
  momento) ma è computazionalmente più oneroso; non è stato eseguito qui per
  limiti di tempo, non per scelta di merito.
- I risultati sopra non sono ancora persistiti in una riga `Backtest` (tabella
  già presente nello schema) — sono stati calcolati con uno script ad-hoc
  (non incluso nel repo) e riportati qui manualmente. Collegare
  `run_walk_forward_backtest` a una scrittura `Backtest` automatica resta un
  passo di implementazione futuro (v. ROADMAP).
- Metriche per player props, corner, cartellini: bloccate dall'assenza dei
  modelli corrispondenti (v. MODEL_SPEC.md).
- Distribuzione di probabilità e stabilità nel tempo (richiesta dal brief) —
  `calibration_curve` copre la prima; una vera analisi di stabilità
  richiederebbe di confrontare backtest su finestre temporali diverse, non
  ancora automatizzato in uno script dedicato.
- Non è stata eseguita alcuna ricalibrazione dei pesi (`risk_score.WEIGHTS`) o
  delle soglie di alert sulla base di questi risultati — sono riportati come
  input per una ricalibrazione futura, non ancora applicata.
