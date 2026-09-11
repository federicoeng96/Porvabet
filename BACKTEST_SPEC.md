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

## Validazione empirica (dati sintetici, per verificare che la pipeline funzioni)

Eseguendo il backtest su un dataset sintetico di 750 partite (10 squadre,
forza vera nota, quote derivate da un margine fisso sulla probabilità vera
— v. script usato in sviluppo, non incluso nel repo perché puramente
diagnostico) si osserva la proprietà attesa: hit rate e ROI **decrescono
monotonicamente** dal Risk 1 al Risk 10 (hit rate dal 78% al 20% circa in
quella prova) — cioè il ranking di rischio separa correttamente selezioni più
sicure da selezioni più rischiose. Questo è il tipo di controllo che va
ripetuto su dati reali non appena disponibili, ed è esattamente il segnale che
guiderebbe una ricalibrazione dei pesi in `risk_score.py` se non si osservasse.

## Cosa manca (onestamente)

- **Nessun dato reale è stato effettivamente processato dal backtest in questo
  repository** — l'ambiente di sviluppo sandboxato non ha accesso di rete verso
  football-data.co.uk (v. ARCHITECTURE.md). Il backtest è stato validato solo
  su dati sintetici (proprietà statistiche generali, non risultati reali).
- Calibrazione/log loss/Brier score reali richiedono di eseguire
  `run_walk_forward_backtest` su dati ingeriti da football-data.co.uk in un
  ambiente con accesso di rete, poi salvare l'esito in una riga `Backtest`
  (tabella già presente nello schema, non ancora scritta da nessun codice —
  prossimo passo di implementazione, v. ROADMAP).
- Metriche per player props, corner, cartellini: bloccate dall'assenza dei
  modelli corrispondenti (v. MODEL_SPEC.md).
- Distribuzione di probabilità e stabilità nel tempo (richiesta dal brief) —
  `calibration_curve` copre la prima; una vera analisi di stabilità
  richiederebbe di confrontare backtest su finestre temporali diverse, non
  ancora automatizzato in uno script dedicato.
