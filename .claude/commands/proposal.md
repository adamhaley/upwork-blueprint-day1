---
description: Writes the application for one job, to submit with your Loom: cover letter, screening answers, bid and the video script.
argument-hint: "<job id or Upwork job link> [fast] | <job id> [more job ids] | <job id> submitted | video"
---

# /proposal

**Before anything else, read [references/upwork-compliance.md](../../references/upwork-compliance.md) in full.** Where a step below reads looser, that file wins.

Before starting, read and follow [analytics capture: proposal](../../references/analytics-capture.md#proposal), including its shared rules and replacement steps.

**`/proposal <id> submitted`:** only run `python3 code/pipeline.py set <id> applied`
and report `Upwork calls: 0`, then stop before any other step. It records the member's submission. The check on a dashboard row makes the same move without this command.

**The fast lane: a posting the member saw minutes ago.** When the argument is an Upwork job link, an id that is not in the pipeline yet, or the word `fast`, speed comes first, because a proposal in the first few minutes is answered far more often than one sent later. Say the posting's age, then, in this order and inside five minutes of the member's message:

1. Take the job id from the link, fetch the posting once with `find_jobs` action `get`, add it with `python3 code/pipeline.py add --file -` (`found_via` set to `notification`) and store it with `python3 code/jobs.py detail <id> <file>`.
2. One line of judgement: the score out of 10 with its three checks (main offer, their tools, a sample like it), any line of the member's own filter it breaks, any trap, and any mandatory opening phrase or screening question. A broken filter line is said, never enforced: they saw the job and chose it.
3. Write the application now, as Step 3 sets out, with one difference: no `[LOOM LINK]` placeholder, because a Loom is recorded for one job and there is no time for one. **If the member has a standard video** (a public YouTube or Loom link under `**Standard proposal video:**` in `context/me.md`, or failing that their `**Intro video:**`), the letter carries it in the Loom's place, as one sentence inviting the client to watch. With no video on record, the letter goes without that sentence. Run the gate with `--fast`.
4. Hand over the letter, the screening answers, the bid, what it costs in Connects and the three form fields of Step 4. The member submits on Upwork and types `/proposal <id> submitted`.

**Several ids run one after another.** Each application gets its own bid and its own approval: the repetition is the command's, never the member's yes.

Follow `references/copy.md` for the application. The
member described in `context/me.md` is the sender.

The application includes a cover letter, bid and any screening answers stated in the full posting, plus the script for the Loom recorded for this job.

Read first: [references/upwork.md](../../references/upwork.md) (hard constraint 8, no contact route before a contract), `context/me.md`.

## Step 1 · The job and its full posting

`python3 code/pipeline.py get $ARGUMENTS`. The posting is in `details.description`. No posting there (older than a day, or never opened): `find_jobs` action `get` for this one job, then `python3 code/jobs.py detail <id> <file>` as `/find-jobs` Step 6 does. Never write from the summary: the letter answers the requirements, and the summary does not carry them.

## Step 2 · Understand the mechanism

For every tool or delivery discipline the posting names, check
`context/tool-knowledge/<tool>.md` if the member has a copy, otherwise the current
`starters/context/tool-knowledge/<tool>.md`. Shipped references cover SEO and Google Ads. Read only the
ones this job uses. If a named system is not covered, research it now with
official docs first, then save decisions in `context/tool-knowledge/<tool>.md` with
sources so the next job does not pay for the same discovery again. A familiar
category is not a reason to skip this: the specific combination is what the
client is paying for.

For SEO, choose the relevant lane from `seo.md` before
planning, and read `delivery.md`, using the same member-copy or starter rule, for how the work is
sequenced. Put the posting's plugins, badges, privacy rules and performance
targets inside the track or step they belong to, instead of turning each
requirement into another box. For Google Ads, put verified conversion measurement
before bidding and keep media spend separate from the implementation fee. These
references guide the mechanism; they never supply proof about the member or facts
about the client.

### Price guide, for every lane

Estimate effort from the full posting, never the client's budget: low, likely and
high hours; two to five milestones summing to likely; confidence; scope assumptions.

```
python3 code/pricing.py <id> --hours <low> <likely> <high> \
  --confidence high|medium|low --contract-type fixed|hourly|unknown \
  --milestone "Foundation|hours" --milestone "Build and QA|hours" \
  --assumption "one concrete scope boundary"
```

Every lane runs this before the application. It uses the member's rate plus a scope-risk
buffer of 5, 15 or 25 percent for high, medium or low confidence. The internal
guide is never the bid, never appears in the letter and never overrides approved terms.

## Step 3 · Application

Use the full posting from Step 1 and `references/copy.md` for
every line the client will read. The member reviews and submits the proposal
on Upwork themselves. Prepare the cover letter, screening answers when the
posting states the questions, and the bid for manual submission.

**The first 230 characters decide.** That is all the applicant card shows a client, roughly the first two lines. The hook, the offer and the guarantee sit inside them, and the video line starts there. A friendly line with nothing in it ("happy to help with this!") spends the card on nothing.

### What is true about you and the scope

List the posting's hard requirements ("built at least 5 sub-accounts for trades", "A2P 10DLC is non-negotiable") and check each against the evidence sections of `context/me.md`. **A requirement your proof does not cover never becomes a claim.** If it is mandatory, ask the member whether they meet it and where that can be checked, one single choice per requirement: met and checkable, met with nothing to point at, not met; the place is typed. Until resolved, save no client-facing draft. If it is a preference, name the gap for the member and draft without claiming it. Lead with the strongest relevant proof by tier; never a badge or number the member does not hold.

Separate explicit deliverables from assumptions. Before quoting a price or
timeline, resolve the contract type, included work, dependencies, revision or
acceptance boundary and payment structure from the posting, saved member policy
or an explicit member decision. If one changes the bid, ask before writing the application. Never convert an hourly profile rate into a fixed-price quote.

When `details.price_estimate` exists, use it as the internal starting point:
show the hour cases, profile rate, risk buffer, assumptions and roadmap together.
It is an estimate, not approval. Recalculate it when the resolved scope changes,
and get the member's explicit bid decision before writing the bid, as a single choice
between the estimate's cases with another figure typed.

### Write the letter

Read [references/persuasion.md](../../references/persuasion.md) in full before the
first line, not its headings. The letter is the member talking to someone they like:
nice, warm, welcoming (`references/copy.md`), with no em-dashes. Its order is fixed
(ruling of 8 October 2026) and every part is one or two lines.

**Above the fold**, the first 230 characters, in this order:

1. **Hook.** A hello by first name and their job in their words, the title when it helps: "Hey Dana, I'd love to be your Google Ads coach!" The name comes from the posting or from a freelancer's review of this client, never from a guess; with none, "Hey there".
2. **Offer and guarantee.** One sentence, always before the video, in this form: "My goal is to get you [the result they asked for] in [a time], or [what happens if it does not]." The result is theirs, in their words. The time and the "or" are the member's commitment: draft two or three versions from the posting, their offers and the risk reversal in `context/me.md`, and take their pick together with the bid. Never a figure they did not choose, and no letter goes out without this sentence.
3. **Video.** One line with the literal [LOOM LINK] placeholder. The Loom is the video recorded for this one job; a member who records none pastes their standard video (`**Standard proposal video:**` in `context/me.md`) in its place.

**Below the fold:**

4. **Social proof.** A review quoted exactly, a retention figure or a credential.
5. **Results.** Two or three, one line each.
6. **About you.** Just enough to show why hiring this member is in the client's interest: "I am new on Upwork, not to n8n. I'm starting at $20/hr while I build my profile here. Will increase soon." A later rate is named only when the member has given one.
7. **Tools, optional.** One line: the tools the posting names or the work needs, from "Tools and systems you can name confidently".
8. **Answers, optional.** Questions the posting asks in its own text. They open with the plain line "To answer your questions:", then each question as a plain line with its answer below. Questions in Upwork's separate fields go under `# Screening answers` instead.
9. **Call to action.** When the member is free and one easy question, with the next step on Upwork. It is the last paragraph.

**Offer, never order.** "I'd love to", "I think I'd be a great fit for", "My goal is
to". "I'll coach you" and "We start with" read as a stranger taking charge, and a
letter that is all facts reads dry.

**No markdown in anything that gets pasted.** Upwork shows a letter as typed: no `#`
headings, no bold stars, no backticks, no bracketed links. Plain lines and numbered
lists only, and the gate refuses the rest.

**Parts 4 and 5 are matched to this job, never a standing list.** Read the Results,
Reviews and Credentials sections of `context/me.md` against the posting and pick by
closeness: the same trade first, then the same problem, then the same metric. Never
stretch unrelated proof to fill a line; a part with nothing true behind it is left out.

Everything but the answers stays under 220 words. Do not recap the posting, explain
a long method, add generic praise, write a biography or pad the pitch. Never add a
refund, free work or date beyond what the member picked for the offer sentence.

Save the cover letter to `jobs/<id>/application.md` in this exact shape so the
cockpit can present it separately:

```markdown
# Cover letter

<the complete letter>

```

When the full posting states screening questions, answer each in one or two
sentences from the posting and verified proof. A mandatory answer without
proof is a hold, written as a `[HOLD: ...]` line that the ready check refuses. Do
not guess questions the posting does not state. Append:

```markdown
# Screening answers

## <the client's exact question>

<one or two sentence answer>
```

Record the member-approved bid amount through
`python3 code/pipeline.py detail <id> --file -` with a JSON object containing
`bid_amount`. Leave out costs or questions the posting did not reveal.

### The video script

A member who presses record with no plan rambles, and a rambling video is worse than none. So write the walkthrough before they record, and **print it in full in the chat** as well as saving it to `jobs/<id>/video-script.md`: what is on screen for each beat, and the words to say. About 60 to 90 seconds, about 150 to 200 words, plain and spoken, numbers as said aloud.

The five beats, in this order:

1. **Their problem, in their words**, inside the first ten seconds, taken from the posting. Open on them, then "let me show you what I would do".
2. **One proof, on screen**: the result closest to their job, with its number.
3. **What I would do, in three steps**, shown on screen. Three steps and never the whole method: for a Google Ads job that is the account check, then the fix (tracking, campaigns and the landing page), then the budget moved to what books. Each step ends on what the client gets from it.
4. **The promise**: the member's risk reversal, word for word as recorded in `context/me.md`.
5. **The next step**: reply here, or a short call to walk through it.

**Show the work, not the face.** The screen carries the video: their own website or posting, a real account or dashboard with nothing private on it. A finished thing on screen is believed where a talking head is skipped. No contact details on screen or in the words, and nothing about their business that cannot be checked.

**`/proposal video` writes the standard version instead:** the same five beats for a member's whole market rather than one client, with the problem named for the business model they serve ("you pay for clicks and cannot tell which ad books the job") and the three steps shown on a real, anonymous example. It is recorded once, its public link goes under `**Standard proposal video:**` in `context/me.md`, and the fast lane links to it when there is no time to record a Loom for that job. Save the script to `context/standard-video.md`.

### The gate

`python3 code/application_check.py jobs/<id>/application.md --job-title "<exact job title>"`. Exit 1 means fix it.

### The reader's grade

A fresh reader grades the letter out of 10 before the member sees it, so nobody sends a 2 and wonders why nothing comes back. Never the writer: hand a subagent only the posting, the letter as it will be pasted with the first 230 characters marked as the card, and one line on the member's standing (reviews on Upwork or none, how many verified results). None of your reasoning and none of the member's file. Without a subagent tool, reread it cold.

**The brief.** "You are the client who wrote this posting. You have dozens of proposals open and you have been let down by freelancers before. Read this one once, as it appears on Upwork. Answer the ten questions yes or no, quoting the words that decided each; a yes needs evidence in the text and any doubt is a no. Grade only what the writer controls: a freelancer with no reviews is not marked down for having none, only for faking, padding or burying what they do have. Then give the one reason you would skip this proposal."

1. Does the card show my job, not a greeting that fits any job?
2. Is there an offer I would want: my result, a time, and what happens if it is missed?
3. Is the video offered before I have to open the letter?
4. Is every line of proof specific enough to believe, with nothing that reads as invented or padded?
5. Do the results come from a business or a problem like mine?
6. Do I know why hiring this person is in my interest, at this rate?
7. Did they answer everything my posting asked for?
8. Can I take in the pitch in twenty seconds: short, plain, no word I would need explained?
9. Does it sound like a person I would like to talk to, warm and not bossy?
10. Is the next step obvious and easy?

**The grade is the count of yeses, and 8 passes.** Show the member the grade, each no with the reader's reason, and the one reason to skip. A no that writing can fix gets one rewrite, the gate again and a new fresh reader: one round, never more, because a proposal sent in the first minutes beats a perfect one sent late. A no only the member can fix (a question still open, proof they do not hold) is named, never written around. Under 8 after that round, the handoff opens with the grade. Under 6, say plainly that it is likely to be skipped and why. The grade never blocks: the member decides. The fast lane gets one reader and no rewrite.

### Manual handoff

Present the letter, any answers, the bid and any preferred qualification the
member does not meet. Then, outside the letter, say what still needs them: one line
per placeholder, naming the part it sits in. Open the saved job URL on Upwork. The member pastes the
fields, reviews Upwork's final cost and submits the proposal on Upwork
themselves.

**Before they paste, run `python3 code/application_check.py jobs/<id>/application.md
--ready`.** Same gate, one more refusal: any placeholder still in the text, such as
`[LOOM LINK]` or a `[HOLD: ...]` answer, correct while the letter is written and wrong the
moment it is pasted. Nothing is pasted, and nothing could ever be submitted, until it passes.

Never mark Applied until the member submits on Upwork, then runs `/proposal <id> submitted`.
That stage rests on their word; `/dashboard` checks once if no proposal ever shows up.

## Step 4 · Report

Run `python3 code/pipeline.py prune` first, because Step 1 fetched the full job. Then the completion report as CLAUDE.md defines it, with the
application linked. Say what the application costs in Connects and what the balance leaves. Then the three fields on Upwork's form, one line each (13 October 2026; reasoned, no data exists either way): leave the scheduled rate increase on Never, since a raise is easier to ask for once they want to keep you; add up to four profile highlights, the sample project closest to this job first; and boost only a job they would be thrilled to win, since serious clients read every proposal.
Next: record the Loom from the video script and return its URL here; replace [LOOM LINK] in the letter.
Then run the ready application check again.
Only then submit on Upwork and run `/proposal <id> submitted`.
End with `Upwork calls: N`.
