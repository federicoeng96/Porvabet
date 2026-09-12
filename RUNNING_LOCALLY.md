# Eseguire Porvabet in locale

Questo progetto viene sviluppato in un ambiente sandbox remoto (container
effimero, ricreato a ogni sessione). Quell'ambiente ha un limite di rete
concreto e verificato che **non esiste sul computer dell'utente**: l'IP di
uscita della sandbox viene bloccato da alcuni servizi esterni a livello di
rete (geo-blocking/anti-frode, WAF), indipendentemente da credenziali o
codice. Questo documento spiega quando e perché serve eseguire il progetto
in locale per completare una verifica, e come farlo.

## Perché serve: il blocco di rete della sandbox

**Betfair Exchange** è il caso verificato in questa sessione: il login
interattivo (`POST https://identitysso.betfair.it/api/login`) restituisce
`HTTP 403` con una pagina Cloudflare che dice esplicitamente

> "Our Software detects that you may be accessing the Betfair website from a
> country that Betfair does not accept bets from or the traffic from your
> network was detected as being unusual."

testato **sia con credenziali placeholder finte sia con le credenziali reali
dell'utente** — stesso risultato in entrambi i casi, il che conferma che il
blocco avviene **prima** di qualunque elaborazione delle credenziali, quindi
è un blocco sull'IP della sandbox, non un problema di account o di codice.
L'utente ha confermato che lo stesso login **funziona correttamente da un IP
italiano/residenziale** (è così che ha ottenuto la propria Delayed
Application Key). Vedi `DATA_SOURCES.md` per il dettaglio completo.

Un limite simile (ma diverso nella causa tecnica: reset del TLS handshake
per qualunque browser headless, non un blocco geografico) è già documentato
per Betson/diretta.it e livescore.com — vedi `DATA_SOURCES.md`.

**In pratica**: qualunque verifica che richieda una vera chiamata di rete
verso Betfair — login, `getDeveloperAppKeys`, copertura mercati 1X2/O-U
2.5/corner/cartellini, un test end-to-end reale del `BetfairExchangeOddsProvider`
— non può essere completata dentro la sandbox e va fatta dal computer
dell'utente.

## Prerequisiti

- Python 3.11+
- Postgres 16 (locale, o raggiungibile in rete)
- Node.js 20+ (solo per il frontend)
- Le tue credenziali Betfair: `BETFAIR_USERNAME`, `BETFAIR_PASSWORD`, e una
  **Delayed** Application Key (`BETFAIR_APP_KEY`) — mai la Live key, a
  pagamento e non necessaria qui. Se non hai ancora una App Key, generala tu
  stesso da `apps.betfair.com` ("Accounts API Demo Tool", operazione
  `createDeveloperAppKeys`) o dal tuo account Betfair — è un passo manuale
  una tantum, questo progetto non lo automatizza (vedi `DATA_SOURCES.md`).

## Setup

```bash
git clone <questo repository>
cd Porvabet/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Postgres locale — una tantum:
sudo -u postgres psql -c "CREATE USER porvabet WITH PASSWORD 'porvabet_dev' SUPERUSER;"
sudo -u postgres psql -c "CREATE DATABASE porvabet OWNER porvabet;"
sudo -u postgres psql -c "CREATE DATABASE porvabet_test OWNER porvabet;"

alembic upgrade head
```

Crea `backend/.env` (mai committato — è in `.gitignore`; usa
`backend/.env.example` come riferimento dei nomi):

```
DATABASE_URL=postgresql+psycopg://porvabet:porvabet_dev@localhost:5432/porvabet
BETFAIR_USERNAME=<il tuo username Betfair>
BETFAIR_PASSWORD=<la tua password Betfair>
BETFAIR_APP_KEY=<la tua Delayed Application Key>
```

**Non incollare mai questi valori in una chat, in un issue, in un commit o in
un log condiviso.** Restano solo in questo file locale, non tracciato da git.

## Verifica end-to-end di Betfair (quello che la sandbox non può fare)

1. **Conferma che il login funzioni da qui**:

   ```bash
   python -c "
   from app.providers.betfair.provider import BetfairExchangeOddsProvider
   p = BetfairExchangeOddsProvider()
   client = p._ensure_client()
   print('Login OK, sessione attiva:', not client.session_expired)
   "
   ```

   Se stampa `Login OK, sessione attiva: True`, il login funziona (a
   differenza della sandbox). Se fallisce, l'errore stampato da
   `betfairlightweight` (status HTTP + `loginStatus`) dice perché — non
   stampa mai la password o il token.

2. **Verifica copertura mercati reale** su una partita Premier League o
   Serie A imminente (nomi squadre come compaiono su Betfair, es. `"Arsenal"`,
   `"Inter"`):

   ```bash
   python -c "
   from app.providers.betfair.provider import BetfairExchangeOddsProvider
   p = BetfairExchangeOddsProvider()
   records = p.get_odds_for_match('Arsenal', 'Chelsea', '2026-09-20T15:00:00+00:00')
   for r in records:
       print(r.market_label, r.outcome_code, r.decimal_odds)
   "
   ```

   Se la lista è vuota, o mancano OVER/UNDER, significa che quel mercato non
   è (ancora) tradable su Betfair per quella partita — comportamento atteso,
   non un bug. Ripeti su 4-5 partite diverse (EPL e Serie A, diverse
   distanze dal kickoff) per farti un'idea reale della copertura, poi
   aggiorna `DATA_SOURCES.md` con quello che trovi (sostituendo le note
   "non verificato dal vivo" con numeri/osservazioni reali).

3. **Test end-to-end completo** (ingestione storica + analisi con quote live
   Betfair) su un'istanza locale del backend:

   ```bash
   python scripts/ingest_football_data.py --competitions EPL SERIE_A --seasons 2015 2024
   uvicorn app.main:app --reload --port 8000
   # poi, per una partita futura già presente nel DB (o creata manualmente):
   curl -X POST http://localhost:8000/matches/<id>/analyze
   ```

   Se Betfair ha una quota liquida per quella partita, la vedrai come quota
   reale (`bookmaker = "Betfair (exchange, dati ritardati 1-180s)"`) nella
   risposta; altrimenti quel mercato resta senza valore/alert calcolabile,
   mai una quota inventata.

## Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL punta al backend locale
npm run dev   # http://localhost:3000
```

## Dopo la verifica

Se trovi differenze reali rispetto a quanto documentato in
`DATA_SOURCES.md` (es. corner/cartellini effettivamente presenti su Betfair
con un market type che non ci aspettavamo, o 1X2/O-U con liquidità diversa
da quanto stimato), aggiorna quel file con i numeri reali osservati — mai
lasciare una nota "non verificato" quando ormai lo è stata.
