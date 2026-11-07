# Upwork Blueprint

Win work on Upwork with Claude Code. Your profile, your job search, your applications and your pipeline, in one folder.

The full product goal and review standard are in [VISION.md](VISION.md).

## Quick start

Before you clone: `/about-me` runs on a Claude plan alone. Every Upwork command
needs the free Upwork connector. Details are in
[Requirements](#requirements) and [What it costs to run](#what-it-costs-to-run).

1. Clone it anywhere on your computer:
   `git clone https://github.com/automatable-skool/upwork-blueprint-day1.git`
2. Open a terminal in the folder and run `./setup.sh` once. It creates your own
   files and `.env`
3. Follow [Connect Upwork](#connect-upwork), then run `/about-me`. It asks about
   your background once; later commands write from those answers

Skipping setup still works: each command walks you through its missing tools.

## Connect Upwork

1. Start `claude` in this folder and approve the project's `upwork` MCP server
   when Claude Code asks (workspace trust).
2. Run `/mcp`, choose upwork and finish the login in the browser.
3. Quit Claude Code and start `claude` here once more before the first command.

The shared allow rules apply after you accept the workspace trust dialog.

What Claude Code reads during a command, including Upwork responses and your
`context/` files, is sent to Anthropic as part of the conversation, as in any
Claude Code session. `RESEARCH.md` is background reading; no command uses it.

## The path (run it in this order, it mirrors the course)

| Step | Command | What it does |
|------|---------|--------------|
| 1 | `/about-me` | Your work history, your offer, your terms and every result you can prove |
| 2 | `/profile` | Measures your live profile, then writes the version that fixes it |
| 3 | `/find-jobs` | Ten leads a day worth applying to, scored against what you sell, straight into your dashboard |
| 4 | `/proposal` | The cover letter, the bid and the video script, ready to submit with your Loom |
| 5 | `/dashboard` | Unlocks day 7. Your day: pulls what changed on Upwork, opens your dashboard with every lead and its next step, and drafts the messages that are due. Type it again to refresh |
| 6 | `/sales-call-prep` | Unlocks day 7. Before a sales call: one page to glance at during it, the seven stops in order with what to say at each, and a few facts about the business and the person |
| 7 | `/sales-call-proposal` | Unlocks day 7. Turns your sales call into the proposal you send, and says whether it is ready to start a project on |
| 8 | `/onboarding` | Unlocks month 2. Turns a started contract into a checklist page you run the kickoff call from, the message that books the call, and the client's own folder |
| Weekly | `/analytics` | Unlocks day 7. Finds the one step losing you deals, gives you the fix, and split tests it until a winner is clear |
| On demand | `/loom-review` | Reviews the Loom you sent with one application and gives you the one change that helps most |
| On demand | `/call-review` | Unlocks day 7. Reviews a finished sales call from its transcript and saves the feedback |

/about-me also works before connecting or creating a public Upwork profile. Run it
first: every later command writes from it, and `/find-jobs` on an empty `me.md`
has nothing to score leads against.

One command sits beside the path, and it unlocks day 7: `/message <client name>` finds that client's
conversation, reads it from the first message, and drafts your reply. Use it for a
single client at any time, including one who never came through `/find-jobs`.

A lead you
will not apply to leaves the list with `/find-jobs skip <job id> <reason>`, which
searches nothing, costs no Connects and keeps the reason the next search learns
from.

## Requirements

- macOS or Linux. On Windows, use WSL; native Windows is unsupported.
- [Claude Code](https://claude.com/claude-code) and an Upwork freelancer account
- Python 3.10 or newer: `python3 -m pip install -r requirements.txt`.
  If pip refuses because the system Python is managed,
  make a virtual environment first: `python3 -m venv .venv && source .venv/bin/activate`
  Activate it with `source .venv/bin/activate` in every new terminal before `claude`.
- [Node.js](https://nodejs.org) 20.19+ (20.x) or 22.12+ for the cockpit
- Google Chrome, which `/sales-call-proposal` uses to print the proposal as a PDF
- Optional: Claude's Google Drive and Gmail connectors. `/about-me` then looks there,
  and in your Documents, Downloads and Desktop, for old CVs, results and client
  messages on its own. Read only; Claude Code still asks before it opens a file
  outside this folder, and saying no just skips that source.

`./setup.sh` and `python3 code/tools_status.py` list what each command still needs.
Upwork commands need the connector. /about-me can start
before it is ready.

## What it costs to run

| Item | Cost |
|------|------|
| Claude Code | a paid Claude plan that includes Claude Code, or API billing |
| Upwork applications | About 70 Connects/day for ten applications; the actual job costs vary and /find-jobs counts them |
| Optional image API | Usage billed separately; paid images require your yes after the cost is shown |

The keys and bills are yours. `KIE_AI_API_KEY` generates images; you can instead
use an image model you already have. `/sales-call-prep` uses `APIFY_API_TOKEN` for review and
ad pulls (at most $0.50 and $0.10 each, only on your pick) and a free `PAGESPEED_API_KEY`.
Details are in `.env.example`.

## Updating

Run `git pull`, then `./setup.sh` again. Activate `.venv` first if you use it.

When the next lesson unlocks, it gives you a new link. Run `git remote set-url origin <that link>`, then `git pull` and `./setup.sh`. If git says the histories diverged, run `git fetch origin && git reset --hard origin/main`: it replaces only the repo's own files, and yours are gitignored.

## What appears in your folder

Everything below is yours and gitignored, so `git pull` never touches it.

- `context/me.md` - who you are and what you can back up
- `profile.md` - the profile to paste, written against what is live today
- `profile.html` - the same draft on the resume's sheet: what a client sees first, whether a client would choose it over the next nine, what is still to decide, and every field ready to copy with one click
- `data/jobs.json` - your pipeline, written only by `code/pipeline.py`
- `data/upwork-calls.jsonl` - the count behind the call cap: a time and a tool name per call, nothing from Upwork
- `jobs/<id>/` - one folder per job: the application,
  the call brief, the proposal, the threads and the drafts

Client folders default to `<repo parent>/clients/<slug>/`, a sibling outside this
repository. Set `**Clients folder:**` in `context/me.md` to use another root: `~`
expands to your home folder, and a relative path resolves against the repository's
parent. A path inside this repository is rejected so Upwork rules do not load in
client delivery sessions.

From month 2, `/onboarding` creates the client's own Claude Code project and git repository:
`CLAUDE.md`, which loads `context/client.md` with the client's facts; `context/`
with the sales files and `call-notes.md`; `output/` with `onboarding.md`;
`references/`, `.env`, and the `/pull-context` skill, which brings in anything new
about the client whenever you run it. It copies; the original `jobs/<id>/` folder
stays unchanged.
The client list reads these external folders and old `clients/<slug>/` folders
inside this repository, marked legacy.

## What this will never do

It never submits a proposal, never buys Connects, and never runs on its own in
the background. It prepares the application; you record the
Loom, paste its link and submit on Upwork yourself, because an application spends
Connects and is a bid.

A reply to a client is the one thing it can put into the thread for you, and only
one message at a time, with the full text in front of you and your yes on that
one message. No answer leaves the draft for you to send by hand, which is also
what happens if anything about the send looks wrong. The details are in
[references/upwork.md](references/upwork.md).

It cannot run away with your account either. Every Upwork call from any chat or
subagent in this folder is counted before it goes out, and refused past 30 a
minute or 500 in 24 hours. You can lower or raise both in `.env`, never past
Upwork's own published limits. What Upwork's terms require, rule by rule with its
source, is in [references/upwork-compliance.md](references/upwork-compliance.md),
and every command reads it first.

One question about this is open, and you should know it before you run
anything. Upwork's own connector guidance asks you to check with their support
before scoring results with a model and before storing connector output. This
Blueprint does both: `/find-jobs` scores postings, and `prune` expires cached
job fields in `data/jobs.json` after 24 hours and saved chats in
`jobs/<id>/thread.json` after 90 days, so your follow-ups and feedback can learn
from them. Upwork's published rule is 24 hours for all of it; to follow it to
the letter, set `KEEP_CHAT_HOURS=24` in `.env`. Nobody here has asked
Upwork yet. The reasoning and the source are in
[RESEARCH.md](RESEARCH.md#what-upwork-says-about-automation).

Stuck? Open an issue on the repository, or ask in the community you got this
from. Include what you ran and what it printed; both are usually enough.

Everything in here is the author's: it ships to members to use in their
own freelancing, not to republish or resell.
