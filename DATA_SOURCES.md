# Fonti dati — valutazione e stato di implementazione

## Uso previsto — nota permanente

**Questo strumento è e resterà a uso esclusivamente personale dell'utente
proprietario del progetto. Non verrà mai distribuito, venduto, condiviso con
terzi né reso disponibile ad altri utenti in nessuna forma.** Questa nota
vale per tutte le valutazioni di rischio in questo documento: dove una
clausola ToS distingue (esplicitamente o implicitamente) tra consultazione/uso
personale e ridistribuzione/uso commerciale/servizio a terzi, il contesto reale
di questo progetto è sempre il primo, mai il secondo — **nessuna
ridistribuzione, nessun terzo esposto**. Questo abbassa il rischio pratico di
violazione (chi farebbe valere un ToS contro un uso privato non distribuito?),
ma **non elimina il rischio contrattuale residuo**: se un domani un ToS
vietasse esplicitamente anche il solo uso personale a scopo di scommessa (non
solo la ridistribuzione), quel rischio resterebbe intatto e andrebbe
rivalutato — non va confuso con un generico "rischio basso" indifferenziato.
Ogni fonte di categoria B sotto riporta questa distinzione esplicitamente,
non la assume.

Metodologia: ogni fonte sotto è stata verificata (in questa sessione di sviluppo)
tramite ricerca web (WebFetch/WebSearch, che instradano diversamente dal proxy di
rete sandboxato usato dal codice applicativo — v. nota di ambiente in
ARCHITECTURE.md) e non per assunzione. Dove la verifica è stata solo parziale
(pagina non raggiungibile direttamente, solo corroborata da fonti secondarie), è
segnalato esplicitamente come "confidenza media/bassa — da riverificare" invece
di essere presentato come fatto accertato.

**Aggiornamento**: a metà sviluppo l'ambiente sandbox ha ricevuto accesso di rete
reale (la policy dell'ambiente è stata cambiata dall'utente). Da quel momento,
football-data.co.uk è stato verificato con un fetch HTTP diretto (non solo
tramite WebFetch/ricerca) e usato per un'ingestione reale di 7.600 partite
(10 stagioni Premier League + 10 stagioni Serie A, 2015/16–2024/25) — la sezione
dedicata sotto è stata aggiornata di conseguenza. Le altre fonti non ancora
implementate/verificate restano come descritte (nessuna verifica aggiuntiva
effettuata per loro in questa sessione).

Legenda categoria (usata anche nel codice, `app.models.enums.DataSourceCategory`
e `app/ingestion/source_registry.py`):
- **A** — Utilizzabile senza riserve particolari (ToS compatibili, gratuita).
- **B** — Utilizzabile solo per uso personale non commerciale — rischio accettato esplicitamente dall'utente.
- **C** — Da NON implementare come provider dati diretto — solo interfaccia astratta.

---

## Categoria A — Utilizzabili senza riserve

### football-data.co.uk — **fonte primaria di questo progetto**
- **Cosa offre**: CSV storici risultati + quote di più bookmaker.
- **URL**: `https://www.football-data.co.uk/mmz4281/<YYZZ>/<div>.csv` (es. `2425/E0.csv`
  per Premier League 2024/25, `2425/I1.csv` per Serie A). Nessuna chiave/login.
- **Colonne — verificate con un fetch HTTP reale** (non solo da documentazione
  secondaria) di `notes.txt` e di un CSV Premier League 2024/25 (380 righe) e
  Serie A 2024/25 (380 righe): `Div, Date, Time, HomeTeam, AwayTeam, FTHG, FTAG,
  FTR, HTHG, HTAG, HTR, Referee (assente nei file Serie A), HS, AS, HST, AST, HC,
  AC, HF, AF, HY, AY, HR, AR`, più due pannelli quote per bookmaker: uno
  **pre-chiusura** (es. `B365H/D/A`, `PSH/PSD/PSA`, `1XBH/D/A`, `BFH/D/A`,
  `MaxH/D/A`, `AvgH/D/A`, `BFEH/D/A` — raccolte il venerdì/martedì pomeriggio
  precedente) e uno di **vera chiusura**, stesso prefisso bookmaker con una "C"
  inserita (es. `B365CH/CD/CA`, `PC>2.5`/`PC<2.5`) — distinzione confermata
  testualmente da `notes.txt`: "These are for pre-closing odds... For the
  closing odds, as below but with an additional 'C' character". Il pannello
  bookmaker completo verificato (2024/25): 1XBet, Bet365, Betfair, Bet&Win,
  Pinnacle, William Hill, Market Max, Market Average, Betfair Exchange (più
  storicamente Interwetten/VC Bet/Ladbrokes/Betfred/BetMGM/BetVictor/Blue
  Square/Coral/Gamebookers/Paddy Power/Skybet/Sporting Odds/Sportingbet/Stan
  James/Stanleybet in stagioni più vecchie). Il pannello cambia nel tempo — il
  provider (`app/providers/football_data_co_uk/provider.py`) lo scopre a runtime
  contro una tabella di prefissi nota invece di assumerne uno fisso, e distingue
  esplicitamente pre-chiusura da chiusura (chiave bookmaker `"<Nome>"` vs
  `"<Nome> (closing)"`).
- **Storico**: Premier League dal 1993/94 (dettagli/quote solo da stagioni più
  recenti); aggiornato almeno due volte a settimana durante la stagione —
  confermato: il file 2024/25 di entrambi i campionati è stato scaricato con
  successo e conteneva la stagione completa (380 partite).
- **Confidenza**: **alta, verificata direttamente** — non più solo da fonti
  secondarie. Una volta ottenuto l'accesso di rete in questa sessione, sono stati
  scaricati con successo `notes.txt` e i CSV 2024/25 di entrambi i campionati, e
  sono state ingerite realmente **7.600 partite** (10 stagioni EPL + 10 stagioni
  Serie A, 2015/16–2024/25, 68 squadre, 343.072 righe di quote) tramite
  `scripts/ingest_football_data.py`.
- **Stato nel codice**: implementato e **verificato con dati reali**
  (`FootballDataCoUkProvider`), con test unitari (`tests/test_football_data_provider.py`,
  fixture sintetica ma con lo schema colonne reale incluse le colonne di
  chiusura) e con l'ingestione bulk reale eseguita e funzionante end-to-end
  (analisi, API, frontend, backtest — vedi sotto).
- **Corner/cartellini/falli (HC/AC/HY/AY/HR/AR/HF/AF)**: il parser li estrae
  da sempre, ma fino a un audit dedicato in questa sessione **venivano
  scartati silenziosamente durante l'ingestione** (mai scritti nel database,
  nonostante fossero già letti dal CSV) — bug corretto:
  `app/ingestion/match_ingestion.py` ora li persiste in `TeamMatchStats` (una
  riga per squadra per partita). Verificato: 15.200 righe popolate su 7.600
  partite reali. **Nessuna colonna quota per corner/cartellini esiste in
  questo CSV** (solo 1X2, Over/Under 2.5 gol, handicap asiatico hanno prezzi)
  — quindi questi dati alimentano un modello di probabilità reale
  (`PoissonCountModel`, v. MODEL_SPEC.md) ma non un mercato con value/edge,
  per assenza strutturale di un prezzo di mercato, non per una scelta di
  design.

### API-Football (api-football.com / api-sports.io)
- **Cosa offre**: fixture, squadre, giocatori, formazioni, infortuni, statistiche —
  l'API strutturata più completa tra quelle gratuite.
- **Piano gratuito**: **100 richieste/giorno** (dato ricorrente in fonti
  secondarie, **confidenza bassa** — non è stato possibile leggere direttamente
  `api-football.com/pricing` in questa sessione). La profondità storica esatta sul
  piano gratuito e i termini precisi sull'uso commerciale **non sono stati
  verificati** — da controllare manualmente su `api-football.com/terms` prima di
  qualunque uso che ecceda un test personale.
- **Stato nel codice**: implementato (`ApiFootballProvider`) contro la REST API v3
  pubblica e documentata (`v3.football.api-sports.io`, header `x-apisports-key`);
  richiede una chiave (`API_FOOTBALL_KEY`) — senza chiave `is_available()` ritorna
  `False` e il layer di ingestione deve saltare la fonte, mai inventare dati.

### fbref.com
- **Cosa offre**: statistiche avanzate squadra/giocatore (tiri, passaggi, azioni
  difensive, metriche per-90).
- **⚠️ Verificato direttamente in questa sessione (rete reale) — bloccato da
  Cloudflare.** `GET https://fbref.com/en/comps/9/Premier-League-Stats`
  risponde `403` con una pagina "Just a moment..." (la sfida
  JavaScript/challenge anti-bot di Cloudflare), non con i dati richiesti. Il
  limite di 10 richieste/minuto dichiarato da fbref è irrilevante qui: il
  blocco avviene prima, a livello di rilevamento bot generico (nessuna
  richiesta arriva mai al contenuto). Superare una sfida Cloudflare
  richiederebbe un browser reale (es. Playwright) che esegue JavaScript — una
  scelta tecnica più pesante e più vicina al confine dell'elusione di
  anti-bot. **Decisione esplicita dell'utente: non aggirare Cloudflare/fbref**
  (v. ROADMAP.md punto 5) — fbref resta non utilizzabile per questo progetto,
  non solo "in sospeso".
- **Stato nel codice**: `FbrefProvider.fetch_table` esiste (con
  `app/core/rate_limiter.py` e la gestione delle tabelle dentro commenti
  HTML) ma **non funziona** contro il sito reale allo stato attuale — il
  problema non è il parsing, è che nessuna risposta valida arriva mai.

### ClubElo — valutato per il Matchup Engine, non xG, non implementato

- **Cosa offre realmente (non xG)**: rating Elo per squadra, aggiornati
  regolarmente — un segnale di forza-squadra generico, non dati di expected
  goals/tiri. Richiesto esplicitamente di verificare "cosa offre davvero":
  confermato che non è un sostituto di understat/fbref per xG, al più una
  feature aggiuntiva di forza-squadra per il Matchup Engine.
- **⚠️ Non raggiungibile in questa sessione — inconcludente sul motivo.**
  Il sito principale (`https://clubelo.com/`) risponde `200` normalmente. Il
  sottodominio API pubblicamente documentato (`https://api.clubelo.com/...`,
  usato da diversi progetti open-source noti) **non risponde**: la
  connessione TLS viene chiusa a metà handshake (`Connection reset by peer`),
  riproducibile more volte con client diversi (`curl`, `httpx`). Non è chiaro
  se sia un blocco specifico di questo ambiente sandboxato (IP/proxy) o un
  comportamento reale del sito verso traffico automatizzato — non abbastanza
  per una conclusione definitiva in nessuna delle due direzioni. `robots.txt`
  non trovato (redirect 302 alla home, nessun file dedicato).
- **Stato nel codice**: non implementato. Anche se fosse raggiungibile, non
  risolverebbe il gap xG (non è quel tipo di dato) — a bassa priorità rispetto
  a understat/fbref per questo motivo.

### StatsBomb Open Data
- **Cosa offre**: dati event-level molto dettagliati, gratuiti, nessuna chiave.
- **Verificato direttamente** (fetch riuscito di `competitions.json` e README su
  GitHub — non bloccato dal proxy sandboxato): Premier League maschile club coperta
  **solo** per le stagioni 2015/16 e 2003/04; Serie A maschile club **solo** 2015/16
  e 1986/87. **Non copre la stagione corrente**, quindi non è utilizzabile come
  fonte per l'analisi corrente — utile solo per validare la metodologia (es. il
  Matchup Engine) su dati di alta qualità, non come feed di ingestione.
- **Licenza**: attribuzione obbligatoria in ogni pubblicazione derivata.
- **Stato nel codice**: non implementato come provider (registrato nel source
  registry con `is_implemented=False` e la motivazione sopra).

### AIA-FIGC (designazioni arbitrali) e Premier League/PGMOL
- **Cosa offre**: designazioni arbitrali per giornata, come pagine HTML pubbliche
  (non API) — confermato che entrambe pubblicano contenuti per la stagione
  corrente (2025/26). Confidenza media (verificato tramite titoli/URL di ricerca,
  non un fetch diretto del DOM in questa sessione).
- **Stato nel codice**: non ancora implementato un parser (registrato nel source
  registry, `is_implemented=False`) — v. ROADMAP.md per il feature arbitro.

### Transfermarkt
- **Cosa offre**: rose, trasferimenti, valori di mercato.
- **Confidenza bassa**: non è stato possibile leggere direttamente il ToS/robots.txt
  di Transfermarkt in questa sessione; una fonte secondaria (aggregatore di
  robots.txt) riporta un file permissivo, e l'ecosistema di scraper open-source
  attorno a questa fonte è ampio, ma questo non sostituisce una lettura diretta
  dei termini. **Da verificare manualmente prima di un uso esteso.**
- **Stato nel codice**: non implementato (registrato nel source registry).

### Open-Meteo (aggiunta non nella lista originale, per il `WeatherProvider`)
- API pubblica, gratuita, senza chiave, per previsioni meteo — usata come
  implementazione reale e verificabile dell'interfaccia `WeatherProvider`
  (`OpenMeteoWeatherProvider`). Uso commerciale richiede un piano a pagamento; l'uso
  qui (tool di analisi personale/di ricerca) non è rivendita del dato meteo, ma va
  ricontrollato se il pattern d'uso cambia.

### Feed RSS/Atom generico (per `NewsProvider`)
- Nessuna fonte specifica hardcoded: `RssNewsProvider` legge qualunque feed
  RSS/Atom valido passato in configurazione — evita di "inventare" un endpoint
  news specifico non verificato.

---

## Categoria B — Solo uso personale non commerciale (rischio accettato dall'utente)

**Nota di verifica**: con accesso di rete reale disponibile in questa sessione,
è stato tentato un fetch diretto di entrambe le pagine ToS sotto (sia via
`curl` con header da browser reale, sia via `WebFetch`) — **entrambe
restituiscono HTTP 403** (stesso tipo di blocco edge osservato per ePlay24).
Le citazioni verbatim sotto restano quindi quelle ottenute tramite estrazione
di ricerca (WebSearch, che ha accesso indicizzato al contenuto anche quando il
fetch diretto della pagina è bloccato) — corroborate due volte, in due sessioni
distinte, con lo stesso testo esatto entrambe le volte, il che ne rafforza
l'affidabilità pur senza un fetch diretto della pagina live.

### WhoScored
- **Clausola ToS specifica sull'uso da piattaforme di scommesse** (non solo la
  clausola generica su copia/ridistribuzione):
  > "The copying, downloading, reproduction, republication, framing, broadcasting
  > and transmission of WhoScored.com content including but not limited to all
  > statistics, data, products, tables, graphics and other information is
  > prohibited without an official licence."
  >
  > **"The use of WhoScored.com ratings by media, betting or fantasy platforms
  > requires an official licence."**
- La seconda clausola nomina **esplicitamente** le piattaforme di scommesse
  ("betting platforms") — non è una clausola generica sul copyright applicata
  per estensione: il documento stesso distingue questo caso d'uso e richiede
  una licenza ufficiale che questo progetto non ha. Qualunque uso che ecceda
  l'uso privato personale dell'utente è quindi una violazione diretta e
  esplicita dei termini, non un'interpretazione.
- **Stato nel codice**: `WhoScoredProvider` porta un flag esplicito
  `LICENSE_RISK = "personal_use_only_betting_platform_clause"` (non solo un
  commento — un attributo di classe leggibile/ispezionabile a runtime) e
  richiede `acknowledge_personal_use_only=True` per essere istanziato
  (altrimenti solleva `PersonalUseNotAcknowledgedError`); lo scraping vero e
  proprio **non è implementato** — gli endpoint reali non sono stati
  verificati in questo progetto, e implementarli "a naso" violerebbe il
  principio di non inventare endpoint.
- **Nel contesto reale d'uso di questo progetto** (v. nota a inizio
  documento — personale, mai distribuito): l'assenza di ridistribuzione
  abbassa il rischio *pratico* di questa clausola specifica (che vieta
  esplicitamente "media, betting or fantasy platforms" — un uso personale
  non distribuito non è, letteralmente, nessuno di questi tre). Questo non
  elimina il rischio: se un domani la clausola vietasse anche il solo uso
  personale (non solo l'operare come piattaforma), il rischio tornerebbe
  pieno. Il flag `LICENSE_RISK` e la classificazione B restano invariati.

### SofaScore
- **Clausola ToS specifica sui bookmaker**:
  > License "does not include any resale or commercial use of the Platform or its
  > contents, derivative use, or use of data mining, robots, or similar data
  > gathering tools."
  >
  > **"SofaScore states that they do not supply sports data to bookmakers, and
  > bookmakers should not rely on their site to verify bets."**
- **Conferma ufficiale aggiuntiva** (dalla loro stessa FAQ pubblica,
  `sofascore.helpscoutdocs.com/article/129-sports-data-api-availability`,
  verificata in questa sessione): *"a causa di accordi con i nostri fornitori
  di dati, non possiamo condividere le fonti dati sotto forma di endpoint
  API"* — nessuna procedura di licenza commerciale è menzionata; l'unica
  opzione per terze parti è un widget per partner media, non un'API dati.
- **Stato nel codice**: stessa logica di `WhoScoredProvider` —
  `SofaScoreProvider` porta lo stesso flag esplicito
  `LICENSE_RISK = "personal_use_only_betting_platform_clause"` e richiede
  `acknowledge_personal_use_only=True`, scraping non implementato.
- **Nel contesto reale d'uso di questo progetto** (personale, mai
  distribuito): stessa lettura di WhoScored sopra — il disclaimer di
  SofaScore è rivolto esplicitamente a "bookmakers" (un operatore
  commerciale), non a un singolo utente che consulta dati per sé; l'uso
  reale di questo progetto abbassa quindi il rischio pratico. Resta però un
  divieto scritto di "data mining, robots, or similar data gathering tools"
  **senza eccezione esplicita per uso personale** — più simile, su questo
  punto, alla clausola di diretta.it/Flashscore sotto che a quella di
  WhoScored. Rischio contrattuale residuo non eliminato; classificazione B
  invariata.

### understat.com — **riclassificato da A a B in questa sessione**

- **Cosa offre**: xG/xGA/npxG/PPDA/deep completions per team e per partita,
  Premier League e Serie A dal 2014/15 — verificato essere, per fonti
  indipendenti, "una delle ultime fonti gratuite di dati xG" per questi
  campionati (nessuna alternativa gratuita realmente equivalente trovata in
  questa sessione, v. ROADMAP.md punto 5 per la ricerca completa).
- **⚠️ Il parser precedente era rotto — ora riparato con l'endpoint reale.**
  Il sito non incorpora più i dati in uno `<script>` della pagina; verificato
  con richieste reali che la pagina `/league/{league}/{season}` carica
  `js/league.min.js`, che a sua volta chiama
  `GET /getLeagueData/{league}/{season}` via AJAX, autenticato dal cookie di
  sessione (`PHPSESSID`) impostato dal caricamento della pagina stessa —
  nessun login, nessuna chiave, solo lo stesso meccanismo che usa il sito per
  sé. Verificato per EPL e Serie A, stagione 2023: risposta reale con i dati
  completi (`teams`, `dates`, `players`). `UnderstatProvider` riscritto per
  usare questo endpoint (visita la pagina lega, poi chiama l'endpoint dati
  con lo stesso client/cookie) — stesso schema di output di prima
  (`get_historical_matches`), più un nuovo metodo
  `get_team_match_tactical_stats` per xG/PPDA/deep completions per il
  Matchup Engine.
- **⚠️ `robots.txt` disallowa tutto — riclassificato da A a B.**
  `https://understat.com/robots.txt` è `User-agent: *` / `Disallow: /` — un
  disallow totale, senza eccezioni, per qualunque crawler (verificato con
  fetch diretto in questa sessione — non era mai stato controllato quando
  questa fonte fu classificata A in origine). **Nessun Terms of Service
  pubblicato è stato trovato** per understat.com (ricerca approfondita) a cui
  attribuire una clausola specifica come per WhoScored/SofaScore/diretta.it
  — il rischio qui è la sola direttiva robots.txt, non un testo legale
  esplicito. Contesto (non un lasciapassare): esistono strumenti/librerie
  open source attivamente mantenuti per anni per questo sito (es. il pacchetto
  PyPI `understatapi`), senza segnali di enforcement attivo osservabile (a
  differenza della sfida Cloudflare di fbref o del blocco edge di ePlay24).
- **Nel contesto reale d'uso di questo progetto** (personale, mai
  distribuito): abbassa il rischio pratico di violare un semplice
  `robots.txt` (pensato più per crawler di massa/motori di ricerca che per
  un singolo script personale a basso volume), ma non lo elimina — resta un
  segnale tecnico esplicito di "non vogliamo bot qui", non ignorabile solo
  perché non è un ToS. Rischio contrattuale/tecnico residuo non eliminato.
- **Stato nel codice**: `UnderstatProvider` richiede
  `acknowledge_personal_use_only=True` per essere istanziato (altrimenti
  `PersonalUseNotAcknowledgedError`), con
  `LICENSE_RISK = "personal_use_only_robots_disallow_all"` — un valore
  distinto da quello di WhoScored/SofaScore, perché il motivo del rischio è
  diverso (robots.txt, non una clausola ToS betting-specifica) — verificato
  da `tests/test_understat_provider.py` (parsing testato su un fixture
  sintetico che replica lo schema JSON reale, senza chiamate di rete nei
  test, stessa convenzione di `test_football_data_provider.py`).

---

## Categoria C — Solo interfaccia astratta, non implementare

### ePlay24 (bookmaker target) — **VERIFICA DEFINITIVA (accesso di rete reale)**

**Conclusione: NO. Non esiste alcun modo tecnicamente lecito di ottenere le
quote ePlay24 in modo automatico.** Non è più una conclusione per assenza di
prove (come nella verifica iniziale, fatta senza accesso di rete diretto) —
è stata testata direttamente, in questa sessione, con accesso di rete reale:

- **Cosa si sa**: ePlay24 è un bookmaker italiano reale, con licenza ADM
  (E-PLAY24 ITA LTD, concessione GAD n. 16004) — confermato tramite siti di
  recensioni scommesse italiani.
- **API pubblica**: nessuna trovata in nessuna ricerca (né direttamente, né
  presso i principali aggregatori commerciali di quote — OpticOdds,
  SportsDataIO, The Odds API, OddsJam, Sportradar — nessuno dei quali elenca
  ePlay24 tra i bookmaker coperti).
- **Test tecnico diretto eseguito in questa sessione** (con accesso di rete
  reale, non solo tramite ricerca): richieste HTTP dirette (`curl`, con e senza
  header da browser reale) e tramite `WebFetch` (instrada diversamente dal
  proxy di rete della sandbox) verso:
  - `https://www.eplay24.it/` → **HTTP 403 "Access Denied"** (pagina di errore
    Akamai/edgesuite.net)
  - `https://www.eplay24.it/robots.txt` → **HTTP 403**, stesso blocco
  - `https://account.eplay24.it/pages/termini-condizioni` (la pagina termini e
    condizioni stessa) → **HTTP 403**, stesso blocco, sia via `curl` sia via
    `WebFetch`
  
  **Il sito blocca ogni richiesta automatizzata a livello di infrastruttura
  edge (Akamai/WAF)**, indipendentemente da User-Agent o percorso richiesto —
  incluso il semplice recupero della pagina dei propri termini di servizio.
  Questo è più forte della precedente conclusione "ToS non verificato": qui è
  stato verificato che **non è nemmeno possibile leggere in modo automatizzato
  il testo dei ToS** per controllarne la clausola specifica sullo scraping,
  perché il blocco tecnico avviene prima, a livello di rete/edge.
- **Conclusione operativa**: non esiste (a) un'API pubblica, (b) un feed
  documentato, né (c) una modalità tecnica di accesso automatizzato che superi
  il blocco edge del sito stesso. `EPlay24OddsProvider` resta un'interfaccia
  `OddsProvider` **senza alcuna implementazione reale** (`is_available()`
  ritorna sempre `False`, ogni metodo dati solleva `NotImplementedError`) —
  esiste solo perché il resto del codice dipenda dall'astrazione
  `OddsProvider`, mai da ePlay24 direttamente. Un'integrazione futura
  richiederebbe un accordo diretto/commerciale con l'operatore (o l'accesso
  manuale dell'utente stesso alle proprie quote, mai uno scraping bypassato
  dell'edge block), non un semplice miglioramento del codice.
- **Implicazione per il resto del sistema**: v. la nota dedicata in
  `ARCHITECTURE.md` — finché questo provider non è implementabile, il sistema
  **stima probabilità e quote fair, ma non calcola un value/edge reale
  rispetto al mercato ePlay24** (il "value" oggi mostrato è sempre calcolato
  contro le quote della fonte realmente disponibile — football-data.co.uk —
  mai contro una quota ePlay24 reale o simulata).

### Lega Serie A (legaseriea.it)
- I termini del sito vietano esplicitamente "data mining, robot o simili
  dispositivi di acquisizione o estrazione" e limitano l'uso a scopi personali
  non commerciali; inoltre i dati ufficiali di partita sono in licenza esclusiva a
  Genius Sports fino alla stagione 2028/29 — non acquistabili liberamente nemmeno
  a pagamento indipendente.
- **Stato nel codice**: `LegaSerieAProvider` è solo interfaccia, non implementata.

### diretta.it / Flashscore — quote reali (bookmaker "Betson"), per il Value/Odds Engine

**Audit completo eseguito in questa sessione, mai fatto prima** (era stato
accantonato in precedenza solo perché il caso d'uso — corner/cartellini/falli
— non serviva più, senza alcuna verifica ToS/tecnica: v. nota storica più
sotto). Il caso d'uso ora è diverso e più sensibile: quote reali per
calcolare edge/value, non statistiche di partita.

**1. Verifica tecnica di accesso — raggiungibile, non bloccato come fbref/ePlay24.**
`GET https://www.diretta.it/` risponde `200` con contenuto reale (nessuna
sfida Cloudflare, nessun blocco edge Akamai come ePlay24). `robots.txt`
(`https://www.diretta.it/robots.txt`, verificato con fetch reale) per
`User-agent: *` disallowa solo `/classifiche/`, `/tabellone/`, `/newsfeed/` e
un pattern di file JS — non le pagine partita/quote. Disallowa esplicitamente
per intero una lista di bot nominati (CCBot, FacebookBot, Meta-ExternalAgent/
Fetcher, Diffbot, AI2Bot, Bytespider, cohere-ai, Webzio-Extended, YouBot,
SmartViper) — chiaramente mirata a crawler di training AI e aggregatori di
contenuto, non a scraper generici con User-Agent da browser normale.
**Conclusione tecnica da sola: accessibile.** Ma l'accesso tecnico non è il
problema qui — lo sono i ToS (punto 2) e la catena di diritti sulle quote
(punto 3).

**2. ToS — trovata una clausola esplicita e diretta sull'estrazione dati,
più ampia di quelle già documentate per WhoScored/SofaScore.**
Verificato via fetch diretto di `https://www.flashscore.com/terms-of-use/`
(diretta.it fa parte dello stesso gruppo Livesport/Flashscore — nessuna
pagina ToS separata trovata specifica per il dominio .it):

> **Clausola 2.9 (Database Protection)**: "The contents of the database
> contained in the Site ("Database Content") are protected by a special
> right of the database provider. Unless otherwise agreed in writing with
> us, Database Content may only be lawfully used to the extent and in the
> manner provided by the applicable law. In particular, no extraction
> (copying) or utilization (making available to the public) of Database
> Content or of a qualitatively or quantitatively substantial part thereof
> is permitted without our explicit consent."
>
> **Clausola 2.10 (Unauthorized Interference)**: "You must not use any
> mechanism, tool, software or procedure that has or could adversely affect
> the operation of our facilities... You may not burden our server... nor
> may you assist any third party in such activity... Furthermore, you are
> not permitted to use the content of the website by embedding, aggregating,
> **scraping** or recreating it without our express consent."

Differenza importante rispetto a WhoScored/SofaScore: quelle clausole
nominano esplicitamente "betting platforms"/bookmaker come caso d'uso
proibito, distinguendo (almeno linguisticamente) l'uso personale ordinario
da un uso commerciale come piattaforma scommesse. Questa clausola **non fa
questa distinzione — vieta scraping/estrazione in generale, senza un'eccezione
esplicita per uso personale**. L'unico spiraglio è il riferimento della
clausola 2.9 a "qualitatively or quantitatively substantial part" del
database (linguaggio che ricalca il diritto sui generis sulle banche dati
UE, Direttiva 96/9/CE, che distingue estrazione di parte sostanziale da
estrazione insostanziale) — un'estrazione minima, per un numero ridotto di
partite di interesse personale, potrebbe non costituire "parte sostanziale"
sotto quella specifica normativa. Non è però una zona franca dichiarata dal
sito, è un'interpretazione giuridica di un margine stretto — non da trattare
come autorizzazione.

**3. La quota non è di diretta.it — è del bookmaker (es. "Betson"), solo
licenziata per la visualizzazione.** Verificato tramite la FAQ ufficiale
Flashscore (`flashscore.com/faq/odds`): il sito mostra le quote **"from
bookmakers we have agreements with, as they need to share their odds data
with us"** — diretta.it/Flashscore è un aggregatore che **licenzia** le quote
da bookmaker terzi per la visualizzazione sul proprio sito, non le possiede.
Nessuna fonte trovata conferma "Betson" come fornitore dati generico
dietro le quinte (a differenza di aggregatori noti come Betradar/Betgenius/
Genius Sports) — è più plausibile sia uno dei bookmaker licenziati le cui
quote live sono mostrate sul sito italiano, analogamente al caso verificato
di Betnacional/Flashscore Brasile. **Questo significa che riutilizzare quella
quota altrove non tocca solo i ToS di diretta.it, ma potenzialmente anche i
termini dell'accordo (privato, non pubblico, non leggibile) tra Betson e
diretta.it/Flashscore** — un accordo di licenza per la sola visualizzazione
sul sito quasi certamente non include il diritto di diretta.it stesso a
concedere a terzi l'estrazione e il riuso altrove, quindi a maggior ragione
non lo concede implicitamente a un utente che fa scraping.

**4. Classificazione: CATEGORIA C — da non implementare come provider dati
diretto.** Motivazione, non solo applicazione meccanica della regola:
- La clausola ToS è più ampia e assoluta di quella già accettata come
  "rischio B" per WhoScored/SofaScore (nessuna eccezione per uso personale,
  divieto di scraping/estrazione/embedding esplicito e diretto).
- A differenza di WhoScored/SofaScore (dati/rating **proprietari** di quelle
  piattaforme), qui il dato **non è nemmeno di diretta.it** — è di un terzo
  (il bookmaker) che lo ha concesso in licenza solo per la visualizzazione:
  un secondo livello di rischio che le altre fonti B non hanno.
- Il caso d'uso è centrale e diretto (calcolo di edge/value reale su cui
  potrebbero basarsi decisioni con soldi reali), non periferico come le
  statistiche tattiche di WhoScored/SofaScore.

**Nota sull'uso personale non distribuito** (v. sezione dedicata a inizio
documento): anche applicando la stessa lettura "uso personale, mai
ridistribuito" già usata per abbassare il rischio pratico di WhoScored/
SofaScore, qui non è sufficiente a spostare la classificazione — il problema
non è solo "il sito non vuole essere ridistribuito" (un rischio che l'uso
personale attenua), ma che **la clausola vieta lo scraping in sé, e il dato
appartiene a un terzo con cui questo progetto non ha alcun rapporto** — due
motivi indipendenti dalla ridistribuzione. Per questo diretta.it/Betson resta
C anche sotto la lente "uso personale", non B.

**Nota storica**: questa fonte era stata precedentemente "chiusa" in questo
documento perché il gap dati (corner/cartellini/falli) non esisteva più,
**senza alcun audit legale condotto allora** — quella chiusura è ora superata
da questo audit completo, motivato dal nuovo caso d'uso (quote).

#### Aggiornamento — override esplicito richiesto dall'utente (quote pre-match)

L'utente, informato per intero del punto 4 sopra (categoria C, clausola
assoluta senza eccezione per uso personale, quota di un terzo in licenza solo
per la visualizzazione), **ha richiesto esplicitamente di procedere comunque**,
con questi vincoli auto-imposti: solo quote pre-match indicative (mai
live/in-play, anche se tecnicamente disponibili sulla stessa pagina), rate
limiting ragionevole per non farsi bloccare l'IP, ed etichettatura ovunque
(codice/log/UI) come **"Betson (via diretta.it)"**, mai genericamente
"bookmaker" — perché la quota resta di un bookmaker terzo che diretta.it
licenzia solo per la visualizzazione (punto 3 sopra), non un dato proprio di
diretta.it.

> **Override richiesto dall'utente in data odierna (12/09/2026), rischio
> accettato consapevolmente nonostante l'assenza di eccezione per uso
> personale nei ToS.** Questo è distinto, nel codice, da un rischio B
> interpretato in favore dell'utente (WhoScored/SofaScore): qui non c'è
> un'ambiguità da risolvere, c'è un divieto esplicito e assoluto
> (clausola 2.10, "Unauthorized Interference", citata sopra) che l'utente ha
> scelto consapevolmente di ignorare. `BetsonDirettaOddsProvider.LICENSE_RISK`
> porta il valore `explicit_tos_prohibition_no_personal_use_exception_user_override`
> — una stringa diversa da quella dei provider B, proprio per rendere questa
> distinzione verificabile nel codice, non solo nella prosa.

**Verifica tecnica reale del punto di accesso alle quote (questa sessione,
richieste live, non da documentazione di terzi):**

`GET https://www.diretta.it/partita/calcio/as-roma-zVqqL0ma/inter-Iw7eKK25/`
(una partita Serie A reale) risponde `200`, ma l'HTML servito dal server **non
contiene alcuna quota** — la tab "Quote pre-partita" (stringa UI confermata
presente altrove sul sito: `"Quote pre-partita"`, `"Quote scommesse sportive"`)
si popola solo dopo l'esecuzione del JS lato client. La pagina espone nel suo
stesso script di configurazione inline l'URL base del feed proprietario
(`"default_url":"https://global.flashscore.ninja"`,
`"url":"https://400.flashscore.ninja"` — 400 è l'id di progetto "calcio" già
visto in altri riferimenti della pagina), ma **nessuno schema di firma delle
richieste a quel feed è documentato o deducibile in modo affidabile** da
questa sola ispezione statica — ho verificato con richieste dirette che alcuni
percorsi plausibili (`/x/feed/d_od_1_<eventId>...`) rispondono `404`: **non ho
proseguito a indovinare ulteriori varianti**, perché sarebbe esattamente
l'endpoint "inventato" che lo standard di qualità di questo progetto vieta.

L'unica via verificabile per leggere quella tab è quindi un browser reale che
esegua la pagina. È stato tentato con Playwright/Chromium (binario reale
disponibile in questo ambiente), fallito per un motivo di infrastruttura di
questa sessione, non per un blocco specifico di diretta.it: il proxy di rete
di questo ambiente sandboxato azzera l'handshake TLS per **qualsiasi** host
esterno raggiunto tramite un motore browser reale — verificato anche contro
google.com e accounts.google.com, con la stessa identica firma di errore
(`ws_closed_mid_exchange`, handshake interrotto a ~1.7KB inviati/39B ricevuti,
sempre la stessa dimensione indipendentemente dall'host). Il file
`/root/.ccr/README.md` di questo ambiente conferma che certe classi di
traffico non sono supportate dal proxy e vanno segnalate, non aggirate — ho
seguito quell'istruzione.

**Conclusione pratica**: l'override è reale e autorizzato dall'utente, la
quota esiste davvero e la UI che la mostra è stata confermata dal vivo, ma
**nessun percorso di codice funzionante per recuperarla esiste in questa
sessione**. `BetsonDirettaOddsProvider` (`app/providers/betson_diretta/`) è
quindi implementato come uno stub onesto — stesso trattamento già riservato a
fbref (bloccato da Cloudflare) ed ePlay24 (bloccato da Akamai): `is_available()`
restituisce sempre `False`, il metodo di fetch solleva `NotImplementedError`
con una spiegazione, mai quote finte o simulate. Chi completerà
l'implementazione in futuro (in un ambiente dove un browser headless raggiunge
davvero internet) dovrà usare un browser reale — non un endpoint feed
indovinato — e leggere solo la tab pre-match.

### livescore.com — backup per le quote pre-match (Betson/diretta.it)

**Auditato da zero, indipendentemente da diretta.it/Flashscore, come richiesto
esplicitamente** (gruppo societario diverso, non un mirror).

**1. Verifica di identità societaria (confidenza alta, verificata dal vivo)**:
il footer di `https://www.livescore.com/en/` (fetch reale) riporta
`"© 1998-2026 LiveScore Limited"` — una società distinta da Livesport
a.s./Flashscore (operatore di diretta.it). Il brand di scommesse proprio di
LiveScore Limited, `LiveScoreBet` (`livescorebet.com`), compare direttamente
nella configurazione client dell'app — diretta.it non ha un equivalente.

**2. Accesso tecnico e robots.txt (verificati dal vivo)**:
`https://www.livescore.com/` risponde `200` (redirect a `/en/`).
`https://www.livescore.com/robots.txt`: `User-agent: *` → `Allow: /`,
`Disallow: /api/`, `/*/news/*/s/`, `/serve/*` — permissivo sulle pagine
normali, esplicito nel vietare l'accesso diretto a `/api/`. Il mirror "legacy"
citato dal sito stesso (`https://www.livescores.com`, robots.txt verificato
anch'esso) è più esplicito: oltre a `Disallow: /api/*`, vieta per nome una
lista di crawler AI/dati (`ClaudeBot`, `GPTBot`, `Amazonbot`,
`meta-externalagent`, `Baiduspider`, `AhrefsBot`, `SleepBot`) — nota
particolarmente rilevante essendo `ClaudeBot` esplicitamente nominato: non
identifica questa sessione (che non opera come quel crawler), ma è un segnale
in più di quanto il sito consideri indesiderata l'estrazione automatica di
massa.

**3. Struttura tecnica delle quote (verificata dal vivo, risultato negativo
concreto)**: le pagine partita di livescore.com sono Next.js **server-side
rendered** — a differenza di diretta.it, la pagina di una partita reale
(`https://www.livescore.com/en/football/italy/serie-a/atalanta-vs-cagliari/1785358/`,
Atalanta-Cagliari, Serie A odierna) incorpora un blob JSON reale
`__NEXT_DATA__` lato server con i dati della partita. **Le quote dei
bookmaker, però, non sono in quel JSON**: la tab "Odds" della stessa
configurazione mostra un sistema di widget esterni (`e2Widgets`:
`odds-comparison`, `smart-odds`, `odds-boost`) con un cancello per
paese/utente — `"user":["isAdult","notSelfExcluded","hasBetFeatures"]` — cioè
livescore.com stesso tratta questa funzione come contenuto di scommessa
regolamentato dietro consenso, non come un feed dati pubblico.
`odds-comparison` risulta abilitato per `"IT"` nella configurazione live, ma
**nessun nome di bookmaker (es. "bet365") o quota reale è mai stato
osservato** in questa sessione: la tab "Odds" della partita di test verificata
risultava `"isVisible": false` lato server.

**4. ToS non recuperabile per intero**: `https://www.livescore.com/en/terms/`
(e le varianti localizzate) servono solo un breve riassunto pre-hydration
("has terms of use covering areas such as the use of LiveScore material...")
senza clausola esplicita su scraping/automazione visibile in quel testo — il
corpo completo carica lato client dopo l'hydration React, che (come per
diretta.it) non è stato possibile eseguire in questa sessione per lo stesso
blocco tecnico del browser headless (v. sopra).

**5. Classificazione: CATEGORIA C, non implementata.** Non per la stessa
ragione di diretta.it (qui non c'è una clausola ToS assoluta verificata), ma
per somma di segnali concreti: funzione trattata come scommessa regolamentata
dietro consenso, nessuna quota reale mai osservata, nessun testo ToS completo
verificato, e lo stesso blocco tecnico del browser headless di questa sessione.
Se il caso venisse ripreso in futuro, va prima recuperato il testo ToS
completo e un esempio reale di quota renderizzata — entrambi richiedono un
motore browser funzionante, non solo richieste HTTP dirette.

**Stato nel codice**: `LivescoreOddsProvider` (`app/providers/livescore/`) è
uno stub onesto — `is_available()` sempre `False`, fetch che solleva
`NotImplementedError`. `FallbackOddsProvider`
(`app/providers/base/odds_provider_chain.py`) implementa la logica di
fallback richiesta dal brief — Betson/diretta.it come priorità di default
(fonte primaria nominata esplicitamente dall'utente), livescore.com come
backup (nominato esplicitamente come backup) — testata con provider finti,
pronta per quando (e se) una delle due fonti reali verrà completata. Nessuna
delle due fonti fornisce oggi quote reali al Value/Odds Engine, che continua
a usare esclusivamente football-data.co.uk per le quote storiche.

### SOS Fanta / Gazzetta dello Sport (probabili formazioni)
- Non fanno parte dell'elenco di fonti analizzate a fondo in questo progetto (il
  brief le nomina come fonti attese per le probabili formazioni di Serie A, ma non
  come parte dell'elenco da verificare tecnicamente). **ToS ed endpoint non
  verificati** — implementarli "a naso" violerebbe lo stesso principio di
  WhoScored/SofaScore. `SosFantaLineupProvider` / `GazzettaLineupProvider` sono
  solo interfacce (`is_available()` → `False`), con la logica di riconciliazione
  (accordo/conflitto tra fonti → confidence) già implementata e testata in
  `app/engine/decision/lineup_reconciliation.py`, pronta per quando (e se) una di
  queste fonti verrà verificata e collegata.

---

## Riepilogo implementazione (anche in `app/ingestion/source_registry.py`)

| Fonte | Categoria | Implementata | Note |
|---|---|---|---|
| football-data.co.uk | A | ✅ | Fonte primaria di questo slice |
| API-Football | A | ✅ | Richiede chiave propria |
| Open-Meteo | A | ✅ | Meteo |
| RSS/Atom generico | A | ✅ | News, URL da configurazione |
| fbref.com | A | ❌ | Bloccato da Cloudflare — decisione utente: non aggirare |
| StatsBomb Open Data | A | ❌ | Non copre stagioni correnti |
| AIA-FIGC / PGMOL | A | ❌ | Parser non ancora scritto |
| Transfermarkt | A | ❌ | ToS non verificato a fondo |
| understat.com | B | ✅ | Riclassificato da A: robots.txt disallow-all. Riparato (nuovo endpoint), flag richiesto |
| WhoScored | B | ❌ | Flag di conferma richiesto, scraping non implementato |
| SofaScore | B | ❌ | Flag di conferma richiesto, scraping non implementato |
| SOS Fanta | C | ❌ | Solo interfaccia |
| Gazzetta dello Sport | C | ❌ | Solo interfaccia |
| ePlay24 | C | ❌ | Solo interfaccia — nessun accesso reale noto |
| legaseriea.it | C | ❌ | Vietato dai propri termini |
| Betson (via diretta.it, quote) | C | ❌ | Override utente esplicito accettato; bloccato da limite tecnico ambiente (browser headless) |
| livescore.com (quote, backup) | C | ❌ | Auditata da zero; quote dietro widget affiliato gated, mai osservate dal vivo |
