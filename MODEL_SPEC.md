# Model Spec

## Scelta dei modelli per mercato

| Mercato | Modello scelto | Perché | Stato |
|---|---|---|---|
| 1X2 / Doppia chance | Dixon-Coles Poisson bivariato | Standard per i mercati a gol nel calcio, interpretabile (rating attacco/difesa per squadra), corregge la sotto-stima dei punteggi bassi correlati (0-0, 1-1) rispetto a due Poisson indipendenti (Dixon & Coles, 1997). | **Implementato** (`app/engine/statistical/dixon_coles.py`) |
| Over/Under gol | Stessa distribuzione di punteggio del modello Dixon-Coles, sommata sulla matrice di score | Nessun motivo di usare un modello diverso: O/U è una proiezione della stessa distribuzione congiunta dei gol. | **Implementato** |
| Both Teams To Score | Idem, proiezione della stessa matrice | Idem | **Implementato** |
| Handicap asiatico | Stessa matrice di score, soglia sulla differenza gol | Stessa distribuzione, cambia solo l'evento aggregato | Non ancora esposto nel Decision Layer (v. ROADMAP) |
| Corner | Da valutare: Poisson/binomiale negativa separata per corner-for/against, corretta per avversario | I corner non seguono la stessa dinamica dei gol (dipendono da possesso, stile di attacco sulle fasce) — serve un modello dedicato con feature tattiche come input, non gli stessi due parametri attacco/difesa. | Non implementato in questo slice (mancano dati corner storici sufficientemente ricchi ingestiti) |
| Cartellini / Falli | Binomiale negativa o Poisson, corretto per arbitro (feature `RefereeStats`) | I cartellini dipendono fortemente dall'arbitro, non solo dalle squadre — un modello che ignori l'arbitro è mal specificato. | Non implementato (richiede feature arbitro, v. ROADMAP) |
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

## Probabilità → quota fair → value

- `fair_odds = 1 / probability` (`app/engine/decision/fair_odds.py`) — formula
  pura, nessun aggiustamento nascosto. Raffinamenti (calibrazione, blend con
  probabilità di mercato) sono un passo esplicito e separato, non ancora
  implementato: la pipeline attuale usa la probabilità grezza del modello.
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
- **affidabilità modello**: nel backtest è una media mobile del Brier score
  *storico* (solo su predizioni già risolte prima nel tempo, mai sulla partita
  corrente — v. BACKTEST_SPEC.md); nell'endpoint di analisi live è oggi un
  valore neutro (0.5) finché non esiste ancora uno storico di backtest persistito
  collegato al `ModelVersion` in uso (v. ROADMAP: collegare `Backtest.brier_score`
  al `ModelVersion` corrente).
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
