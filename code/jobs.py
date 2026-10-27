#!/usr/bin/env python3
"""The counting half of /find-jobs. The judging half (does this job fit you?) is Claude's.

    python3 code/jobs.py window                                   # hours to search back
    python3 code/jobs.py filter [bids=50 posted=24h ...]          # print the filter, or save one pasted from the dashboard
    python3 code/jobs.py candidates data/search/*.json [--window-hours 10]
    python3 code/jobs.py score [--min 50]                         # merges data/fit.json, logs
    python3 code/jobs.py detail <job_id> <find_jobs-get-response.json>
    python3 code/jobs.py lessons                                  # your past calls, to calibrate

A job's score is out of 10 and means one thing: how close the job is to what the
member does. It is 7 when the job is a service they sell, plus one for each of three
checks Claude answers in data/fit.json: it is their main offer, it names tools they
use, they have a result or sample project like it. Client, competition and budget are
not in the number: they are counted here as doubts and shown in their own columns,
where the member weighs them. The hard no's are the member's own filter, read from
context/me.md.
"""
import argparse
import collections
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
# BLUEPRINT_DATA points tests at a throwaway folder, like BLUEPRINT_JOBS does for the pipeline.
DATA = pathlib.Path(os.environ.get('BLUEPRINT_DATA') or ROOT / 'data')
CANDIDATES = DATA / 'candidates.json'
FIT = DATA / 'fit.json'
# What the gate turned down, kept across runs. `clean` deletes a run's raw
# responses; this is not one of them.
DECISIONS = DATA / 'decisions.jsonl'
# When this account last searched. The member's own record of their own runs, so
# `prune` leaves it alone: it holds no Upwork content, only a timestamp.
LAST_SEARCH = DATA / 'last-search.json'
PIPELINE = ROOT / 'code' / 'pipeline.py'
ME = pathlib.Path(os.environ.get('BLUEPRINT_ME') or ROOT / 'context' / 'me.md')
TAG = re.compile(r'</?untrusted_participant_content>')
MIN_WINDOW, MAX_WINDOW = 10, 24
RUN_FLOOR = 2          # the smallest window a repeat run asks for, in hours
# Everything a member reads about a job is one number out of ten, so there is no
# second scale to translate, no "points" behind a "grade", and nothing for the
# cockpit to print twice.
FIT_GATE = 6           # below this the job is not the member's work, whatever else is true
TRAP_CAP = 6           # a named trap can never reach the gate
MIN_SCORE = 7          # the gate, and the floor of the shortlist
SERVICE_SCORE = 7      # a job that is a service the member sells starts here
CHECKS = ('main_offer', 'tools', 'proof')   # one point each: their main offer, tools they use,
                                            # a result or sample project like it
# The starting filter, the one the series teaches (12.10.2026). It holds until the member
# changes a line: no pay floors, because first reviews are worth more than first dollars,
# and unverified clients shown, because many are simply hiring for the first time.
MIN_CLIENT_RATING = 4.0   # hidden below this, once three freelancers have rated the client
MAX_PROPOSALS = 50        # hidden above this many bids


def clean(text):
    return TAG.sub('', text or '').strip()


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def parse_time(stamp):
    try:
        return datetime.datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
    except ValueError:
        return None


def numbers(text):
    return [float(n.replace(',', '')) for n in re.findall(r'\d[\d,]*(?:\.\d+)?', str(text or ''))]


def money_value(text):
    found = numbers(text)
    return found[0] if found else None


def pipeline(*args, stdin=None):
    return subprocess.run([sys.executable, str(PIPELINE), *args], input=stdin,
                          capture_output=True, text=True)


def jobs_file():
    return pathlib.Path(os.environ.get('BLUEPRINT_JOBS') or DATA / 'jobs.json')


def load_json(path, default):
    path = pathlib.Path(path)
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else default


def me_number(label):
    """One `**Label:**` figure from context/me.md, or None when it is not answered."""
    if not ME.is_file():
        return None
    match = re.search(rf'(?im)^\*\*{re.escape(label)}:\*\*[ \t]*\$?([\d,.]+)', ME.read_text(encoding='utf-8'))
    return float(match.group(1).replace(',', '')) if match else None


def me_text(label):
    """The words after one `**Label:**` line in context/me.md, lowercased. Empty when absent or unanswered."""
    if not ME.is_file():
        return ''
    match = re.search(rf'(?im)^\*\*{re.escape(label)}[^:\n]*:\*\*[ \t]*(.*)$', ME.read_text(encoding='utf-8'))
    value = match.group(1).strip().lower() if match else ''
    return '' if 'not answered' in value else value


def me_limit(label, default):
    """A limit from the member's own filter: its number, None when they switched it off, the default when unset.

    Off has to be sayable. A member with no reviews who wants every paid job needs
    "none" to mean none, and not to fall back to a floor somebody else picked.
    """
    value = me_text(label)
    if not value:
        return default
    if re.match(r'(none|no\b|off|0\b|any)', value):
        return None
    number = re.search(r'\d[\d,.]*', value)
    return float(number.group(0).replace(',', '')) if number else default


def me_allows(label, default=False):
    """True when the member's filter lets this kind of posting through ("show", "allow", "yes").

    An unanswered line takes the starting filter's side, given as `default`.
    """
    value = me_text(label)
    return value.startswith(('show', 'allow', 'yes')) if value else default


def member_rate():
    """Your hourly rate: the live profile first, then the file you filled in.

    The profile is the truth while it is fresh, but `prune` deletes it after a day,
    and without a rate two of the hard no's silently stop applying. So the answer in
    `context/me.md` is the fallback rather than nothing.
    """
    profile = load_json(DATA / 'profile.json', {})
    personal = profile.get('data', {}).get('personalData', {})
    return money_value((personal.get('chargeRate') or {}).get('rawValue')) or me_number('Hourly rate')


def member_limits():
    """The member's own job filter: their answers first, the shipped starting points after.

    None of these is a number this repository gets to decide for everybody. A member
    without a single review wins nothing in a queue of forty proposals and needs no
    pay floor, a member at sixty dollars an hour loses nothing by refusing fifteen,
    and a fixed budget that is small in one country is a good week in another. So
    `/find-jobs` shows each member the starting filter once, to keep or to change,
    and this reads what they picked. `missing` names every limit that is
    switched off because the figure behind it is unknown, because a silent limit is
    worse than a loose one.
    """
    rate = member_rate()
    share = me_limit('Lowest share of your rate', None)                 # no pay floor unless they set one
    limits = {
        'rate': rate,
        'proposals': me_limit('Maximum proposals on a job', MAX_PROPOSALS),
        'fixed_floor': me_limit('Smallest project worth taking', None),
        'hourly_share': share / 100 if share else None,
        'min_rating': me_limit('Lowest client rating', MIN_CLIENT_RATING),
        'unverified': me_allows('Unverified clients', True),
        'full_time': me_allows('Full-time roles'),
    }
    limits['missing'] = [] if rate or not limits['hourly_share'] else ['hourly floor, because no rate is known']
    return limits


def max_window():
    """The oldest posting the member wants to see, in hours: their own pick, or a day."""
    return int(me_limit('Oldest posting', MAX_WINDOW) or MAX_WINDOW)


# --- the filter, set on the dashboard ------------------------------------------

# The dashboard shows the filter as seven choices and builds one line to paste after
# `/find-jobs filter`. Each key maps to the line in context/me.md that the limits
# above read. This file is the one writer of those lines outside the pickers.
FILTER_LABELS = {
    'bids': 'Maximum proposals on a job',
    'posted': 'Oldest posting',
    'full-time': 'Full-time roles',
    'rating': 'Lowest client rating',
    'unverified': 'Unverified clients',
    'hourly': 'Lowest share of your rate',
    'fixed': 'Smallest project worth taking',
}


def member_filter():
    """The saved filter in the dashboard's own words, shipped starting points included."""
    limits = member_limits()
    figure = lambda value: f'{value:g}' if value else 'none'
    return {
        'bids': figure(limits['proposals']),
        'posted': f'{max_window()}h',
        'full-time': 'show' if limits['full_time'] else 'hide',
        'rating': figure(limits['min_rating']),
        'unverified': 'show' if limits['unverified'] else 'hide',
        'hourly': f'{limits["hourly_share"] * 100:g}%' if limits['hourly_share'] else 'none',
        'fixed': figure(limits['fixed_floor']),
    }


def parse_filter(text):
    """Settings pasted from the dashboard, as {label: the words for context/me.md}.

    Every setting is checked before anything is written, and a bad one raises a
    ValueError that names it: half a filter saved is worse than none.
    """
    def number(key, value, low, high, unit=''):
        raw = re.sub(r'(hours?|h|%|\$|,)', '', value)
        try:
            found = float(raw)
        except ValueError:
            found = None
        if found is None or not low <= found <= high:
            raise ValueError(f'{key}={value} is not usable: give a number from {low:g} to {high:g}{unit}.')
        return found

    lines = {}
    for token in re.split(r'[\s,]+', text.strip()):
        if not token:
            continue
        key, sep, value = token.partition('=')
        key, value = key.lower(), value.lower()
        if not sep or not value or key not in FILTER_LABELS:
            raise ValueError(f'"{token}" is not a filter setting. The settings are: '
                             + ', '.join(f'{name}=' for name in FILTER_LABELS) + '.')
        if key in ('full-time', 'unverified'):
            if value not in ('hide', 'show'):
                raise ValueError(f'{key}={value} is not usable: write {key}=hide or {key}=show.')
            words = 'show them, marked' if (key, value) == ('unverified', 'show') else value
        elif value == 'none' and key != 'posted':
            words = 'none'
        elif key == 'bids':
            words = f'{number(key, value, 1, 1000):g}'
        elif key == 'posted':
            words = f'{number(key, value, 1, 168, " hours"):g} hours'
        elif key == 'rating':
            words = f'{number(key, value, 1, 5):g}'
        elif key == 'hourly':
            words = f'{number(key, value, 1, 100, " percent"):g}%'
        else:
            words = f'${number(key, value, 1, 100000):g}'
        lines[FILTER_LABELS[key]] = words
    if not lines:
        raise ValueError('No filter settings were given.')
    return lines


def write_filter(lines):
    """Put each setting on its own line in context/me.md, replacing the old answer."""
    text = ME.read_text(encoding='utf-8')
    today = datetime.date.today()
    stamp = f'(set on the dashboard, {today.day} {today:%B %Y})'
    missing = []
    for label, words in lines.items():
        new = f'**{label}:** {words} {stamp}'
        pattern = re.compile(rf'(?im)^\*\*{re.escape(label)}[^:\n]*:\*\*.*$')
        if pattern.search(text):
            text = pattern.sub(lambda _: new, text, count=1)
        else:
            missing.append(new)
    if missing:
        text = text.rstrip('\n') + '\n\n## Job filter\n\n' + '\n'.join(missing) + '\n'
    ME.write_text(text, encoding='utf-8')


def filter_summary():
    """The saved filter in two lines: what it cuts, what it lets through."""
    limits, cut, kept = member_limits(), [], []
    (cut if limits['proposals'] else kept).append(
        f'more than {limits["proposals"]:g} bids' if limits['proposals'] else 'any number of bids')
    cut.append(f'posted over {max_window()} hours ago')
    (kept if limits['full_time'] else cut).append('full-time roles')
    (cut if limits['min_rating'] else kept).append(
        f'clients rated under {limits["min_rating"]:g} by 3 or more freelancers' if limits['min_rating'] else 'any client rating')
    (kept if limits['unverified'] else cut).append('unverified clients, marked' if limits['unverified'] else 'unverified clients')
    (cut if limits['hourly_share'] else kept).append(
        f'hourly pay under {limits["hourly_share"] * 100:g}% of your rate' if limits['hourly_share'] else 'any hourly rate')
    (cut if limits['fixed_floor'] else kept).append(
        f'fixed price under ${limits["fixed_floor"]:g}' if limits['fixed_floor'] else 'any fixed budget')
    lines = ['Cut: ' + ' · '.join(cut), 'Kept: ' + (' · '.join(kept) or 'everything else')]
    return lines + [f'LIMIT OFF: {name}' for name in limits['missing']]


def cmd_filter(args):
    """Save a filter pasted from the dashboard, then print the saved filter either way."""
    settings = ' '.join(args.settings)
    if settings.strip():
        try:
            lines = parse_filter(settings)
        except ValueError as problem:
            print(f'{problem} Nothing was saved.', file=sys.stderr)
            return 2
        if not ME.is_file():
            print('context/me.md is missing, so the filter has nowhere to live. Run /about-me first.', file=sys.stderr)
            return 2
        write_filter(lines)
    print('\n'.join(filter_summary()))
    return 0


# --- window -----------------------------------------------------------------

def last_search():
    """When this account last searched, from the stamp `clean` leaves behind."""
    return parse_time(load_json(LAST_SEARCH, {}).get('at'))


def record_search():
    """Stamp this run, so the next one asks for the hours since it and no more."""
    DATA.mkdir(exist_ok=True)
    LAST_SEARCH.write_text(json.dumps({'at': now().isoformat()}, indent=2), encoding='utf-8')


def search_window_hours():
    """The hours to look back: since the last run, never past a day.

    The stamp is the honest source, because a run that found nothing still covered
    its hours. The newest saved lead is the fallback for an account whose stamp was
    never written, and 24 hours the fallback for a first run. The floor is small on
    purpose: searching four times a day should cost four small windows, not four
    overlapping ten-hour ones.
    """
    stamp = last_search()
    if stamp:
        hours = (now() - stamp).total_seconds() / 3600
        return int(max(RUN_FLOOR, min(max_window(), round(hours + 0.5))))
    raw = load_json(jobs_file(), [])
    stamps = [parse_time(j.get('found_at')) for j in raw if j.get('found_at')]
    stamps = [s for s in stamps if s]
    hours = 24 if not stamps else (now() - max(stamps)).total_seconds() / 3600
    return int(min(max_window(), max(MIN_WINDOW, round(hours + 0.5))))


def cmd_window(args):
    """Hours since the newest job in the pipeline, between 10 and 72.

    Ten hours is the floor because a job older than that already has a day of
    proposals on it. The window stretches to cover the gap since the last run, so
    skipping a weekend never leaves a hole nobody sees.
    """
    print(search_window_hours())
    return 0


def member_search_themes():
    try:
        text = ME.read_text(encoding='utf-8')
    except OSError:
        return []
    match = re.search(r'(?ms)^## Job search tracks\s*\n(.*?)(?=^## |\Z)', text)
    if not match:
        return []
    themes = []
    for line in match.group(1).splitlines():
        if not line.startswith('- ') or not line[2:].strip():
            continue
        item = line[2:].strip()
        if ':' in item:
            label, raw_terms = (part.strip() for part in item.split(':', 1))
            # Older runs put a dated verdict in parentheses beside the terms.
            # It is a decision about the theme, never part of a search query.
            raw_terms = re.sub(r'\s*\([^)]*\)', '', raw_terms)
            terms = [term.strip() for term in re.split(r'\s*[·|]\s*', raw_terms) if term.strip()]
        else:
            label, terms = item, [item]
        if label and terms:
            slug = re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')
            themes.append({'label': label, 'slug': slug, 'terms': terms, 'query': ', '.join(terms)})
    return themes


def source_matches_theme(source, theme):
    """Match current query slugs and the older per-term search file names."""
    source = str(source or '').lower()
    if not source.startswith(('query-', 'title-', 'search-')):
        return False
    source = re.sub(r'^(?:query|title|search)-', '', source)
    source_key = re.sub(r'[^a-z0-9]+', '', source)
    keys = [theme.get('slug', '')] + theme.get('terms', [])
    return source_key in {re.sub(r'[^a-z0-9]+', '', str(key).lower()) for key in keys}


def query_performance(themes):
    """Observed downstream outcomes for saved leads, grouped by search theme."""
    jobs = load_json(jobs_file(), [])
    performance = []
    for theme in themes:
        matched = [job for job in jobs if any(source_matches_theme(source, theme)
                   for source in job.get('found_via', []))]
        applied = [job for job in matched if job.get('applied_at') or
                   job.get('status') in ('applied', 'replied', 'call', 'offer', 'won')]
        conversations = [job for job in matched if job.get('status') in ('replied', 'call', 'offer', 'won')]
        won = [job for job in matched if job.get('status') == 'won']
        skipped = [job for job in matched if job.get('status') == 'skipped']
        reasons = {}
        for job in skipped:
            for reason in re.findall(r'not a fit:\s*([^.]*(?:\.|$))', job.get('notes') or '', re.I):
                reason = reason.strip().rstrip('.')
                if reason:
                    reasons[reason] = reasons.get(reason, 0) + 1
        performance.append({
            'label': theme['label'],
            'saved': len(matched),
            'applied': len(applied),
            'conversations': len(conversations),
            'won': len(won),
            'skipped': len(skipped),
            'not_fit_reasons': [{'reason': reason, 'count': count}
                                for reason, count in sorted(reasons.items(), key=lambda item: (-item[1], item[0]))[:3]],
        })
    return performance


def cmd_rules(args):
    """The live search and ranking contract, for people and the cockpit."""
    themes = member_search_themes()
    _LIMITS = member_limits()
    print(json.dumps({
        'tracks': [theme['label'] for theme in themes],
        'themes': themes,
        'query_mode': 'Semantic match across the job title and description',
        'performance': query_performance(themes),
        'performance_scope': 'Downstream outcomes for saved leads only. Upwork retrieval totals are not retained.',
        'window_hours': search_window_hours(),
        'window_bounds': [RUN_FLOOR, max_window()],
        'sources': ['Upwork recommendations', 'Semantic search themes'],
        'filters': ['Already applied', 'Already in the pipeline', f'Posted more than {max_window()} hours ago',
                    *([] if _LIMITS['unverified'] else ['Unverified payment']),
                    *([] if _LIMITS['full_time'] else ['Full-time role']),
                    *([f'More than {_LIMITS["proposals"]:g} proposals'] if _LIMITS['proposals'] else []),
                    *([f'Client rated under {_LIMITS["min_rating"]:g} by at least 3 freelancers']
                      if _LIMITS['min_rating'] else []),
                    *([f'Fixed price under ${_LIMITS["fixed_floor"]:g}'] if _LIMITS['fixed_floor'] else []),
                    *([f'Hourly top under {int(_LIMITS["hourly_share"] * 100)}% of the member rate']
                      if _LIMITS['hourly_share'] else [])],
        'ranking': [
            {'label': 'Similarity', 'points': 10,
             'uses': 'How close the job is to what the member does: 7 for a service they sell, '
                     'plus one each for their main offer, tools they use, and a result or sample '
                     'project like it. Client, competition and budget stay out of the number.'},
        ],
        'gate': {'fit': FIT_GATE, 'score': MIN_SCORE, 'trap_cap': TRAP_CAP},
    }, ensure_ascii=False))
    return 0


# --- candidates -------------------------------------------------------------

def normalize(job, track):
    c = job.get('client') or {}
    proposals = job.get('proposal_count')
    return {
        'id': str(job.get('id')),
        'title': clean(job.get('title')),
        'url': job.get('url'),
        'posted_date': job.get('published_date') or job.get('created_date'),
        'found_via': [track],
        'budget': job.get('budget') or job.get('hourly_budget_type') or '',
        'job_type': job.get('job_type'),
        'engagement': job.get('engagement'),
        'duration': job.get('duration'),
        'experience_level': job.get('experience_level'),
        'skills': job.get('skills') or [],
        'snippet': clean(job.get('description_snippet'))[:400],
        'proposals': proposals if proposals is not None else job.get('proposals_tier'),
        'applied': bool(job.get('applied')),
        'client': {
            'country': c.get('country'), 'rating': c.get('rating'), 'reviews': c.get('total_reviews'),
            'spent': money_value(c.get('total_spent')), 'posted_jobs': c.get('total_posted_jobs'),
            'hires': c.get('total_hires'), 'verified': (c['verification_status'] == 'VERIFIED'
                         if c.get('verification_status') in ('VERIFIED', 'UNVERIFIED') else None),
        },
    }


def recency_points(posted, window_hours):
    t = parse_time(posted)
    if not t:
        return None
    age = (now() - t).total_seconds() / 3600
    if age > window_hours:
        return None
    return max(0, min(10, round(10 * (1 - age / window_hours))))


def budget_top(job):
    """The highest number the posting states, and whether it is an hourly figure."""
    budget = str(job.get('budget') or '')
    values = numbers(budget)
    hourly = '/hr' in budget or job.get('job_type') == 'hourly'
    return (max(values) if values else None), hourly


def disqualified(job, limits):
    """The short list of hard no's. A reason, or None when the posting stays in.

    Points are for ranking what could be applied to. These are the cases where no
    score should be computed at all, because no fit saves them: the client cannot
    pay, the posting is an employment ad, the queue is too long to be worth
    Connects, or the money is below what the member said they work for. Every one
    of them is also a search filter, so this is the net under the filters, not a
    second opinion.
    """
    c = job.get('client') or {}
    if not c.get('verified') and not limits['unverified']:
        return 'unverified payment'
    if str(job.get('engagement') or '').upper() == 'FULL_TIME' and not limits['full_time']:
        return 'full-time role, not a project'
    proposals = job.get('proposals')
    if limits['proposals'] and isinstance(proposals, (int, float)) and proposals > limits['proposals']:
        return f'{int(proposals)} proposals, over your cap of {limits["proposals"]:g}'
    # Search rows carry a tier ("20 to 50", "50+", "Fewer than 5"), not a count.
    # A tier is over the cap when even its low end reaches the cap and it runs past it.
    if limits['proposals'] and isinstance(proposals, str):
        bounds = numbers(proposals)
        low = 0 if 'fewer' in proposals.lower() else (bounds[0] if bounds else None)
        high = float('inf') if '+' in proposals else (bounds[-1] if bounds else None)
        if low is not None and low >= limits['proposals'] and high > limits['proposals']:
            return f'{proposals} proposals, over your cap of {limits["proposals"]:g}'
    rating, reviews = c.get('rating'), c.get('total_reviews')
    if limits['min_rating'] and rating is not None and rating < limits['min_rating'] and (reviews or 0) >= 3:
        return f'client rated {rating} by freelancers'
    top, hourly = budget_top(job)
    if top is not None:
        rate = limits['rate']
        if hourly and rate and limits['hourly_share'] and top < limits['hourly_share'] * rate:
            return f'pays {top:g} against your rate of {rate:g}'
        if not hourly and limits['fixed_floor'] and top < limits['fixed_floor']:
            return f'fixed budget of {top:g} under your floor of {limits["fixed_floor"]:g}'
    return None


def similarity(verdict):
    """How close a job is to what the member does, out of ten, with the checks behind it.

    One number, one meaning (12.10.2026). A job that is a service the member sells is a
    7. Each of three checks adds one: it is their main offer, it names tools they use,
    they have a result or sample project like it. A job that is not their service stays
    under the gate. Before this the number was Claude's fit with points shaved for the
    client and the pay, and nobody could say why an 8 was an 8.

    An entry written the old way, with a `fit` and no service answer, is read as it was.
    """
    if 'service' not in verdict and not isinstance(verdict.get('checks'), dict):
        try:
            return max(0, min(10, int(verdict.get('fit', 0)))), None
        except (TypeError, ValueError):
            return 0, None
    answers = verdict.get('checks') if isinstance(verdict.get('checks'), dict) else {}
    checks = {name: bool(answers.get(name)) for name in CHECKS}
    if not verdict.get('service'):
        return FIT_GATE - 1, checks
    return SERVICE_SCORE + sum(checks.values()), checks


def doubts(job, limits):
    """What a member would hold against a job they otherwise want, as short reasons.

    These never move the score. The dashboard uses them to colour the client and the
    budget column, where the member weighs them for themselves.

    A client with no history and an hourly post with no range are not doubts: the
    first is every new client, which is where a new freelancer wins, and the second
    is simply how many hourly jobs are posted. Pay counts against a job only where
    the member set a floor for it.
    """
    out = []
    c = job.get('client') or {}
    rate = limits['rate']
    if c.get('hires') == 0 and (c.get('posted_jobs') or 0) >= 2:
        out.append('has posted before and never hired')
    if not c.get('verified'):
        out.append('payment not verified yet: start nothing before it is')
    top, hourly = budget_top(job)
    if top is not None and hourly and rate and limits['hourly_share'] and top < rate:
        out.append(f'tops out under your rate ({top:g} against {rate:g})')
    elif top is not None and not hourly and limits['fixed_floor'] and top < 2 * limits['fixed_floor']:
        out.append(f'small fixed budget ({top:g})')
    return out


# How many different postings a run reads before it picks its ten.
POOL_FLOOR = 100


def cmd_candidates(args):
    limits = member_limits()
    rate = limits['rate']
    merged, dropped, pool = {}, collections.Counter(), set()
    for f in args.files:
        track = pathlib.Path(f).stem
        for job in load_json(f, {}).get('jobs', []):
            n = normalize(job, track)
            pool.add(n['id'])
            if n['id'] in merged:
                merged[n['id']]['found_via'].append(track)
                continue
            if n['applied']:
                dropped['already applied'] += 1
                continue
            rec = recency_points(n['posted_date'], args.window_hours)
            if rec is None:
                dropped['outside window'] += 1
                continue
            no = disqualified(n, limits)
            if no:
                dropped[no] += 1
                continue
            n.update(recency=rec, deduction=0, deduction_reasons=doubts(n, limits))
            merged[n['id']] = n
    known = set()
    if merged:
        out = pipeline('add', '--check', *merged)
        known = {line.split()[-1] for line in out.stdout.splitlines() if line.startswith('KNOWN')}
    fresh = [j for j in merged.values() if j['id'] not in known]
    DATA.mkdir(exist_ok=True)
    CANDIDATES.write_text(json.dumps(fresh, indent=2, ensure_ascii=False), encoding='utf-8')
    for j in sorted(fresh, key=lambda j: j['recency'], reverse=True):
        c = j['client']
        print(f'{j["id"]}  {j["title"][:70]}')
        print(f'    via {",".join(j["found_via"])} · {j["budget"] or "no budget"} · {j["engagement"] or ""} · '
              f'proposals {j["proposals"]} · client {c["rating"] or "unrated"}, '
              f'${c["spent"] or 0:,.0f} spent · {j["recency"]}/10 fresh')
        print(f'    doubts: {"; ".join(j["deduction_reasons"]) or "none"}')
        print(f'    {j["snippet"][:220]}')
    for off in limits['missing']:
        print(f'LIMIT OFF: {off}')
    gone = ', '.join(f'{v} {k}' for k, v in dropped.most_common()) or 'none'
    print(f'\n{len(fresh)} new candidate(s), {len(known)} already in the pipeline, dropped: {gone}.')
    # Ten good leads come out of a wide pool, not out of the first thirty rows.
    short = '' if len(pool) >= POOL_FLOOR else f': below the floor of {POOL_FLOOR}, so widen the search before scoring'
    print(f'POOL {len(pool)} different posting(s) read{short}.')
    print(f'Next: answer the service question and the three checks for each in data/fit.json, then run score. '
          f'The doubts above colour the dashboard and never move the score; the gate is {MIN_SCORE}.')
    return 0


# --- score ------------------------------------------------------------------

def grade(total):
    """Kept so older records still render: the score has been the member's number since
    the scale became 0 to 10, and there is nothing left to translate."""
    return total


def record_rejections(ranked, kept, minimum):
    """Write one line per candidate the gate turned down, with the numbers behind it.

    The member never sees this step and never types anything for it. It is the half
    of the record that costs nothing: thirty labelled no's per run against the two or
    three yes's that reach the pipeline.
    """
    kept_ids = {record['id'] for record in kept}
    today = datetime.date.today().isoformat()
    lines = []
    for total, niche, candidate, verdict in ranked:
        if candidate['id'] in kept_ids:
            continue
        lines.append(json.dumps({
            'at': today,
            'id': candidate['id'],
            'title': candidate.get('title', ''),
            'found_via': candidate.get('found_via', ''),
            'decision': 'gate',
            'failed': 'fit' if niche < FIT_GATE else 'score',
            'score': total,
            'grade': grade(total),
            'niche_fit': niche,
            'deduction': candidate.get('deduction') or 0,
            'deduction_reasons': candidate.get('deduction_reasons') or [],
            'recency': candidate['recency'],
            'reason': (verdict.get('trap') or verdict.get('rationale', ''))[:300],
        }, ensure_ascii=False))
    if not lines:
        return 0
    DATA.mkdir(parents=True, exist_ok=True)
    with DECISIONS.open('a', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
    return len(lines)


def cmd_score(args):
    candidates = load_json(CANDIDATES, [])
    fit = load_json(FIT, {})
    missing = [c['id'] for c in candidates if c['id'] not in fit]
    if missing:
        print(f'ABORT: no niche fit in data/fit.json for {len(missing)} candidate(s): {", ".join(missing[:5])}',
              file=sys.stderr)
        return 1
    ranked, logged = [], []
    for c in candidates:
        f = fit[c['id']]
        niche, checks = similarity(f)
        total = niche
        # A named trap caps the score: a disguised full-time or operator role is not
        # the member's service, however the posting words it.
        if f.get('trap'):
            total = min(total, TRAP_CAP)
        ranked.append((total, niche, c, f))
        if niche >= FIT_GATE and total >= args.min:
            record = {k: c[k] for k in ('id', 'title', 'url', 'posted_date', 'found_via', 'budget',
                                         'job_type', 'engagement', 'skills', 'proposals', 'client')}
            # The doubts ride along for the dashboard's colours; nothing is taken off for them.
            record.update(score=total, grade=grade(total), niche_fit=niche, recency=c['recency'],
                          deduction=0, deduction_reasons=c.get('deduction_reasons') or [],
                          checks=checks,
                          rationale=f.get('rationale', ''), summary=f.get('summary', c['snippet'][:280]),
                          headline=f.get('headline', ''), trap=f.get('trap'))
            logged.append(record)
    if logged:
        out = pipeline('add', '--file', '-', stdin=json.dumps(logged))
        if out.returncode:
            print(out.stderr, file=sys.stderr)
            return 1
    # Four scores are possible, so ties are the rule: the freshest posting leads each.
    for total, niche, c, f in sorted(ranked, key=lambda r: (r[0], r[2].get('recency') or 0), reverse=True):
        mark = 'LOGGED' if any(r['id'] == c['id'] for r in logged) else 'skip  '
        why = f.get('trap') or f.get('rationale', '')
        _, checks = similarity(f)
        ticks = ', '.join(name.replace('_', ' ') for name in CHECKS if (checks or {}).get(name)) or 'no extra checks'
        print(f'{mark} {total:2d}/10 ({ticks})  {c["title"][:60]}  · {why[:90]}')
    turned_down = record_rejections(ranked, logged, args.min)
    print(f'\n{len(logged)} of {len(ranked)} logged (score at least {args.min}: a service you sell).')
    if turned_down:
        print(f'{turned_down} rejection(s) recorded in {DECISIONS.name}: what the gate says no to, '
              f'and why. `python3 code/learn.py report` reads them.')
    return 0


def cmd_reassess(args):
    """Apply one fit decision rewritten after reading the full posting."""
    fit = load_json(FIT, {}).get(args.job_id)
    job = next((j for j in load_json(jobs_file(), []) if str(j.get('id')) == args.job_id), None)
    if not isinstance(fit, dict) or not job:
        print(f'ABORT: job {args.job_id} needs both a pipeline record and data/fit.json entry.', file=sys.stderr)
        return 1
    if 'service' not in fit and 'fit' not in fit:
        print(f'ABORT: job {args.job_id} needs the service answer and the three checks in data/fit.json.', file=sys.stderr)
        return 1
    niche, checks = similarity(fit)
    total = niche
    if fit.get('trap'):
        total = min(total, TRAP_CAP)
    assessment = {
        'niche_fit': niche,
        'score': max(0, min(100, total)),
        'rationale': fit.get('rationale') or '',
        'summary': fit.get('summary') or job.get('summary') or '',
        'headline': fit.get('headline') or job.get('headline') or '',
        'trap': fit.get('trap') or '',
    }
    if checks is not None:
        assessment['checks'] = checks
    out = pipeline('assess', args.job_id, '--file', '-', stdin=json.dumps(assessment))
    if out.returncode:
        print(out.stderr, file=sys.stderr)
        return 1
    print(out.stdout.strip())
    if niche < FIT_GATE or total < MIN_SCORE:
        # The same prefix the member writes by hand. query_performance counts a
        # reason only when it carries it, so an automatic skip without the prefix
        # is a lead removed and a lesson lost.
        reason = fit.get('trap') or 'full posting does not meet the search gate'
        moved = pipeline('set', args.job_id, 'skipped', '--note', f'not a fit: {reason}')
        if moved.returncode:
            print(moved.stderr, file=sys.stderr)
            return 1
        print(moved.stdout.strip())
    return 0


# --- detail -----------------------------------------------------------------

def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            hit = find_key(v, key)
            if hit is not None:
                return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = find_key(v, key)
            if hit is not None:
                return hit
    return None


def member_standing():
    """Your numbers the client's minimums are compared against."""
    profile = load_json(DATA / 'profile.json', {})
    agg = profile.get('profileAggregates') or profile.get('data', {}).get('profileAggregates') or {}
    me = (ROOT / 'context' / 'me.md')
    jss = None
    if me.is_file():
        m = re.search(r'Job Success Score:\*\*\s*(\d+)', me.read_text(encoding='utf-8'))
        jss = int(m.group(1)) if m else None
    return {'earnings': money_value(agg.get('totalEarnings')), 'jss': jss}


def clean_brief(raw):
    brief = find_key(raw, 'brief')
    if not isinstance(brief, dict):
        return None
    outcome = clean(brief.get('outcome')) if isinstance(brief.get('outcome'), str) else ''
    scope = [clean(item) for item in (brief.get('scope') if isinstance(brief.get('scope'), list) else []) if isinstance(item, str) and clean(item)]
    requirements = [clean(item) for item in (brief.get('requirements') if isinstance(brief.get('requirements'), list) else [])
                    if isinstance(item, str) and clean(item)]
    return {k: v for k, v in {'outcome': outcome, 'scope': scope, 'requirements': requirements}.items() if v}


def cmd_detail(args):
    raw = load_json(args.file, {})
    activity = find_key(raw, 'jobActivity') or {}
    bids = find_key(raw, 'applicationsBidStats') or {}
    quals = find_key(raw, 'preferred_qualifications') or {}
    terms = find_key(raw, 'contractTerms') or {}
    company = find_key(raw, 'clientCompanyPublic') or {}
    timezone = find_key(company, 'timezone')
    details = {
        'experience_level': find_key(terms, 'experienceLevel'),
        'engagement_type': find_key(terms, 'engagementType'),
        'client_city': find_key(company, 'city'),
        'client_timezone': timezone if isinstance(timezone, str) else None,
        'connects_cost': find_key(raw, 'connects_cost'),
        'can_apply': find_key(raw, 'can_apply'),
        'total_hired': activity.get('totalHired'),
        'invites_sent': activity.get('invitesSent'),
        'interviewing': activity.get('totalInvitedToInterview'),
        'offers': activity.get('totalOffered'),
        'bid_avg': money_value(bids.get('avgRateBid')), 'bid_min': money_value(bids.get('minRateBid')),
        'bid_max': money_value(bids.get('maxRateBid')),
        'min_jss': quals.get('min_job_success_score'), 'min_earnings': quals.get('min_earnings'),
        'client_record': find_key(raw, 'client_record'),
        'description': clean(find_key(raw, 'description') if isinstance(find_key(raw, 'description'), str) else ''),
        'brief': clean_brief(raw),
    }
    details = {k: v for k, v in details.items() if v not in (None, '', {})}
    out = pipeline('detail', args.job_id, '--file', '-', stdin=json.dumps(details))
    if out.returncode:
        print(out.stderr, file=sys.stderr)
        return 1
    current = next((job for job in load_json(jobs_file(), []) if str(job.get('id')) == args.job_id), {})
    if details.get('can_apply') is False and current.get('status') == 'new':
        pipeline('set', args.job_id, 'skipped', '--note', 'Upwork says you cannot apply')
        print(f'{args.job_id}: skipped, Upwork says you cannot apply')
        return 0
    # A posting can hire more than one person. Preferred qualifications are
    # signals for a human decision, not proof that an application is forbidden.
    reasons = []
    if (details.get('total_hired') or 0) >= 1:
        reasons.append(f'{details["total_hired"]} already hired; check whether more people are needed')
    me = member_standing()
    if details.get('min_jss') and me['jss'] is not None and details['min_jss'] > me['jss']:
        reasons.append(f'wants Job Success {details["min_jss"]}, you have {me["jss"]}')
    need = money_value(details.get('min_earnings'))
    if need and me['earnings'] is not None and need > me['earnings']:
        reasons.append(f'wants {details["min_earnings"]} earned, you have ${me["earnings"]:,.0f}+')
    if reasons:
        print(f'{args.job_id}: advisory, {"; ".join(reasons)}')
    print(f'{args.job_id}: details saved. {details.get("connects_cost", "?")} Connects to apply, '
          f'{details.get("invites_sent", 0)} invites, {details.get("interviewing", 0)} interviewing, '
          f'bids average {details.get("bid_avg", "?")}.')
    return 0


# --- lessons ----------------------------------------------------------------

def cmd_lessons(args):
    """Your own past decisions: the anchors Claude scores new jobs against."""
    jobs = load_json(jobs_file(), [])
    decided = [j for j in jobs if j.get('status') != 'new']
    decided.sort(key=lambda j: j.get('status_updated_at') or '', reverse=True)
    if not decided:
        print('No decisions yet. Every job you apply to or skip becomes an anchor here.')
        return 0
    for j in decided[:args.limit]:
        note = f' · {j["notes"]}' if j.get('notes') else ''
        print(f'{j.get("status"):<8} scored {j.get("score", "?"):>3}  {j.get("title", "")[:70]}{note}')
    return 0


def cmd_clean(args):
    """Deletes this run's raw responses. Only our own scores and records stay."""
    import shutil
    gone = 0
    for name in ('search', 'details'):
        folder = DATA / name
        if folder.is_dir():
            gone += sum(1 for _ in folder.glob('*.json'))
            shutil.rmtree(folder)
    for f in (CANDIDATES, FIT):
        if f.is_file():
            f.unlink()
            gone += 1
    record_search()
    print(f'{gone} raw file(s) from this run removed. Search time stamped, so the next '
          f'run looks back only as far as this one.')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('clean')
    p.set_defaults(func=cmd_clean)
    p = sub.add_parser('window')
    p.set_defaults(func=cmd_window)
    p = sub.add_parser('rules')
    p.set_defaults(func=cmd_rules)
    p = sub.add_parser('filter')
    p.add_argument('settings', nargs='*')
    p.set_defaults(func=cmd_filter)
    p = sub.add_parser('candidates')
    p.add_argument('files', nargs='+')
    p.add_argument('--window-hours', type=float, default=MIN_WINDOW)
    p.set_defaults(func=cmd_candidates)
    p = sub.add_parser('score')
    p.add_argument('--min', type=int, default=MIN_SCORE)
    p.set_defaults(func=cmd_score)
    p = sub.add_parser('reassess')
    p.add_argument('job_id')
    p.set_defaults(func=cmd_reassess)
    p = sub.add_parser('detail')
    p.add_argument('job_id')
    p.add_argument('file')
    p.set_defaults(func=cmd_detail)
    p = sub.add_parser('lessons')
    p.add_argument('--limit', type=int, default=20)
    p.set_defaults(func=cmd_lessons)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
