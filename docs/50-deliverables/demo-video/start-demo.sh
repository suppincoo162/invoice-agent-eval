#!/usr/bin/env bash
# Demo environment for Linux / macOS: start the WebUI static server and print deep links.
# Usage: see start-demo.readme.md (Chinese docs).
#
#   bash docs/50-deliverables/demo-video/start-demo.sh
#   bash docs/50-deliverables/demo-video/start-demo.sh --no-browser
#   PORT=8080 bash docs/50-deliverables/demo-video/start-demo.sh
#
# NOTE: keep this file ASCII-only and bash-3.2 compatible (macOS ships bash 3.2).

set -eu

PORT="${PORT:-8000}"
NO_BROWSER=0
for arg in "$@"; do
    case "$arg" in
        --no-browser) NO_BROWSER=1 ;;
        --port=*)     PORT="${arg#--port=}" ;;
        -h|--help)
            echo "usage: $0 [--no-browser] [--port=N]"
            exit 0
            ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
WEBUI_DIR="$ROOT/outputs/webui"
BASE="http://127.0.0.1:$PORT"

if [ ! -f "$WEBUI_DIR/index.html" ]; then
    echo "[ERROR] $WEBUI_DIR/index.html not found." >&2
    echo "        Run: python3 -m invoice_eval webui ... (see README)" >&2
    exit 1
fi

# Python: prefer python3, fall back to python.
PY=""
if command -v python3 >/dev/null 2>&1; then PY="python3"
elif command -v python >/dev/null 2>&1; then PY="python"
else
    echo "[ERROR] python3/python not found in PATH." >&2
    exit 1
fi

PIDFILE="${TMPDIR:-/tmp}/invoice-eval-demo-${PORT}.pid"

http_up() {
    if command -v curl >/dev/null 2>&1; then
        curl -fsS -o /dev/null --max-time 1 "$BASE/index.html"
    else
        "$PY" - "$BASE/index.html" <<'PYEOF'
import sys, urllib.request
try:
    urllib.request.urlopen(sys.argv[1], timeout=2).read(1)
except Exception:
    sys.exit(1)
PYEOF
    fi
}

if http_up; then
    echo "[INFO] port $PORT already serving, reusing it."
else
    echo "[INFO] starting WebUI static server at $BASE (dir: outputs/webui) ..."
    # nohup + full detach so the server survives this script exiting.
    ( cd "$ROOT" && nohup "$PY" -m http.server "$PORT" --directory outputs/webui \
        >/dev/null 2>&1 </dev/null & echo $! > "$PIDFILE" ) || true
    i=0
    while [ "$i" -lt 60 ]; do
        sleep 0.25
        if http_up; then break; fi
        i=$((i + 1))
    done
    if ! http_up; then
        echo "[ERROR] server did not start within 15s." >&2
        exit 1
    fi
    echo "[INFO] server PID: $(cat "$PIDFILE" 2>/dev/null || echo unknown) (pidfile: $PIDFILE)"
fi

echo "[OK] server ready: $BASE"
echo ""
echo "Deep links for each scene (paste into the address bar while recording):"
echo "  S4  INV-V07 summary    $BASE/index.html#case=INV-V07&tab=summary"
echo "  S4  INV-V07 timeline   $BASE/index.html#case=INV-V07&tab=timeline"
echo "  S5  INV-V08 summary    $BASE/index.html#case=INV-V08&tab=summary"
echo "  S5  INV-V08 timeline   $BASE/index.html#case=INV-V08&tab=timeline"
echo "  S6  INV-V04 sources    $BASE/index.html#case=INV-V04&tab=sources"
echo "  S7  appendices dir     $BASE/appendices/"
echo ""
echo "Recording tips:"
echo "  - Browser fullscreen (F11 / Ctrl+Cmd+F); hide the bookmarks bar."
echo "  - Record at 1920x1080. Keep the topbar (version + commit) in frame."
echo "  - Stop server:  kill \$(cat \"$PIDFILE\")   # or: lsof -ti:$PORT | xargs kill"

if [ "$NO_BROWSER" -eq 0 ]; then
    URL="$BASE/index.html#case=INV-V07&tab=summary"
    if command -v open >/dev/null 2>&1; then
        open "$URL"                     # macOS
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$URL" >/dev/null 2>&1 || true   # Linux
    else
        echo "[WARN] no open/xdg-open found; open manually: $URL"
    fi
fi
