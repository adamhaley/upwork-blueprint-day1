#!/usr/bin/env python3
"""Assembles the pitch page for one job: headline, walkthrough video,
reviews, background, the plan, scope, and the next step.

SEO and Google Ads jobs do not come through here at all: they get the one-page
roadmap in templates/roadmap/ as their pitch page, because a programme the member
runs the same way every time sells better as phases than as a drawing.

Pure assembly. The diagram plan and every sentence are written by Claude from the
job posting before this runs; this script checks them and fills the template.
Reviews and background come from the evidence sections of context/me.md, so the page can never claim
something the evidence sections do not hold.

    python3 code/pitch_generate.py <job_id> \\
        --hook "..." \\
        --build-lede "..." \\
        --graph jobs/<job_id>/pitch-graph.json \\
        --kickoff "..." --kickoff "..." \\
        --updates "Twice a week|Upwork, then the client's workspace" \\
        [--loom-url https://www.loom.com/share/...] [--video-length "3 minute"] \\
        --hero-illustration path [--profile-image path] [--live-artifact "Label|URL"] \\
        [--proof-link "Label|Detail|URL"] [--next-step "..."] \\
        [--theme warm|steel|signal|growth|calm] [--dither-source path]

Writes jobs/<job_id>/pitch.html. Exits 1 on anything missing or malformed: a half
page with a silent gap is worse than a stop that names the cause.
"""
import argparse
import base64
import datetime
import html
import json
import math
import pathlib
import re
import subprocess
import sys
from pipeline import jobs_dir

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import context_check
ASSETS = ROOT / 'templates' / 'pitch'
TEMPLATE = ASSETS / 'template.html'
DIAGRAM_JS = ASSETS / 'diagram.js'
LOGO_DIR = ASSETS / 'logos'
DITHER = ASSETS / 'ink-plume.png'
PIPELINE = ROOT / 'code' / 'pipeline.py'
PROOF = ROOT / 'context' / 'me.md'
ME = ROOT / 'context' / 'me.md'
VIDEOS = ROOT / 'context' / 'videos.json'
LIBRARY = ROOT / 'data' / 'pitch-library'

GRAPH_KINDS = {'source', 'step', 'sink', 'service', 'decision', 'note', 'datastore', 'milestone', 'actor'}
GRAPH_OWNERS = {'you', 'client', 'thirdparty'}
DEFAULT_NEXT = ("Send me your website or a screenshot of your current setup here on Upwork, "
                "and I'll reply with the first three things I would build.")

YT_PLAY = ('<svg viewBox="0 0 28 20" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
           '<path fill="#FF0000" d="M27.4 3.1A3.51 3.51 0 0 0 24.9.6C22.7 0 14 0 14 0S5.3 0 3.1.6'
           'A3.51 3.51 0 0 0 .6 3.1C0 5.3 0 10 0 10s0 4.7.6 6.9a3.51 3.51 0 0 0 2.5 2.5C5.3 20 14 20 14 20'
           's8.7 0 10.9-.6a3.51 3.51 0 0 0 2.5-2.5C28 14.7 28 10 28 10s0-4.7-.6-6.9z"/>'
           '<path fill="#ffffff" d="M11.2 14.29 18.5 10l-7.3-4.29z"/></svg>')

CV_ICONS = (
    '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 17l5-5 3 3 7-8"/>'
    '<path d="M14 7h5v5"/></svg>',
    '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="3"/>'
    '<path d="M8 5V3m8 2V3M8 12l2.5 2.5L16 9"/></svg>',
    '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3l2.7 5.5 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.8 1-6.1-4.4-4.3 6.1-.9L12 3z"/></svg>',
)

EVIDENCE_ICON = ('<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">'
                 '<path d="M7 12.5l3 3L17.5 8"/><circle cx="12" cy="12" r="9"/></svg>')
BACKGROUND_ICON = ('<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">'
                   '<path d="M4 7.5L12 4l8 3.5-8 3.5-8-3.5zM7 10v5.5c2.8 2 7.2 2 10 0V10"/></svg>')
LANGUAGE_ICON = ('<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">'
                 '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.5 3.7 5.5 3.7 9s-1.2 6.5-3.7 9M12 3c-2.5 2.5-3.7 5.5-3.7 9s1.2 6.5 3.7 9"/></svg>')


def abort(msg):
    print(f'ABORT: {msg}', file=sys.stderr)
    sys.exit(1)


def esc(text):
    return html.escape(str(text), quote=True)


def safe_job_title(text):
    """Client titles are data, but the generated page follows our copy rules."""
    return str(text or '').replace(chr(0x2014), '-')


def data_uri(path, mime=None):
    p = pathlib.Path(path)
    if not p.is_file():
        abort(f'media "{p}" does not exist.')
    detected = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml',
        '.mp4': 'video/mp4',
        '.webm': 'video/webm',
    }
    mime = mime or detected.get(p.suffix.lower(), 'application/octet-stream')
    return f'data:{mime};base64,{base64.b64encode(p.read_bytes()).decode("ascii")}'


def load_job(job_id):
    r = subprocess.run([sys.executable, str(PIPELINE), 'get', job_id], capture_output=True, text=True)
    if r.returncode:
        abort(r.stderr.strip() or f'job "{job_id}" is not in the pipeline.')
    return json.loads(r.stdout)


def section(text, heading):
    m = re.search(rf'^## {re.escape(heading)}[^\n]*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    return (m.group(0).split('\n', 1)[0], m.group(1)) if m else ('', '')


def bullets(block):
    return [l[2:].strip() for l in block.splitlines() if l.startswith('- ')]


def reviews(proof_text, limit):
    """Real client words from the Reviews section: - "quote" · job."""
    head, block = section(proof_text, 'Reviews')
    five = '5 star' in head.lower()
    out = []
    for line in bullets(block):
        m = re.match(r'^"(.+)"\s*·\s*(.+)$', line)
        if m:
            out.append({'quote': m.group(1), 'job': m.group(2), 'stars': five})
    # /about-me writes one "### Who" block per review: the quote on its own line, then "Job: ...".
    for who, body in re.findall(r'^### ([^\n]+)\n(.*?)(?=^### |\Z)', block, re.M | re.S):
        quote = next((l.strip() for l in body.splitlines() if l.strip().startswith('"')), '')
        job = next((l.strip()[4:].strip() for l in body.splitlines() if l.strip().startswith('Job:')), '')
        if quote.endswith('"') and len(quote) > 2:
            label = who.strip() + (f' · {re.split(r"[.,;]", job)[0]}' if job else '')
            out.append({'quote': quote[1:-1].replace('\u2014', '-'), 'job': label, 'stars': 'rating 5.0' in body.lower()})
    return out[:limit] if limit else out


def cv_block(proof_text, me_text):
    """Background from the proof and facts files. Nothing here is typed in by hand."""
    _, record = section(proof_text, 'Results')
    _, creds = section(proof_text, 'Credentials')
    parts = []
    stats = []
    for line in bullets(record)[:1]:
        for index, chunk in enumerate(line.split(',')):
            m = re.match(r'\s*(\$?[\d.,]+[KkMm]?\+?%?)\s+(.+)', chunk)
            if m:
                icon = CV_ICONS[min(index, len(CV_ICONS) - 1)]
                stats.append('<article class="cv-stat">'
                             f'<span class="cv-stat-icon">{icon}</span><div>'
                             f'<strong>{esc(m.group(1))}</strong><span>{esc(m.group(2).strip())}</span>'
                             '</div></article>')
    if stats:
        parts.append(f'<div class="cv-stats">{"".join(stats)}</div>')
    more = bullets(record)[1:]
    if more:
        parts.append('<p class="cv-sub">Track record</p><ul class="cv-list">'
                     + ''.join(f'<li><span class="cv-list-icon">{EVIDENCE_ICON}</span>'
                               f'<span>{esc(b)}</span></li>' for b in more) + '</ul>')
    if bullets(creds):
        parts.append('<p class="cv-sub">Background</p><ul class="cv-list">'
                     + ''.join(f'<li><span class="cv-list-icon">{BACKGROUND_ICON}</span>'
                               f'<span>{esc(b)}</span></li>' for b in bullets(creds)) + '</ul>')
    lang = re.search(r'\*\*Education, certificates, languages:\*\*\s*(.+)', me_text)
    if lang:
        parts.append(f'<p class="cv-lang"><span class="cv-list-icon">{LANGUAGE_ICON}</span>'
                     f'<span>{esc(lang.group(1).strip())}</span></p>')
    if not parts:
        return ''
    return ('<section class="cv" aria-label="Builder profile">'
            '<div class="cv-heading"><small>Builder profile</small>'
            '<strong>Proven experience behind your build</strong></div>'
            f'<div class="cv-body">{"".join(parts)}</div></section>')


def profile_media(path):
    """Use a member-supplied action photo, or keep an explicit neutral fallback."""
    if path:
        return ('<figure class="freelancer-photo has-photo">'
                f'<img src="{data_uri(path)}" alt="The freelancer working with a client team">'
                '<figcaption><strong>The person behind the build</strong>'
                '<span>Strategy, automation and QA</span></figcaption></figure>')
    return ('<div class="freelancer-photo" aria-label="Freelancer photo placeholder">'
            '<svg viewBox="0 0 160 190" fill="none" aria-hidden="true">'
            '<circle cx="80" cy="58" r="39" fill="currentColor"/>'
            '<path d="M22 174c4-43 25-67 58-67s54 24 58 67" fill="currentColor"/>'
            '</svg><span>Freelancer photo</span></div>')


def profile_url():
    try:
        url = context_check.field(ME.read_text(encoding='utf-8'), 'Public Upwork profile URL') or ''
        return url if re.fullmatch(r'https://(?:www\.)?upwork\.com/freelancers/[^\s]+', url) else ''
    except OSError:
        return ''


def build_graph(spec):
    try:
        if str(spec).lstrip().startswith(('{', '[')):
            source = spec
        else:
            p = pathlib.Path(spec)
            source = p.read_text(encoding='utf-8') if p.is_file() else spec
        g = json.loads(source)
    except OSError as e:
        abort(f'--graph could not be read: {e}')
    except json.JSONDecodeError as e:
        abort(f'--graph is not valid JSON: {e}')
    if not isinstance(g, dict):
        abort('--graph must be a JSON object with nodes, edges and optional groups.')
    nodes = g.get('nodes', [])
    edges = g.get('edges', [])
    groups = g.get('groups', [])
    if not isinstance(nodes, list) or not isinstance(edges, list) or not isinstance(groups, list):
        abort('--graph nodes, edges and groups must be arrays.')
    if not nodes:
        abort('--graph has no nodes.')
    if len(nodes) > 20:
        abort(f'--graph has {len(nodes)} nodes; keep the client-level plan to 20 or fewer and move implementation detail into notes.')
    if groups and len(nodes) < 2 * len(groups):
        abort(f'--graph has {len(nodes)} nodes across {len(groups)} groups. One node per phase is a '
              'numbered list; give each phase at least two steps or use fewer phases.')
    ids = set()
    for n in nodes:
        if not isinstance(n, dict):
            abort(f'each node must be an object, got: {n!r}')
        if not isinstance(n.get('id'), str) or not isinstance(n.get('label'), str):
            abort(f'node without id or label: {n}')
        n['id'], n['label'] = n['id'].strip(), n['label'].strip()
        if not n['id'] or not n['label']:
            abort(f'node without id or label: {n}')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', n['id']) or re.fullmatch(r'e\d+', n['id']):
            abort(f'node id "{n["id"]}" must use 1-64 letters, numbers, _ or - and cannot look like an edge id.')
        if len(n['label']) > 69:
            abort(f'node "{n["id"]}" label is over 69 characters, which is all the renderer draws '
                  '(three lines of 23); move the detail into its note.')
        if n['id'] in ids:
            abort(f'duplicate node id "{n["id"]}".')
        ids.add(n['id'])
        if not isinstance(n.setdefault('kind', 'step'), str) or n['kind'] not in GRAPH_KINDS:
            abort(f'unknown kind "{n["kind"]}". Allowed: {sorted(GRAPH_KINDS)}')
        if n.get('owner') is not None and (not isinstance(n['owner'], str) or n['owner'] not in GRAPH_OWNERS):
            abort(f'unknown owner "{n["owner"]}". Allowed: {sorted(GRAPH_OWNERS)}')
        if 'note' in n and (not isinstance(n['note'], str) or not n['note'].strip()):
            abort(f'node "{n["id"]}" note must be non-empty text.')
        if len(n.get('note', '')) > 800:
            abort(f'node "{n["id"]}" note is over 800 characters.')
        if 'logo' in n and (not isinstance(n['logo'], str) or not re.fullmatch(r'[a-z0-9-]+', n['logo'])):
            abort(f'node "{n["id"]}" logo must be a lowercase slug.')
        positioned = [axis in n for axis in ('x', 'y')]
        if any(positioned) and not all(positioned):
            abort(f'node "{n["id"]}" must provide both x and y, or neither.')
        if all(positioned) and any(isinstance(n[axis], bool) or not isinstance(n[axis], (int, float))
                                   or not math.isfinite(n[axis]) for axis in ('x', 'y')):
            abort(f'node "{n["id"]}" x and y must be finite numbers.')

    pairs = set()
    linked = set()
    adjacency = {node_id: [] for node_id in ids}
    indegree = {node_id: 0 for node_id in ids}
    for e in edges:
        if not isinstance(e, dict):
            abort(f'each edge must be an object, got: {e!r}')
        for side in ('from', 'to'):
            if not isinstance(e.get(side), str) or e[side] not in ids:
                abort(f'edge points at unknown node "{e.get(side)}".')
        pair = (e['from'], e['to'])
        if pair[0] == pair[1]:
            abort(f'node "{pair[0]}" cannot connect to itself.')
        if pair in pairs:
            abort(f'duplicate edge "{pair[0]}" to "{pair[1]}".')
        pairs.add(pair)
        linked.update(pair)
        adjacency[pair[0]].append(pair[1])
        indegree[pair[1]] += 1
        if 'dashed' in e and not isinstance(e['dashed'], bool):
            abort(f'edge "{pair[0]}" to "{pair[1]}" dashed must be true or false.')
        if 'label' in e and (not isinstance(e['label'], str) or not e['label'].strip()
                             or len(e['label']) > 48):
            abort(f'edge "{pair[0]}" to "{pair[1]}" label must be 1-48 characters.')
        if 'label' in e:
            e['label'] = e['label'].strip()

    if len(nodes) > 1:
        isolated = sorted(ids - linked)
        if isolated:
            abort(f'disconnected node "{isolated[0]}"; connect it or remove it from the client flow.')

    # The layout and one-shot playback both rely on a forward-moving plan.
    # Reject a loop here instead of silently drawing it in an arbitrary rank.
    ready = [node_id for node_id, degree in indegree.items() if degree == 0]
    visited = 0
    while ready:
        node_id = ready.pop()
        visited += 1
        for target in adjacency[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    if visited != len(nodes):
        abort('--graph contains a cycle; this client-level plan must move forward without loops.')

    grouped = set()
    group_labels = set()
    for grp in groups:
        if not isinstance(grp, dict) or not isinstance(grp.get('label'), str) or not grp['label'].strip():
            abort(f'group without label: {grp}')
        grp['label'] = grp['label'].strip()
        if len(grp['label']) > 60:
            abort(f'group label "{grp["label"]}" is over 60 characters.')
        if grp['label'] in group_labels:
            abort(f'duplicate group label "{grp["label"]}".')
        group_labels.add(grp['label'])
        members = grp.get('nodes') or []
        if not isinstance(members, list) or not members:
            abort(f'group "{grp["label"]}" must name at least one node.')
        for nid in members:
            if not isinstance(nid, str) or nid not in ids:
                abort(f'group "{grp["label"]}" names unknown node "{nid}".')
            if nid in grouped:
                abort(f'node "{nid}" belongs to more than one group.')
            grouped.add(nid)
    data = json.dumps({'nodes': nodes, 'edges': edges, 'groups': groups},
                      ensure_ascii=False)
    fallback = '\n            '.join(f'<li>{esc(n["label"])}</li>' for n in nodes)
    return data, fallback


def logos_json(nodes):
    """Only the logos this graph names, not all of them."""
    out = {}
    for slug in sorted({n.get('logo') for n in nodes if n.get('logo')}):
        f = LOGO_DIR / f'{slug}.svg'
        if not f.is_file():
            print(f'  note: no logo "{slug}", the node shows its shape only.', file=sys.stderr)
            continue
        inner = re.sub(r'^.*?<svg[^>]*>|</svg>\s*$', '', f.read_text(encoding='utf-8'), flags=re.S)
        out[slug] = re.sub(r'<title>.*?</title>', '', inner, flags=re.S).strip()
    return json.dumps(out, ensure_ascii=False)


def videos_block():
    """Your own videos from context/videos.json: [{"id", "title", "thumb"}], thumbs beside it."""
    if not VIDEOS.is_file():
        return '', ''
    cfg = json.loads(VIDEOS.read_text(encoding='utf-8'))
    cards = []
    for v in cfg.get('videos', []):
        thumb = VIDEOS.parent / v.get('thumb', '')
        img = f'<img src="{data_uri(thumb, "image/jpeg")}" alt="{esc(v["title"])}">' if thumb.is_file() else ''
        cards.append(f'<a class="yt-card" href="https://www.youtube.com/watch?v={esc(v["id"])}" '
                     f'target="_blank" rel="noopener"><span class="yt-thumb">{img}'
                     f'<span class="pin">{YT_PLAY}</span></span><p>{esc(v["title"])}</p></a>')
    return '\n        '.join(cards), cfg.get('channel', '')


def keep_or_strip(page, name, keep):
    start, end = f'<!-- {name}:start -->', f'<!-- {name}:end -->'
    if start not in page or end not in page:
        abort(f'template lost its {name} markers.')
    if keep:
        return page.replace(start, '').replace(end, '')
    return re.sub(re.escape(start) + '.*?' + re.escape(end), '', page, flags=re.S)


def split_label(raw, parts, flag):
    bits = [b.strip() for b in raw.split('|')]
    if len(bits) != parts or not all(bits):
        abort(f'{flag} needs {parts} parts split by |, got: {raw!r}')
    return bits


def updates_html(text):
    cadence, platform = split_label(text, 2, '--updates')
    return ('<dl class="work-details">'
            f'<div><dt>Cadence</dt><dd>{esc(cadence)}</dd></div>'
            f'<div><dt>Platform</dt><dd>{esc(platform)}</dd></div>'
            '</dl>')


def plan_cards(kickoff, updates, outcomes, images, job_title):
    """Render the short client journey: onboarding, then updates."""
    labels = ['Onboarding', 'Updates']
    defaults = ['Turn the scope into one build plan', 'Always know what is done and next']
    outcomes = outcomes or defaults
    if len(outcomes) != len(labels):
        abort(f'exactly {len(labels)} --plan-outcome values expected, got {len(outcomes)}.')
    if images and len(images) != len(labels):
        abort(f'exactly {len(labels)} --plan-image values expected, got {len(images)}.')

    bodies = ['<ul class="scope-list">'
              + ''.join(f'<li>{esc(item)}</li>' for item in kickoff)
              + '</ul>',
              updates_html(updates)]

    cards = []
    for index, (label, outcome, body) in enumerate(zip(labels, outcomes, bodies), 1):
        media = ''
        if images:
            src = data_uri(images[index - 1])
            media = (f'<div class="plan-media"><img src="{src}" '
                     f'alt="{esc(label)} for {esc(safe_job_title(job_title))}"></div>')
        cards.append(
            '<article class="plan-item">'
            f'{media}<div class="plan-copy"><span class="plan-step">{index:02d}</span>'
            f'<p class="plan-outcome">{esc(outcome)}</p>'
            f'<p class="plan-label">{esc(label)}</p>{body}</div></article>'
        )
    return ''.join(cards)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('job_id')
    ap.add_argument('--hook', required=True, help='the one headline, unmistakably about this job')
    ap.add_argument('--build-lede', required=True, help='one job-specific sentence explaining the proposed flow')
    ap.add_argument('--graph', required=True, help='the plan as JSON, or a path to it')
    ap.add_argument('--kickoff', action='append', required=True)
    ap.add_argument('--updates', required=True, help='"cadence|platform" for client updates')
    ap.add_argument('--plan-outcome', action='append', default=[],
                    help='job-specific benefit headline for each working-together card')
    ap.add_argument('--plan-image', action='append', default=[],
                    help='job-specific image for each working-together card')
    ap.add_argument('--loom-url', default='')
    ap.add_argument('--video-length', default='3 minute')
    ap.add_argument('--hero-illustration', default='',
                    help='16:9 image of the project or finished outcome. Draw one with '
                         'code/proposal_illustrate.py when KIE_AI_API_KEY is set; without '
                         'it the pitch is built without a hero image')
    ap.add_argument('--profile-image', default='', help='member-supplied action photo for the proof section')
    ap.add_argument('--theme', choices=('warm', 'steel', 'signal', 'growth', 'calm'), default='warm')
    ap.add_argument('--dither-source', default='',
                    help='high-contrast industry artwork used by the moving dither field')
    ap.add_argument('--live-artifact', action='append', default=[], help='"Label|URL" of something already built')
    ap.add_argument('--proof-link', default='', help='"Label|Detail|URL" of past work, no contact details on it')
    ap.add_argument('--next-step', default=DEFAULT_NEXT)
    ap.add_argument('--max-reviews', type=int, default=3)
    ap.add_argument('--out')
    args = ap.parse_args(argv)

    job = load_job(args.job_id)
    proof_text = (context_check.proof_only(PROOF.read_text(encoding='utf-8'))
                  if PROOF.is_file() else '')
    me_text = ME.read_text(encoding='utf-8') if ME.is_file() else ''
    diagram_data, diagram_fallback = build_graph(args.graph)
    url = profile_url()

    dither_path = pathlib.Path(args.dither_source) if args.dither_source else DITHER
    if args.dither_source and not dither_path.is_file():
        abort(f'dither source "{dither_path}" does not exist.')
    dither = data_uri(dither_path) if dither_path.is_file() else ''
    dither_fit = '1.05' if args.dither_source else ''
    # A named file that is missing is still an error: the member asked for a picture
    # and did not get one. No picture asked for is not an error.
    hero_art = ''
    if args.hero_illustration:
        illustration_path = pathlib.Path(args.hero_illustration)
        if not illustration_path.is_file():
            abort(f'hero illustration "{illustration_path}" does not exist.')
        illustration_src = data_uri(illustration_path)
        hero_art = (f'<div class="hero-art" data-settle><img src="{illustration_src}" '
                    f'alt="Illustration of the proposed outcome for {esc(safe_job_title(job.get("title")))}"></div>')

    live = ''
    if args.live_artifact:
        items = []
        for raw in args.live_artifact:
            label, link = split_label(raw, 2, '--live-artifact')
            items.append(f'<li><a href="{esc(link)}" target="_blank" rel="noopener">{esc(label)}'
                         f'<span class="arrow" aria-hidden="true">&rarr;</span></a></li>')
        live = ('<div class="live-artifacts"><p class="live-lede">Already built, not just drawn. '
                f'Open it yourself:</p><ul>{"".join(items)}</ul></div>')

    proof_link = ''
    if args.proof_link:
        label, detail, link = split_label(args.proof_link, 3, '--proof-link')
        proof_link = (f'<a class="proof-link" href="{esc(link)}" target="_blank" rel="noopener">'
                      f'<span class="proof-copy"><strong>{esc(label)}</strong><span>{esc(detail)}</span></span>'
                      '<span class="arrow" aria-hidden="true">→</span></a>')

    found = reviews(proof_text, args.max_reviews)
    if found:
        reviews_html = '<div class="testimonials">' + ''.join(
            f'<div class="testimonial"><p class="quote">"{esc(r["quote"])}"</p><p class="meta">'
            + (f'<span class="stars">★★★★★</span>' if r['stars'] else '')
            + f'<span class="job">{esc(r["job"])}</span></p></div>' for r in found) + '</div>'
    else:
        reviews_html = ''

    videos, channel = videos_block()
    footer = [f'<a href="{esc(url)}" target="_blank" rel="noopener">Upwork profile</a>'] if url else []
    if channel:
        footer.append(f'<a href="{esc(channel)}" target="_blank" rel="noopener">YouTube</a>')

    page = TEMPLATE.read_text(encoding='utf-8')
    page = keep_or_strip(page, 'videos', bool(videos))

    nodes = json.loads(diagram_data)['nodes']
    js = DIAGRAM_JS.read_text(encoding='utf-8').replace('{{LOGOS_JSON}}', logos_json(nodes))
    fills = {
        '{{BODY_CLASS}}': '' if args.loom_url else 'no-video',
        '{{JOB_TITLE}}': esc(safe_job_title(job.get('title'))),
        '{{THEME}}': args.theme,
        '{{HOOK}}': esc(args.hook),
        '{{BUILD_LEDE}}': esc(args.build_lede),
        '{{HERO_ART}}': hero_art,
        '{{LOOM_URL}}': esc(args.loom_url or '#'),
        '{{VIDEO_LENGTH}}': esc(args.video_length),
        '{{PROFILE_MEDIA}}': profile_media(args.profile_image),
        '{{CV_BLOCK}}': cv_block(proof_text, me_text),
        '{{PLAN_CARDS}}': plan_cards(args.kickoff, args.updates,
                                     args.plan_outcome, args.plan_image, job.get('title')),
        '{{LIVE_ARTIFACTS}}': live,
        '{{PROOF_LINK}}': proof_link,
        '{{TESTIMONIALS_BLOCK}}': reviews_html,
        '{{VIDEOS_BLOCK}}': videos,
        '{{VIDEOS_NOTE}}': 'A few recent builds from my channel.',
        '{{CHANNEL_URL}}': esc(channel),
        '{{NEXT_STEP}}': esc(args.next_step),
        '{{PROFILE_URL}}': esc(url or '#'),
        '{{FOOTER_LINKS}}': '<span class="dot">·</span>'.join(footer),
        '{{DITHER_SRC_NEXT}}': dither, '{{DITHER_SRC}}': dither,
        '{{DITHER_FIT}}': dither_fit,
        '{{DIAGRAM_FALLBACK}}': diagram_fallback,
    }
    for key, value in fills.items():
        page = page.replace(key, value)
    # Last, because the diagram carries user text that must never be re-scanned for placeholders.
    page = page.replace('{{DIAGRAM_DATA}}', diagram_data.replace('</', '<\\/')).replace('{{DIAGRAM_JS}}', js)
    left = sorted(set(re.findall(r'\{\{[A-Z_]+\}\}', page)))
    if left:
        abort(f'unfilled placeholders: {", ".join(left)}')

    out = pathlib.Path(args.out) if args.out else jobs_dir() / args.job_id / 'pitch.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding='utf-8')
    LIBRARY.mkdir(parents=True, exist_ok=True)
    (LIBRARY / f'{args.job_id}.json').write_text(diagram_data, encoding='utf-8')
    print(f'written: {out}  ({len(page) // 1024} KB, {len(nodes)} diagram nodes, '
          f'{len(found)} reviews, video: {"yes" if args.loom_url else "not yet"})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
