#!/usr/bin/env bash
# Porvabet - Avvio (macOS/Linux)
#
# Usa questo script OGNI VOLTA che vuoi avviare Porvabet, dopo aver gia'
# eseguito setup.sh almeno una volta.
#
# Uso:
#   chmod +x start.sh   # solo la prima volta
#   ./start.sh
#
# Le due finestre di terminale che si aprono (backend/frontend) restano
# aperte con i log: NON chiuderle mentre usi l'app. Per fermare tutto,
# chiudi quelle due finestre (o premi Ctrl+C dentro ciascuna).

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

step() { echo; echo -e "\033[36m==> $1\033[0m"; }
ok()   { echo -e "    \033[32mOK: $1\033[0m"; }
warn() { echo -e "    \033[33mATTENZIONE: $1\033[0m"; }
fail() { echo -e "    \033[31mERRORE: $1\033[0m"; }

if [ ! -x "$ROOT/backend/.venv/bin/python" ]; then
    fail "Non trovo backend/.venv — esegui prima ./setup.sh"
    exit 1
fi
if [ ! -f "$ROOT/backend/.env" ]; then
    fail "Non trovo backend/.env — esegui prima ./setup.sh"
    exit 1
fi

port_open() {
    (echo > "/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1
}

wait_for_port() {
    local port="$1" label="$2" timeout="${3:-60}" waited=0
    while ! port_open "$port"; do
        sleep 2
        waited=$((waited + 2))
        if [ "$waited" -ge "$timeout" ]; then
            fail "$label non risponde dopo $timeout secondi sulla porta $port."
            return 1
        fi
    done
    return 0
}

open_terminal_window() {
    # Prova macOS (Terminal.app via osascript) poi le opzioni Linux piu' comuni.
    local title="$1" cmd="$2"
    if command -v osascript >/dev/null 2>&1; then
        osascript -e "tell application \"Terminal\" to do script \"$cmd\"" >/dev/null
    elif command -v gnome-terminal >/dev/null 2>&1; then
        gnome-terminal --title="$title" -- bash -c "$cmd; exec bash"
    elif command -v xterm >/dev/null 2>&1; then
        xterm -T "$title" -e bash -c "$cmd; exec bash" &
    else
        warn "Non trovo un terminale grafico noto — avvio $title in background in questa stessa finestra (log in /tmp)."
        bash -c "$cmd" >"/tmp/porvabet_${title// /_}.log" 2>&1 &
    fi
}

# --- 1. PostgreSQL --------------------------------------------------------
step "Verifico che PostgreSQL sia raggiungibile"
if port_open 5432; then
    ok "PostgreSQL risponde sulla porta 5432."
else
    fail "PostgreSQL non risponde sulla porta 5432."
    echo "    macOS: 'brew services start postgresql@16'"
    echo "    Linux: 'sudo systemctl start postgresql' (o 'sudo pg_ctlcluster 16 main start')"
    exit 1
fi

# --- 2. Backend ------------------------------------------------------------
step "Avvio il backend (FastAPI)"
if port_open 8000; then
    warn "La porta 8000 e' gia' occupata — presumo che il backend sia gia' avviato, non ne apro un altro."
else
    open_terminal_window "Porvabet backend" "cd '$ROOT/backend' && .venv/bin/uvicorn app.main:app --reload --port 8000"
    echo "    Finestra del backend aperta. Attendo che sia pronto..."
    if ! wait_for_port 8000 "Backend"; then
        echo "    Guarda la finestra/il log del backend per l'errore esatto."
        exit 1
    fi
    ok "Backend pronto su http://localhost:8000"
fi

# --- 3. Frontend -------------------------------------------------------------
step "Avvio il frontend (Next.js)"
if port_open 3000; then
    warn "La porta 3000 e' gia' occupata — presumo che il frontend sia gia' avviato, non ne apro un altro."
else
    open_terminal_window "Porvabet frontend" "cd '$ROOT/frontend' && npm run dev"
    echo "    Finestra del frontend aperta. Attendo che sia pronto..."
    if ! wait_for_port 3000 "Frontend"; then
        echo "    Guarda la finestra/il log del frontend per l'errore esatto."
        exit 1
    fi
    ok "Frontend pronto su http://localhost:3000"
fi

# --- 4. Ingestione fixture reali ---------------------------------------------
step "Scarico le partite reali della prossima giornata (Premier League/Serie A)"
if grep -qE "FOOTBALL_DATA_ORG_API_KEY\s*=\s*\S|FOOTBALL_DATA_API_KEY\s*=\s*\S" "$ROOT/backend/.env"; then
    (cd "$ROOT/backend" && .venv/bin/python scripts/ingest_upcoming_fixtures.py --competitions EPL SERIE_A)
else
    warn "Nessuna chiave football-data.org configurata in backend/.env — salto questo passo."
fi

# --- 5. Apri il browser -------------------------------------------------------
step "Apro il browser"
if command -v open >/dev/null 2>&1; then
    open "http://localhost:3000"
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://localhost:3000"
else
    warn "Apri manualmente http://localhost:3000 nel browser."
fi

echo
echo "=================================================="
echo -e " \033[32mPorvabet e' in esecuzione.\033[0m"
echo "=================================================="
echo "Backend:  http://localhost:8000/docs"
echo "Frontend: http://localhost:3000"
