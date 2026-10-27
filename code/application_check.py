#!/usr/bin/env python3
"""The gate for an Upwork application before the member reads it.

    python3 code/application_check.py jobs/<id>/application.md [--job-title "..."] [--proof context/me.md]

Counts what can be counted, on the cover letter alone (screening answers after a
"Screening answers" heading do not count toward its length):

    at most 220 words            the pitch; what follows "To answer your questions:" is not counted
    no markdown                   Upwork shows a letter as typed, hashes and stars included
    none of the generic phrases   the tells that mark a letter as a template
    no em-dashes                  the fastest tell of machine writing
    the saved Loom or YouTube URL the application links to the finished video
    no placeholder left (--ready) nothing in brackets is ever pasted to a client
    --modality uma               Uma's answers replace the letter, so the word cap is off

A video link counts only on an exact host, loom.com or youtube.com with or without
www., and a non-empty path. "loom.com.example.test" is somebody else's domain.
The client's screening question is the client's wording, not the member's, so the
phrase and em-dash checks read the answer lines only.
    unsupported past numbers     also checked in screening answers

Job specificity, commitments and the ask are reported for a human eye, not scored: no pattern
can tell a real risk reversal from a sentence that contains the word "refund",
and a checker that cries wolf gets ignored.
"""
import argparse
import json
import pathlib
import re
import sys
from urllib.parse import urlparse, parse_qs

import pipeline

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import profile_checks as pc  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import context_check
BANNED = ("i'm excited", 'i am excited', 'what stood out', 'passionate',
          'results-driven', 'i want in', 'rockstar', 'ninja', 'i hope this finds you')
RISK = ("you don't pay", 'you do not pay', 'risk-free', 'risk free', 'full refund', 'only pay',
        'approve each', 'milestones, not', 'milestone', 'you decide', 'free until')
# The offer and guarantee as one sentence: "My goal is to get you x in y, or z."
OFFER = re.compile(r'\bmy goal is\b(?:[^.!?]|[.!?](?=\S))*?\bor\b', re.I)  # "$1.5k" stays inside the sentence
# Upwork shows a letter as typed, so markdown reaches the client as stray characters.
# Two hashes open a title with or without a space ("##Why me"); one hash needs the space,
# so "#1 rated" and a hashtag stay plain text.
HEADING_LINE = re.compile(r'^[ \t]{0,3}(?:#{2,6}[ \t]*\S|#[ \t]+\S).*$', re.M)
INLINE_MARKDOWN = re.compile(r'\*\*|`|\]\(')
# The plain line that opens the answers to questions the posting asks in its own text.
ANSWERS_START = re.compile(r'^[ \t]*to answer your questions?:?[ \t\r]*$', re.I | re.M)
ASK = ('send me', 'reply with', 'when works', 'let me know', 'tell me', 'here on upwork')
MAX_WORDS = 220
# The applicant card shows about this many characters, so the hook, the offer, the
# guarantee and the start of the video line have to sit inside them.
FOLD_CHARS = 230
VIDEO_START = re.compile(r'\[LOOM LINK\]|https://(?:www\.)?(?:loom\.com|youtu\.be|youtube\.com)/', re.I)
LOOM_PLACEHOLDER = '[LOOM LINK]'
# A blank somebody meant to fill before sending: [LOOM LINK], [Loom_Video], [HOLD: ...],
# <Your name>, {{name}}, PUT-YOUR-ID. A pasted letter has no reason to carry any of them.
# A bracketed blank may wrap over a line; an angle blank may not hold a space before its
# closing sign, so "under <a day, costs >nothing" stays a comparison.
PLACEHOLDER = re.compile(r'\[[^\]]{1,200}\]|\{\{[^}\n]{1,80}\}\}|<[A-Za-z][^<>\n]{0,80}(?<!\s)>|PUT-YOUR-[A-Z-]+')
# The applicant card shows about 230 to 240 characters, so the client decides whether to
# open the letter from its first words. These openings spend them on nothing.
CARD_WORDS = 45
FILLER_OPENERS = (r'i hope', r'hope you', r'my name is', r"i'?m a\b", r'i am a\b',
                  r'with (over )?\d+ years', r'allow me to', r'i came across',
                  r'just saw your', r'greetings')



def tracking_target(candidate):
    url = urlparse(candidate)
    match = re.fullmatch(r'/go/([0-9]{6,25})/([a-z0-9-]{1,80})', url.path)
    if not match or url.username or url.password:
        return None
    jid, slug = match.groups()
    job = next((job for job in pipeline.load() if job['id'] == jid), None)
    if not job:
        return None
    try:
        links = json.loads((pipeline.jobs_dir() / jid / 'tracking-links.json').read_text(encoding='utf-8'))
        link = links.get(slug, {})
        base = urlparse(link.get('base') or job.get('pitch_url') or '')
        if url.scheme == base.scheme == 'https' and url.netloc == base.netloc:
            return link.get('target')
    except (OSError, ValueError, TypeError):
        pass
    return None


def has_video(text):
    for candidate in re.findall(r'https://[^\s<>]+', text):
        candidate = candidate.rstrip(').,]')
        target = tracking_target(candidate)
        url = urlparse(target or candidate)
        if url.username or url.password:
            continue
        if url.hostname in ('loom.com', 'www.loom.com') and re.fullmatch(r'/share/[^/]+', url.path):
            return True
        if url.hostname == 'youtu.be' and len(url.path.strip('/')) > 0:
            return True
        if url.hostname in ('youtube.com', 'www.youtube.com') and url.path == '/watch' and parse_qs(url.query).get('v'):
            return True
    return False


def placeholders(text: str) -> list[str]:
    """Every unfilled blank in the lines the member wrote, once each, in reading order.

    A `#` line is the file's own heading or the client's question in the client's
    wording, so a bracket there is theirs and is left alone.
    """
    authored = '\n'.join(line for line in text.splitlines() if not re.match(r'^\s*#', line))
    return list(dict.fromkeys(match.group(0) for match in PLACEHOLDER.finditer(authored)))


def split_letter(text):
    m = re.search(r'^\W*screening (answers|question)', text, re.I | re.M)
    return (text[:m.start()], text[m.start():]) if m else (text, None)


def letter_body(text):
    """The part the client reads: without a leading title line or file header."""
    lines = text.splitlines()
    while lines and (lines[0].startswith('#') or not lines[0].strip()):
        lines.pop(0)
    return '\n'.join(lines)


def pc_contacts(text):
    """Every way of reaching the member off Upwork, found in the letter itself.

    The walkthrough video is the exception the application is built around, so a
    Loom or YouTube link is not a contact detail. Everything else is.
    """
    import pitch_check  # noqa: E402  (same folder, imported where it is used)
    text = re.sub(r'https://[^\s<>]+',
                  lambda match: tracking_target(match.group(0).rstrip(').,]')) or match.group(0), text)
    body = re.sub(r'https?://(www\.)?(loom\.com|youtu\.be|youtube\.com)\S*', ' ', text, flags=re.I)
    problems = []
    if pitch_check.EMAIL.search(body):
        problems.append('an email address is in the letter: Upwork bans contact details before a contract')
    # A link's digits (a pitch page path is the job id) are not a phone number.
    if pitch_check.phone_hit(re.sub(r'https?://\S+', ' ', body)):
        problems.append('a phone number is in the letter: Upwork bans contact details before a contract')
    hit = pitch_check.CONTACT_LINKS.search(body)
    if hit:
        problems.append(f'a way to reach you off Upwork is in the letter: "{hit.group(0)}"')
    ask = pitch_check.BOOKING_WORDS.search(body)
    if ask:
        problems.append(f'the letter asks to move off Upwork: "{ask.group(0)}"')
    return problems


def pitch_only(letter: str) -> str:
    """The letter without its answers: what stands before "To answer your questions:", plus the closing paragraph.

    Answers to questions the posting asks in its own text sit inside the letter, above
    the call to action, and are as long as the client's questions need them to be. The
    length cap is for the pitch around them.
    """
    start = ANSWERS_START.search(letter)
    if not start:
        return letter
    blocks = [block for block in re.split(r'\n\s*\n', letter[start.end():]) if block.strip()]
    return letter[:start.start()] + '\n\n' + (blocks[-1] if len(blocks) > 1 else '')


def markdown_marks(text: str) -> list[str]:
    """Markdown a client would read as typed characters, once each, in reading order.

    Inside the letter a `#` line is markdown too. In the screening section it is this
    file's own way of naming a question, so only the answer lines are read there.
    """
    letter, screening = split_letter(text)
    letter = letter_body(letter)
    answers = '\n'.join(line for line in (screening or '').splitlines() if not re.match(r'^\s*#', line))
    headings = [match.group(0).strip()[:40] for match in HEADING_LINE.finditer(letter)]
    inline = [match.group(0) for match in INLINE_MARKDOWN.finditer(letter + '\n' + answers)]
    return list(dict.fromkeys([*headings, *inline]))


def check(text, job_title='', proof_text='', ready=False, fast=False, modality='text', video_required=False):
    letter, screening = split_letter(text)
    letter = letter_body(letter)
    low = letter.lower()
    fails, notes = [], []
    words = len(re.findall(r"\b[\w'$%+-]+\b", pitch_only(letter)))
    if modality == 'text' and words > MAX_WORDS:
        fails.append(f'the pitch is {words} words without its answers, the cap is {MAX_WORDS}: cut {words - MAX_WORDS}')
    if not words:
        fails.append('the submitted Uma answers are empty' if modality == 'uma' else 'the cover letter is empty')
    authored = '\n'.join(line for line in text.splitlines() if not re.match(r'^\s*#', line))
    hits = [b for b in BANNED if b in authored.lower()]
    if hits:
        fails.append('generic phrasing: ' + ', '.join(f'"{h}"' for h in hits))
    if chr(0x2014) in text:
        fails.append('em-dash present: use a colon, comma or full stop')
    for mark in markdown_marks(text):
        fails.append(f'markdown in the text ({mark}): Upwork shows it as typed, so write plain lines')
    # Contact details violate the pre-contract rule, so the application gate
    # refuses them just as the pitch-page gate does.
    for problem in pc_contacts(text):
        fails.append(problem)
    if modality not in ('text', 'uma'):
        fails.append('unknown application modality')
    # The fast lane sends the letter within minutes of the posting, before a page or a
    # walkthrough can exist, so it is the one letter allowed to go out without a video.
    if (video_required or not fast) and not has_video(letter) and LOOM_PLACEHOLDER not in letter:
        fails.append('no Loom or YouTube link: include the walkthrough URL or the [LOOM LINK] placeholder')
    if fast and LOOM_PLACEHOLDER in letter:
        fails.append('a fast-lane letter carries no [LOOM LINK] placeholder: there is no video yet')
    # A placeholder is correct while the letter is being written and wrong the moment
    # it is pasted: a client who reads "[LOOM LINK]" learns that nobody read it back.
    # Only the submit check refuses them, so writing stays possible before the Loom
    # exists or a held answer is given. Every blank counts, not only the Loom's.
    blanks = placeholders(text)
    # The Loom blank is refused wherever it sits, a heading line included.
    if LOOM_PLACEHOLDER in text and LOOM_PLACEHOLDER not in blanks:
        blanks = [LOOM_PLACEHOLDER, *blanks]
    if ready:
        for blank in blanks:
            fix = 'paste the real walkthrough URL' if blank == LOOM_PLACEHOLDER else 'fill it or take it out'
            fails.append(f'the placeholder {blank} is still in the text: {fix} before you submit')
    elif blanks:
        notes.append('still to fill before you submit: ' + ', '.join(blanks))
    card = ' '.join(re.findall(r"\b[\w'$%+-]+\b", letter)[:CARD_WORDS]).lower()
    spent = [p for p in FILLER_OPENERS if re.search(p, card)]
    if spent and modality == 'text':
        fails.append(f'the first {CARD_WORDS} words are all the client sees on the applicant card, '
                     f'and they open with filler: {", ".join(repr(p) for p in spent)}')
    if job_title and modality == 'text':
        own = [w for w in re.findall(r"[\w']+", job_title.lower()) if len(w) > 3]
        if own and not any(w in card for w in own):
            notes.append(f'none of this job\'s own words appear in the first {CARD_WORDS} words, '
                         'which is all the client sees before deciding to open it')
    import profile_draft  # noqa: E402
    # This catches suspect numbers, not fabricated qualitative claims or a number
    # copied from unrelated proof. The member must verify claim-to-proof relevance.
    for sentence in re.split(r'(?<=[.!?])\s+|\n', text):
        if not re.search(r'\b(got|saved|raised|increased|built|delivered|rebuilt|contacted|helped|grew|cut|worked|managed|generated|achieved|have|has)\b', sentence, re.I):
            continue
        missing = profile_draft.unproven_numbers({'title': '', 'overview': sentence, 'portfolio': None}, proof_text)
        for number in missing:
            fails.append(f'"{number}" reads as a past result but is not in the evidence sections of context/me.md')
    notes.append('human review: match each claim to relevant proof, and confirm scope, rate and commitments')
    eye = [('risk reversal', any(r in low for r in RISK)), ('a specific ask', any(a in low for a in ASK))]
    if not fast:
        flat = re.sub(r'\s+', ' ', letter).strip()
        video = VIDEO_START.search(flat)
        eye = [*eye,
               ('"My goal is ..., or ..." before the video',
                bool(OFFER.search(flat[:video.start()] if video else flat))),
               (f'the video line inside the first {FOLD_CHARS} characters',
                bool(video) and video.start() < FOLD_CHARS)]
    return fails, notes, eye, words, screening is not None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('draft')
    ap.add_argument('--job-title', default='')
    ap.add_argument('--proof', default=str(ROOT / 'context' / 'me.md'))
    ap.add_argument('--modality', choices=('text', 'uma'), default='text')
    ap.add_argument('--video-required', action='store_true')
    ap.add_argument('--ready', action='store_true',
                    help='check the text as it will be pasted: any placeholder left in it is then a failure')
    ap.add_argument('--fast', action='store_true',
                    help='the fast lane: a letter sent minutes after the posting, with no video yet')
    args = ap.parse_args(argv)
    text = pathlib.Path(args.draft).read_text(encoding='utf-8')
    proof = pathlib.Path(args.proof)
    fails, notes, eye, words, has_screening = check(
        text, args.job_title,
        context_check.proof_only(proof.read_text(encoding='utf-8')) if proof.is_file() else '',
        ready=args.ready, fast=args.fast, modality=args.modality, video_required=args.video_required)
    for n in notes:
        print(f'note  {n}')
    for f in fails:
        print(f'FAIL  {f}')
    for label, found in eye:
        print(f'eye   {label}: {"looks present" if found else "NOT FOUND, check"}')
    if not has_screening:
        print('eye   no screening answers: correct only if the job asks no questions')
    print(f'\n{"PASS" if not fails else f"{len(fails)} problem(s)."}  {words} words in the letter')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
