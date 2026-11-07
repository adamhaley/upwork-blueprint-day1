#!/usr/bin/env python3
"""What this machine can do, and what each part of it buys.

    python3 code/tools_status.py [--json]

`setup.sh` prints what is missing. That answers "what do I install" and leaves
the other question open: a member looking at a gap cannot tell whether it stops
them today, next week or never. This prints every tool with the same three
facts, present or not, so the answer is visible without installing anything.

One entry is not measurable from here. Whether the Upwork connector is logged in
is visible to Claude, which sees its tools, and to nobody else, so it is listed
with the state `ask-claude` and /about-me fills it in.
"""
import argparse
import json
import os
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
from env_file import load_dotenv  # noqa: E402


def env_with_files():
    env = dict(os.environ)
    load_dotenv(ROOT / '.env', env)
    load_dotenv(pathlib.Path.home() / '.config' / 'credentials.env', env)
    return env


def has_key(env, *names):
    return any(str(env.get(name) or '').strip() for name in names)


def python_packages():
    """Pillow, the one package the image steps import."""
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return True


def chrome(env):
    named = env.get('CHROME_BIN')
    if named and pathlib.Path(named).is_file():
        return True
    if shutil.which('google-chrome') or shutil.which('chromium'):
        return True
    return pathlib.Path('/Applications/Google Chrome.app').is_dir()


def rows(env):
    """Every tool, in the order a member meets it."""
    return [
        ('Upwork connector', 'ask-claude', 'required',
         'reads your profile and the job market',
         '/profile, /find-jobs, /dashboard, /message', 'nothing replaces it, and only you can connect it'),
        ('Node.js', shutil.which('node') is not None, 'optional',
         'runs the cockpit',
         '/find-jobs, /dashboard', 'install from nodejs.org, or work from the chat'),
        ('Python packages', python_packages(), 'optional',
         'sizes the proposal sketch so the page stays one file',
         '/sales-call-proposal',
         'pip install -r requirements.txt. Without it the pages are built without those images'),
        ('Google Chrome', chrome(env), 'optional',
         'screenshots a page before you send it',
         '/sales-call-proposal', 'without it you check the page by eye'),
        ('kie.ai', has_key(env, 'KIE_AI_API_KEY'), 'optional',
         'draws the sketch on the proposal page',
         '/sales-call-proposal', 'without it the command prints the prompt for any image model you have'),
        ('Apify', has_key(env, 'APIFY_API_TOKEN'), 'optional',
         "pulls a client's Google reviews and live Meta ads, capped per pull",
         '/sales-call-prep', 'without it the brief names what those pulls would have shown'),
        ('PageSpeed key', has_key(env, 'PAGESPEED_API_KEY') or shutil.which('lighthouse') is not None, 'optional',
         "measures a client's mobile page speed",
         '/sales-call-prep', 'free from Google Cloud; without it or a local Lighthouse the speed stays unmeasured'),
    ]


def shipped(used):
    """Only the commands this copy has: a member copy cut for day 1 ships fewer."""
    have = {'/' + path.stem for path in (ROOT / '.claude' / 'commands').glob('*.md')}
    return ', '.join(command for command in used.split(', ') if command in have)


def state(value):
    if value == 'ask-claude':
        return 'ask-claude'
    return 'ready' if value else 'missing'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='machine-readable')
    args = parser.parse_args(argv)
    entries = [{'tool': name, 'state': state(ok), 'need': need, 'buys': buys,
                'used_by': shipped(used), 'without_it': without}
               for name, ok, need, buys, used, without in rows(env_with_files()) if shipped(used)]
    if args.json:
        print(json.dumps(entries, indent=2))
        return 0
    width = max(len(e['tool']) for e in entries)
    for e in entries:
        line = f"{e['state']:<10} {e['tool']:<{width}}  {e['buys']}  ({e['used_by']})"
        print(line if e['state'] == 'ready' else f"{line}\n{'':<10} {'':<{width}}  {e['without_it']}")
    missing = [e['tool'] for e in entries if e['state'] == 'missing']
    print(f"\n{len(entries) - len(missing) - 1} ready, {len(missing)} missing, "
          f"1 only Claude can see. Nothing here is required by /about-me.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
