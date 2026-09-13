# Porvabet - Setup iniziale per Windows (PowerShell)
#
# Esegui questo script UNA SOLA VOLTA, la prima volta che prepari il progetto
# su questo computer. Dopo, per avviare il progetto ogni giorno, usa
# start.ps1 (molto piu' veloce, non rifa tutto da capo).
#
# Come eseguirlo:
#   1. Apri PowerShell nella cartella di Porvabet (tasto destro nella
#      cartella -> "Apri in Terminale" oppure "Apri finestra PowerShell qui").
#   2. Se è la prima volta che esegui uno script PowerShell su questo PC,
#      esegui prima questo comando (autorizza SOLO questa finestra, non
#      cambia impostazioni permanenti del PC):
#        Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   3. Poi esegui:
#        .\setup.ps1
#
# Questo script e' pensato per essere eseguito piu' volte senza problemi
# (non rompe nulla se lo rilanci dopo un errore, salta i passi gia' fatti).

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Write-Ok($msg) {
    Write-Host "    OK: $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    Write-Host "    ATTENZIONE: $msg" -ForegroundColor Yellow
}

function Write-Fail($msg) {
    Write-Host "    ERRORE: $msg" -ForegroundColor Red
}

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

Write-Host "=================================================="
Write-Host " Porvabet - Setup iniziale"
Write-Host "=================================================="

# --- 1. Prerequisiti ---------------------------------------------------
Write-Step "Controllo prerequisiti (Python, Node.js, PostgreSQL)"

$pythonCmd = $null
foreach ($candidate in @("python", "py")) {
    if (Test-Command $candidate) {
        $verOutput = & $candidate --version 2>&1
        if ($verOutput -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]; $minor = [int]$Matches[2]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 11)) {
                $pythonCmd = $candidate
                Write-Ok "Python trovato: $verOutput ($candidate)"
                break
            } else {
                Write-Warn "$candidate e' $verOutput, ma serve Python 3.11 o superiore."
            }
        }
    }
}
if (-not $pythonCmd) {
    Write-Fail "Python 3.11+ non trovato."
    Write-Host "    Scaricalo da https://www.python.org/downloads/ (durante l'installazione,"
    Write-Host "    spunta 'Add python.exe to PATH'), poi riavvia PowerShell e rilancia questo script."
    exit 1
}

if (-not (Test-Command "node")) {
    Write-Fail "Node.js non trovato."
    Write-Host "    Scaricalo da https://nodejs.org/ (versione LTS, va bene qualunque versione 20 o piu' recente),"
    Write-Host "    poi riavvia PowerShell e rilancia questo script."
    exit 1
} else {
    $nodeVer = (node --version) -replace "v", ""
    $nodeMajor = [int]($nodeVer.Split(".")[0])
    if ($nodeMajor -lt 20) {
        Write-Warn "Node.js $nodeVer trovato, ma questo progetto e' stato testato con Node 20+. Puo' comunque funzionare."
    } else {
        Write-Ok "Node.js trovato: v$nodeVer"
    }
}

$psqlFound = Test-Command "psql"
if (-not $psqlFound) {
    Write-Fail "PostgreSQL (comando 'psql') non trovato nel PATH."
    Write-Host "    Se non hai ancora installato PostgreSQL: scaricalo da"
    Write-Host "    https://www.postgresql.org/download/windows/ (versione 16), durante"
    Write-Host "    l'installazione ricorda la password che scegli per l'utente 'postgres'."
    Write-Host "    Se lo hai gia' installato ma 'psql' non si trova, aggiungi al PATH la cartella"
    Write-Host "    tipo 'C:\Program Files\PostgreSQL\16\bin' (Impostazioni di sistema -> Variabili"
    Write-Host "    d'ambiente -> Path), poi riavvia PowerShell e rilancia questo script."
    exit 1
} else {
    Write-Ok "PostgreSQL (psql) trovato nel PATH."
}

# --- 2. Ambiente virtuale Python + dipendenze backend -------------------
Write-Step "Preparazione ambiente Python (backend)"
Set-Location "$root\backend"

if (-not (Test-Path ".venv")) {
    Write-Host "    Creo l'ambiente virtuale Python in backend\.venv ..."
    & $pythonCmd -m venv .venv
} else {
    Write-Ok "Ambiente virtuale gia' presente (backend\.venv)."
}

$venvPython = "$root\backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Fail "Creazione dell'ambiente virtuale fallita: $venvPython non trovato."
    exit 1
}

Write-Host "    Installo le dipendenze Python (puo' richiedere qualche minuto la prima volta)..."
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -e ".[dev]" --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Installazione delle dipendenze Python fallita — vedi l'errore sopra (spesso una connessione internet instabile: riprova)."
    exit 1
}
Write-Ok "Dipendenze Python installate."

# --- 3. Database PostgreSQL ---------------------------------------------
Write-Step "Preparazione database PostgreSQL"
Write-Host "    Ora verranno creati l'utente e i database 'porvabet'/'porvabet_test'."
Write-Host "    Se richiesto, inserisci la password dell'utente PostgreSQL 'postgres'"
Write-Host "    (quella scelta durante l'installazione di PostgreSQL)."
Write-Host ""

function Invoke-PsqlAdmin($sql) {
    # Restituisce $true se il comando è andato a buon fine O se l'oggetto esisteva
    # già (postgres risponde con un errore "already exists", che qui è normale e
    # non un fallimento — questo script è pensato per essere rieseguito).
    $output = & psql -U postgres -h localhost -c $sql 2>&1
    $ok = ($LASTEXITCODE -eq 0) -or ($output -match "already exists")
    if (-not $ok) {
        Write-Warn "Comando psql non riuscito: $sql"
        Write-Host "    Dettaglio: $output"
    }
    return $ok
}

$dbOk = $true
$dbOk = (Invoke-PsqlAdmin "CREATE USER porvabet WITH PASSWORD 'porvabet_dev' SUPERUSER;") -and $dbOk
$dbOk = (Invoke-PsqlAdmin "CREATE DATABASE porvabet OWNER porvabet;") -and $dbOk
$dbOk = (Invoke-PsqlAdmin "CREATE DATABASE porvabet_test OWNER porvabet;") -and $dbOk

if (-not $dbOk) {
    Write-Fail "Preparazione database non completata — vedi i messaggi sopra."
    Write-Host "    Errore comune: 'password authentication failed for user postgres' significa"
    Write-Host "    che la password inserita non e' quella giusta per l'utente postgres — riprova."
    Write-Host "    Errore comune: 'connection refused' o 'server non risponde' significa che il"
    Write-Host "    servizio PostgreSQL non e' avviato — apri 'Servizi' di Windows (cerca 'Servizi'"
    Write-Host "    nel menu Start), trova un servizio che inizia con 'postgresql-x64-', e verifica"
    Write-Host "    che sia 'In esecuzione' (se non lo e', tasto destro -> Avvia)."
    exit 1
} else {
    Write-Ok "Database pronti (porvabet, porvabet_test)."
}

# --- 4. File .env --------------------------------------------------------
Write-Step "Configurazione backend\.env"
$envPath = "$root\backend\.env"
if (-not (Test-Path $envPath)) {
    Copy-Item "$root\backend\.env.example" $envPath
    Write-Warn "Creato backend\.env da .env.example — ora si aprira' con Blocco Note."
    Write-Host "    Compila (o lascia vuote per ora) le chiavi Betfair/football-data.org."
    Write-Host "    DATABASE_URL e' gia' corretto per il database appena creato, non toccarlo."
    Write-Host ""
    Start-Process notepad.exe $envPath
    Read-Host "    Premi INVIO qui nel terminale quando hai salvato e chiuso Blocco Note" | Out-Null
} else {
    Write-Ok "backend\.env gia' presente — non lo tocco (per non perdere le tue chiavi)."
}

# --- 5. Migrazioni database ----------------------------------------------
Write-Step "Applico le migrazioni del database (creazione tabelle)"
& $venvPython -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Fail "alembic upgrade head fallito — vedi l'errore sopra."
    Write-Host "    Errore comune: se DATABASE_URL in backend\.env punta a un database diverso da"
    Write-Host "    quello appena creato, correggilo e rilancia questo script."
    exit 1
}
Write-Ok "Tabelle create/aggiornate."

# --- 6. Frontend ----------------------------------------------------------
Write-Step "Preparazione frontend (Node.js)"
Set-Location "$root\frontend"

$envLocalPath = "$root\frontend\.env.local"
if (-not (Test-Path $envLocalPath)) {
    Copy-Item "$root\frontend\.env.local.example" $envLocalPath
    Write-Ok "Creato frontend\.env.local (punta al backend locale, nessuna modifica necessaria)."
} else {
    Write-Ok "frontend\.env.local gia' presente."
}

Write-Host "    Installo le dipendenze del frontend (puo' richiedere qualche minuto)..."
npm install --silent
if ($LASTEXITCODE -ne 0) {
    Write-Fail "npm install fallito — vedi l'errore sopra (spesso una connessione internet instabile: riprova)."
    exit 1
}
Write-Ok "Dipendenze frontend installate."

Set-Location $root

Write-Host ""
Write-Host "=================================================="
Write-Host " Setup completato." -ForegroundColor Green
Write-Host "=================================================="
Write-Host ""
Write-Host "Se non hai ancora compilato backend\.env con le tue chiavi Betfair/"
Write-Host "football-data.org, puoi farlo ora (apri il file con Blocco Note) — o lasciarlo"
Write-Host "vuoto e farlo dopo, il progetto degrada semplicemente mostrando 'n/d' finche'"
Write-Host "quelle chiavi non ci sono."
Write-Host ""
Write-Host "Per avviare il progetto (ogni volta, d'ora in poi), esegui:"
Write-Host "    .\start.ps1" -ForegroundColor Cyan
Write-Host ""
