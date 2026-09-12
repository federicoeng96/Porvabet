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
- `375c8aa` — Aggiornato CHANGELOG.
- `ea4cffb` — understat.com **riparato per davvero** (nuovo endpoint reale
  `getLeagueData`, verificato con richieste live) e **riclassificato da A a
  B** (robots.txt disallow-all, mai controllato prima). fbref non toccato
  (decisione utente). ClubElo verificato: non è xG, non raggiungibile in
  questa sessione. Nessuna altra fonte xG gratuita reale trovata. Risolti
  mismatch nomi squadra reali (Man City/Manchester City ecc.) con una mappa
  di alias esplicita. Prima estrazione reale: 10.640 righe `TacticalFeature`
  (xG/PPDA/deep completions, EPL+Serie A 2023/24) — non ancora usate da
  nessun modello statistico.
- `2e1d35b` — Aggiornato CHANGELOG.
- `d475d63` — Roadmap item 6 (Intelligence Engine): costruito solo il
  livello di **validazione** di un'ipotesi qualitativa contro dati
  `TacticalFeature` reali (fail-conservative, mai un verdetto indovinato) —
  nessuna fonte reale di segnali (news/LLM/manuale) esiste ancora, non
  fabbricata. Nessuna nuova tabella DB (dataclass in memoria).
- `46397fa` — Aggiornato CHANGELOG.
- `c818bfa` — xG di understat collegato a Dixon-Coles (correzione lambda/mu
  basata su xG-vs-gol-reali, leak-free, clippata, mai applicata sotto 5
  partite di dato). Backtestato su EPL+Serie A 2023/24: migliora davvero
  l'EPL (Brier/log loss/calibrazione code alte), non aiuta la Serie A —
  **non attivata di default** per nessuno dei due campionati, decisione
  basata sui numeri, codice testato ma non collegato al layer live.
- `0237c4f` — Correzione corner da PPDA/deep completions: correlazione reale
  confermata prima di costruire nulla (r=-0.264 PPDA, +0.447 deep
  completions) ma la correzione costruita **peggiora** Brier/log
  loss/calibrazione su ogni metrica, per entrambi i campionati — risultato
  negativo più netto di quello xG. **Non attivata**, codice testato ma non
  collegato al layer live.
- `7d42d91` — Betson (via diretta.it): override ToS esplicito richiesto
  dall'utente su un divieto assoluto (categoria C, nessuna eccezione uso
  personale), `LICENSE_RISK` dedicato distinto dai provider B. **Non
  implementato**: le quote renderizzano solo lato client e un tentativo reale
  con Playwright ha verificato che questa sessione non riesce a far passare
  un browser headless attraverso il proxy verso **nessun** host esterno
  (stessa firma di errore anche su google.com) — limite d'ambiente
  documentato, non blocco specifico del sito. livescore.com auditato da zero
  come backup (società distinta, verificata dal footer): quote reali dietro
  un widget affiliato gated per paese/utente, mai osservate dal vivo.
  `FallbackOddsProvider` implementa il fallback tra le due fonti, testato con
  provider finti. ROADMAP.md: colonna ALERT frontend rivalutata, resta non
  sbloccata (nessuna quota reale disponibile da nessuna delle due fonti).
- `939133b` — Audit FantaLab (moduli/titolari/ballottaggi): **bloccato e
  segnalato, nessuna implementazione**. Nessuna API dati piana esiste (bundle
  JS unico ispezionato per intero); i dati reali sono dietro un Firebase
  Realtime Database autenticato con un login Cognito il cui ponte verso
  Firebase non è verificabile staticamente. Richiederebbe login Premium reale
  automatizzato via browser (bloccato in questo ambiente) più un rischio
  verso l'account Premium dell'utente stesso — decisione lasciata
  esplicitamente all'utente, non presa autonomamente. Solo documentazione.
- `e11bd1a` — FantaLab **accantonato su decisione esplicita dell'utente**:
  rifiutata l'autorizzazione ad automatizzare il login Premium/Cognito.
  Documentata la distinzione esplicita da chiarire nel tempo: qui il motivo
  è rischio di autenticazione/account, non un divieto ToS come per le altre
  fonti categoria C di questo documento (nessuna clausola ToS anti-scraping
  è mai stata trovata per FantaLab). Solo documentazione.
- `25e2359` — Riaudit fonti editoriali moduli/tattica (Serie A + Premier
  League), verificato prima se il blocco precedente di SOS Fanta/Gazzetta
  fosse per ToS o altro (era "non verificato", non un divieto) prima di
  riaprirle. **Gazzetta dello Sport confermata categoria C con motivo
  concreto nuovo**: Data Mining Policy esplicita di RCS Mediagroup
  (art. 70-quater, opt-out TDM UE), nessuna eccezione uso personale — il
  nuovo caso d'uso non riapre la fonte. SOS Fanta non perseguita (affiliata
  RCS + prosa non strutturata). Sky Sport Italia bloccato tecnicamente
  (Akamai). **Corriere dello Sport implementato** (`CorriereDelloSportLineupProvider`,
  categoria B, Serie A): pagina Probabili Formazioni reale, dati Opta,
  llms.txt esplicito che autorizza uso informativo — limite dichiarato,
  solo modulo tattico, mai nomi giocatori. Premier League: nessuna fonte
  equivalente trovata (BBC Sport divieto più esplicito del progetto, Sky
  Sports UK non perseguita per assenza di struttura verificata) —
  documentato onestamente invece di forzare un parser fragile.
- `a97db5e` — Aggiunta Betfair Exchange come fonte quote **ufficiale**
  (Betting API, account personale) — nuova categoria distinta
  `D_OFFICIAL_API_PERSONAL_ACCOUNT` (non A/B/C: qui non c'è scraping da
  classificare), con migrazione Alembic dedicata per l'ENUM Postgres.
  Verificata la documentazione ufficiale (login interattivo senza
  certificato, scelto esplicitamente al posto del login "bot"; Application
  Key Delayed gratuita, mai la Live a pagamento) prima di implementare.
  Usata `betfairlightweight` (libreria reale, attiva) invece di un client
  scritto da zero. `BetfairExchangeOddsProvider` sempre etichettato
  "Betfair (exchange, dati ritardati 1-180s)", mai confuso con una quota
  da bookmaker. `FallbackOddsProvider` ora gestisce anche eccezioni
  impreviste da un provider reale, non solo `NotImplementedError`. **Non
  testato contro l'API live** (nessuna credenziale disponibile in questa
  sessione) — solo contro le classi di risorse reali di betfairlightweight.
  149 test passano (7 nuovi), lint pulito.
- `7bfbdff`/`855c1a4`/(finale) — Roadmap item 5: estensione dell'ingestione
  reale `TacticalFeature` (understat) da 1 a **tutte e 10 le stagioni**
  disponibili (2015/16–2024/25), EPL+Serie A: **106.400 righe reali**,
  verificate 15.200/15.200 apparizioni squadra-partita attese (100%). Tre
  nuovi alias squadra trovati e verificati durante il backfill (stesso
  pattern hand-curated già in uso): West Bromwich Albion→West Brom, SPAL
  2013→Spal, Parma Calcio 1913→Parma. Un ciclo di retry troppo aggressivo
  contro understat ha prodotto un pattern di errori coerente con un
  rate-limit/soft-block (non instabilità casuale) — corretto lo script:
  pausa 2s→10s tra richieste, e un controllo solo-DB che salta del tutto la
  richiesta live per una stagione già completamente persistita invece di
  rifarla sempre. Una singola esecuzione pulita ha poi completato il resto
  senza errori. 149 test passano, lint pulito.
- Rifinitura interfaccia Betfair (utente in attesa di KYC, nessuna
  credenziale ancora disponibile — nessun tentativo contro l'API live).
  Aggiunto `.env.example` con `BETFAIR_APP_KEY`/`BETFAIR_USERNAME`/
  `BETFAIR_PASSWORD` (verificato che `app.config.Settings` li legge
  correttamente). Due nuovi test: il messaggio d'errore per credenziali
  mancanti nomina esplicitamente le variabili da impostare e il livello di
  chiave richiesto (mai criptico), e la lettura reale da variabili
  d'ambiente (non solo dagli argomenti costruttore, unico percorso testato
  finora) è ora verificata. 151 test passano, lint pulito.
