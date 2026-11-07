// What a lead needs next: a command to copy into Claude Code, or a sentence for
// the member's own hands, plus the other commands that fit its stage. The
// cockpit runs nothing itself.
// The stage decides what a lead carries. `new` writes the application until
// it exists, then the member submits by hand, and `/find-jobs skip <id>
// <reason>` stays available on every new lead. `applied` waits. `replied`, `call` and `offer`
// answer a waiting client first and a due follow-up second, where due means
// `next_follow_up <= today`; a future date stays Waiting. `/sales-call-prep` is the task
// of a booked call until its brief exists, and `/sales-call-proposal` the task after the
// call until the proposal exists. `won`
// writes the handover and records the result once. `lost` and `skipped` carry
// no task even when a date is set and a client is waiting.
//
// A message is written with `/message <id>`, never `/dashboard <id>` (13.10.2026): it reads
// the one conversation whole and drafts the reply or the follow-up.
//
// Every card on the board offers the same four commands in the same order, whatever its
// stage: `/message`, `/sales-call-prep`, `/sales-call-proposal`, `/onboarding` (13.10.2026;
// /onboarding added 15.10.2026, its own contract gate stops it before a contract starts). The member
// decides what a lead needs and when; the stage only says which of them is the task, and
// the side panel shows that task with the rest beside it.
//
// The list never shows a date the reader has to subtract from today: it says
// `Waiting 3 days`, `Follow up in 5 days`, `Follow up . 2 days overdue`. Overdue
// is the only red state on the board.
import { todayIso } from './dates.mjs';
import { BOARD } from './stages.mjs';

const WAITING = 'Waiting for the client. /dashboard picks up replies.';
const NOTHING = Object.freeze({ label: '', detail: '', command: null, extras: [] });

const has = (job, name) => (job.artifacts || []).includes(name);
// A quiet lead is due on day three: the first of the two follow-up days in
// references/follow-ups.md (day 3, then day 7, then left alone).
//
// This is the fallback, not the schedule. Once `/dashboard` has read the thread it
// plans the sequence, the member's own `Follow-up days` included, and
// `next_follow_up` wins here. The three days apply only where nothing is planned
// yet, so the two never disagree about the same lead.
const CHASE_DAYS = 3;
const LANE_STEPS = { active: 2, reactivation: 2 };

export function stageEnteredAt(job) {
  const entry = [...(job.history || [])].reverse().find(item => item?.status === job.status);
  return entry?.at || job.status_updated_at || job.found_at || '';
}

function parked(job) {
  if (job.follow_up_plan) return false;
  const last = (job.follow_up_history || []).at(-1);
  if (!last || (last.action === 'cleared' && String(last.reason || '').startsWith('The client replied'))) return false;
  return last.action === 'cleared' || (last.action === 'sent'
    && (last.completed || last.step >= LANE_STEPS[last.lane]));
}

/** Whole days from a stamp to today, or null when there is no usable stamp. */
function daysSince(stamp, today) {
  const then = Date.parse(String(stamp || '').slice(0, 10) + 'T00:00:00Z');
  const now = Date.parse(`${today}T00:00:00Z`);
  if (Number.isNaN(then) || Number.isNaN(now)) return null;
  return Math.max(0, Math.round((now - then) / 864e5));
}

/** The follow-up a member owes when nothing else is scheduled: due on day three of silence. */
function chase(job, today, command) {
  if (parked(job)) return step('Parked', 'The follow-up sequence has stopped. Wait for the client to return.');
  const silent = daysSince(job.last_activity_at || stageEnteredAt(job), today);
  if (silent == null) return step('Waiting', WAITING);
  const over = silent - CHASE_DAYS;
  if (over >= 0) {
    return step('Follow up', `No answer for ${silent} day${silent === 1 ? '' : 's'}. Draft a follow-up with a reason to write; approve one message or send it on Upwork.`, command);
  }
  return step('Waiting', `Follow up in ${-over} day${over === -1 ? '' : 's'} unless they answer.`);
}
const step = (label, detail, command = null, extras = []) => ({ label, detail, command, extras });

/** The four commands a lead on the board can run at any time, in one fixed order. */
export function boardCommands(job) {
  const id = job.id;
  return [`/message ${id}`, `/sales-call-prep ${id}`, `/sales-call-proposal ${id} <transcript path or notes>`, `/onboarding ${id}`];
}

export function nextStep(job, today = todayIso()) {
  const found = stageStep(job, today);
  if (!BOARD.includes(job.status)) return found;
  return { ...found, extras: boardCommands(job).filter(command => command !== found.command) };
}

/** What a card offers to copy: on the board the same four everywhere, in the list the lead's own task. */
export function cardCommands(job, found) {
  return BOARD.includes(job.status) ? boardCommands(job) : [found.command].filter(Boolean);
}

function stageStep(job, today) {
  const id = job.id;
  const [message, prep, proposal] = boardCommands(job);
  switch (job.status) {
    case 'new': {
      const skip = [`/find-jobs skip ${id} <reason>`];
      return has(job, 'application.md')
        ? step('Submit', `Submit on Upwork with your standard video, then tick the check here. Optional: record a Loom for this job and give its URL to /proposal ${id} first.`, null, skip)
        : step('Write application', 'Writes the cover letter, the bid and the video script.', `/proposal ${id}`, skip);
    }
    case 'applied':
      return step('Waiting', WAITING);
    case 'replied':
    case 'call':
    case 'offer': {
      // A waiting client or a planned follow-up can outrank the brief and the proposal as the task.
      const briefed = has(job, 'call-prep.md');
      const callAhead = job.status === 'call' && job.call_at && job.call_at >= today;
      if (job.client_waiting) return step('Reply', 'The client is waiting. Draft a reply; approve one message or send it on Upwork.', message);
      if (job.next_follow_up && job.next_follow_up <= today) return step('Follow up', 'A follow-up is due. Draft a nudge; approve one message or send it on Upwork.', message);
      if (job.next_follow_up && job.next_follow_up > today) return step('Waiting', `Follow up ${whenText(dueIn(job.next_follow_up, today))}.`);
      if (job.status === 'call') {
        // Booked for today or later with no brief yet: the brief is the work until the call.
        if (callAhead && !briefed) {
          return step('Prepare the call', `The call is on ${job.call_at}. Researches the client and writes your call brief.`, prep);
        }
        // Call day: the one-pager is not the task before the call, only one click away after it.
        if (callAhead && job.call_at === today) {
          return step('Call booked', 'The call is today. Your call brief is ready; write the proposal right after it.');
        }
        // Booked for later: the chase stops until the call has happened.
        if (callAhead) {
          return step('Call booked', `The call is on ${job.call_at}. Your call brief is ready.`);
        }
        // The call is behind us, and the one-pager is the work the stage carries. A call
        // agreed without a date can still be ahead, so the brief stays one click away.
        if (!has(job, 'proposal.md')) {
          return step('Write the proposal', 'Turns the call into the one-pager the client decides on.', proposal);
        }
        // Sent, and now it is chased like anything else the client owes an answer to.
        return chase(job, today, message);
      }
      if (job.status === 'offer') {
        return step('Review offer', 'Review the offer on Upwork. /dashboard moves it to Won once the contract starts.');
      }
      // In conversation: chase until there is a call.
      return chase(job, today, message);
    }
    case 'won': {
      // A won lead used to show nothing at all, which reads as finished when the work has
      // not started, so until /onboarding has written project.md it is the next step.
      if (job.client_waiting) return step('Reply', 'The client is waiting. Draft a reply; approve one message or send it on Upwork.', message);
      if (job.follow_up_plan?.lane === 'reactivation') {
        return job.next_follow_up && job.next_follow_up <= today
          ? step('Follow up', 'Draft a message; approve one message or send it on Upwork.', message)
          : step('Waiting', `Follow up ${whenText(dueIn(job.next_follow_up, today))}.`);
      }
      if (parked(job)) return step('Parked', 'The follow-up sequence has stopped. Wait for the client to return.');
      if (has(job, 'project.md')) return { ...NOTHING, extras: [] };
      return job.imported ? { ...NOTHING, extras: [] }
        : step('Onboard', 'Turns the contract into the checklist, the kickoff message and the client folder.', `/onboarding ${id}`);
    }
    default:
      return { ...NOTHING, extras: [] };
  }
}

/** The reply drafts written after the client's latest message. Older drafts answer an old message. */
// What a member needs at a glance in the list: are we acting, waiting, or has a
// follow-up already been set, and how long has this lead sat where it sits.
/** Whole days from today to a date, negative once it is in the past. */
export function dueIn(iso, today = todayIso()) {
  if (!iso) return null;
  const then = Date.parse(`${iso}T00:00:00Z`), now = Date.parse(`${today}T00:00:00Z`);
  if (Number.isNaN(then) || Number.isNaN(now)) return null;
  return Math.round((then - now) / 864e5);
}

/** The same number as a person would say it. */
export function whenText(days) {
  if (days == null) return '';
  if (days === 0) return 'today';
  if (days === 1) return 'tomorrow';
  if (days > 1) return `in ${days} days`;
  return days === -1 ? '1 day overdue' : `${-days} days overdue`;
}

export function waitingState(job, today = todayIso(), now = Date.now()) {
  const at = Date.parse(job.last_activity_at || stageEnteredAt(job));
  const days = Number.isNaN(at) ? null : Math.max(0, Math.floor((now - at) / 864e5));
  const age = days == null ? '' : days === 0 ? 'today' : days === 1 ? '1 day' : `${days} days`;
  const step = nextStep(job, today);
  // Submitting is the member's own move too, although no command does it.
  const acting = Boolean(step.command) || step.label === 'Reply' || step.label === 'Follow up' || step.label === 'Submit';
  const due = dueIn(job.next_follow_up, today);
  if (step.label !== 'Reply' && job.next_follow_up && job.next_follow_up > today) {
    return { kind: 'follow-up set', detail: `Follow up ${whenText(due)}`, age, days, due };
  }
  if (acting) {
    // A task with a date carries it: late is the only thing on this board that is red.
    const detail = step.label || 'Act';
    return { kind: 'act', detail: due != null && due < 0 ? `${detail} · ${whenText(due)}` : detail,
             age, days, due, late: due != null && due < 0 };
  }
  return { kind: 'waiting', detail: step.label === 'Parked' ? 'Parked' : age ? `Waiting ${age}` : 'Waiting', age, days, due };
}

export function replyDrafts(job) {
  const replies = job.replies || {};
  const drafts = (Array.isArray(replies.drafts) ? replies.drafts : [])
    .map(draft => ({ label: String(draft?.label || '').trim(), text: String(draft?.text || '').trim() }))
    .filter(draft => draft.text);
  if (!drafts.length) return [];
  const clientTimes = ((job.thread || {}).messages || [])
    .filter(message => message?.kind !== 'event' && message?.from !== 'me')
    .map(message => Date.parse(message.at) || 0);
  return (Date.parse(replies.generated_at) || 0) >= Math.max(0, ...clientTimes) ? drafts : [];
}
