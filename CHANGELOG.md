# Changelog

Un rigo di sintesi per ogni commit di questa (lunga) sessione autonoma, in
ordine cronologico, per una revisione rapida senza dover rileggere ogni
commit singolarmente. Non sostituisce `git log`/i messaggi di commit
completi — è un indice.

## Sessione precedente (contesto)

- `e5dba5b` — Vertical slice iniziale: motore di analisi pre-match (dati
  sintetici, architettura completa).
- `6055d0a` — Prima ingestione reale (7.600 partite EPL+Serie A) e primo
  backtest walk-forward reale.
- `cb791e8` — Mercati corner/cartellini, verifica definitiva accesso ePlay24,
  tracciamento esplicito del rischio legale per fonte dati.

## Sessione corrente

- `540b242` — Binomiale negativa testata contro Poisson per corner/cartellini
  (stesso backtest reale, stesso periodo): non risolve l'overconfidence nelle
  code alte in modo consistente → **Poisson resta il modello di produzione**.
  Chiusura definitiva di diretta.it (gap già coperto da football-data.co.uk).
  Aggiunta `app/backtest/persistence.py` (aggregazione backtest → riga DB).
- `6dffd09` — Roadmap item 1 (persistere risultati di backtest) completato
  con numeri reali: 8 righe `ModelVersion`/`Backtest` scritte in DB.
- `3b8aac6` — Roadmap item 2 (refit più frequente su tutte le stagioni)
  completato: Brier/log loss migliorano leggermente, calibrazione code alte
  non risolta del tutto.
- `8cbc063` — `model_reliability` reale al posto del placeholder 0.5 (gap di
  calibrazione dalla riga `Backtest` persistita, fail-conservative se non
  stimabile). Trovato e corretto un bug di etichettatura (`refit_batch_days`
  mostrato come 21 quando il codice usava 7) in BACKTEST_SPEC.md/ROADMAP.md.
  Aggiunto modulo di calibrazione post-hoc (Platt + isotonica) non ancora
  validato sui dati reali (prossimo commit).
- `fee54c0` — Aggiornato CHANGELOG.
- `45e6d63` — Platt/isotonica testate sugli 8 segmenti reali: nessuna delle
  due migliora la calibrazione code alte in modo consistente → **nessuna
  attivata in produzione**. Terzo tentativo indipendente (dopo NB e più
  stagioni) con la stessa conclusione — rafforza l'ipotesi "feature mancanti"
  sulla struttura media, non un problema di forma/calibrazione.
- `606aafb` — Aggiornato CHANGELOG.
- `2a3d20b` — Verificati fbref/understat con rete reale per la prima volta:
  **entrambi rotti**. understat ha cambiato struttura (dati non più
  incorporati nell'HTML); fbref blocca con una sfida Cloudflare prima del
  contenuto. Item 5 roadmap (Matchup Engine) bloccato sul lato dati,
  documentato onestamente invece di forzare un workaround (bypassare
  Cloudflare richiederebbe un browser reale, decisione non presa
  autonomamente).
- `5620547` — Aggiornato CHANGELOG.
- `1819e94` — Roadmap item 10 (parte 1): endpoint batch
  `POST /matches/analyze-batch` al posto di N chiamate parallele dal
  frontend. Trovato e corretto un gap reale nell'isolamento delle
  transazioni nei test (`join_transaction_mode="create_savepoint"`),
  scoperto scrivendo i primi test a livello API del progetto. Verificato
  anche end-to-end con curl contro il DB dev reale.
- `773b9ab` — Aggiornato CHANGELOG.
- `4f00313` — Roadmap item 10 (parte 2, schedina): **non implementata**,
  segnalata come ambiguità reale — non è chiaro cosa si dovrebbe salvare, e
  non esiste alcun modello utente/sessione in questo progetto su cui
  agganciarla. Nessuna decisione di prodotto presa autonomamente.
- `ba8ed21` — Aggiornato CHANGELOG.
- `07ab9d6` — Audit completo diretta.it/Betson come fonte quote reali per il
  Value/Odds Engine: **categoria C, non implementato** — ToS vieta lo
  scraping senza eccezione per uso personale, e la quota è di un bookmaker
  terzo in licenza solo per la visualizzazione. Aggiunta nota permanente
  "uso esclusivamente personale" in README.md/DATA_SOURCES.md; rivista la
  nota di rischio di WhoScored/SofaScore con la distinzione esplicita
  "uso personale abbassa il rischio pratico, non elimina il rischio
  contrattuale residuo" — nessuna fonte declassata da B ad A.
