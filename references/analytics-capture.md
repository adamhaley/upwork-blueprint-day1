# Analytics capture in other commands

## ROADMAP

Claude follows the matching hook below during the caller's existing workflow.
Show the caller's duration, decisions and possible source gaps before tools.
Wait at its member gates; these capture steps govern the matching actions.

## Shared rules

Use `references/copy.md` and the member's `context/me.md`. Judge applications,
conversations, calls and proposals with `references/coach-brief.md`; support each
claim with a quote or number and separate observation from interpretation.
Code computes numbers. Code and its errors define payloads and checks.

Missing or unreadable means unknown. In “What I couldn't check”, name the
source, blocked result and exact supply route. Request other missing inputs at
their exact local path or as readable pasted text; restore missing scripts and
references from the repository. Continue supported work only.

Write pipeline state through `python3 code/pipeline.py record <id> --file -`
or the specific writer below. Award lines the writers return are not shown to the
member; badges are hidden. A successful data write remains successful.
Follow CLAUDE.md's completion report, under 90 words, and count actual Upwork
calls, including failures and shortcuts.

For quest proof in /dashboard, /message, /proposal and /sales-call-proposal, read the latest
agreed `data/goals.jsonl` and copy its exact `goal_id` from cockpit or analytics
quests. Record only a saved message, submitted copy or exact member-confirmed action:

```sh
python3 code/pipeline.py note <id> 'analytics goal_action: {"goal_id":"<exact quest goal_id>","kpi":"<key>","at":"<zoned ISO time>","evidence":"<source or verbatim action proof>"}'
```

Include message ID/date/excerpt or submitted source and confirmation time. An outcome or generic self-report proves no action.

**Split test.** Before writing the piece a running test covers, run
`python3 code/split_test.py assign <id> --stage <stage>` and write it to the variant it
prints: `proposal` in /proposal, `messages` for a reply or follow-up in /dashboard and
/message, `call` in /sales-call-prep, `after-call` then `close` in /sales-call-proposal.
"No split test running" means write as usual. A follow-up rhythm test needs nothing:
`pipeline.py follow-up plan` gives each quiet lead its side's days. Read `## Split test winners` in
`context/me.md` as the member's default ([split tests](split-tests.md)).

## About me

1. Claude runs the existing interview and its project-results ladder. Ask
   checkboxes for money, time, volume, scale or the client's words; ask whether
   the highest selected category has a number, an estimate or none, then obtain
   the figure or inputs and period. Confirm found facts before writing
   `context/me.md`; `python3 code/context_check.py` checks the result.
2. Claude reports supported facts and remaining sources. Missing
   `context/me.md`: run `./setup.sh`, then /about-me. Unreadable career material:
   request its exact readable path, URL or pasted text; reconnect Drive/Gmail
   or paste only the relevant career material. Missing profile/highlights/contracts:
   reconnect through `README.md#connect-upwork` and rerun /about-me.
   Ask the matching question for exact Job Success Score or public video URL.
   Count account/profile/highlight/contract reads and each custom-direction search.

## Profile

1. Claude reads `references/profile.md`, `references/upwork.md` and
   `context/me.md`. Focus writes only the requested section with available
   facts; video uses existing context/profile without live reads or role models.
   Run `python3 code/context_check.py` and
   `python3 code/context_check.py --status`; an untouched file or unfinished proof
   interview goes to /about-me or /about-me proof. Missing individual proof
   blocks that claim, while supported offer-led drafting may continue.
2. Claude follows the caller's draft/check/preview workflow. Ask for role-model
   URLs or agreement to proceed without them, the rate and the shown profile
   fields. Wait for exact before/after approval before live writes; unsupported
   fields stay manual.
3. After the member says it is online, Claude reads fresh `get_profile action=get`
   and `list_highlights`, then runs
   `python3 code/profile_checks.py data/profile.json data/highlights.json --json`.
   Show verified completeness or unknown, what is online and each remaining
   field's percentage and exact edit location. Unreadable profile/highlights:
   reconnect Upwork and rerun /profile. Missing references: paste Upwork URLs.
   Missing video: record, upload publicly to YouTube and paste its URL. For
   unreadable fields ask for the exact value or screenshot at the named location.
   Run `python3 code/pipeline.py prune`, link `profile.md`, name /find-jobs next
   and count preview, confirmation and readback calls separately.

## Find jobs

1. Claude keeps the caller's search and skip routes. A skip uses
   `python3 code/pipeline.py get <id>`, asks for a missing reason, then runs
   `python3 code/pipeline.py set <id> skipped --note "not a fit: <reason>"`.
   Report the saved reason/removal, zero calls and stop.
2. For search, Claude runs `python3 code/workspace.py`,
   `python3 code/pipeline.py prune`, `python3 code/pipeline.py reset-search`
   and `python3 code/jobs.py window`. Read limits/history from
   `python3 code/jobs.py rules`. On the member's Analytics day run
   `python3 code/analytics.py due`; when true, print once:
   “Analytics due: run /analytics”. Ask for tracks and limits before search calls.
3. Claude uses `python3 code/learn.py report` for decisions/outcomes,
   `python3 code/learn.py lessons` for supported lessons and
   `python3 code/jobs.py score` to apply them. Report changed scores and thin
   dimensions from code. Keep full postings for every final lead.
4. Missing context/direction: /about-me or /about-me offer. Missing invitations,
   search pages or full posts: reconnect Upwork and rerun /find-jobs for that
   source; incomplete pagination is a gap and an unread lead stays out of the
   final list and /proposal. Missing `data/decisions.jsonl` or history blocks
   history lessons only; recover evidence through /dashboard. Missing cost/balance:
   reread job details or balance after reconnecting; buy no Connects. Finish
   with the caller's checks and measured costs/calls, naming /proposal or cockpit.

## Dashboard

1. Claude follows the caller's refresh selection and fresh-state reuse, reads
   `python3 code/cockpit.py state` and states the read-call budget. Use stored
   identities first. Backfill missing proposal IDs with
   `list_freelancer_proposals action=list`, modified newest first; stop when
   matched or exhausted. On first sync or first analytics history backfill,
   instead exhaust every documented status, including Archived. Deduplicate
   IDs, keep the newest modified copy and classify each record's own status.
   Archived alone proves no loss; disclose incomplete pages/status coverage.
   Read `get_room` for selected proposals lacking a saved room, save identities
   through `python3 code/pipeline.py record <id> --file -`, and record explicit
   no-room results only for jobs checked now.
2. Without a job argument, Claude reads `list_offers action=list_mine`,
   `list_contracts action=search` with ACTIVE contracts, one page each, and
   available invitations. Preserve stable identities and evidenced origins.
   Use a complete room's first client message for invitation time, otherwise
   the current observation; later complete-room proof replaces that fallback.
   For selected contracts lacking terms read `list_contracts action=get`.
   Preserve returned fixed/hourly terms; a rate alone proves no contract value.
   Refresh `get_freelancer_financials action=summary` for the current and prior
   four weeks, including corrections, and `action=connects_balance` transactions
   back to last sync (one page on first sync). Capture all negative ledger spends,
   including invitation badges, and positive receipts. Proposal bid/boost costs
   remain separate evidence, never additional ledger spends.
3. Claude refreshes every selected stored room with
   `get_messages action=list_messages`, newest 30 messages, and pages
   `list_rooms` until selected room cards are covered or pages end.
   Preserve reply ownership; mark a thread complete only when pagination proves
   no older page. Fewer than 30 messages proves no completeness.
4. For selected call-stage rooms or meeting cards, Claude reads
   `manage_meetings action=list` and `action=list_recaps`, reusing fresh evidence
   and following Upwork pacing. Keep requests, bookings, reschedules and held
   sessions distinct. Record scheduled start separately from verified booking
   agreement and actual held start/duration. A pending request never books or
   moves a lead to call. Preserve request creation time, or first observation
   when absent, with its provenance. Missing recap proves no no-show; preserve
   prior attendance and include the verbatim read error as unknown coverage.
5. Claude follows `code/sync.py`'s snapshot contract for all returned evidence
   and runs `python3 code/sync.py apply --file -`. Include views and proposal
   costs when returned; view time is observation time, never actual viewing time.
   For submitted proposals without insights, read
   `list_freelancer_proposals action=get` once per ID and save the returned
   insights with observation/source through the record writer; reuse later.
   Keep original application facts. Retain the prior successful sync timestamp
   (or observation start) for summarising new `data/badges.jsonl` awards without
   repeating printed lines. A nonzero apply means refresh failed; keep the prior
   successful timestamp and name mutation failures. Run
   `python3 code/pipeline.py prune`. First-sync history stays imported; later
   evidenced invitations/offers/contracts are live leads, with unknown origin
   unless affirmatively proved.
6. Claude sets an agreed/held call with
   `python3 code/pipeline.py set <id> call`, adding `--call-at <YYYY-MM-DD>`
   for the scheduled day. Record verified booking and held events separately
   with `python3 code/pipeline.py observe <id> <call_booked|call_held> <ISO time> --source <source> --verified`;
   save scheduled start via the record writer. Reschedules preserve the original
   booking. Use `references/call-transcript.md` for attendance/transcript evidence.
   For `no_show_candidate` from `python3 code/pipeline.py summary`, ask the member
   before recording no-show. A later held session clears it.
   Silent follow-ups use business days 3 and 7 then stop; use `--follow-up`
   only for an agreed date. Read any saved proposal before replying to an offer.
   Ask once about an unchecked submission older than three days; record the check
   and, on “not submitted”, run
   `python3 code/pipeline.py set <id> skipped --note "never submitted"`.
7. Claude keeps the caller's exact per-message approval, send/readback and
   `python3 code/pipeline.py follow-up <id> sent` after confirmed arrival.
   Record supported quest actions through Shared rules. On silence/dismissal/
   “send nothing”, retain drafts and ask no second time.
8. Missing account/financial/meeting evidence: reconnect and rerun /dashboard or
   /dashboard <id>, or supply exact meeting evidence. Missing thread/room ownership:
   /dashboard <id>; missing sent material: paste exact submitted text with job ID.
   Missing transcript: /call-review <id> with a full labelled transcript;
   missing sent proposal: supply it for /sales-call-proposal <id>.
   Missing goal proof: supply action source/date/text for the note writer.
   Missing context: /about-me. Never draft without a client message.
   Prune and report who waits, what moved/sent and every named gap.
9. Claude follows the caller's existing-process check and
   `python3 code/cockpit.py --no-open` launch. Reuse the correct running cockpit;
   restart after source changes; select a free `--port` when another app owns it.
   Wait for readiness and open the exact printed URL. Missing Node.js:
   ask for LTS installation, a new terminal and /dashboard again.
10. Use /analytics' app content contract and code snapshots for every displayed
   number and period. Missing snapshot: /analytics; missing Upwork state:
   /dashboard <id> or /dashboard. Show each saved coverage source, blocked result and supply route
   unchanged. An open page proves no source completeness. Report the exact
   URL; the cockpit runs no command and sends nothing.

## Proposal

1. Claude reads the full post with `python3 code/pipeline.py get <id>`.
   If absent, fetch this one job with `find_jobs action=get`, then
   `python3 code/jobs.py detail <id> <file>`. Prepare Uma's requested
   answers/video instead of a cover letter. Ask for missing mandatory proof
   and bid terms before drafting; the member submits on Upwork.
2. A walkthrough video is optional, chosen for requirements, value and preparation cost.
3. Claude writes the application from the full post and verified proof, using
   `references/copy.md` and the coach brief. Use [LOOM LINK] only for an agreed
   walkthrough. Run
   `python3 code/application_check.py jobs/<id>/application.md --modality <text|uma> --job-title "<exact job title>"`,
   adding `--video-required` only when explicitly required. Fix errors and read
   against the post. Before manual handoff run
   `python3 code/application_check.py jobs/<id>/application.md --ready --modality <text|uma>`.
4. Once the Loom URL replaces [LOOM LINK], repeat the ready application gate.
5. For `submitted`, ask for actual submitted copy, answers and bid,
   or explicit confirmation each matches its approved source. Run `python3 code/pipeline.py sent <id> --file <submitted-copy> --answers-file <submitted-answers.json> --bid <actual-amount>`;
   use `--confirmed-match` instead of `--file` for a confirmed draft match,
   and omit answers-file only when none were required. Preserve actual Uma
   answers/video. Read back `application.sent.md`, applicable `answers.sent.json`,
   and bid with `python3 code/pipeline.py get <id>` before
   `python3 code/pipeline.py set <id> applied`. A conflicting immutable copy
   is a reconciliation gap; missing submission proof blocks this shortcut.
6. Claude obtains missing proposal ID through Dashboard's bounded discovery,
   captures missing insights/view/cost evidence as above and records supported
   quest actions. Missing IDs/insights do not undo recorded submission.
   Missing post: reconnect/fetch this job; missing submitted source: supply or
   confirm the approved source.
   Run `python3 code/pipeline.py prune`, report actual calls and stop the shortcut.

## Sales call proposal

1. Claude runs `python3 code/workspace.py` and
   `python3 code/pipeline.py get <id>`, then follows
   `references/call-transcript.md`. Show the matching session's saved review
   and next step first; a distinct session needs /call-review <id> once.
   Missing transcript blocks feedback; ask for the full labelled transcript.
   Independently verified notes/thread agreements may support the proposal
   alone, with that limitation named. With no call evidence, ask and stop.
2. Claude reads all evidence and lists each promise with its supporting sentence,
   using the coach brief for judgment. Separate agreed work, wishes and options.
   Ask before drafting unless an agreed proposal next step exists, including a
   request for scope/pricing options. Record evidenced qualification through
   `python3 code/pipeline.py record <id> --file -`. Wait for the caller's
   scope/price/input/timing decisions; label open terms and assumptions.
3. Claude follows the caller's document/page steps and runs
   `python3 code/document_check.py check proposal <id>`; fix errors and read
   back against verified agreements. Send/accept nothing; /dashboard owns the
   thread and offer stage. After member-confirmed manual send run
   `python3 code/pipeline.py observe <id> proposal_sent <ISO time>`
   with actual confirmed send time, then capture supported quest proof.
   Scheduled start or a draft proves no proposal timing; obtain actual call
   end/duration and send evidence. Prune, link the proposal and report gaps.

## Onboarding

1. No started contract matched: stop and say so; an offer is not a contract.
   A missing thread, proposal or transcript: work from what exists and name the
   missing file in the report.
2. `python3 code/document_check.py check project <id>` passes before the folder
   is created. Report the first open checklist item as Next and count actual calls.

## Message

1. Claude keeps the caller's per-message approval, send/readback and
   `python3 code/pipeline.py follow-up <id> sent` after confirmed arrival.
   Record supported quest actions through Shared rules. On silence/dismissal/
   "send nothing", retain drafts and ask no second time. Report actual Upwork calls.
