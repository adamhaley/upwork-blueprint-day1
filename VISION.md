# Upwork Blueprint vision

**What:** a complete local Upwork operating system for freelancers.
**Goal:** turn the right opportunities into conversations and won contracts with less busywork.
**Standard:** clear, valuable, minimal and professional. No gimmicks.

## The outcome

A freelancer opens one place and knows what matters and what to do next. The
system carries the work from profile positioning through job discovery and
application, conversation and follow-up, to a won contract handed over.

The goal is not more automated activity. The goal is more good-fit applications,
more useful client conversations and more won work. Speed matters only when the
quality and account safety stay intact.

## The division of work

The system researches, checks, scores, drafts, schedules and keeps the pipeline
current. It turns every completed run into a plain result: what it found, what it
made, what it recommends and what the member should do next.

The member owns identity, proof, judgment, price and every irreversible action.
They record the Loom, review client-facing copy, and submit every proposal and
offer on Upwork themselves. A reply to a client can leave from here, but only one
message at a time and only on their yes to that message. The cockpit shows the
pipeline; it sends nothing.

## Product principles

1. **Decision first.** A member should understand a job, a run result or a next
   step in ten seconds.
2. **One operating loop.** Profile, leads, applications, conversations,
   follow-ups and clients belong to one connected system.
3. **Only valuable functions.** A feature belongs only if it saves time,
   improves a decision, increases trust or conversion, or reduces risk.
4. **Real evidence.** Copy uses the member's facts and verified proof. Reports
   distinguish measured facts from assumptions.
5. **Human control.** The system prepares the work. The member controls what
   leaves the account and submits proposals in Upwork themselves.
6. **Minimal and professional.** Quiet hierarchy, plain language and a polished
   native-feeling desktop interface. No novelty or automation for its own sake.
7. **Transferable by design.** Every required command, skill, rule and starter
   travels in this repository. Personal machine state never does.
8. **Efficient connector use.** Read fresh saved state first, make the fewest
   Upwork calls that answer the question and never poll in the background.

The cockpit applies these principles to the interface in
[`website/PRINCIPLES.md`](website/PRINCIPLES.md).

## What success looks like

- The member consistently submits the daily applications they chose to pursue.
- Job decisions and application preparation take less time without becoming
  generic.
- Reply, offer and win rates improve once enough applications exist to measure
  them honestly.
- Dormant leads receive relevant follow-ups and stop when the context says stop.
- Every client-facing claim is supported, every reply that leaves carries the member's
  yes to that one message, and every run leaves a clear next action.

## Review contract

Review the system against this file, then against the evidence a run actually
leaves: what `tools/check_repo.py` reports, what the built report shows at 1440
and 390 pixels, and what the real interface does. A review ends PASS or FAIL and
answers five questions:

1. Does the flow help a freelancer win or deliver work?
2. Can the member understand the decision and next action in ten seconds?
3. Is the feature part of the connected operating loop rather than a separate
   tool?
4. Does it preserve proof, human approval, account safety and transferability?
5. Would removing it change a useful outcome? If not, remove it.
