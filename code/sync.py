#!/usr/bin/env python3
"""Sync: brings the pipeline in line with what Upwork shows right now.

    python3 code/sync.py apply --file <snapshot.json>|-
    python3 code/sync.py last

/dashboard reads your proposals, offers, contracts and client threads through the
connector, read only, and hands that snapshot to `apply`. Apply moves each job to
the furthest stage Upwork shows evidence for, saves each client thread for the
cockpit's chat window, adds proposals you sent outside the cockpit, and records
when it ran. Status changes go through code/pipeline.py, the one writer. A saved
thread is Upwork content, so `pipeline.py prune` deletes it after KEEP_CHAT_HOURS (90 days).

The snapshot, one JSON object (every list optional):
    {"proposals": [{"job_id", "proposal_id", "room_id", "title", "url", "status", "applied_at"}],
     "invitations": [{"job_id", "invitation_id", "title", "url", "invited_at", "invited_at_source", "room_id"}],
     "no_rooms":  ["job_id"],
     "offers":    [{"job_id", "offer_id", "title", "state", "client_name", "source": "invite"|"direct_offer", "offered_at"}],
     "contracts": [{"job_id", "contract_id", "title", "status", "client_name",
                    "terms": {"type": "fixed"|"hourly", "fixed_amount", "hourly_rate", "weekly_hours", "currency", "start_date"}}],
     "earnings": [{"week_start", "contract_id", "billed", "currency"}],
     "connects": [{"at", "amount", "reason", "job_id"}],
     "meetings": [{"job_id", "room_id", "status", "requested_at", "request_id", "booked_at", "scheduled_at", "session_id", "held_at", "duration_s"}],
     "recaps": [{"job_id", "room_id", "recap_state": "ok"|"empty"|"unknown", "recap_reason"}],
     "threads":   [{"job_id", "room_id", "awaiting_reply_from", "messages_complete", "messages":
                    [{"from": "client"|"me", "name", "at", "text"}]}]}
Offers and contracts without a job_id are matched only by a stored unique
proposal, room, invitation, offer or contract identity. An unmatched record needs a stable offer_id or contract_id to import.

`applied_at` is the proposal's Upwork creation time. `messages_complete` is true
only when connector pagination explicitly proves there are no older messages.
Normalized invitations may supply a verified zoned invited_at with source room or
sync. A supplied date without a source is legacy validated room evidence. Raw
invitations without dates use actual sync observation time, source sync. Complete
room first-client-message evidence wins over supplied dates and repairs fallbacks;
the earliest valid date for each source is retained across replay. Room evidence
upgrades sync evidence even when the room date is later; sync cannot replace room.
Proposals may also carry viewedByClient (boolean), terms.connectsBid, boosted and
proposal_insights: {data: object, fetched_at: zoned ISO, source: "upwork-proposal"}.
The view flag's timestamp is observation time, never the actual viewing time.
Proposal costs are evidence only; connects is exclusively the financial ledger.
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
import pipeline  # noqa: E402  (read-only use: load, jobs_dir)
import threads as thread_io  # noqa: E402  (cleans raw Upwork messages)

RANK = {'new': 0, 'applied': 1, 'replied': 2, 'call': 3, 'offer': 4, 'won': 5}
# A lead the member closed stays closed. Upwork keeps serving the thread and the
# proposal that got it there, so without this it climbs back every morning.
EXITS = ('lost', 'skipped')
# Upwork's proposal words. "Accepted" means submitted, not that the client said yes.
PROPOSAL_STAGE = {'accepted': 'applied', 'pending': 'applied', 'activated': 'applied',
                  'archived': 'applied', 'offered': 'offer', 'hired': 'won', 'declined': 'lost', 'withdrawn': 'lost'}
OFFER_STAGE = {'awaiting_your_acceptance': 'offer', 'contract_started': 'won',
               'declined': 'lost', 'withdrawn': 'lost', 'expired': 'lost'}
CONTRACT_STAGE = {'active': 'won', 'paused': 'won', 'closed': 'won'}


def data_dir():
    return pathlib.Path(os.environ.get('BLUEPRINT_DATA') or ROOT / 'data')


_mutation_failures = []


def run_pipeline(*args, stdin=None):
    r = subprocess.run([sys.executable, str(ROOT / 'code' / 'pipeline.py'), *args],
                       input=stdin, capture_output=True, text=True)
    for line in pipeline.award_lines(r.stdout):
        print(line)
    if r.stderr.strip():
        print(r.stderr.strip(), file=sys.stderr)
    if r.returncode:
        _mutation_failures.append({'command': args[0], 'job_id': args[1] if len(args) > 1 else None})
    return r.returncode == 0


def status_word(value):
    """Read the record's status, never the status used to request its page."""
    if isinstance(value, dict):
        value = value.get('status') or value.get('value') or value.get('name') or ''
    return str(value or '').strip().lower()


def proposal_records(records):
    """Overlapping status pages count a stable proposal once; newest copy wins."""
    indexed = {}
    for position, item in enumerate(records):
        identity = str(item.get('proposal_id') or item.get('id') or '')
        key = ('proposal', identity) if identity else ('row', position)
        previous = indexed.get(key)
        order = verified_timestamp(item.get('modified_at', item.get('modifiedDateTime'))) or ''
        prior_order = verified_timestamp((previous or {}).get('modified_at', (previous or {}).get('modifiedDateTime'))) or ''
        if previous is None or order >= prior_order:
            indexed[key] = item
    return list(indexed.values())


def meeting_is_request(meeting):
    """Explicit requests/pending states outrank misleading booking-shaped fields."""
    status = status_word(meeting.get('status') or meeting.get('state'))
    kind = status_word(meeting.get('kind') or meeting.get('type'))
    return (meeting.get('is_request') is True or meeting.get('isRequest') is True
            or any(word in status for word in ('request', 'pending', 'proposed', 'tentative', 'unconfirmed'))
            or 'request' in kind)


def record_metadata(job, value):
    """Record only changed metadata, including removal of the waiting marker."""
    changed = {key: item for key, item in value.items() if job.get(key) != item}
    # The sole writer needs provenance alongside a changed timestamp, even when
    # that provenance is unchanged; otherwise its room guard rejects the repair.
    if 'invited_at' in changed and 'invited_at_source' in value:
        changed['invited_at_source'] = value['invited_at_source']
    if 'source' in value and isinstance(job.get('application_facts'), dict) and job['application_facts'].get('source') != value['source']:
        changed['source'] = value['source']
    if not changed:
        return True
    if not run_pipeline('record', job['id'], '--file', '-', stdin=json.dumps(changed)):
        return False
    job.update(changed)
    if changed.get('follow_up_source', 'waiting') is None:
        job.pop('follow_up_source', None)
    return True


def verified_timestamp(value):
    """Return a canonical nonfuture zoned timestamp, or None for weak evidence."""
    try:
        stamp = datetime.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        return None
    stamp = stamp.astimezone(datetime.timezone.utc)
    if stamp > datetime.datetime.now(datetime.timezone.utc):
        return None
    return stamp.isoformat()


def booked_timestamp(value):
    """A scheduled meeting may be future, but its start must have a timezone."""
    try:
        stamp = datetime.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    return stamp.astimezone(datetime.timezone.utc).isoformat() if stamp.tzinfo and stamp.utcoffset() is not None else None


def applied_expired(job, today=None):
    """An unanswered proposal leaves the active pipeline after 14 full days."""
    if job.get('status') != 'applied' or job.get('application_date_unknown'):
        return False
    stamp = verified_timestamp(job.get('applied_at'))
    if not stamp:
        return False
    applied_day = pipeline.local_day(stamp)
    return applied_day <= (today or pipeline.local_day()) - datetime.timedelta(days=14)


def first_complete_client_message(thread):
    """The first reply exists only when this response proves complete history.

    A message that is not an object leaves the history incomplete. It moves no stage
    and blocks every verified timestamp from this thread: a timeline built on a
    payload we could not read is a guess wearing a date.
    """
    if thread.get('messages_complete') is not True:
        return None
    turns = complete_turns(thread)
    if turns is None:
        return None
    return next((at for at, message in turns if message['from'] == 'client'), None)


def complete_turns(thread):
    """Validate a complete room, skip system events and preserve invitation turns."""
    if thread.get('messages_complete') is not True or not isinstance(thread.get('messages'), list):
        return None
    raw = []
    for item in thread['messages']:
        if not isinstance(item, dict) or not isinstance(item.get('node', item), dict):
            return None
        node = item.get('node', item)
        if node.get('kind') in ('system', 'event') or node.get('from_side') == 'system' or node.get('from') == 'system':
            continue
        if 'from_side' in node and node['from_side'] not in ('client', 'freelancer') and not node.get('from_self'):
            return None
        raw.append(item)
    turns = []
    for message in thread_io.normalize(raw):
        if message.get('kind') in ('system', 'event') or message.get('from') == 'system':
            continue
        at = verified_timestamp(message.get('at'))
        if message.get('from') not in ('me', 'client') or at is None:
            return None
        turns.append((at, message))
    return sorted(turns, key=lambda turn: turn[0])


def first_reply(thread):
    """The first client turn to the first member answer, including invitations."""
    turns = complete_turns(thread)
    if turns is None:
        return None
    client_at = None
    for at, message in turns:
        if message['from'] == 'client' and client_at is None:
            client_at = at
        elif message['from'] == 'me' and client_at is not None:
            seconds = int((datetime.datetime.fromisoformat(at) - datetime.datetime.fromisoformat(client_at)).total_seconds())
            return {'first_reply_s': seconds, 'first_reply_at': at, 'client_at': client_at}
    return None


def reply_gaps(thread):
    """Seconds from each client turn to the next member turn in a complete room.

    The snapshot marks invitation rooms with invitation_room/opened_by_invite,
    or marks the first client turn kind:invite/is_invitation.
    """
    if thread.get('invitation_room') or thread.get('opened_by_invite'):
        return []
    if thread.get('messages_complete') is not True:
        return None
    raw = thread.get('messages') or []
    if not isinstance(raw, list):
        return None
    messages, invites = [], set()
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get('node', item), dict):
            return None
        node = item.get('node', item)
        if (node.get('kind') in ('system', 'event') or
                node.get('from_side') == 'system' or node.get('from') == 'system'):
            continue
        if 'from_side' in node and node['from_side'] not in ('client', 'freelancer') and not node.get('from_self'):
            return None
        stamp = verified_timestamp(node.get('createdDateTime', node.get('at')))
        if node.get('is_invitation') or node.get('kind') in ('invite', 'invitation'):
            invites.add(stamp)
        messages.append(item)
    turns = []
    for message in thread_io.normalize(messages):
        if message.get('kind') in ('system', 'event') or message.get('from') == 'system':
            continue
        stamp = verified_timestamp(message.get('at'))
        if message.get('from') not in ('me', 'client') or not stamp:
            return None
        at = datetime.datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        turns.append((at, stamp, message))
    turns.sort(key=lambda turn: turn[0])
    if turns and turns[0][2]['from'] == 'client' and turns[0][1] in invites:
        return []
    gaps, pending = [], None
    for at, _, message in turns:
        if message['from'] == 'client':
            if pending is None:
                pending = at
        elif pending is not None:
            gaps.append(int((at - pending).total_seconds()))
            pending = None
    return gaps


def source_stage(item, kind):
    key, stages = {'proposals': ('status', PROPOSAL_STAGE), 'offers': ('state', OFFER_STAGE),
                   'contracts': ('status', CONTRACT_STAGE)}[kind]
    raw = status_word(item.get(key))
    stage = stages.get(raw)
    if stage is None:
        print(f'WARNING: unknown {kind} status {raw!r}.', file=sys.stderr)
    return stage


def identity_match(item, jobs):
    for key in ('contract_id', 'offer_id', 'proposal_id', 'invitation_id', 'room_id'):
        if item.get(key):
            matches = [j['id'] for j in jobs if str(j.get(key) or '') == str(item[key])]
            if len(matches) == 1:
                return matches[0]
    return None


def matched_id(item, jobs):
    # Titles are client-authored labels, never a cross-client identity.
    if item.get('job_id'):
        supplied = str(item['job_id'])
        return next((job['id'] for job in jobs if supplied in job.get('aliases', [])), supplied)
    return identity_match(item, jobs)


def evidence(snapshot, jobs):
    """Per job id: the furthest stage Upwork shows, and whether it says lost."""
    seen = {}

    def note(job_id, title, stage):
        job_id = str(job_id or '')
        if job_id and stage:
            seen.setdefault(job_id, set()).add(stage)
        return job_id

    for kind in ('proposals', 'offers', 'contracts'):
        for item in snapshot.get(kind) or []:
            note(matched_id(item, jobs), item.get('title'), source_stage(item, kind))
    for t in snapshot.get('threads') or []:
        if any(m.get('from') == 'client' and m.get('kind') not in ('system', 'event')
               for m in thread_io.normalize(t.get('messages') or [])):
            note(t.get('job_id'), None, 'replied')
    for meeting in snapshot.get('meetings') or []:
        if not meeting_is_request(meeting) and (verified_timestamp(meeting.get('booked_at')) or verified_timestamp(meeting.get('held_at'))):
            note(meeting.get('job_id'), None, 'call')
    return seen


def target(current, stages):
    """The status Upwork's evidence calls for, or None when nothing should move."""
    best = max((s for s in stages if s in RANK), key=RANK.get, default=None)
    if 'lost' in stages and 'won' not in stages and current not in ('won', 'lost'):
        return 'lost'
    if current in EXITS:
        # Only real movement reopens a closed lead: an offer or a started contract.
        return best if best in ('offer', 'won') else None
    if best and (current not in RANK or RANK[best] > RANK[current]):
        return best
    return None


def contract_value(terms):
    """Use only complete member-owned contract terms; never guess missing money."""
    if not isinstance(terms, dict) or terms.get('type') not in ('fixed', 'hourly'):
        return None
    amount = terms.get('fixed_amount' if terms['type'] == 'fixed' else 'hourly_rate')
    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or not math.isfinite(amount) or amount < 0:
        return None
    if not isinstance(terms.get('currency'), str) or not terms['currency'].strip():
        return None
    try:
        datetime.date.fromisoformat(terms.get('start_date'))
    except (ValueError, TypeError):
        return None
    result = {'type': terms['type'], 'amount': amount, 'currency': terms['currency'], 'start_date': terms['start_date']}
    hours = terms.get('weekly_hours', terms.get('agreed_weekly_hours'))
    if terms['type'] == 'hourly' and isinstance(hours, (int, float)) and not isinstance(hours, bool) and math.isfinite(hours) and hours >= 0:
        result['weekly_hours'] = hours
    return result


def write_json_atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as handle:
        tmp = pathlib.Path(handle.name)
        json.dump(value, handle, ensure_ascii=False, indent=2)
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def append_financials(snapshot):
    """Upsert authoritative weekly totals; a validated empty source is checked."""
    data_dir().mkdir(parents=True, exist_ok=True)
    with pipeline.transaction():
        for name, keys in (('earnings', ('week_start', 'contract_id', 'billed', 'currency')),
                           ('connects', ('at', 'amount', 'reason', 'job_id', 'transaction_id', 'purpose', 'settled'))):
            if name not in snapshot:
                continue
            if not isinstance(snapshot[name], list):
                raise ValueError(f'{name} must be a list; omitted means unavailable, empty means checked-empty.')
            path = data_dir() / f'{name}.jsonl'
            existing = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.exists() else []
            indexed = {}
            def identity(row):
                if name == 'earnings':
                    return (row.get('week_start'), str(row.get('contract_id')))
                return ('id', str(row['transaction_id'])) if row.get('transaction_id') else tuple(row.get(key) for key in keys[:4])
            for row in existing:
                indexed[identity(row)] = row
            for item in snapshot[name]:
                if not isinstance(item, dict):
                    raise ValueError(f'{name} record must be an object.')
                row = {key: item.get(key) for key in keys if key in item or key in keys[:4]}
                number = row['billed' if name == 'earnings' else 'amount']
                if not isinstance(number, (int, float)) or isinstance(number, bool) or not math.isfinite(number):
                    raise ValueError(f'{name} amount must be finite.')
                if name == 'earnings':
                    datetime.date.fromisoformat(row['week_start'])
                    if not row['contract_id'] or not isinstance(row['currency'], str) or not row['currency'].strip():
                        raise ValueError('earnings need contract identity and currency.')
                    row['contract_id'] = str(row['contract_id'])
                else:
                    row['at'] = verified_timestamp(row['at'])
                    if not row['at'] or not isinstance(row['reason'], str):
                        raise ValueError('connects need a verified timestamp and reason.')
                    if row.get('job_id') is not None:
                        row['job_id'] = str(row['job_id'])
                indexed[identity(row)] = row
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as handle:
                tmp = pathlib.Path(handle.name)
                for row in indexed.values():
                    handle.write(json.dumps(row, ensure_ascii=False) + '\n')
            try:
                os.replace(tmp, path)
            finally:
                tmp.unlink(missing_ok=True)


def cmd_apply(args):
    raw = sys.stdin.read() if args.file == '-' else pathlib.Path(args.file).read_text(encoding='utf-8')
    snapshot = json.loads(raw)
    snapshot['proposals'] = proposal_records(snapshot.get('proposals') or [])
    _mutation_failures.clear()
    jobs = pipeline.load()
    known = {j['id'] for j in jobs}
    previous_sync = json.loads((data_dir() / 'sync.json').read_text()) if (data_dir() / 'sync.json').is_file() else {}
    first_import = not previous_sync.get('synced_at')
    observed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    observation_started_at = previous_sync.get('observation_started_at') or previous_sync.get('synced_at') or observed_at

    added = []
    for kind in ('invitations', 'proposals', 'offers', 'contracts'):
        for item in snapshot.get(kind) or []:
            real_id = str(item['job_id']) if item.get('job_id') else None
            alias = identity_match(item, jobs)
            if real_id and alias and alias != real_id:
                alias_job = next(j for j in jobs if j['id'] == alias)
                if alias_job.get('synthetic_import'):
                    if run_pipeline('reconcile', alias, real_id):
                        jobs = pipeline.load()
                        known = {j['id'] for j in jobs}
            jid = matched_id(item, jobs)
            stage = 'new' if kind == 'invitations' else source_stage(item, kind)
            if not jid and stage:
                identity = item.get('contract_id') or item.get('offer_id') or item.get('invitation_id')
                if identity:
                    # A decimal local id works with every lead command. The source
                    # kind is included so unrelated platform ids cannot collide.
                    digest = hashlib.sha256(f'{kind}:{identity}'.encode()).digest()
                    jid = str(int.from_bytes(digest[:10], 'big'))
                else:
                    print(f'WARNING: unmatched {kind} record has no stable id; not imported.', file=sys.stderr)
            if jid and jid not in known and stage:
                record = {'id': jid, 'title': item.get('title') or 'Untitled job', 'url': item.get('url') or '',
                          'status': stage, 'found_via': ['sync'], 'notes': 'imported Upwork history' if first_import else 'observed Upwork lead',
                          'imported': first_import, 'application_date_unknown': True, 'synthetic_import': not bool(item.get('job_id')),
                          'source': 'invite' if kind == 'invitations' else 'outbound' if kind == 'proposals' else item.get('source') or 'unknown'}
                activity = max((verified_timestamp(message.get('at')) or ''
                                for thread in snapshot.get('threads') or [] if str(thread.get('job_id')) == jid
                                for message in thread.get('messages') or [] if isinstance(message, dict)
                                and message.get('from') in ('me', 'client') and message.get('kind') != 'event'), default='')
                if activity:
                    record['last_activity_at'] = activity
                if run_pipeline('add', '--file', '-', stdin=json.dumps(record)):
                    added.append(jid)
                    known.add(jid)
                    jobs = pipeline.load()
            if jid in known:
                metadata = {key: str(item[key]) for key in ('proposal_id', 'room_id', 'contract_id', 'invitation_id', 'offer_id') if item.get(key)}
                job = next(j for j in jobs if j['id'] == jid)
                if kind == 'invitations':
                    metadata['source'] = 'invite'
                    room_times = [stamp for thread in snapshot.get('threads') or []
                                  if (str(thread.get('job_id') or '') == jid or
                                      (item.get('room_id') and str(thread.get('room_id')) == str(item['room_id'])))
                                  if (stamp := first_complete_client_message(thread))]
                    if room_times:
                        prior = verified_timestamp(job.get('invited_at')) if job.get('invited_at_source') == 'room' else None
                        metadata.update(invited_at=min([*room_times, *([prior] if prior else [])]), invited_at_source='room')
                    elif (supplied := verified_timestamp(item.get('invited_at'))) and item.get('invited_at_source') in (None, 'room', 'sync'):
                        source = item.get('invited_at_source') or 'room'
                        prior = verified_timestamp(job.get('invited_at')) if job.get('invited_at_source') == source else None
                        if job.get('invited_at_source') != 'room' or source == 'room':
                            metadata.update(invited_at=min(supplied, prior) if prior else supplied, invited_at_source=source)
                    elif job.get('invited_at_source') not in ('room', 'sync') or not job.get('invited_at'):
                        metadata.update(invited_at=observed_at, invited_at_source='sync')
                elif kind == 'proposals':
                    if status_word(item.get('status')):
                        metadata['proposal_status'] = status_word(item.get('status'))
                    flag = item.get('viewedByClient', item.get('viewed_by_client'))
                    if isinstance(flag, bool):
                        metadata['proposal_viewed'] = {'value': flag, 'observed_at': observed_at, 'source': 'upwork-proposal'}
                    cost = {'observed_at': observed_at, 'source': 'upwork-proposal'}
                    connects_bid = pipeline.numeric((item.get('terms') or {}).get('connectsBid', item.get('connectsBid')))
                    if connects_bid is not None:
                        cost['connectsBid'] = connects_bid
                    if isinstance(item.get('boosted'), bool):
                        cost['boosted'] = item['boosted']
                    if len(cost) > 2:
                        metadata['proposal_cost'] = cost
                    insights = item.get('proposal_insights')
                    if insights is not None and not job.get('proposal_insights'):
                        metadata['proposal_insights'] = insights
                    source = item.get('source')
                    if source in ('outbound', 'invite'):
                        metadata['source'] = source
                    elif job.get('source') in (None, 'unknown'):
                        metadata['source'] = 'outbound'
                elif kind == 'offers':
                    source = item.get('source')
                    if source in ('invite', 'direct_offer'):
                        metadata['source'] = source
                    # Missing proposal evidence does not prove direct-offer origin.
                if kind == 'contracts':
                    value = contract_value(item.get('terms'))
                    if value is not None:
                        metadata['won_value'] = value
                if item.get('client_name'):
                    metadata['contract_client'] = str(item['client_name'])
                if metadata:
                    record_metadata(next(j for j in jobs if j['id'] == jid), metadata)
                item['job_id'] = jid
    jobs = pipeline.load()

    aliases = {alias: job['id'] for job in jobs for alias in job.get('aliases', [])}
    for kind in ('threads', 'meetings', 'recaps', 'connects'):
        for item in snapshot.get(kind) or []:
            if isinstance(item, dict) and item.get('job_id'):
                item['job_id'] = aliases.get(str(item['job_id']), str(item['job_id']))
    snapshot['no_rooms'] = [aliases.get(str(jid), str(jid)) for jid in snapshot.get('no_rooms') or []]
    today = pipeline.local_day().isoformat()
    moved, waiting = [], []
    threads = {}
    for room in snapshot.get('threads') or []:
        if room.get('job_id'):
            threads.setdefault(str(room['job_id']), []).append(room)
    for jid, stages in evidence(snapshot, jobs).items():
        job = next((j for j in jobs if j['id'] == jid), None)
        if not job:
            continue
        new = target(job.get('status'), stages)
        if new:
            date_args = ['--applied-at', 'unknown'] if new == 'applied' else []
            force = ['--force'] if job.get('status') in EXITS else []
            activity = max((verified_timestamp(message.get('at')) or ''
                            for room in threads.get(jid, []) for message in room.get('messages') or []
                            if isinstance(message, dict) and message.get('from') in ('me', 'client')
                            and message.get('kind') != 'event'), default='')
            activity = activity or verified_timestamp(job.get('last_activity_at') or job.get('status_updated_at'))
            activity_args = ['--activity-at', activity] if activity else []
            if run_pipeline('set', jid, new, *date_args, *force, *activity_args):
                moved.append({'id': jid, 'from': job.get('status'), 'to': new})
                job['status'] = new

    # Polling history is observation time; conversion uses verified event time.
    for kind, event_name, source in (('offers', 'offered', 'upwork-offer'), ('contracts', 'won', 'upwork-contract')):
        for item in snapshot.get(kind) or []:
            jid = str(item.get('job_id') or '')
            raw_event = item.get('offered_at', item.get('offer_at', item.get('created_at'))) if kind == 'offers' else item.get('started_at', item.get('start_at'))
            if kind == 'contracts' and not raw_event:
                date = (item.get('terms') or {}).get('start_date')
                try:
                    raw_event = datetime.datetime.combine(datetime.date.fromisoformat(date), datetime.time(), pipeline.member_zone()).isoformat()
                except (TypeError, ValueError):
                    pass
            stamp = verified_timestamp(raw_event)
            if jid in known and stamp:
                run_pipeline('observe', jid, event_name, stamp, '--source', source, '--verified')

    # Proposal creation time is measured Upwork evidence. Record it even when
    # this sync did not move the job, so an old unknown import can be repaired.
    applied_observations = {}
    for proposal in snapshot.get('proposals') or []:
        jid = str(proposal.get('job_id') or '')
        stamp = verified_timestamp(proposal.get('applied_at'))
        stage = PROPOSAL_STAGE.get(status_word(proposal.get('status')))
        if jid in known and stage and stamp:
            applied_observations[jid] = min(stamp, applied_observations.get(jid, stamp))
        if jid in known and proposal.get('viewedByClient', proposal.get('viewed_by_client')) is True:
            run_pipeline('observe', jid, 'proposal_viewed', observed_at, '--source', 'upwork-proposal', '--verified')
    for jid, stamp in applied_observations.items():
        run_pipeline('observe', jid, 'applied', stamp, '--source', 'upwork-proposal', '--verified')

    # Merge every session before choosing the current booking; connector ordering
    # cannot let an old recap replace a newer pending session.
    meetings, session_jobs = [], {}
    for meeting in snapshot.get('meetings') or []:
        jid = str(meeting.get('job_id') or '')
        if jid not in known:
            continue
        if meeting_is_request(meeting):
            request = {key: str(meeting[key]) for key in ('request_id', 'session_id', 'room_id') if meeting.get(key)}
            request.update(status=status_word(meeting.get('status') or meeting.get('state')) or 'request',
                           source='upwork-meeting', observed_at=observed_at)
            if booked_timestamp(meeting.get('scheduled_at')):
                request['scheduled_at'] = booked_timestamp(meeting['scheduled_at'])
            if pipeline.numeric(meeting.get('duration_s')) is not None:
                request['duration_s'] = pipeline.numeric(meeting['duration_s'])
            requested = verified_timestamp(meeting.get('requested_at') or meeting.get('created_at') or meeting.get('createdDateTime'))
            saved_job = next(j for j in pipeline.load() if j['id'] == jid)
            prior_request = saved_job.get('call_request') or {}
            identity_key = next((key for key in ('request_id', 'session_id', 'room_id') if request.get(key)), None)
            same_request = identity_key and prior_request.get(identity_key) == request[identity_key]
            request['requested_at_source'] = ('upwork' if requested else
                prior_request.get('requested_at_source', 'sync') if same_request else 'sync')
            requested = requested or (verified_timestamp(saved_job.get('call_requested_at')) if same_request else None) or observed_at
            record_metadata(saved_job, {'call_request': request, 'call_requested_at': requested})
            continue
        if jid not in session_jobs:
            saved_job = next(j for j in pipeline.load() if j['id'] == jid)
            session_jobs[jid] = dict(saved_job.get('call_sessions') or {})
        sessions = session_jobs[jid]
        session_id = str(meeting.get('session_id') or meeting.get('room_id') or 'default')
        session = dict(sessions.get(session_id) or {})
        if meeting.get('room_id'):
            session['room_id'] = str(meeting['room_id'])
        for event, field in (('call_booked', 'booked_at'), ('call_held', 'held_at')):
            stamp = verified_timestamp(meeting.get(field))
            if stamp:
                session[field] = stamp
                run_pipeline('observe', jid, event, stamp, '--source', 'upwork-meeting', '--verified', '--session-id', session_id)
        scheduled = booked_timestamp(meeting.get('scheduled_at'))
        if scheduled:
            if session.get('scheduled_at') and scheduled != session['scheduled_at'] and not session.get('held_at'):
                session.setdefault('reschedule_history', []).append({'scheduled_at': session['scheduled_at'], 'no_show': bool(session.get('no_show'))})
                session['no_show'] = False
            session['scheduled_at'] = scheduled
        if isinstance(meeting.get('cancelled'), bool):
            session['cancelled'] = meeting['cancelled']
        if isinstance(meeting.get('no_show'), bool):
            session['no_show'] = meeting['no_show']
        seconds = meeting.get('duration_s')
        if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) and math.isfinite(seconds) and seconds >= 0:
            session['duration_s'] = seconds
            if session.get('held_at'):
                ended = verified_timestamp((datetime.datetime.fromisoformat(session['held_at']) + datetime.timedelta(seconds=seconds)).isoformat())
                if ended:
                    session['ended_at'] = ended
        if session.get('held_at'):
            session['no_show'] = False
        sessions[session_id] = session
        meetings.append({'job_id': jid, 'session_id': session_id, **session})
    for jid, sessions in session_jobs.items():
        def session_order(pair):
            identity, session = pair
            return (verified_timestamp(session.get('booked_at')) or booked_timestamp(session.get('scheduled_at')) or
                    verified_timestamp(session.get('held_at')) or '', identity)
        session_id, current = max(sessions.items(), key=session_order)
        metadata = {'call_sessions': sessions, 'call_session_id': session_id,
                    'call_scheduled_at': current.get('scheduled_at'),
                    'call_no_show': bool(current.get('no_show')) and not bool(current.get('held_at'))}
        if current.get('room_id'):
            metadata['room_id'] = current['room_id']
        # Lead progression keeps the first held event; its end must belong to
        # that same session rather than whichever recap arrived last.
        held_sessions = [session for session in sessions.values() if verified_timestamp(session.get('held_at'))]
        if held_sessions:
            first_held = min(held_sessions, key=lambda session: session['held_at'])
            metadata['call_ended_at'] = first_held.get('ended_at')
            metadata['call_duration_s'] = first_held.get('duration_s')
        record_metadata(next(j for j in pipeline.load() if j['id'] == jid), metadata)

    # A newest-message window is not proof of a first reply. Only a thread whose
    # pagination explicitly proves completeness may establish replied_at.
    reply_observations = {}
    for thread in snapshot.get('threads') or []:
        jid = str(thread.get('job_id') or '')
        stamp = first_complete_client_message(thread)
        if jid in known and stamp:
            reply_observations[jid] = min(stamp, reply_observations.get(jid, stamp))
    for jid, stamp in reply_observations.items():
        run_pipeline('observe', jid, 'replied', stamp, '--source', 'upwork-thread', '--verified')
        job = next(j for j in pipeline.load() if j['id'] == jid)
        if job.get('source') == 'invite' and (job.get('invited_at_source') != 'room' or stamp < job.get('invited_at', stamp)):
            record_metadata(job, {'invited_at': stamp, 'invited_at_source': 'room'})

    # Update complete rooms by identity; a partial refresh preserves earlier rooms.
    for jid, rooms in threads.items():
        if jid not in known:
            continue
        job = next(j for j in pipeline.load() if j['id'] == jid)
        metrics = dict(job.get('room_reply_metrics') or {})
        for room in rooms:
            room_id = str(room.get('room_id') or '')
            turns = complete_turns(room)
            if not room_id or turns is None:
                continue
            first_client = next((at for at, message in turns if message['from'] == 'client'), None)
            if not first_client:
                continue
            answer = first_reply(room)
            metrics[room_id] = {'first_client_at': first_client,
                'first_reply_s': answer['first_reply_s'] if answer else None,
                'first_reply_at': answer['first_reply_at'] if answer else None,
                'reply_gaps_s': reply_gaps(room) or []}
        if metrics:
            earliest = min(metrics.values(), key=lambda metric: metric['first_client_at'])
            value = {'room_reply_metrics': metrics, 'first_client_message_at': earliest['first_client_at'],
                     'reply_gaps_s': [gap for metric in metrics.values() for gap in metric.get('reply_gaps_s', [])]}
            if earliest.get('first_reply_at'):
                value.update(first_reply_s=earliest['first_reply_s'], first_reply_at=earliest['first_reply_at'])
            record_metadata(job, value)

    # A sync replays message times, never poll time. Observed sends advance the
    # sequence before client replies stop it, so the same nudge is not drafted twice.
    for jid, rooms in threads.items():
        for t in rooms:
            job = next((j for j in pipeline.load() if j['id'] == jid), None)
            if not job:
                continue
            thread_path = pipeline.jobs_dir() / jid / 'thread.json'
            previous_thread = json.loads(thread_path.read_text()) if thread_path.is_file() else {}
            saved_rooms = dict(previous_thread.get('rooms') or {})
            if previous_thread.get('room_id') and not saved_rooms:
                saved_rooms[str(previous_thread['room_id'])] = {key: previous_thread.get(key) for key in ('room_id', 'messages', 'awaiting_reply_from')}
            thread_io.save(jid, t.get('messages') or [], t.get('room_id'), t.get('awaiting_reply_from'))
            current_thread = json.loads(thread_path.read_text())
            current_thread['messages_complete'] = complete_turns(t) is not None
            if t.get('room_id'):
                saved_rooms[str(t['room_id'])] = {key: current_thread.get(key) for key in ('room_id', 'messages', 'awaiting_reply_from', 'messages_complete', 'fetched_at')}
            current_thread['rooms'] = saved_rooms
            current_thread['messages_complete'] = bool(saved_rooms) and all(
                room.get('messages_complete') is True for room in saved_rooms.values())
            thread_io.write_json(thread_path, current_thread)
            if t.get('room_id'):
                record_metadata(job, {'room_id': str(t['room_id'])})
            normalized = thread_io.normalize(t.get('messages') or [])
            messages = [(verified_timestamp(m.get('at')), m) for m in normalized
                        if isinstance(m, dict) and m.get('from') in ('me', 'client') and m.get('kind') not in ('event', 'system')]
            messages = sorted((pair for pair in messages if pair[0]), key=lambda pair: pair[0])
            if t.get('room_id'):
                refs = dict(job.get('thread_refs') or {})
                room_id = str(t['room_id'])
                refs[room_id] = {'room_id': room_id, 'messages_complete': current_thread['messages_complete'],
                                'fetched_at': current_thread['fetched_at'],
                                'last_writer': messages[-1][1]['from'] if messages else 'unknown',
                                'source': 'upwork-thread'}
                record_metadata(job, {'thread_refs': refs})
            activity_at = verified_timestamp(job.get('last_activity_at')) or ''
            new_messages = [pair for pair in messages if pair[0] > activity_at]
            plan = job.get('follow_up_plan') or {}
            last = (job.get('follow_up_history') or [{}])[-1]
            follow_up_at = max(verified_timestamp(plan.get('reviewed_at')) or '',
                               verified_timestamp(last.get('at')) or '')
            for stamp, message in (pair for pair in messages if follow_up_at and pair[0] > follow_up_at):
                plan = job.get('follow_up_plan') or {}
                reviewed = verified_timestamp(plan.get('reviewed_at'))
                silent_due = plan.get('lane') != 'active' or pipeline.local_day(stamp).isoformat() >= (job.get('next_follow_up') or '9999-12-31')
                if message.get('from') == 'me' and reviewed and stamp > reviewed and silent_due:
                    if run_pipeline('follow-up', jid, 'sent', '--on', pipeline.local_day(stamp).isoformat(), '--at', stamp):
                        job = next(j for j in pipeline.load() if j['id'] == jid)
                last = (job.get('follow_up_history') or [{}])[-1]
                stopped_at = verified_timestamp(last.get('at'))
                if (message.get('from') == 'client' and stopped_at and stamp > stopped_at
                        and (last.get('action') == 'cleared' or last.get('completed'))):
                    if run_pipeline('follow-up', jid, 'clear', '--at', stamp, '--reason', 'The client replied; review the new message first.'):
                        job = next(j for j in pipeline.load() if j['id'] == jid)
            if new_messages:
                stamp, message = new_messages[-1]
                if stamp > (verified_timestamp(job.get('last_activity_at')) or ''):
                    run_pipeline('acted', jid, '--at', stamp, '--note',
                                 'Client replied on Upwork.' if message.get('from') == 'client' else 'Member sent a message on Upwork.')
            job = next(j for j in pipeline.load() if j['id'] == jid)
            # A message the member marked as read on the dashboard is not waiting, however
            # often the room is read again. Only something newer from the client is.
            if (t.get('awaiting_reply_from') == 'you' and job.get('status') not in ('lost', 'skipped')
                    and not pipeline.read_covers(job, t)):
                if job.get('follow_up_plan'):
                    run_pipeline('follow-up', jid, 'clear', '--at', max((at for at, message in messages if message['from'] == 'client'), default=datetime.datetime.now(datetime.timezone.utc).isoformat()), '--reason', 'The client replied; review the new message first.')
                    job = next(j for j in pipeline.load() if j['id'] == jid)
                if job.get('status') in ('replied', 'call', 'offer', 'won') and record_metadata(
                        job, {'next_follow_up': today, 'follow_up_source': 'waiting'}):
                    waiting.append(jid)
            elif not job.get('follow_up_plan') and job.get('follow_up_source') == 'waiting':
                record_metadata(job, {'next_follow_up': None, 'follow_up_source': None})

    # Expiration needs fresh evidence that this exact proposal was checked and
    # still has no room. Absence from a limited proposal page proves nothing.
    no_rooms = {str(jid) for jid in snapshot.get('no_rooms') or []}
    stale = []
    for job in pipeline.load():
        if job.get('status') == 'applied' and (job.get('next_follow_up') or job.get('follow_up_plan')):
            run_pipeline('follow-up', job['id'], 'clear', '--reason', 'Applied proposals cannot be followed up before the client replies.')
        # Lost is the member's call, never the sync's. A proposal that sat 14 days
        # without a room is only listed, so /dashboard can ask.
        if job['id'] in no_rooms and applied_expired(job):
            stale.append(job['id'])

    # Read errors are coverage facts, never attendance evidence or mutation failures.
    recap_coverage = []
    for recap in [*(snapshot.get('recaps') or []),
                  *(meeting for meeting in snapshot.get('meetings') or [] if 'recap_state' in meeting)]:
        jid = matched_id(recap, pipeline.load())
        state = recap.get('recap_state', 'unknown')
        reason = recap.get('recap_reason')
        if state not in ('ok', 'empty', 'unknown'):
            state, reason = 'unknown', f'Unrecognised recap state: {state}'
        if state == 'unknown' and not reason:
            reason = 'Recaps could not be read.'
        value = {'recap_state': state, 'recap_reason': str(reason) if reason is not None else None}
        recap_coverage.append({'job_id': jid, 'room_id': recap.get('room_id'), **value})
        if jid in known:
            record_metadata(next(j for j in pipeline.load() if j['id'] == jid), value)
    try:
        append_financials(snapshot)
    except (ValueError, TypeError, OSError) as error:
        print(f'Financial sync failed: {error}', file=sys.stderr)
        _mutation_failures.append({'command': 'financials'})
    record = {'synced_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
              'moved': moved, 'added': added, 'threads': sum(map(len, threads.values())), 'awaiting_you': waiting,
              'stale_applications': stale, 'meetings': meetings, 'observation_started_at': observation_started_at,
              'coverage': {name: ('checked' if name in snapshot else 'unavailable') for name in ('earnings', 'connects')},
              'status': 'error' if _mutation_failures else 'ok', 'errors': list(_mutation_failures)}
    record['coverage']['recaps'] = {'state': 'unknown' if any(row['recap_state'] == 'unknown' for row in recap_coverage)
                                  else 'checked' if 'recaps' in snapshot or recap_coverage else 'unavailable',
                                  'rooms': recap_coverage}
    if _mutation_failures:
        record['attempted_at'] = record['synced_at']
        record['synced_at'] = previous_sync.get('synced_at')
    data_dir().mkdir(parents=True, exist_ok=True)
    write_json_atomic(data_dir() / 'sync.json', record)
    if not _mutation_failures:
        pipeline.check_badges('--all-since', previous_sync.get('synced_at') or observed_at)
    for m in moved:
        print(f'moved   {m["id"]}  {m["from"]} -> {m["to"]}')
    for jid in added:
        print(f'added   {jid}  ({"imported Upwork history" if first_import else "observed Upwork lead"})')
    for jid in waiting:
        print(f'waiting {jid}  (the client is waiting for your reply)')
    print(f'\n{len(moved)} moved, {len(added)} added, {sum(map(len, threads.values()))} threads saved, '
          f'{len(waiting)} waiting on you.')
    return 1 if _mutation_failures else 0


def cmd_last(args):
    f = data_dir() / 'sync.json'
    if not f.is_file():
        print('Never synced.')
        return
    print(json.loads(f.read_text(encoding='utf-8')).get('synced_at'))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('apply', help='Bring the pipeline in line with a snapshot from Upwork.')
    p.add_argument('--file', required=True, help='JSON snapshot. "-" reads stdin.')
    p.set_defaults(func=cmd_apply)
    p = sub.add_parser('last', help='When the last sync ran.')
    p.set_defaults(func=cmd_last)
    args = ap.parse_args(argv)
    return args.func(args) or 0


if __name__ == '__main__':
    sys.exit(main())
