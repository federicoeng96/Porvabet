# Riepilogo sessione notturna autonoma

Buongiorno. Questo documento riassume tutto il lavoro fatto in autonomia
durante la notte, dopo il tuo messaggio "Lavora in autonomia per tutta la
notte...". Copre anche il blocco di lavoro immediatamente precedente
(collegamento di Betfair) per dare un quadro completo di una sessione
continua. Per il dettaglio riga-per-riga di ogni commit vedi `CHANGELOG.md`;
per lo stato reale di ogni parte del sistema vedi `ROADMAP.md` (appena
aggiornato per riflettere tutto questo).

## Cosa è stato completato

### 1. Betfair Exchange collegato al Decision Layer
- Credenziali reali configurate e verificate al sicuro: mai stampate, loggate
  o committate (controllato esplicitamente prima di ogni test).
- **Login verificato bloccato da questa sandbox, non da credenziali o
  codice**: HTTP 403 Cloudflare "Restricted" (geo/anti-frode), stesso
  risultato sia con credenziali finte sia reali — confermato dall'utente che
  funziona da un IP italiano. Il blocco copre **l'intero dominio
  betfair.com**, non solo login/Betting API (scoperto testando anche le
  pagine di documentazione ufficiali).
- `BetfairExchangeOddsProvider` ora interroga sia `MATCH_ODDS` (1X2) sia
  `OVER_UNDER_25` (O/U 2.5 gol). Corretto un bug reale trovato leggendo il
  sorgente di `betfairlightweight` (`client.login()` è l'endpoint cert-based,
  serve `login_interactive()`). Aggiunti locale italiano e rinnovo automatico
  della sessione (`session_expired`/`keep_alive`, fallback a re-login) — non
  serve mai reinserire nulla manualmente.
- `ingest_live_odds_quotes` collega il provider al Decision Layer:
  `run_analysis_for_match` lo interroga per ogni partita non `FINISHED`,
  mai un crash o una quota inventata se la fonte fallisce.
- **Corner/cartellini**: indagati a fondo (non solo "non ancora fatto").
  Impossibile verificare da questa sandbox se Betfair li offra — bloccata
  anche la documentazione. Un indizio reale (il vero In-Play Service di
  Betfair traccia `numberOfCorners`/`numberOfYellowCards` come statistiche
  live) suggerisce che l'infrastruttura esista, ma non conferma un market
  type exchange specifico. Restano "n/d" per tua istruzione esplicita.

### 2. Decision Layer: "n/d" esplicito invece di riga saltata
- `_build_candidates_and_predictions` ora fa get-or-create di
  `Market`/`MarketOutcome` per MATCH_RESULT/TOTAL_GOALS (prima dipendeva da
  righe già esistenti) e persiste **sempre** una `Prediction` per ogni esito
  con probabilità calcolabile dal modello: con quota reale quando esiste
  (come prima), altrimenti con `bookmaker_odds=None`/`value=None` — mai una
  riga assente, mai un prezzo inventato.
- Scelta di design presa (opzione (b) tra le due segnalate una sessione fa):
  un tipo di riga separato (`NoOddsEstimateOut`, generalizzazione di
  `CountEstimateOut` — uno per esito, non solo coppie Over/Under, necessario
  per i 3 esiti di MATCH_RESULT), non rendere `RiskFactors`/`Candidate`
  opzionali. Il layer di rischio/valore esistente, già testato, resta
  invariato.
- Frontend aggiornato di conseguenza (sezione "Stime senza quota reale").

### 3. Fixture future reali: football-data.org (non diretta.it)
- Avevi corretto esplicitamente il piano originale (diretta.it): verificato
  dal vivo che anche il calendario di diretta.it è caricato via JS lato
  client, stesso blocco tecnico delle quote Betson — costruirci sopra
  sarebbe stata una "fonte inventata".
- `FootballDataOrgFixtureProvider` (categoria A): endpoint reale
  `GET /v4/competitions/{PL|SA}/matches?matchday=N` verificato dal vivo (non
  assunto), header `X-Auth-Token`, piano gratuito confermato per
  Premier League + Serie A. **La rete di questa sandbox NON è bloccata verso
  questa API** (a differenza di Betfair) — verificato con una chiamata
  pubblica reale e un test a token non valido (risposta corretta "token
  invalido", non un blocco di rete).
- Manca solo una chiave gratuita (registrazione su football-data.org) per
  renderlo operativo — non è la stessa cosa di "spendere denaro", ma è
  comunque un passo che solo tu puoi fare.
- `ingest_upcoming_fixture` persiste ogni fixture come `Match` `SCHEDULED`,
  idempotente, non tocca mai una partita già `FINISHED`.

### 4. Verificato (non re-implementato): precompute 10 livelli + frontend
Prima di scrivere altro codice, ho controllato direttamente cosa esisteva
già — e i due punti seguenti **erano già completi da una sessione
precedente**, non solo "a memoria":
- `build_risk_ladder` (`selection.py`) precomputa già tutti i 10 livelli di
  rischio (1 principale + 2 alternative, evitando il riuso dello stesso
  mercato come principale quando possibile), persistiti come `RiskSelection`
  dentro `run_analysis_for_match` — nessun ricalcolo quando l'utente cambia
  lo slider nel frontend.
- Lo stesso `build_risk_ladder` è già usato dentro il backtest walk-forward
  (`run_walk_forward_backtest`), con hit rate/ROI per livello 1-10 già
  pubblicati su dati reali in `BACKTEST_SPEC.md` (60%→20% dal Risk 1 al 10,
  proprietà di ranking confermata).
- Il frontend (`page.tsx`/`match/[id]/page.tsx`) ha già: tabella con tutte
  le colonne richieste, rischio di gruppo modificabile per singola partita
  senza ricalcolo, schedina automatica senza pulsante "+", popover alert con
  esattamente le soglie 10%/15% richieste e il linguaggio "potenziale
  mispricing"/mai "quota sicuramente sbagliata".

Nessun lavoro necessario qui — solo verifica diretta nel codice.

### 5. Coerenza documentale
- Aggiornati DATA_SOURCES.md, ARCHITECTURE.md, MODEL_SPEC.md, ROADMAP.md,
  README.md, RUNNING_LOCALLY.md, CHANGELOG.md per riflettere tutto quanto
  sopra.
- Trovate e corrette **due voci obsolete/contraddittorie** in ROADMAP.md
  durante il controllo (non solo un controllo formale): una diceva che un
  ri-test già fatto non era stato fatto; un'altra diceva che la colonna
  ALERT era ancora bloccata, quando Betfair l'ha appena sbloccata.

## Decisioni prese in autonomia (con motivazione)

- **football-data.org invece di continuare a investigare diretta.it per le
  fixture**: hai corretto tu stesso questo punto a metà lavoro — non è stata
  una mia decisione indipendente, ma l'ho eseguita verificando dal vivo
  l'endpoint reale invece di fidarmi della tua premessa "già categoria A fin
  dai primi audit" (non risultava da nessuna parte in questo progetto — l'ho
  verificato e classificato io stesso stanotte, non era mai stato fatto).
- **Corner/cartellini restano "n/d" invece di un market type indovinato**:
  hai già anticipato questo fallback nel tuo stesso messaggio ("se Betfair
  non li offre, documentalo e lasciali n/d"); l'ho applicato dopo aver
  esaurito ogni verifica possibile da questa sandbox, non per pigrizia.
- **Opzione (b) per il design "n/d"** (tipo di riga separato) invece
  dell'opzione (a) (rendere `RiskFactors` opzionale): scelta per minimizzare
  il rischio sul layer di rischio/valore già testato — un cambiamento più
  contenuto a parità di risultato visibile per l'utente.
- **Non ho toccato la persistenza server-side della schedina** (ROADMAP.md,
  punto 10): resta un'ambiguità di prodotto reale (richiederebbe inventare
  un modello Utente/sessione che non esiste in questo progetto) — non è uno
  dei due punti che hai esplicitamente escluso stanotte, ma è lo stesso tipo
  di "decisione di prodotto, non tecnica" che meritava di restare segnalata
  invece di forzata, coerente con come l'ho trattata la volta scorsa.
- **Non ho iniziato una nuova fonte dati non richiesta stanotte** (es. dati
  arbitro AIA-FIGC/PGMOL, già flaggati in ROADMAP.md come prossimo passo
  concreto per migliorare il modello cartellini): è un lavoro sostanzioso
  (nuovo provider, nuovo parser HTML, nuovo collegamento al modello) fuori
  dallo scope esplicito dei 6 punti che hai chiesto stanotte — meglio
  iniziarlo con un contesto fresco dedicato che infilarlo di corsa in coda a
  una sessione già molto lunga.

## Cosa resta esplicitamente bloccato dai due punti che hai escluso

1. **Nessuna spesa di denaro**: non incontrato un caso concreto stanotte in
   cui servisse (football-data.org e la registrazione Betfair sono entrambe
   gratuite) — ma resta il vincolo per il futuro (es. se mai si considerasse
   la Betfair Live App Key, ~£499 di attivazione: **non farlo mai senza
   chiedere**, non serve comunque per questo progetto).
2. **Nessuna fonte nuova con divieto ToS assoluto mai vista prima**: non
   incontrata stanotte. Le fonti già categoria C esistenti (diretta.it/
   Betson, WhoScored, SofaScore, legaseriea.it, ecc.) restano come già
   impostate, non riaperte.

Non c'è quindi nulla di "bloccato in attesa" da questi due vincoli stanotte
— i blocchi reali che restano (chiave football-data.org, verifica Betfair
dal vivo, corner/cartellini non verificabili) sono tutti per ragioni di rete
o di credenziali, non per i due punti che hai escluso.

## Prossimo passo più importante da affrontare insieme

**Ottenere le due chiavi/verifiche che restano bloccate su questa sandbox**:
1. Registrati su football-data.org (gratuito) e passami la chiave
   (`FOOTBALL_DATA_ORG_API_KEY`) — con quella posso verificare dal vivo
   `scripts/ingest_upcoming_fixtures.py` anche da qui, senza dover aspettare
   una sessione locale.
2. Dal tuo computer (v. `RUNNING_LOCALLY.md`), verifica end-to-end Betfair:
   login, copertura reale 1X2/O-U sulle partite Premier League/Serie A
   effettivamente in calendario, e se noti per caso un mercato
   corner/cartellini mentre sei lì, dimmelo — è l'unico modo rimasto per
   chiudere quel punto con certezza invece che con un indizio circostanziale.

Una volta con questi due elementi, il sistema avrebbe per la prima volta
**partite future reali + quote Betfair reali** insieme nello stesso posto —
il primo vero test end-to-end del prodotto come sarà usato normalmente,
non solo dei suoi pezzi separati.

Oltre a questo, il prossimo punto di valore più alto già identificato in
ROADMAP.md (non iniziato stanotte, per lo scope esplicito dei 6 punti) è il
collegamento dei dati arbitro (AIA-FIGC/PGMOL, già categoria A) al modello
cartellini — vale la pena discuterne l'ordine di priorità insieme prima che
lo inizi.

---

Test puliti (172), lint pulito, build frontend verificata prima di ogni
commit. 5 commit pushati durante la sessione notturna vera e propria
(`fc37ef8`..`491b85a`), più i 2 del blocco Betfair immediatamente precedente
(`730c3e5`, `27b5621`) — 7 commit in totale in questa sessione continua, tutti
su `claude/sports-betting-prematch-engine-5m4z1t`.
