#!/usr/bin/env bash
# Bootstrap for ytmusic-mcp:
#   1. Ensure Homebrew, Python 3.11+, and gh CLI are installed
#   2. Create a venv and install the package
#   3. Initialize a git repo and push to a new GitHub repo (public)
#   4. Register the MCP in Claude Desktop's config
#
# Idempotent: safe to re-run.

set -euo pipefail

# ---------- pretty output ----------
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
RED=$'\033[0;31m'
BLUE=$'\033[0;34m'
RESET=$'\033[0m'

info()  { printf "${BLUE}[i]${RESET} %s\n" "$*"; }
ok()    { printf "${GREEN}[✓]${RESET} %s\n" "$*"; }
warn()  { printf "${YELLOW}[!]${RESET} %s\n" "$*"; }
fail()  { printf "${RED}[✗]${RESET} %s\n" "$*" >&2; exit 1; }

# ---------- prelude ----------
[[ "$(uname)" == "Darwin" ]] || fail "This setup script targets macOS. Adapt as needed for other OS."

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"
info "Project directory: $PROJECT_DIR"

REPO_NAME="ytmusic-mcp"

# ---------- 1. Homebrew ----------
if ! command -v brew >/dev/null 2>&1; then
  warn "Homebrew not found. Installing — this will prompt for your password."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Make brew available in this session
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
else
  ok "Homebrew is installed."
fi

# ---------- 2. Python 3.11+ ----------
PY_BIN=""
for cand in python3.12 python3.11 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    ver="$("$cand" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo 0)"
    major="${ver%%.*}"
    minor="${ver##*.}"
    if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
      PY_BIN="$(command -v "$cand")"
      break
    fi
  fi
done

if [[ -z "$PY_BIN" ]]; then
  info "Installing Python 3.11 via Homebrew..."
  brew install python@3.11
  PY_BIN="$(brew --prefix)/bin/python3.11"
fi
ok "Using Python: $PY_BIN ($("$PY_BIN" --version))"

# ---------- 3. gh CLI ----------
if ! command -v gh >/dev/null 2>&1; then
  info "Installing GitHub CLI via Homebrew..."
  brew install gh
else
  ok "gh CLI is installed."
fi

if ! gh auth status >/dev/null 2>&1; then
  warn "gh is not authenticated."
  info "Running 'gh auth login' — choose GitHub.com → HTTPS → Login with browser."
  gh auth login
fi
ok "gh CLI is authenticated."

# ---------- 4. venv + install ----------
if [[ ! -d "$PROJECT_DIR/venv" ]]; then
  info "Creating virtual environment..."
  "$PY_BIN" -m venv "$PROJECT_DIR/venv"
fi
# shellcheck disable=SC1091
source "$PROJECT_DIR/venv/bin/activate"
pip install --quiet --upgrade pip
info "Installing dependencies (this can take a minute)..."
pip install --quiet -e .
ok "Package installed in editable mode."

# ---------- 5. git init + GitHub repo ----------
if [[ ! -d "$PROJECT_DIR/.git" ]]; then
  info "Initializing git repository..."
  git init -q -b main
  git add .
  git -c user.email="${USER}@local" -c user.name="${USER}" commit -q -m "Initial commit: ytmusic-mcp v0.1.0"
else
  ok "Git repo already initialized."
fi

# Check if remote exists
if ! git remote get-url origin >/dev/null 2>&1; then
  GH_USER="$(gh api user --jq .login)"
  info "Creating GitHub repo: $GH_USER/$REPO_NAME (public)..."
  if gh repo view "$GH_USER/$REPO_NAME" >/dev/null 2>&1; then
    warn "Repo $GH_USER/$REPO_NAME already exists. Linking remote and pushing."
    git remote add origin "https://github.com/$GH_USER/$REPO_NAME.git"
  else
    gh repo create "$REPO_NAME" --public \
      --description "YouTube Music MCP server: playlist management + smart recommendations" \
      --source="$PROJECT_DIR" --remote=origin
  fi
  git push -u origin main
  ok "Pushed to GitHub: https://github.com/$GH_USER/$REPO_NAME"
else
  info "Pushing latest changes..."
  if ! git diff --quiet HEAD 2>/dev/null; then
    git add -A
    git -c user.email="${USER}@local" -c user.name="${USER}" commit -q -m "Update" || true
  fi
  git push origin main || true
  ok "GitHub remote already set up."
fi

# ---------- 6. Register MCP in Claude Desktop config ----------
CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
if [[ ! -f "$CLAUDE_CONFIG" ]]; then
  warn "Claude Desktop config not found at: $CLAUDE_CONFIG"
  warn "Make sure Claude Desktop is installed and has been launched at least once."
else
  info "Updating Claude Desktop config..."
  "$PY_BIN" - <<PYEOF
import json
from pathlib import Path

cfg_path = Path("$CLAUDE_CONFIG")
data = {}
if cfg_path.exists() and cfg_path.stat().st_size > 0:
    data = json.loads(cfg_path.read_text(encoding="utf-8"))

data.setdefault("mcpServers", {})
data["mcpServers"]["YouTube Music"] = {
    "command": "$PROJECT_DIR/venv/bin/python",
    "args": ["-m", "ytmusic_mcp"]
}

cfg_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print("Wrote", cfg_path)
PYEOF
  ok "Claude Desktop config updated."
fi

# ---------- 7. final next steps ----------
echo
ok "Setup complete!"
echo
echo "Next steps:"
echo "  1. Open Chrome → https://music.youtube.com (make sure you're logged in)"
echo "  2. Open DevTools (Cmd+Opt+I) → Network tab"
echo "  3. Click any request to music.youtube.com"
echo "  4. Right-click → Copy → Copy request headers"
echo "  5. Run the auth setup:"
echo
echo "       cd \"$PROJECT_DIR\""
echo "       source venv/bin/activate"
echo "       ytmusic-mcp auth"
echo
echo "     (paste headers when prompted, finish with Ctrl+D)"
echo
echo "  6. Verify:    ytmusic-mcp status"
echo "  7. Restart Claude Desktop"
echo
echo "After restarting, you'll have a 'YouTube Music' MCP available in chats."
