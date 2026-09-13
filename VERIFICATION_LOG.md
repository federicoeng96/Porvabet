# Verification Log — primo giro end-to-end con dati reali (2026-09-13)

Registro onesto di un singolo giro end-to-end reale (fixture → motore statistico →
tentativo quota Betfair → Decision Layer → precompute rischio → frontend),
richiesto esplicitamente dall'utente per vedere esattamente cosa succede *oggi*
con una partita vera, non con dati sintetici. Ogni riga qui sotto è stata
verificata eseguendo il codice reale contro il DB reale di questa sessione, non
dedotta o assunta.

## 0. Blocco iniziale e causa reale

`FOOTBALL_DATA_API_KEY` era presente nell'ambiente fin dall'inizio (confermato
con `env | grep -c`), ma sotto un nome diverso da quello letto dal codice
(`FOOTBALL_DATA_ORG_API_KEY`, via `pydantic-settings`). Corretto in
`app/config.py` con un `AliasChoices` che accetta entrambi i nomi (v. CHANGELOG.md,
commit `ae42a47`). Non era quindi né un problema della sandbox né una chiave
mai davvero impostata — un mismatch di una sola parola (`_ORG_`) mai notato
prima perché nessuna sessione precedente aveva stampato il valore effettivo
della variabile per confrontarlo col nome atteso dal codice.

## 1. Fixture provider reale (football-data.org)

`python scripts/ingest_upcoming_fixtures.py --competitions EPL SERIE_A`:

```
[OK]   EPL: 3 upcoming fixtures
[OK]   SERIE_A: 6 upcoming fixtures
Done. 9 real upcoming fixtures ingested (source=football_data_org).
```

9 partite reali della prossima giornata (13-14/09/2026), incluse Man United –
Man City (EPL) e Napoli – Bologna (Serie A).

**Trovato e corretto in diretta un mismatch nomi squadra reale** (lo stesso tipo
di problema già risolto per Man City/AC Milan, come previsto dall'utente):
football-data.org restituisce i nomi ufficiali completi ("Manchester United FC",
"FC Internazionale Milano", "AS Roma", ecc.), diversi da quelli già usati da
football-data.co.uk ("Man United", "Inter", "Roma"). Senza correzione, la prima
ingestione ha creato **16 `Team` duplicati su 18 squadre** (verificato
interrogando il DB prima/dopo, non assunto) — solo Coventry City, mai vista
nelle 10 stagioni storiche EPL/Serie A già ingerite, avrebbe dovuto legittimamente
creare una riga nuova. Aggiunta `FOOTBALL_DATA_ORG_TEAM_NAME_ALIASES` +
`resolve_or_create_team` (stesso pattern hand-curated già usato per understat),
ripulito il DB dai 16 duplicati, rieseguita l'ingestione: ora tutte le squadre
già note si risolvono sulla riga esistente. 3 nuovi test dedicati (v.
`tests/test_ingestion.py`).

## 2. Motore statistico (Dixon-Coles) su fixture reali

Eseguito direttamente contro le due partite target (3.800 partite di training
per campionato, le stesse 10 stagioni già in `BACKTEST_SPEC.md`):

| Partita | 1X2 (Home/Draw/Away) | Over/Under 2.5 |
|---|---|---|
| Man United – Man City (EPL) | 19.0% / 22.2% / 58.7% | 54.6% / 45.4% |
| Napoli – Bologna (Serie A) | 51.3% / 27.1% / 21.6% | 45.5% / 54.5% |

Probabilità sensate (sommano a 1 per mercato, riflettono la forza relativa reale
delle squadre nelle 10 stagioni ingerite — Man City favorito in trasferta su Man
United, Napoli favorito in casa su Bologna). Nessun dato inventato: stesso
`DixonColesModel`/stesso identico percorso di codice già usato nel backtest.

## 3. Tentativo quota Betfair (atteso fallire da qui)

```
ERROR app.providers.base.odds_provider_chain: OddsProvider betfair_exchange
failed fetching Man United vs Man City — falling back to the next source
...
betfairlightweight.exceptions.StatusCodeError: Status code error: 403
```

Confermato di nuovo, dal vivo, con una chiamata reale (non simulata) verso
l'API Betfair reale: stesso blocco geografico/anti-frode già documentato in
`DATA_SOURCES.md` per l'intero dominio betfair.com. Nessun'altra fonte di quote
pre-match reali configurata in questo ambiente (v. `DATA_SOURCES.md`) — quindi
zero `OddsQuote` per entrambe le partite, come atteso.

## 4. Decision Layer — risultato reale, non quello atteso

**Qui il giro reale ha trovato qualcosa che nessun test sintetico precedente
aveva mai potuto trovare**: chiamare `run_analysis_for_match` (o
`POST /matches/{id}/analyze`) su una qualunque delle due partite reali
restituisce oggi:

```
HTTP 422
{"detail":"No market has both a model probability and a bookmaker odds quote
for this match — nothing to analyze."}
```

Causa (letta nel codice, non assunta — `app/engine/decision/analysis_runner.py`):
quando **nessun mercato ha una quota reale da nessuna fonte** (né Betfair live,
né una quota storica di chiusura — il caso normale per qualunque fixture
genuinamente futura in questa sandbox, dato che Betfair è sempre bloccato),
`_build_candidates_and_predictions` produce zero `Candidate` (corretto: un
`Candidate` richiede per costruzione una quota bookmaker reale). Il chiamante
interrompe l'intera analisi con `InsufficientDataError` non appena
`candidates` è vuoto — **prima** di calcolare le stime "n/d" per CORNERS/CARDS
(`compute_count_market_estimates`, che non dipende affatto da una quota
bookmaker e infatti produce output sensato se chiamata direttamente, bypassando
il guardrail — v. sotto) e senza mai arrivare a costruire il precompute a 10
livelli (`build_risk_ladder` richiede almeno un `Candidate`).

Verificato chiamando direttamente le funzioni interne (senza commit, solo
diagnostica) che, se il guardrail non fermasse tutto, l'output sarebbe sensato:

```
CORNERS  Man Utd vs Man City: line=9.5  P(over)=57.6% P(under)=42.4%
CARDS    Man Utd vs Man City: line=3.5  P(over)=46.7% P(under)=53.3%
CORNERS  Napoli vs Bologna:   line=9.5  P(over)=34.2% P(under)=65.8%
CARDS    Napoli vs Bologna:   line=3.5  P(over)=54.4% P(under)=45.6%
```

**Importante**: questo non è un bug introdotto stanotte. È un comportamento
deliberato di una sessione precedente, bloccato da un test esistente
(`tests/test_analysis_runner.py::test_run_analysis_survives_live_odds_provider_failure`,
che documenta esplicitamente questo esatto scenario — zero quote ovunque — come
"correttamente" risolto con `InsufficientDataError`). Il giro reale di stanotte
è semplicemente la prima volta che questo scenario si verifica con una vera
fixture futura invece che con dati sintetici stagionati con quote finte, quindi
la prima volta che le sue conseguenze diventano visibili.

**Questa è la vera domanda architetturale aperta**, non un dettaglio tecnico
che ho risolto da solo (v. messaggio in chat): il Decision Layer dovrebbe
comunque salvare le righe "n/d" (probabilità modello, nessuna quota) con una
risk ladder vuota/parziale quando **letteralmente nessun mercato** ha una quota
reale, invece di annullare l'intera analisi? Le due opzioni ragionevoli:

- **A — comportamento attuale**: nessuna quota da nessuna parte → 422,
  nient'altro salvato. Semplice, ma significa che *nessuna* fixture futura reale
  può mai apparire nell'app finché Betfair non è raggiungibile da qui o non
  esiste una quota storica.
- **B — cambiare**: salvare comunque `AnalysisVersion` + predizioni "n/d" per
  MATCH_RESULT/TOTAL_GOALS/CORNERS/CARDS, con `risk_levels=[]` (nessuna
  ladder possibile senza un prezzo reale da rankare). Coerente con la filosofia
  già scritta nel codice ("mai una riga saltata"), ma cambia un comportamento
  già deliberatamente testato.

Non ho scelto autonomamente: modifica il comportamento di un test esistente
scritto con intento esplicito, è esattamente il tipo di fork che richiede una
decisione del proprietario del prodotto, non un dettaglio tecnico.

## 5. Precompute 10 livelli di rischio

Non raggiunto per nessuna delle due partite reali, conseguenza diretta del
punto 4 (`build_risk_ladder` non viene mai chiamato). Il meccanismo stesso
(`build_risk_ladder`, già usato con successo nel backtest walk-forward su
migliaia di partite storiche reali) non è in discussione — è solo mai
raggiunto per queste due fixture specifiche nello stato attuale.

## 6. Frontend — verificato con Playwright, dati reali

- **Homepage**: mostra correttamente le 16 partite reali **storiche** (non
  sintetiche — chiusura odds reale da football-data.co.uk, non il seed di ieri
  notte) già analizzate in sessioni precedenti. Le 9 nuove fixture reali
  **non appaiono** nella tabella, per il motivo del punto 4 (nessuna
  `RiskSelection` esiste per loro).
- **Pagina dettaglio partita** (`/match/7612`, Man United – Man City, dato reale
  da football-data.org): mostra correttamente "nessuna analisi disponibile" /
  "Nessuna selezione disponibile per questo livello di rischio" — nessun dato
  inventato, nessun crash, stato onestamente vuoto.
- **Bug minore trovato cliccando davvero "AGGIORNA ANALISI"** su questa pagina:
  la risposta 422 diventa un'eccezione JS non gestita (`PAGEERROR` catturato da
  Playwright) — il pulsante torna correttamente al suo stato normale dopo il
  `finally`, ma l'utente non vede **nessun messaggio d'errore** in pagina (a
  differenza della home, che ha un banner di errore dedicato). Non corretto
  qui: è un dettaglio dell'UI, minore rispetto alla domanda architetturale del
  punto 4, e la correzione dipende da quale decisione viene presa lì (il
  messaggio d'errore giusto per un 422 "insufficient data" è diverso se quello
  stato deve continuare a esistere o no).

Screenshot inviati separatamente in chat.

## 7. Decisione presa e fix implementato

L'utente ha scelto l'opzione **B** del punto 4: quando nessun mercato ha una
quota reale da nessuna fonte, il Decision Layer deve produrre comunque la risk
ladder completa (10 livelli, 1 principale + 2 alternative), con probabilità/
quota-modello sempre presenti e Value/Alert = "n/d" ovunque — nessuna eccezione
speciale per il caso limite "zero quote ovunque", stessa identica logica già
implementata per "alcuni mercati senza quota", solo estesa.

**Implementazione** (`app/engine/decision/selection.py`, `risk_score.py`,
`analysis_runner.py`, `schemas/analysis.py`, `api/routers/matches.py` +
equivalenti frontend):
- `Candidate.bookmaker_odds`/`RiskFactors.bookmaker_odds`/`ScoredCandidate.value`
  diventano `float | None`. `_build_candidates_and_predictions` ora costruisce
  **sempre** un `Candidate` per ogni esito MATCH_RESULT/TOTAL_GOALS (5 esiti,
  incondizionatamente), con quota reale quando esiste, altrimenti
  `bookmaker_odds=None`/`value=None` — mai più un ramo che salta la
  costruzione del `Candidate`.
- `risk_score.compute_risk_raw`: quando `bookmaker_odds` è `None`, il peso del
  fattore "odds_magnitude" (10%) viene **redistribuito proporzionalmente** sugli
  altri fattori reali (probabilità, incertezza, affidabilità modello, ecc.) —
  mai un prezzo sostitutivo inventato (es. la fair odds del modello stesso,
  che avrebbe solo duplicato "improbability" sotto altro nome).
- La riga `if not candidates: raise InsufficientDataError(...)` in
  `run_analysis_for_match` è stata **rimossa**: `candidates` non è più mai
  vuota una volta che il modello ha fatto fit (i due controlli
  `InsufficientDataError` legittimi — storico insufficiente, squadra mai vista
  — restano invariati, sono un problema diverso).
- `_no_odds_estimates_out` (endpoint `additional_estimates`) ora esclude le
  Prediction già coperte da una `RiskSelection`, per non duplicare la stessa
  riga sia nella ladder sia in "stime senza quota" — che resta quindi
  riservato a CORNERS/CARDS, mai parte del meccanismo ladder.
- Frontend (`types.ts`, `page.tsx`, `AlertPopover.tsx`, `BetSlip.tsx`,
  `match/[id]/page.tsx`): `bookmaker_odds`/`value` nullable ovunque, renderizzati
  come "n/d"; la schedina automatica esclude le selezioni principali n/d (nessun
  prezzo reale con cui calcolare una quota totale), pur restando visibili e
  navigabili in tabella.

**Audit di coerenza** (richiesto esplicitamente): cercato ogni altro punto con
la stessa assunzione "serve almeno una quota". Trovato un solo altro punto,
`app/backtest/runner.py` (`_build_candidates`) — **deliberatamente lasciato
invariato**: il backtest valuta solo scommesse effettivamente piazzabili
storicamente (quota di chiusura reale sempre presente per dati football-data.co.uk),
quindi "salta la partita se non c'è quota" resta l'unico comportamento corretto
lì — non è lo stesso problema del Decision Layer live, che deve invece mostrare
qualcosa anche per una fixture futura reale senza quota ancora pubblicata.

**Ri-verificato con le stesse due fixture reali di prima** (Man United–Man
City, Napoli–Bologna), stesso identico giro (fixture → Dixon-Coles → tentativo
Betfair → Decision Layer):

```
=== Running analysis for match 7612 ===
[stesso 403 reale di Betfair, invariato]
OK: risk_levels computed = 10   count_market_estimates = 2
=== Running analysis for match 7615 ===
[stesso 403 reale di Betfair, invariato]
OK: risk_levels computed = 10   count_market_estimates = 2
```

Contenuto reale di un livello (`GET /matches/7612`, livello 1):
`main` = 1X2 AWAY, probabilità 58.7%, `bookmaker_odds: null`, `value: null`,
`alert: null`, rationale "quota n/d, valore atteso n/d" — e lo stesso per le 2
alternative. `additional_estimates` mostra solo CORNERS/CARDS (2+2 righe), come
da disegno. Confermato via `GET /matches?risk_level=5`: entrambe le fixture
reali ora compaiono nella tabella principale con quota "n/d" invece di essere
assenti.

**Frontend, Playwright, dati reali**: nuovi screenshot (inviati in chat)
mostrano la homepage con le due fixture reali visibili in tabella (quota
"n/d", escluse dalla schedina automatica) e le pagine dettaglio con la ladder
completa (selezione principale + 2 alternative, tutte n/d) al posto della
pagina d'errore "nessuna analisi disponibile" di prima.

**Test**: 3 nuovi test dedicati in `tests/test_decision_layer.py` (risk score
con quota assente, ladder tutta n/d, ladder mista priced/n/d) + i 3 test
esistenti che assumevano il vecchio comportamento riscritti per il nuovo
(`test_run_analysis_shows_nd_for_market_with_no_liquid_quote`,
`test_run_analysis_survives_live_odds_provider_failure`,
`test_match_detail_exposes_nd_estimates_for_markets_without_a_quote`). 185
test passano, lint pulito, build/typecheck frontend puliti.

## Conclusione onesta

Reale, verificato end-to-end oggi, in due giri: ingestione fixture, mapping
nomi squadra, motore statistico, tentativo Betfair (fallito come atteso),
frontend con dati reali. Il primo giro ha trovato un limite architetturale
reale (analisi interrotta quando zero mercati hanno una quota); il secondo,
dopo una decisione esplicita dell'utente e la relativa implementazione, mostra
**la ladder a 10 livelli completa con Value/Alert "n/d"** per entrambe le
fixture reali, visibili e navigabili in tabella e in pagina dettaglio — non
più un errore, non più un'assenza silenziosa, mai un prezzo inventato.
