# Fonti dati — valutazione e stato di implementazione

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

### understat.com
- **Cosa offre**: dati xG/xA per team e partita, Premier League e Serie A dal
  2014/15 (confermato: copre "big 5 + Russia").
- **Come**: nessuna API pubblica — i dati sono incorporati come JSON dentro
  `<script>` nelle pagine (`var datesData = JSON.parse('...')`), con encoding
  esadecimale/unicode da decodificare (tecnica standard, usata da più scraper
  open-source indipendenti).
- **Confidenza**: medio-alta — pattern confermato da più tool indipendenti, ma
  non verificato con un fetch diretto in questa sessione; gli internals della
  pagina possono cambiare senza preavviso.
- **Stato nel codice**: implementato (`UnderstatProvider.parse_dates_data` +
  `get_historical_matches`); il metodo per lo xG per-team/per-partita è dichiarato
  ma non ancora implementato (v. ROADMAP.md).

### fbref.com
- **Cosa offre**: statistiche avanzate squadra/giocatore (tiri, passaggi, azioni
  difensive, metriche per-90).
- **Limite dichiarato**: 10 richieste/minuto sulla famiglia Sports-Reference/Stathead
  per questo sito specifico (oltre: blocco temporaneo). Confermato da più fonti
  (non da un fetch diretto della pagina `bot-traffic.html` in questa sessione —
  confidenza medio-alta, non verbatim).
- **Stato nel codice**: implementato (`FbrefProvider.fetch_table`) con
  `app/core/rate_limiter.py` (10 richieste/60s) e gestione delle tabelle che fbref
  incorpora dentro commenti HTML (necessario per farle leggere da `pandas.read_html`).

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

### WhoScored
- **Clausola ToS (letta tramite estrazione diretta della pagina)**:
  > "The copying, downloading, reproduction, republication, framing, broadcasting
  > and transmission of WhoScored.com content including but not limited to all
  > statistics, data, products, tables, graphics and other information is
  > prohibited without an official licence."
  >
  > "The use of WhoScored.com ratings by media, **betting** or fantasy platforms
  > requires an official licence."
- La seconda clausola nomina esplicitamente le piattaforme di scommesse — quindi
  qualunque uso di questo progetto che ecceda l'uso privato personale dell'utente
  è una violazione dei termini.
- **Stato nel codice**: `WhoScoredProvider` richiede
  `acknowledge_personal_use_only=True` per essere istanziato (altrimenti solleva
  `PersonalUseNotAcknowledgedError`); lo scraping vero e proprio **non è
  implementato** — gli endpoint reali non sono stati verificati in questo
  progetto, e implementarli "a naso" violerebbe il principio di non inventare
  endpoint.

### SofaScore
- **Clausola ToS**:
  > License "does not include any resale or commercial use of the Platform or its
  > contents, derivative use, or use of data mining, robots, or similar data
  > gathering tools."
  >
  > "SofaScore states that they do not supply sports data to bookmakers, and
  > bookmakers should not rely on their site to verify bets."
- **Stato nel codice**: stessa logica di `WhoScoredProvider` —
  `SofaScoreProvider` richiede lo stesso flag esplicito, scraping non implementato.

---

## Categoria C — Solo interfaccia astratta, non implementare

### ePlay24 (bookmaker target)
- **Cosa si sa**: ePlay24 è un bookmaker italiano reale, con licenza ADM
  (E-PLAY24 ITA LTD, concessione GAD n. 16004) — confermato tramite siti di
  recensioni scommesse italiani.
- **API pubblica**: **nessuna trovata**. Solo pagine consumer-facing, nessuna
  documentazione per sviluppatori in nessuna ricerca effettuata.
- **ToS sullo scraping**: **non verificato direttamente** in questa sessione (il
  fetch diretto di eplay24.it non è riuscito nell'ambiente di ricerca usato) — non
  va presentato come "vietato dal ToS" con certezza, ma la mancanza di qualunque
  accesso pubblico/API rende comunque l'integrazione automatica non praticabile
  senza un accordo diretto con l'operatore.
- **Conclusione operativa**: `EPlay24OddsProvider` è un'interfaccia `OddsProvider`
  che non fa nulla (`is_available()` ritorna `False`, ogni metodo dati solleva
  `NotImplementedError`) — esiste solo perché il resto del codice dipenda
  dall'astrazione `OddsProvider`, mai da ePlay24 direttamente. **In questo
  vertical slice le quote mostrate provengono da football-data.co.uk (quote
  storiche di chiusura di vari bookmaker), non da ePlay24** — il frontend lo
  segnala esplicitamente nell'interfaccia.

### Lega Serie A (legaseriea.it)
- I termini del sito vietano esplicitamente "data mining, robot o simili
  dispositivi di acquisizione o estrazione" e limitano l'uso a scopi personali
  non commerciali; inoltre i dati ufficiali di partita sono in licenza esclusiva a
  Genius Sports fino alla stagione 2028/29 — non acquistabili liberamente nemmeno
  a pagamento indipendente.
- **Stato nel codice**: `LegaSerieAProvider` è solo interfaccia, non implementata.

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
| understat.com | A | ✅ | xG/xA, non risultati completi |
| fbref.com | A | ✅ | Rate-limited 10/min |
| Open-Meteo | A | ✅ | Meteo |
| RSS/Atom generico | A | ✅ | News, URL da configurazione |
| StatsBomb Open Data | A | ❌ | Non copre stagioni correnti |
| AIA-FIGC / PGMOL | A | ❌ | Parser non ancora scritto |
| Transfermarkt | A | ❌ | ToS non verificato a fondo |
| WhoScored | B | ❌ | Flag di conferma richiesto, scraping non implementato |
| SofaScore | B | ❌ | Flag di conferma richiesto, scraping non implementato |
| SOS Fanta | C | ❌ | Solo interfaccia |
| Gazzetta dello Sport | C | ❌ | Solo interfaccia |
| ePlay24 | C | ❌ | Solo interfaccia — nessun accesso reale noto |
| legaseriea.it | C | ❌ | Vietato dai propri termini |
