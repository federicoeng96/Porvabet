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
- `0f4feee` — Riconfermata correlazione PPDA/deep-completions vs corner su
  10 stagioni (r=−0.310/+0.424 su 15.122 oss., contro −0.264/+0.447 su
  1.516) — non un artefatto di campione piccolo. Backtest walk-forward
  completo non ripetuto: la riconferma della correlazione grezza risponde
  già alla domanda posta (il problema è nel meccanismo della correzione,
  non nella scarsità di dati) — motivato esplicitamente invece di rifare
  un test dall'esito già prevedibile.
- `11d2dfb` — Scaffolding frontend (tabella con probabilità/quota-modello
  per partite future senza quota reale): **fermato prima di implementare**,
  due blocchi architetturali reali trovati investigando, non un rinvio
  arbitrario. (1) `_build_candidates_and_predictions` salta un mercato
  senza `OddsQuote` reale — non produce mai un `Candidate` senza quota
  bookmaker, `RiskFactors.bookmaker_odds` è obbligatorio e usato nel risk
  score. (2) Verificato via query diretta: 0 partite future/senza
  risultato nei 7.600 match reali ingeriti — nessuna fonte di calendario
  fixture future è mai stata collegata. Nessuna decisione di design presa
  autonomamente su come rappresentare una "stima senza quota" nel Decision
  Layer già testato.
- `22e2a46` — Ri-testata la correzione xG su Dixon-Coles con tutte le 10
  stagioni (~12x più dati): **il precedente segnale positivo per l'EPL non
  regge** — differenze aggregate ora marginali (±0.0005-0.0007) e
  incoerenti per entrambi i campionati, compatibili con rumore. Il
  miglioramento osservato su una sola stagione era verosimilmente un
  artefatto di campione piccolo. Decisione (non attivata) confermata, ora
  su base molto più solida. Nota tecnica: riscritta la comparazione con uno
  storico per-squadra precomputato (la versione naive, O(n²) via query
  per-match, è stata uccisa dopo 7+ minuti senza output su 10 stagioni).
  151 test passano, lint pulito.
- `730c3e5` — Credenziali Betfair reali configurate (Delayed App Key
  generata manualmente dall'utente); **login verificato bloccato da questa
  sandbox, non dalle credenziali o dal codice**: HTTP 403 Cloudflare
  (geo/anti-frode) sia con credenziali placeholder sia reali, stesso
  risultato in entrambi i casi — l'utente conferma che funziona da un IP
  italiano/residenziale. Nessuna credenziale reale stampata/loggata/
  committata in nessun momento. `BetfairExchangeOddsProvider` ora interroga
  anche `OVER_UNDER_25` (non solo 1X2); corretto un bug reale nel sorgente
  di `betfairlightweight` letto direttamente (`login()` è cert-based, va
  usato `login_interactive()`); aggiunti locale italiano e rinnovo
  automatico della sessione (`keep_alive`/re-login). Nuova
  `ingest_live_odds_quotes` collega il provider al Decision Layer
  (`run_analysis_for_match` la chiama per ogni partita non `FINISHED`,
  mai un crash o una quota inventata se la fonte fallisce). I due blocchi
  architetturali già segnalati (Candidate senza quota obbligatoria;
  nessuna fixture futura reale in DB) restano aperti, non risolti da
  questo collegamento — documentato onestamente, non forzato. Nuovo
  `RUNNING_LOCALLY.md` per completare la verifica dal computer dell'utente.
  161 test passano, lint pulito.
- `fc37ef8` — **Decision Layer: "n/d" invece di riga saltata.**
  `_build_candidates_and_predictions` fa ora get-or-create di
  `Market`/`MarketOutcome` per MATCH_RESULT/TOTAL_GOALS e persiste sempre
  una `Prediction` per ogni esito con probabilità calcolabile — con quota
  reale (`Candidate`/`RiskSelection`) quando esiste, altrimenti
  `bookmaker_odds=None`/`value=None` esplicito, mai una riga assente.
  `CountEstimateOut` generalizzato in `NoOddsEstimateOut` (uno per esito,
  non solo coppie Over/Under). Frontend aggiornato. 163 test passano
  (2 nuovi end-to-end), lint pulito, build frontend verificata.
- `ac68684` — **Fixture provider reale: football-data.org, non diretta.it**
  (correzione esplicita dell'utente). diretta.it verificato dal vivo avere
  lo stesso blocco JS-rendering delle quote Betson anche per il calendario.
  `FootballDataOrgFixtureProvider` (categoria A): endpoint reale
  `GET /v4/competitions/{PL|SA}/matches?matchday=N` verificato dal vivo
  (non assunto), rete della sandbox NON bloccata verso questa API (a
  differenza di Betfair). Nessuna chiave disponibile — testato con
  `httpx.MockTransport` sullo schema JSON reale verificato.
  `ingest_upcoming_fixture` persiste `Match` `SCHEDULED`, idempotente.
  172 test passano, lint pulito.
- `10b860a` — Indagine Betfair corner/cartellini: il blocco di rete copre
  in realtà l'intero dominio betfair.com (confermato anche su
  `docs.developer.betfair.com`), non solo login/Betting API — non
  verificabile da questa sandbox. `betfairlightweight` non ha un catalogo
  market type, ma il suo In-Play Service traccia corner/cartellini come
  statistiche live (indizio reale, non conferma di un market type
  exchange). Corner/cartellini restano "n/d" per istruzione esplicita
  dell'utente — nessuna modifica di codice, solo documentazione.
- **Sessione notturna autonoma** (istruzioni: procedere con piena autorità
  decisionale tranne su due punti — nessuna spesa di denaro, nessuna fonte
  nuova con divieto ToS assoluto mai vista prima): verificato direttamente
  nel codice, non a memoria, che il precompute dei 10 livelli di rischio
  (`build_risk_ladder`, 1 principale + 2 alternative) e la sua simulazione
  nel backtest walk-forward (hit rate/ROI per livello, già in
  `BACKTEST_SPEC.md`) **erano già entrambi implementati e testati prima di
  questa sessione** — nessun lavoro necessario, solo verifica e conferma
  nei documenti (v. `ROADMAP.md` punto 19). Stesso per il frontend
  (tabella, rischio di gruppo/per-partita senza ricalcolo, schedina
  automatica, popover alert con le soglie provvisorie richieste
  10%/15%) — già completo. Aggiornati ARCHITECTURE.md/MODEL_SPEC.md/
  README.md per coerenza con lo stato reale del codice.
- `eb520ab` — Aggiunto `MORNING_SUMMARY.md`: riepilogo della sessione
  notturna (Betfair collegato, "n/d" generalizzato, fixture reali via
  football-data.org, verifica precompute 10 livelli, coerenza documentale).
- `f7e907b` — `football-data.org`: nuova `FootballDataOrgInvalidApiKeyError`
  distingue "chiave assente" da "chiave presente ma rifiutata" (400/403
  verificati dal vivo), con messaggio che nomina la variabile d'ambiente.
  Box "Azione richiesta ora" aggiunto in `RUNNING_LOCALLY.md`. 174 test
  passano, lint pulito.
- `4d8a929` — `tests/test_backtest_runner.py`: primo test automatico
  dedicato per la simulazione a 10 livelli di rischio dentro il backtest
  walk-forward (prima solo eseguita manualmente). 178 test passano.
- `2213806` — Ri-scaricato un CSV reale e fresco (E0.csv, Premier League
  2024/25): confermato che football-data.co.uk non ha mai avuto colonne
  quota per corner/cartellini (solo conteggi) — limite strutturale del
  formato, non temporaneo. Corretto un riferimento obsoleto in
  `MODEL_SPEC.md` su Betfair.
- `500c848` — Scansione completa di tutti i file tracciati: nessuna
  credenziale reale committata. Corretta un'ultima imprecisione in
  `BACKTEST_SPEC.md` (corner/cartellini elencati per errore come bloccati
  da assenza di modello — hanno già risultati reali; solo i player props
  sono bloccati da modello mancante).
- `9d6f474` — Aggiunta sezione 13/09 a `MORNING_SUMMARY.md`.
- `b4f5a79` — **Ricalibrate le soglie alert sul backtest reale** (74.100
  predizioni risolte, 10 stagioni): hit rate/ROI peggiorano
  monotonicamente al crescere della discrepanza modello-quota (39,5%→22,2%
  hit rate, ROI -3,0%→-14,6%) — il contrario dell'assunzione implicita del
  brief. `ALERT_THRESHOLD_STRONG` spostata da 0.15 a 0.20 (punto di
  rottura reale nei dati), `ALERT_THRESHOLD_INTERESTING` confermata a
  0.10. Testo di `classify_alert`/`AlertPopover.tsx` corretto: STRONG è
  ora un segnale di cautela, non più descritto come "potenziale
  mispricing". Rimossa `alert_explanation()`, funzione morta mai chiamata.
  178 test passano, lint pulito, build frontend verificata.
- Verificato che Gazzetta/Sky/BBC (auditate mesi fa in `DATA_SOURCES.md`)
  non avessero un gap implementazione-vs-audit: nessun gap trovato, il
  verdetto era già correttamente negativo per tutte tranne Corriere dello
  Sport (già implementato, ma copre solo il modulo tattico, mai i nomi
  giocatore — non sblocca i player props). `ROADMAP.md` aggiornato con un
  nuovo "Quadro onesto: verificato con dati reali vs costruito vs
  bloccato" che distingue esplicitamente cosa è verificato end-to-end con
  dati reali, cosa è costruito ma mai verificato dal vivo (in primis
  `FootballDataOrgFixtureProvider` senza chiave funzionante in questo
  ambiente) e cosa resta bloccato con motivo verificato.
- Roadmap punto 7 (prossimo item): **riverificata dal vivo la feature
  arbitro per il modello cartellini** (item 4 di "Prossimi passi
  concreti"), bloccata da mesi solo come "parser non ancora scritto".
  Verificato con richieste di rete reali da questa sandbox: `aia-figc.it`
  dietro sfida Cloudflare "Just a moment..." (stesso blocco di
  fbref.com/betfair.com), `pgmol.com` con connessione TCP azzerata (stesso
  blocco geografico di betfair.com). `premierleague.com` è raggiungibile
  ma è una SPA React lato client (nessun contenuto articolo nell'HTML
  grezzo) — non perseguita oltre: la sua API interna
  (`footballapi.pulselive.com`) non è mai stata auditata come fonte a sé,
  e usarla per un dominio dati nuovo senza lo stesso audit ToS/rischio
  già applicato a ogni altra fonte violerebbe la regola di questo
  progetto. `DATA_SOURCES.md`/`source_registry.py`/`ROADMAP.md`
  aggiornati con il motivo reale del blocco. Nessun cambio di codice
  (solo documentazione + note del registry), 178 test passano, lint
  pulito.
- **Trovata la causa reale del blocco `football-data.org` di più sessioni**:
  la chiave era presente nell'ambiente fin dall'inizio, ma sotto il nome
  `FOOTBALL_DATA_API_KEY` — il codice (via `pydantic-settings`) leggeva solo
  `FOOTBALL_DATA_ORG_API_KEY`, un nome diverso di una sola parola
  (`_ORG_`). Corretto in `app/config.py` con un `AliasChoices` che accetta
  entrambi i nomi, mantenendo `_ORG_` come nome primario per continuare a
  distinguere questa fonte (fixture live) da football-data.co.uk (CSV
  storico) in tutto il resto del codice/documentazione.
- **Prima ingestione reale di fixture future da football-data.org**
  (`scripts/ingest_upcoming_fixtures.py`): 9 partite reali della prossima
  giornata (EPL 3, Serie A 6) — inclusa esattamente la stessa classe di
  problema già vista con Man City/Man United/Milan (nomi completi
  football-data.org, es. "Manchester United FC", "FC Internazionale
  Milano", "AS Roma") che senza correzione creava un `Team` duplicato per
  ogni club già esistente da football-data.co.uk (16 duplicati su 18
  squadre, confermato interrogando il DB prima/dopo). Aggiunta
  `FOOTBALL_DATA_ORG_TEAM_NAME_ALIASES` + `resolve_or_create_team` in
  `app/ingestion/match_ingestion.py` (stesso pattern hand-curated di
  `UNDERSTAT_TEAM_NAME_ALIASES`), rieseguita l'ingestione: tutte le 17
  squadre già note ora si risolvono sulla riga `Team` esistente, solo
  Coventry City (mai vista nelle 10 stagioni storiche EPL/Serie A
  ingerite) crea una riga nuova, correttamente. 3 nuovi test dedicati,
  181 test passano, lint pulito.
- **Primo giro end-to-end reale completo, documentato in
  `VERIFICATION_LOG.md`**: fixture reale → Dixon-Coles (probabilità
  sensate su Man United–Man City e Napoli–Bologna) → tentativo quota
  Betfair (403 reale confermato di nuovo dal vivo) → Decision Layer.
  Qui il giro reale ha trovato quello che nessun test sintetico aveva mai
  potuto trovare: quando **nessun mercato ha una quota da nessuna fonte**
  (il caso normale per ogni fixture futura reale in questa sandbox),
  `run_analysis_for_match` interrompe l'intera analisi con
  `InsufficientDataError` invece di salvare le righe "n/d" — un
  comportamento preesistente e deliberatamente testato (non un bug di
  stanotte, v. `test_run_analysis_survives_live_odds_provider_failure`),
  le cui conseguenze reali (nessuna fixture futura appare mai nel
  frontend da questa sandbox) diventano visibili solo ora. Non corretto
  autonomamente: è una vera decisione di prodotto, documentata con le due
  opzioni concrete in `VERIFICATION_LOG.md`, rimandata all'utente.
  Playwright confermato: homepage con dati reali storici (non più il seed
  sintetico), pagina dettaglio della fixture reale mostra correttamente
  "nessuna analisi disponibile" (nessun crash, nessun dato inventato), un
  piccolo bug UI trovato (errore 422 non mostrato all'utente, solo in
  console) e non corretto perché dipende dalla decisione sopra.
  `ROADMAP.md`/`RUNNING_LOCALLY.md` aggiornati di conseguenza.
- **Ri-verificato di nuovo dal vivo (non solo riletto)**, su richiesta
  esplicita dell'utente: `CorriereDelloSportLineupProvider` è codice reale
  e funzionante, non uno stub — chiamata live proprio ora a
  `corrieredellosport.it/probabili-formazioni/calcio/serie-a` (HTTP 200, 6
  fixture reali della prossima giornata correttamente estratte, le stesse
  6 già ingerite da football-data.org). `GazzettaLineupProvider`/
  `SosFantaLineupProvider` confermati stub veri (`NotImplementedError`),
  nessuna classe provider esiste per Sky/BBC — coerente con l'audit
  negativo già in `DATA_SOURCES.md`. Conferma anche che questo non sblocca
  i player props (solo modulo di squadra, mai nomi giocatore).
  `ROADMAP.md` aggiornato con questa ri-verifica.
- **Decisione dell'utente implementata: risk ladder completa con "n/d" anche
  quando NESSUN mercato ha una quota reale**, chiudendo l'unico punto aperto
  di `VERIFICATION_LOG.md`. `Candidate.bookmaker_odds`/
  `RiskFactors.bookmaker_odds`/`ScoredCandidate.value` diventano `float |
  None`; `_build_candidates_and_predictions` costruisce sempre un `Candidate`
  per ogni esito MATCH_RESULT/TOTAL_GOALS (mai più un ramo che salta la sua
  costruzione); `compute_risk_raw` redistribuisce il peso "odds_magnitude"
  sugli altri fattori reali quando la quota manca, invece di inventare un
  prezzo sostitutivo; rimossa la riga che interrompeva l'analisi con
  `InsufficientDataError` quando `candidates` era vuota (non più raggiungibile).
  `additional_estimates` ora esclude le Prediction già coperte da una
  `RiskSelection`, per non duplicare MATCH_RESULT/TOTAL_GOALS n/d sia nella
  ladder che lì — resta riservato a CORNERS/CARDS. Frontend (`types.ts`,
  `page.tsx`, `AlertPopover.tsx`, `BetSlip.tsx`, `match/[id]/page.tsx`)
  aggiornato per `bookmaker_odds`/`value` nullable, renderizzati "n/d"; la
  schedina automatica esclude le selezioni n/d (nessun prezzo reale da
  moltiplicare). Audit dell'intero codebase per assunzioni simili: trovato un
  solo altro punto (`app/backtest/runner.py`), lasciato deliberatamente
  invariato perché il backtest valuta solo scommesse storicamente piazzabili,
  problema diverso dal Decision Layer live.

  Ri-verificato con le stesse due fixture reali di stanotte (Man United–Man
  City, Napoli–Bologna): entrambe producono ora una ladder a 10 livelli
  completa (Betfair fallisce ancora con lo stesso 403 reale, invariato), sia
  via chiamata diretta sia via API/frontend — nuovi screenshot Playwright
  mostrano le due fixture visibili in tabella con quota "n/d" e la pagina
  dettaglio con la ladder completa, non più la pagina d'errore.
  `VERIFICATION_LOG.md`/`ROADMAP.md`/`MODEL_SPEC.md`/`DATA_SOURCES.md`
  aggiornati di conseguenza.

  6 nuovi test dedicati (`test_decision_layer.py`: quota assente in
  `compute_risk_raw`, ladder tutta n/d, ladder mista) + 3 test esistenti
  riscritti per il nuovo comportamento invece del vecchio. 185 test passano,
  lint pulito, build/typecheck frontend puliti.
- **Ri-audit Betfair corner/cartellini, su richiesta esplicita**: confermato
  con fonti web reali e indipendenti (materiale educativo Betfair
  sull'Exchange, siti di trading/recensioni indipendenti) che questi mercati
  esistono davvero sull'Exchange (non solo Sportsbook, un prodotto diverso)
  — più forte del precedente indizio circostanziale (campi
  `numberOfCorners` dell'In-Play Service). Il codice esatto del market type
  resta però bloccato: ogni sotto-dominio della documentazione ufficiale
  Betfair restituisce lo stesso 403 Cloudflare, confermato di nuovo anche
  tramite uno strumento di fetch web assistito da AI (non solo richieste
  dirette dalla sandbox). Invece di indovinare un codice, aggiunto
  `BetfairExchangeOddsProvider.discover_market_types_for_match`: chiama
  `listMarketTypes` (operazione reale e documentata dell'API-NG) per la
  fixture specifica e restituisce l'elenco vero dei market type che Betfair
  offre, segnalando quelli che sembrano corner/cartellini con un'euristica
  su sottostringa (mai usata per scegliere un mercato automaticamente).
  Aggiunto `scripts/discover_betfair_market_types.py` per farlo girare su
  ogni fixture reale già in DB dal computer dell'utente. 2 nuovi test
  dedicati con risposte mock realistiche (stesso standard di
  MATCH_ODDS/OVER_UNDER_25). `DATA_SOURCES.md`/`ROADMAP.md`/docstring del
  provider aggiornati con l'evidenza rafforzata. 187 test passano, lint
  pulito.
- **Setup locale automatizzato, priorità esplicita dell'utente**: aggiunti
  `setup.ps1`/`start.ps1` (Windows PowerShell, il sistema dell'utente) e
  `setup.sh`/`start.sh` (macOS/Linux, per parità). `setup.*` controlla i
  prerequisiti (Python 3.11+, Node 20+, PostgreSQL) con messaggi d'errore
  che spiegano cosa installare e da dove, crea l'ambiente virtuale, installa
  le dipendenze backend/frontend, crea utente/database Postgres (idempotente
  — rieseguibile senza rompere nulla), applica le migrazioni, e crea
  `backend/.env` da `.env.example` aprendolo in Blocco Note/editor per la
  compilazione. `start.*` (da usare ogni volta) verifica che Postgres
  risponda, avvia backend e frontend ciascuno in una finestra separata
  (mai con `Activate.ps1`, per evitare il blocco da policy di esecuzione
  PowerShell su una nuova finestra), attende che entrambi rispondano,
  scarica le fixture reali della prossima giornata se la chiave
  football-data.org è configurata, e apre il browser sulla homepage.
  `RUNNING_LOCALLY.md` riscritto da zero per un utente che non ha mai usato
  un terminale (linguaggio semplice, passi numerati, sezione "Problemi
  comuni" con la causa e la soluzione esatta per: policy di esecuzione
  PowerShell bloccata, porta già occupata, password Postgres sbagliata,
  servizio Postgres non avviato, versione Python sbagliata, comando non
  riconosciuto, pagina vuota dopo "AGGIORNA ANALISI").
- **Audit qualità: copertura test — colmati i gap reali, non solo
  documentati**. Generato un report di copertura reale (`pytest-cov`, ora
  anche dipendenza dev dichiarata in `pyproject.toml`): partiva da 86% totale
  su 187 test. Classificati tutti i file a copertura 0%/parziale in due
  categorie — stub deliberatamente non implementati (eplay24, legaseriea,
  probable_lineups: già decisioni esplicite di sessioni precedenti per
  rischio ToS, 0% atteso e accettato) vs. codice reale mai testato. Per la
  seconda categoria:
  - `lineup_reconciliation.py` (0% → 100%): logica di decisione reale (non
    un provider) che alimenta `RiskFactors.data_quality`/
    `Candidate.lineup_conflict` — 6 nuovi test coprono tutti e 5 i rami
    (lineup ufficiale, nessuna fonte probabile, una sola fonte, fonti
    concordi, fonti in conflitto).
  - `rate_limiter.py` (68% → 100%): 3 nuovi test, incluso il ramo di blocco
    reale (`time.sleep`) con finestre minuscole per restare veloci.
  - `db/session.py` (64% → 100%): 2 nuovi test — il resto della suite
    sovrascrive sempre `get_db` con una sessione di test, quindi il generator
    reale (yield/finally/close) non veniva mai eseguito davvero.
  - `api/routers/matches.py` (69% → 98%): 7 nuovi test — `GET /matches`
    (mai testato: lista, validazione risk_level), 404 su match sconosciuto,
    dettaglio senza alcuna analisi, `POST /matches/{id}/analyze` (successo,
    422 dati insufficienti, 404) con la odds-provider chain mockata per non
    tentare mai un vero login Betfair (questa sandbox ha credenziali reali in
    `.env`), e il caso `additional_estimates` con stime CORNERS/CARDS reali.
  - 4 provider reali ma mai testati, ora coperti con
    `httpx.MockTransport` (stesso pattern di `test_understat_provider.py`):
    `open_meteo` (100%), `rss_news` (95%), `api_football` (100%), `fbref`
    (97%). Scrivere i test per `fbref` ha scoperto un bug reale e non
    ipotetico, non un problema del test: `pandas.read_html` su questa
    versione di pandas tratta una stringa HTML letterale come percorso file
    e fallisce con `FileNotFoundError` a meno di incapsularla in
    `io.StringIO` — corretto in `fbref/provider.py`, con `flavor="lxml"`
    fissato esplicitamente per evitare un fallback implicito a html5lib (non
    installato) quando una tabella non viene trovata. `lxml` era inoltre
    assente come dipendenza dichiarata pur essendo necessario a runtime per
    `pandas.read_html`: aggiunto a `pyproject.toml`. Il provider fbref era
    quindi, prima di questa correzione, completamente non funzionante in
    questo stesso ambiente installato — scoperto solo scrivendo i test, non
    da un problema segnalato dall'utente.
  - `source_registry.py` (0% → 100%): 4 test di coerenza sui dati statici
    (chiavi uniche, nome/note non vuoti, categoria enum valida) — guardia
    contro un typo/duplicato silenzioso, non logica da esercitare.
  Risultato: 187 → 240 test, copertura totale 86% → 95%. Gap residui
  onestamente non chiusi (nessuno riguarda codice reale non testato):
  due `continue` difensivi in `matches.py` (righe 141/188, scenari di ladder
  incompleta mai prodotti dalla pipeline attuale) e gli stub C-category già
  citati sopra. Lint pulito su tutti i file toccati.
- **Audit qualità: gestione errori / punti di interruzione brusca**. Passata
  critica sul codice che gira su dati reali esterni (network/CSV/API), non
  solo sul percorso di analisi live già indurito in sessioni precedenti (la
  `FallbackOddsProvider` già isola i fallimenti per singolo provider; il
  guard `if not candidates: raise ValueError` in `build_risk_ladder` rende
  di fatto irraggiungibile il `RuntimeError` difensivo in
  `_nearest_non_empty_bucket`, verificato non un bug reale). Trovati e
  corretti 4 punti dove un singolo elemento malformato interrompeva
  bruscamente un intero batch invece di degradare in modo controllato —
  stesso pattern già usato per `analyze_matches_batch` (isolamento per
  singolo elemento), qui assente:
  - `scripts/ingest_football_data.py` e `scripts/ingest_upcoming_fixtures.py`:
    un singolo record malformato (es. nome squadra mancante/nullo) durante
    l'ingestione di 10 stagioni × 2 competizioni interrompeva l'intero script
    — nessun commit per la stagione in corso, e nessun'altra
    stagione/competizione successiva veniva processata. Corretto con una
    SAVEPOINT (`db.begin_nested()`) per record: un record malformato viene
    ora saltato e loggato, i record già ingeriti nella stessa stagione
    restano. Verificato con una prova funzionale end-to-end contro il
    database reale (poi ripulita) prima di considerarlo risolto.
  - `scripts/ingest_understat_tactical_features.py`: il proprio commento nel
    codice descriveva già un `RemoteProtocolError` osservato realmente
    durante il backfill di sessioni precedenti — eppure un fallimento di una
    singola stagione avrebbe interrotto l'intero backfill multi-stagione.
    Corretto isolando per stagione (try/except attorno a `persist_season`),
    coerente con il suo stesso design idempotente ("stagione già
    persistita, salto").
  - `app/providers/football_data_co_uk/provider.py::parse_csv`: `FTHG`/
    `FTAG` erano castati con `int()` diretto (a differenza di ogni altra
    colonna numerica, che passa per `_safe_int`) — un singolo valore non
    numerico in una riga CSV reale avrebbe fatto fallire l'intera stagione
    (~380 partite), non solo quella riga. Corretto isolando per riga
    (try/except attorno alla costruzione di ogni `HistoricalMatchRecord`,
    riga malformata saltata e loggata). Nuovo test di regressione dedicato.
  Verificato inoltre (nessuna modifica necessaria): FastAPI senza un
  exception handler globale restituisce già un 500 generico senza fuga di
  stack trace su un'eccezione non gestita in un singolo endpoint (non
  abbatte il processo); `matches.py` non ha ancora isolamento per riga nel
  caso di un record DB corrotto/orfano (es. `MarketOutcome` mancante) — non
  corretto perché richiederebbe validazioni difensive su un invariante
  interno garantito da vincoli FK, non un confine di sistema, coerente con
  lo stile di questo progetto ("non validare scenari che non possono
  accadere"); documentato qui come rischio residuo teorico, non come bug.
  241 test passano (4 nuovi), lint pulito.
- **Audit qualità: performance su più partite reali contemporaneamente** —
  la domanda esplicita dell'utente ("il precompute a 10 livelli per molte
  fixture insieme"). Misurato tutto contro i dati reali già nel database di
  sviluppo (7600+ partite storiche, 10 stagioni), non solo stimato:
  - **`GET /matches` (tabella principale) — il bug più grave trovato in
    questo audit**: l'endpoint iterava su OGNI partita mai ingerita (10
    stagioni di risultati storici) invece che solo sulle partite con
    un'analisi corrente, interrogando il database una volta per ogni
    partita per verificare se avesse un'analisi — misurato **7733 query SQL
    per 18 righe reali restituite**. Corretto con una singola query JOIN
    diretta `Match`/`AnalysisVersion` invece di scansionare tutto: **124
    query per le stesse 18 righe** (62 volte meno). Peggiorava
    progressivamente a ogni stagione aggiuntiva ingerita — ora è
    indipendente dalla quantità di storico.
  - **`count_market_estimates.py::_load_count_training_matches`**: N+1 query
    reale — una query `TeamMatchStats` per ogni partita storica dentro un
    ciclo Python invece di una query in batch, misurato **~3800 round-trip
    individuali** (una history completa), chiamato due volte per ogni
    partita analizzata (corner + cartellini). Corretto con una singola
    query batch (`WHERE match_id IN (...)`), poi raggruppata in Python:
    tempo di calcolo delle stime corner/cartellini sceso da **7.68s a
    3.67s** per partita. Nuovo test di regressione che conta le query SQL
    reali (guardia contro una futura reintroduzione dell'N+1).
  - **Refit ridondante del modello per un batch di più partite reali**: sia
    `DixonColesModel` (mercato 1X2/Over-Under) sia `PoissonCountModel`
    (corner/cartellini) venivano rifittati da zero per OGNI partita
    analizzata in un batch, anche quando più partite della stessa
    competizione condividono esattamente lo stesso set di allenamento (es.
    più partite con lo stesso orario di calcio d'inizio, comune nel calcio
    reale). Misurato contro i dati reali: **~2.2s per il fit Dixon-Coles +
    ~3.7s per i due fit corner/cartellini ≈ 10s per partita**, moltiplicato
    per ogni partita di un batch — il pulsante "AGGIORNA ANALISI" (che già
    usa `analyze-batch`, non N chiamate parallele, per la scelta fatta nella
    roadmap item 10) avrebbe richiesto minuti per un turno completo di
    partite reali. Aggiunto un parametro opzionale `model_fit_cache` (mai
    attivo di default — nessun cambiamento di comportamento per l'endpoint
    singolo `/analyze` né per nessun test esistente) condiviso da
    `analyze_matches_batch` tra tutte le partite dello stesso batch: due
    partite con la stessa competizione e lo stesso orario esatto di calcio
    d'inizio (chiave di cache rigorosa, mai un'approssimazione per data —
    garantisce che il set di allenamento sia sempre identico, non solo
    simile) riusano lo stesso modello già fittato invece di rifittarlo.
    Verificato con test dedicati che contano le chiamate a `.fit()` (una
    sola volta condivisa, non una per partita) sia per il modello dei gol
    sia per i due modelli corner/cartellini, oltre a un test che conferma
    che senza cache il comportamento resta invariato (ogni chiamata rifitta,
    esattamente come prima di questa ottimizzazione).
  - Verificato anche cosa NON è stato corretto in questo giro, con la
    stessa misurazione reale: `GET /matches/{id}` (pagina dettaglio) fa
    circa 138 query SQL per singola partita — un N+1 minore ma reale
    (~3 selezioni × 10 livelli, `_selection_out` non battuta), NON corretto
    perché non peggiora con la crescita dello storico (è limitato alla
    struttura fissa a 10 livelli di una singola partita, non scala con il
    database) — categoria di problema diversa da quelli sopra, a priorità
    più bassa, documentata qui onestamente.
  246 test passano (7 nuovi), lint pulito. Verificato anche end-to-end
  contro 4 fixture reali già in database (Coventry-Brighton, Man
  United-Man City, Leeds-Newcastle, Lecce-Monza): 3 analizzate con successo,
  nessun crash, comportamento identico a prima delle correzioni (stesso
  fallimento Betfair 403 già noto e documentato).
- **Mercato falli abilitato in produzione** — ROADMAP.md item 4 segnalava
  dati già ingeriti (`TeamMatchStats.fouls_committed`, 100% popolato,
  15.200 righe) ma nessun modello/mercato costruito sopra, priorità bassa.
  `MarketCategory.FOULS` esisteva già nello schema dal primo slice, mai
  collegato al Decision Layer — nessuna nuova fonte dati, nessuna decisione
  di prodotto, solo completare un collegamento già scaffolded. Prima di
  abilitarlo: backtest reale con lo stesso protocollo walk-forward già
  usato per corner/cartellini (`PoissonCountModel`, nessun modello nuovo),
  linea 24.5 (vicina alla media reale osservata, ~24.0 falli/partita).
  Risultato, a differenza di corner/cartellini: **calibrazione buona nelle
  fasce alte** (EPL: hit-rate 72.9%, gap 1.5-4.7 punti percentuali nei bin
  0.7-1.0; Serie A: hit-rate 65.4%, gap 3.3-4.7 punti) — non i 15-25 punti
  di overconfidence osservati per corner/cartellini. Decisione basata sui
  numeri, non presa a priori: abilitato in `count_market_estimates.py`
  (`compute_count_market_estimates`, `_fouls_extractor`,
  `STANDARD_LINES["FOULS"]`) ed `analysis_runner.py` (`MARKET_LABELS`).
  Nessuna modifica frontend necessaria (già generico su `market_category`/
  `market_label`). `BACKTEST_SPEC.md`/`MODEL_SPEC.md`/`ROADMAP.md`
  aggiornati con i numeri completi. Test esistenti estesi (non solo
  aggiunti) per includere falli nella verifica end-to-end di
  `additional_estimates` e nella cache di fit condivisa. 246 test passano,
  lint pulito.
- **Ipotesi dispersione NB per singola squadra — retestata con un backtest
  reale, decisione presa dai numeri**. BACKTEST_SPEC.md aveva lasciato
  esplicitamente aperta questa ipotesi dopo che la NB condivisa non aveva
  risolto in modo consistente l'overconfidence di corner/cartellini.
  Implementato `NegativeBinomialPerTeamCountModel` (un `alpha` per squadra
  invece che condiviso, stessa struttura attacco/difesa) e backtestato sugli
  stessi 4 segmenti (EPL/Serie A × corner/cartellini), stesso protocollo
  walk-forward — eseguito in background per via del costo computazionale
  reale (~126 refit/segmento, singolo fit fino a ~25s con 103 parametri
  contro ~1-3s del modello condiviso; backtest completo 10-24 minuti/segmento,
  misurato non stimato). Risultato: **miglioramento reale e più consistente
  della NB condivisa** — Brier/log loss migliori in 3 segmenti su 4 (netto
  su entrambe le competizioni per i corner), e calibrazione nelle fasce alte
  migliorata in **7 bin su 7** con abbastanza osservazioni (non più un
  pattern misto) — ma il gap residuo resta sostanziale (4-18 punti
  percentuali) e il costo (10-25x più lento) non ancora giustificato da un
  miglioramento parziale. **Decisione: `PoissonCountModel` resta in
  produzione**, `NegativeBinomialPerTeamCountModel` resta nel codice
  testato e funzionante (stesso trattamento di `NegativeBinomialCountModel`).
  3 nuovi test dedicati + esteso il set parametrizzato esistente a tutte e
  tre le classi modello (24 test totali in `test_count_market_model.py`).
  `BACKTEST_SPEC.md`/`MODEL_SPEC.md`/`ROADMAP.md` aggiornati con la tabella
  completa. 255 test passano, lint pulito.
