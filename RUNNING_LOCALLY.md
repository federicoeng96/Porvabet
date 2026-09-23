# Eseguire Porvabet sul tuo computer

Questa guida è scritta per chi non ha mai usato un terminale prima. Segui i
passi in ordine, uno alla volta — non serve capire cosa fa ogni comando,
basta copiarlo ed eseguirlo.

**Perché serve farlo sul tuo computer e non da questa sessione**: l'ambiente
in cui questo progetto viene sviluppato (una sandbox remota) non riesce a
raggiungere Betfair — il suo indirizzo di rete viene bloccato (blocco
geografico/anti-frode, verificato: stesso blocco sia con credenziali finte
sia con le tue credenziali reali). Dal tuo computer, con una connessione
internet normale, questo blocco non c'è — è così che hai già ottenuto la tua
Delayed Application Key. Il resto del progetto (football-data.org, il
database, il sito) funziona invece anche da dentro la sandbox, ed è già
stato verificato lì con dati reali (vedi `VERIFICATION_LOG.md`).

## Riepilogo in 3 passi

1. Installa 3 programmi (una volta sola) — vedi sotto.
2. Apri PowerShell nella cartella del progetto ed esegui `.\setup.ps1` (una
   volta sola).
3. Ogni volta che vuoi usare Porvabet, esegui `.\start.ps1` — apre tutto da
   solo e ti porta dritto alla pagina con le partite.

## Passo 1 — Installa i 3 programmi necessari

Se li hai già installati, salta al Passo 2.

1. **Python** — <https://www.python.org/downloads/> (scarica l'ultima
   versione). **Importante**: durante l'installazione, spunta la casella
   "Add python.exe to PATH" (di solito in basso nella prima schermata) —
   se non la spunti, dovrai reinstallare.
2. **Node.js** — <https://nodejs.org/> (scarica la versione "LTS",
   consigliata).
3. **PostgreSQL** — <https://www.postgresql.org/download/windows/>
   (versione 16). Durante l'installazione ti verrà chiesto di scegliere una
   password per l'utente `postgres`: **scegline una e segnala da qualche
   parte**, ti servirà tra un minuto. Puoi lasciare tutte le altre opzioni
   come sono (porta 5432 di default).

Dopo aver installato tutti e 3, **chiudi e riapri** qualunque finestra
PowerShell già aperta (serve perché riconosca i nuovi programmi).

## Passo 2 — Setup (una volta sola)

*Hai già clonato questo progetto in precedenza?* Esegui `git pull` prima di
procedere, per essere sicuro di avere l'ultima versione degli script
(alcuni problemi di setup.ps1 sono stati corretti dopo la prima versione).

1. Scarica/clona questo progetto sul tuo computer, in una cartella a tua
   scelta (es. `C:\Porvabet`).
2. Apri quella cartella in Esplora File, tieni premuto **Shift** e clicca
   col tasto destro in uno spazio vuoto → **"Apri finestra PowerShell qui"**
   (su Windows 11: tasto destro → "Apri nel terminale").
3. Se è la prima volta che esegui uno script PowerShell su questo computer,
   incolla questo comando e premi Invio (autorizza solo questa finestra, non
   cambia nulla in modo permanente):
   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   ```
4. Poi esegui:
   ```powershell
   .\setup.ps1
   ```
5. Lo script controlla tutto da solo, crea il database, e — se è la prima
   volta — ti chiederà la password di PostgreSQL scelta al Passo 1 (appare
   un prompt nel terminale: scrivila e premi Invio, non si vedrà nulla
   mentre digiti, è normale) e aprirà **Blocco Note** con un file da
   compilare con le tue chiavi Betfair/football-data.org — se non le hai
   ancora, lascia il file com'è e chiudilo, potrai completarlo più tardi
   (vedi sotto).
6. Verso la fine, lo script chiede: **"Scaricare lo storico ora? [S/n]"** —
   rispondi con **Invio** (o `S`) per scaricare automaticamente ~10 stagioni
   di partite passate (Premier League + Serie A, risultati/corner/
   cartellini/falli/quote di chiusura) da football-data.co.uk. **Questo
   passaggio è necessario**: senza storico il motore statistico rifiuta di
   calcolare previsioni (serve un minimo di partite passate per stimare la
   forza delle squadre) — non serve nessuna chiave per questo passo (fonte
   diversa da football-data.org, usata invece per le partite future). Ci
   vogliono un paio di minuti; puoi anche saltarlo e farlo più tardi (te lo
   ripete lo script stesso, con il comando esatto da copiare).

Se qualcosa va storto, lo script stampa in rosso cosa non ha funzionato e
cosa fare — leggi con calma il messaggio prima di richiedere aiuto, spesso
dice esattamente il problema (vedi anche "Problemi comuni" più sotto).

**Rilanciare `.\setup.ps1` più volte è del tutto normale e sicuro** (es. se
il setup si è interrotto a metà, o vuoi solo essere sicuro che tutto sia a
posto): lo script riconosce da solo cosa è già stato fatto (database già
creati, ambiente virtuale già presente, ecc.) e salta quei passaggi senza
generare errori — non serve "ripulire" nulla prima di rilanciarlo.

## Passo 2bis — Le tue chiavi (se non le hai ancora messe)

Apri `backend\.env` con Blocco Note e compila queste righe (le altre
non toccarle):

```
BETFAIR_APP_KEY=<la tua Delayed Application Key>
BETFAIR_USERNAME=<il tuo username Betfair>
BETFAIR_PASSWORD=<la tua password Betfair>
FOOTBALL_DATA_ORG_API_KEY=<la tua chiave gratuita football-data.org>
THE_ODDS_API_KEY=<la tua chiave gratuita the-odds-api.com>
```

Non hai ancora una chiave football-data.org? È gratuita e richiede un
minuto: vai su <https://www.football-data.org>, clicca "Get started",
registrati con la tua email (nessuna carta di credito richiesta), e trovi
la chiave nella tua area account.

Non hai ancora una chiave The Odds API? Anche questa è gratuita e richiede
un minuto: vai su <https://the-odds-api.com/> (**con il trattino** — non
`theoddsapi.com`, un prodotto diverso con un piano gratuito che non copre il
calcio), scorri alla sezione prezzi, scegli il piano **"Starter"
(gratuito)**, registrati con la tua email (nessuna carta di credito
richiesta) e trovi la chiave nella dashboard. Serve solo come riserva:
se Betfair è configurato e raggiungibile, Porvabet lo usa per primo e non
tocca questa chiave; se Betfair non è ancora pronto (es. KYC in corso),
questa fa da fallback con 500 richieste gratuite al mese (v. DATA_SOURCES.md
per il dettaglio). Puoi anche lasciarla vuota per ora: senza, Porvabet
prova solo Betfair e mostra "n/d" quando anche quello non ha una quota.

**Non condividere mai questi valori** (chat, email, screenshot, commit) —
restano solo in questo file sul tuo computer, che non viene mai caricato
online da questo progetto.

## Passo 3 — Avvia Porvabet (ogni volta che lo usi)

Nella stessa cartella, in PowerShell:

```powershell
.\start.ps1
```

Questo script:
1. controlla che PostgreSQL sia acceso;
2. apre due nuove finestre (backend e frontend) — **lasciale aperte**,
   mostrano cosa succede "dietro le quinte"; chiuderle equivale a spegnere
   Porvabet;
3. scarica le partite reali della prossima giornata (Premier
   League/Serie A) da football-data.org, se hai messo la chiave;
4. apre il browser sulla pagina principale.

La prima volta la tabella potrebbe apparire vuota o con poche righe: clicca
il pulsante **"AGGIORNA ANALISI"** in alto per far calcolare le analisi
sulle partite appena scaricate (con Betfair configurato, questa volta le
quote reali dovrebbero comparire invece di "n/d" — è proprio questo il
test che stai facendo). Se non hai ancora scaricato lo storico
multi-stagione (Passo 2, punto 6), "AGGIORNA ANALISI" non produrrà
risultati — vedi "Problemi comuni" più sotto.

Per chiudere tutto: chiudi semplicemente le due finestre PowerShell aperte
da `start.ps1`.

## Cosa verificare, la prima volta che Betfair funziona davvero

Questa è la parte che la sandbox non ha mai potuto verificare da sola:

1. Apri una partita nella tabella (click sulla riga) e controlla che la
   colonna "Quota" mostri un numero reale con `Betfair (exchange, dati
   ritardati 1-180s)` invece di "n/d".
2. Prova un paio di partite diverse (Premier League e Serie A, alcune più
   vicine al kickoff, altre più lontane) — è normale che alcune abbiano
   quota e altre ancora "n/d" (Betfair non apre tutti i mercati subito).
3. Se vuoi anche indagare corner/cartellini (ancora "n/d" per tutti):
   ```powershell
   cd backend
   .venv\Scripts\python.exe scripts\discover_betfair_market_types.py
   ```
   Stampa l'elenco reale dei mercati che Betfair offre per ogni partita
   già scaricata, segnalando quelli che sembrano corner/cartellini — se ne
   trovi, riportameli (il testo esatto stampato) così posso collegarli.
4. Qualunque cosa trovi (quote presenti/assenti, mercati nuovi), dimmelo o
   annotalo in `DATA_SOURCES.md` — sostituendo le note "non verificato dal
   vivo" con quello che hai osservato davvero.

## Problemi comuni

**"impossibile caricare... perché l'esecuzione di script è disabilitata su
questo sistema"** — Esegui `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
in quella stessa finestra PowerShell, poi riprova il comando. Va rifatto a
ogni nuova finestra (non è permanente, per scelta — più sicuro).

**Una finestra (backend o frontend) si chiude subito da sola** — riapri
PowerShell, vai nella cartella (`cd C:\percorso\della\cartella`) e rilancia
`.\start.ps1`: questa volta l'errore resta visibile invece di sparire con
la finestra. Le cause più comuni sono elencate sotto.

**"la porta 8000 (o 3000) è già occupata"** — probabilmente Porvabet è già
in esecuzione da un avvio precedente (`start.ps1` se ne accorge da solo e
non ne apre un secondo). Se invece vuoi essere sicuro che non sia rimasto
nulla acceso, chiudi tutte le finestre PowerShell aperte in precedenza e
riprova.

**"password authentication failed for user postgres"** — hai scritto la
password di PostgreSQL sbagliata quando richiesta. Rilancia `.\setup.ps1` e
scrivila con attenzione (non si vede nulla mentre digiti in un prompt
password, è normale, non significa che non stia scrivendo).

**PostgreSQL non risponde / "connection refused"** — il servizio
PostgreSQL non è avviato. Premi il tasto Windows, scrivi "Servizi", apri
l'app "Servizi", cerca un servizio che inizia con `postgresql-x64-`,
verifica che sia "In esecuzione" (tasto destro → Avvia se non lo è).

**Versione Python sbagliata / "Python 3.11+ richiesto"** — hai una
versione di Python troppo vecchia (o `python` punta a Python 2, raro ma
possibile). Installa Python da <https://www.python.org/downloads/>
seguendo di nuovo il Passo 1, assicurandoti di spuntare "Add python.exe to
PATH", poi riapri PowerShell.

**"npm: comando non riconosciuto" oppure "python: comando non
riconosciuto"** — il programma non è nel PATH di Windows. Riapri
PowerShell (a volte basta), altrimenti reinstalla il programma mancante
controllando di spuntare l'opzione "aggiungi al PATH" durante
l'installazione.

**La pagina nel browser resta vuota anche dopo "AGGIORNA ANALISI"** —
apri la finestra del backend (quella con i log): se mostra un errore in
rosso, quello spiega cosa non ha funzionato. Due cause comuni:
1. **Errore che parla di partite passate/storico insufficiente
   ("need >= N matches", o simile)** — hai saltato il passo dello storico
   multi-stagione durante `setup.ps1` (Passo 2, punto 6): senza quello, il
   motore rifiuta correttamente di calcolare previsioni (serve un minimo di
   partite passate per stimare la forza delle squadre — non è un bug).
   Risolvi con, dalla cartella `backend` e con il venv attivo:
   ```powershell
   .venv\Scripts\python.exe scripts\ingest_football_data.py
   ```
   poi torna nel browser e clicca di nuovo "AGGIORNA ANALISI".
2. **Chiave football-data.org non valida, o nessuna partita futura
   scaricata** (l'errore lo nomina esplicitamente, es. "chiave non
   valida") — verifica che `FOOTBALL_DATA_ORG_API_KEY` sia compilata in
   `backend\.env` e rilancia `.\start.ps1`.

**Ho chiuso per sbaglio una finestra, e ora?** — nessun danno: rilancia
`.\start.ps1`, riapre solo quello che manca (non tocca ciò che è già
acceso).

## Per chi preferisce macOS/Linux

Sono disponibili `setup.sh`/`start.sh`, equivalenti a `setup.ps1`/`start.ps1`
ma per macOS/Linux (bash):

```bash
chmod +x setup.sh start.sh   # solo la prima volta
./setup.sh                   # una volta sola
./start.sh                   # ogni volta che vuoi avviare Porvabet
```

## Dopo la verifica

Se trovi differenze reali rispetto a quanto documentato in
`DATA_SOURCES.md` (es. corner/cartellini effettivamente presenti su Betfair
con un market type che non ci aspettavamo, o 1X2/O-U con liquidità diversa
da quanto stimato), aggiorna quel file con i numeri reali osservati — mai
lasciare una nota "non verificato" quando ormai lo è stata.
