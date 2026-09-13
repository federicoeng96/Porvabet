# Porvabet - Avvio (Windows / PowerShell)
#
# Usa questo script OGNI VOLTA che vuoi avviare Porvabet, dopo aver gia'
# eseguito setup.ps1 almeno una volta.
#
# Come eseguirlo: apri PowerShell nella cartella di Porvabet e lancia
#     .\start.ps1
#
# Cosa fa:
#   1. Controlla che PostgreSQL sia raggiungibile.
#   2. Avvia il backend (FastAPI) in una nuova finestra.
#   3. Avvia il frontend (Next.js) in un'altra nuova finestra.
#   4. Appena entrambi sono pronti, scarica le partite reali della prossima
#      giornata (Premier League/Serie A) da football-data.org, se la chiave
#      e' configurata.
#   5. Apre il browser sulla pagina principale.
#
# Le due finestre che si aprono (backend/frontend) restano aperte con i log:
# NON chiuderle mentre usi l'app. Per fermare tutto, chiudi semplicemente
# quelle due finestre (o premi Ctrl+C dentro ciascuna).

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}
function Write-Ok($msg) { Write-Host "    OK: $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    ATTENZIONE: $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "    ERRORE: $msg" -ForegroundColor Red }

$venvPython = "$root\backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Fail "Non trovo backend\.venv - esegui prima .\setup.ps1"
    exit 1
}
if (-not (Test-Path "$root\backend\.env")) {
    Write-Fail "Non trovo backend\.env - esegui prima .\setup.ps1"
    exit 1
}

function Test-Port($portNumber) {
    $conn = Test-NetConnection -ComputerName "127.0.0.1" -Port $portNumber -WarningAction SilentlyContinue
    return $conn.TcpTestSucceeded
}

function Wait-ForPort($portNumber, $label, $timeoutSeconds = 60) {
    $elapsed = 0
    while (-not (Test-Port $portNumber)) {
        Start-Sleep -Seconds 2
        $elapsed += 2
        if ($elapsed -ge $timeoutSeconds) {
            Write-Fail "$label non risponde dopo $timeoutSeconds secondi sulla porta $portNumber."
            return $false
        }
    }
    return $true
}

# --- 1. PostgreSQL --------------------------------------------------------
Write-Step "Verifico che PostgreSQL sia raggiungibile"
if (Test-Port 5432) {
    Write-Ok "PostgreSQL risponde sulla porta 5432."
} else {
    Write-Fail "PostgreSQL non risponde sulla porta 5432."
    Write-Host "    Apri 'Servizi' di Windows (cerca 'Servizi' nel menu Start), trova il"
    Write-Host "    servizio che inizia con 'postgresql-x64-' e verifica che sia 'In esecuzione'"
    Write-Host "    (se non lo e', tasto destro -> Avvia), poi rilancia questo script."
    exit 1
}

# --- 2. Backend ------------------------------------------------------------
Write-Step "Avvio il backend (FastAPI)"
if (Test-Port 8000) {
    Write-Warn "La porta 8000 e' gia' occupata - presumo che il backend sia gia' avviato da una finestra precedente, non ne apro un'altra."
    Write-Host "    Se invece la porta 8000 e' usata da un altro programma, chiudilo e rilancia questo script."
} else {
    # Nota: si invoca direttamente l'eseguibile python del venv (non si "attiva"
    # il venv con Activate.ps1) apposta - Activate.ps1 e' anch'esso uno script
    # PowerShell e potrebbe essere bloccato dalla policy di esecuzione di questa
    # nuova finestra, anche se questo script e' stato sbloccato per la finestra
    # corrente. Chiamare python.exe direttamente evita del tutto il problema.
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "cd '$root\backend'; & '.venv\Scripts\python.exe' -m uvicorn app.main:app --reload --port 8000"
    )
    Write-Host "    Finestra del backend aperta. Attendo che sia pronto..."
    if (-not (Wait-ForPort 8000 "Backend")) {
        Write-Host "    Guarda la finestra del backend appena aperta per l'errore esatto."
        Write-Host "    Causa comune: DATABASE_URL sbagliato in backend\.env, o le migrazioni"
        Write-Host "    non ancora applicate (rilancia .\setup.ps1)."
        exit 1
    }
    Write-Ok "Backend pronto su http://localhost:8000"
}

# --- 3. Frontend -------------------------------------------------------------
Write-Step "Avvio il frontend (Next.js)"
if (Test-Port 3000) {
    Write-Warn "La porta 3000 e' gia' occupata - presumo che il frontend sia gia' avviato da una finestra precedente, non ne apro un'altra."
} else {
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "cd '$root\frontend'; npm run dev"
    )
    Write-Host "    Finestra del frontend aperta. Attendo che sia pronto..."
    if (-not (Wait-ForPort 3000 "Frontend")) {
        Write-Host "    Guarda la finestra del frontend appena aperta per l'errore esatto."
        Write-Host "    Causa comune: 'npm install' non ancora eseguito (rilancia .\setup.ps1)."
        exit 1
    }
    Write-Ok "Frontend pronto su http://localhost:3000"
}

# --- 4. Ingestione fixture reali ---------------------------------------------
Write-Step "Scarico le partite reali della prossima giornata (Premier League/Serie A)"
$envContent = Get-Content "$root\backend\.env" -Raw
$hasFootballKey = ($envContent -match "FOOTBALL_DATA_ORG_API_KEY\s*=\s*\S") -or ($envContent -match "FOOTBALL_DATA_API_KEY\s*=\s*\S")
if (-not $hasFootballKey) {
    Write-Warn "Nessuna chiave football-data.org configurata in backend\.env - salto questo passo."
    Write-Host "    La tabella si apre comunque, ma potrebbe essere vuota o mostrare solo dati"
    Write-Host "    gia' presenti nel database. Registrati gratis su football-data.org, aggiungi"
    Write-Host "    FOOTBALL_DATA_ORG_API_KEY a backend\.env, poi rilancia questo script."
} else {
    Push-Location "$root\backend"
    & $venvPython scripts\ingest_upcoming_fixtures.py --competitions EPL SERIE_A
    Pop-Location
}

# --- 5. Apri il browser -------------------------------------------------------
Write-Step "Apro il browser"
Start-Process "http://localhost:3000"
Write-Ok "Fatto - se la pagina e' vuota, clicca 'AGGIORNA ANALISI' per calcolare le analisi delle partite appena scaricate."

Write-Host ""
Write-Host "=================================================="
Write-Host " Porvabet e' in esecuzione." -ForegroundColor Green
Write-Host "=================================================="
Write-Host "Backend:  http://localhost:8000/docs"
Write-Host "Frontend: http://localhost:3000"
Write-Host ""
Write-Host "Le due finestre PowerShell appena aperte mostrano i log in diretta - lasciale"
Write-Host "aperte finche' usi l'app. Per fermare tutto, chiudile (o Ctrl+C dentro ciascuna)."
