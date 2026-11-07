#!/usr/bin/env bash
# Run once, right after cloning. Creates your working files, then tells you exactly what is
# missing for which command and how to get it.
#
# Why this exists: everything it creates is gitignored, so it is YOURS. When an update ships
# you run `git pull` and it lands cleanly, because your files and the repo's files never touch
# the same paths. Nothing here talks to Upwork, and nothing here blocks: a missing tool costs
# you one command, not the package.
set -e
cd "$(dirname "$0")"

command -v python3 >/dev/null || { echo "python3 is missing. Install Python 3, then run this again."; exit 1; }

python3 code/workspace.py

[ -f .env ] || { cp .env.example .env; echo "created .env from the example."; }

# The commands read .env first and ~/.config/credentials.env after it, so a key kept
# centrally is a key the run will find. Checking only .env reported gaps that were not
# there, and a member who trusts that list buys a second key they already own.
env_has() {
  python3 - "$1" <<'PY'
import os
import pathlib
import sys
sys.path.insert(0, 'code')
from env_file import load_dotenv

env = dict(os.environ)
load_dotenv(pathlib.Path('.env'), env)
load_dotenv(pathlib.Path.home() / '.config' / 'credentials.env', env)
raise SystemExit(0 if str(env.get(sys.argv[1]) or '').strip() else 1)
PY
}
missing=0
note() { echo "  · $1"; missing=$((missing + 1)); }

echo
echo "What each command still needs from you:"

command -v node >/dev/null || note "node: the dashboard needs it. https://nodejs.org"

if ! python3 -c "import PIL" >/dev/null 2>&1; then
  note "Python packages: /proposal and /sales-call-proposal size their images with Pillow. Run 'python3 -m pip install -r requirements.txt'. If pip refuses because the system Python is managed, make a virtual environment first: 'python3 -m venv .venv && source .venv/bin/activate', then run setup.sh again."
fi

if ! command -v google-chrome >/dev/null && ! command -v chromium >/dev/null \
   && [ ! -d "/Applications/Google Chrome.app" ] && ! env_has CHROME_BIN; then
  note "Google Chrome: /sales-call-proposal draws its sketch and prints its PDF with it. Install it from google.com/chrome, or put the path in CHROME_BIN."
fi

if [ ! -d website/node_modules ] && command -v npm >/dev/null; then
  note "the dashboard installs its own packages the first time it starts, which takes a few minutes once. Run 'cd website && npm install' now if you would rather wait for it here."
fi

[ ! -f .claude/commands/sales-call-proposal.md ] || env_has KIE_AI_API_KEY || note "KIE_AI_API_KEY in .env: lets /sales-call-proposal draw the plan for the client's trade without leaving the terminal. kie.ai. Skip it if you already have an image model: /sales-call-proposal prints the prompt for you to paste anywhere, and the page picks the picture up from jobs/<id>/proposal-sketch.png whoever drew it."

[ "$missing" -eq 0 ] && echo "  nothing is missing. This checks that a key exists, never that it still
  has credit, and never which account a token belongs to."

echo
echo "Your context, data and job files are yours now; git will not touch them."
echo
echo "Upwork is next. Start claude here and it walks you through connecting it."
echo "(I'd tell you a joke about the connector, but it takes a few tries to get through.)"
echo
echo "Then /about-me. It reads this same list and tells you which of it you need"
echo "now and which can wait, then asks about your background. After that: /profile"
