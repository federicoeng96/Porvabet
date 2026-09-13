#!/usr/bin/env bash
# Porvabet - Setup iniziale per macOS/Linux
#
# Esegui questo script UNA SOLA VOLTA, la prima volta che prepari il progetto
# su questo computer. Dopo, per avviare il progetto ogni giorno, usa
# start.sh (molto piu' veloce, non rifa tutto da capo).
#
# Uso:
#   chmod +x setup.sh   # solo la prima volta
#   ./setup.sh
#
# Pensato per essere rieseguito piu' volte senza problemi (salta i passi
# gia' fatti, non rompe nulla se lo rilanci dopo un errore).

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

step() { echo; echo -e "\033[36m==> $1\033[0m"; }
ok()   { echo -e "    \033[32mOK: $1\033[0m"; }
warn() { echo -e "    \033[33mATTENZIONE: $1\033[0m"; }
fail() { echo -e "    \033[31mERRORE: $1\033[0m"; }

echo "=================================================="
echo " Porvabet - Setup iniziale"
echo "=================================================="

# --- 1. Prerequisiti ---------------------------------------------------
step "Controllo prerequisiti (Python, Node.js, PostgreSQL)"

PYTHON_CMD=""
for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        ver="$("$candidate" --version 2>&1)"
        # `|| true` sulla pipeline: se "--version" non stampasse un numero
        # riconoscibile (caso limite, mai osservato con un python3 reale),
        # `grep -oE` senza corrispondenze uscirebbe con stato 1 e, con
        # "pipefail" attivo, farebbe terminare l'intero script qui - stesso
        # tipo di bug gia' trovato e corretto sopra per psql, individuato
        # rileggendo questo file con lo stesso occhio critico.
        major="$(echo "$ver" | grep -oE '[0-9]+' | sed -n 1p || true)"
        minor="$(echo "$ver" | grep -oE '[0-9]+' | sed -n 2p || true)"
        if [ "${major:-0}" -gt 3 ] 2>/dev/null || { [ "${major:-0}" -eq 3 ] 2>/dev/null && [ "${minor:-0}" -ge 11 ] 2>/dev/null; }; then
            PYTHON_CMD="$candidate"
            ok "Python trovato: $ver ($candidate)"
            break
        fi
    fi
done
if [ -z "$PYTHON_CMD" ]; then
    fail "Python 3.11+ non trovato."
    echo "    Installalo (macOS: 'brew install python@3.11', Linux: dal gestore pacchetti"
    echo "    della tua distribuzione), poi rilancia questo script."
    exit 1
fi

if ! command -v node >/dev/null 2>&1; then
    fail "Node.js non trovato."
    echo "    Scaricalo da https://nodejs.org/ (versione LTS, 20 o piu' recente)."
    exit 1
else
    node_ver="$(node --version | tr -d 'v')"
    node_major="${node_ver%%.*}"
    if [ "$node_major" -lt 20 ]; then
        warn "Node.js $node_ver trovato, ma questo progetto e' stato testato con Node 20+."
    else
        ok "Node.js trovato: v$node_ver"
    fi
fi

if ! command -v psql >/dev/null 2>&1; then
    fail "PostgreSQL (comando 'psql') non trovato."
    echo "    macOS: 'brew install postgresql@16 && brew services start postgresql@16'"
    echo "    Linux: installa 'postgresql' dal gestore pacchetti della tua distribuzione."
    exit 1
else
    ok "PostgreSQL (psql) trovato."
fi

# --- 2. Ambiente virtuale Python + dipendenze backend -------------------
step "Preparazione ambiente Python (backend)"
cd "$ROOT/backend"

if [ ! -d ".venv" ]; then
    echo "    Creo l'ambiente virtuale Python in backend/.venv ..."
    "$PYTHON_CMD" -m venv .venv
else
    ok "Ambiente virtuale gia' presente (backend/.venv)."
fi

echo "    Installo le dipendenze Python (puo' richiedere qualche minuto la prima volta)..."
.venv/bin/python -m pip install --upgrade pip --quiet
.venv/bin/python -m pip install -e ".[dev]" --quiet
ok "Dipendenze Python installate."

# --- 3. Database PostgreSQL ---------------------------------------------
step "Preparazione database PostgreSQL"
echo "    Se richiesto, potresti dover autenticarti come utente 'postgres' del sistema."
echo

# Un solo script SQL invece di 3 comandi CREATE separati: controlla prima se
# ruolo/database esistono gia' (query di sistema, mai testo d'errore) e crea
# solo quello che manca. Il vecchio approccio cercava la frase inglese
# "already exists" nell'output di psql, ma PostgreSQL traduce i suoi
# messaggi nella lingua di sistema — su un sistema in italiano il messaggio
# reale e' diverso, quindi il controllo falliva silenziosamente e lo script
# si fermava con un errore anche quando non c'era nulla di rotto.
DB_SETUP_SQL="$(mktemp)"
cat > "$DB_SETUP_SQL" <<'EOF'
DO $do$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'porvabet') THEN
      CREATE ROLE porvabet WITH LOGIN PASSWORD 'porvabet_dev' SUPERUSER;
   END IF;
END
$do$;

SELECT 'CREATE DATABASE porvabet OWNER porvabet' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'porvabet')
\gexec

SELECT 'CREATE DATABASE porvabet_test OWNER porvabet' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'porvabet_test')
\gexec
EOF

# set +e/-e attorno alla chiamata: con "set -e" attivo, un'assegnazione
# semplice come `VAR="$(comando_che_fallisce)"` termina lo script
# immediatamente (comportamento reale di bash, verificato) - qui invece
# serve catturare l'output ANCHE quando psql fallisce, per mostrare un
# messaggio d'errore chiaro invece di un'uscita silenziosa.
set +e
PSQL_OUTPUT="$(psql -U postgres -h localhost -f "$DB_SETUP_SQL" 2>&1)"
DB_OK=$?
set -e
rm -f "$DB_SETUP_SQL"

if [ "$DB_OK" -ne 0 ]; then
    fail "Preparazione database non completata — vedi i messaggi sopra."
    echo "    Dettaglio: $PSQL_OUTPUT"
    echo "    Errore comune: se 'psql -U postgres' chiede una password che non conosci, prova"
    echo "    'sudo -u postgres psql' al posto di 'psql -U postgres' (comune su Linux)."
    exit 1
else
    ok "Database pronti (porvabet, porvabet_test) - creati se mancanti, lasciati invariati se gia' presenti."
fi

# --- 4. File .env --------------------------------------------------------
step "Configurazione backend/.env"
ENV_PATH="$ROOT/backend/.env"
if [ ! -f "$ENV_PATH" ]; then
    cp "$ROOT/backend/.env.example" "$ENV_PATH"
    warn "Creato backend/.env da .env.example."
    echo "    Apri backend/.env con un editor di testo e compila (o lascia vuote per ora)"
    echo "    le chiavi Betfair/football-data.org. DATABASE_URL e' gia' corretto, non toccarlo."
    echo
    read -rp "    Premi INVIO qui quando hai finito (o subito, per farlo dopo)..." _
else
    ok "backend/.env gia' presente — non lo tocco (per non perdere le tue chiavi)."
fi

# --- 5. Migrazioni database ----------------------------------------------
step "Applico le migrazioni del database (creazione tabelle)"
.venv/bin/python -m alembic upgrade head
ok "Tabelle create/aggiornate."

# --- 6. Frontend ----------------------------------------------------------
step "Preparazione frontend (Node.js)"
cd "$ROOT/frontend"

ENV_LOCAL_PATH="$ROOT/frontend/.env.local"
if [ ! -f "$ENV_LOCAL_PATH" ]; then
    cp "$ROOT/frontend/.env.local.example" "$ENV_LOCAL_PATH"
    ok "Creato frontend/.env.local (punta al backend locale, nessuna modifica necessaria)."
else
    ok "frontend/.env.local gia' presente."
fi

echo "    Installo le dipendenze del frontend (puo' richiedere qualche minuto)..."
npm install --silent
ok "Dipendenze frontend installate."

cd "$ROOT"

echo
echo "=================================================="
echo -e " \033[32mSetup completato.\033[0m"
echo "=================================================="
echo
echo "Per avviare il progetto (ogni volta, d'ora in poi), esegui:"
echo -e "    \033[36m./start.sh\033[0m"
echo
