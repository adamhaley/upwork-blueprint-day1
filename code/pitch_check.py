#!/usr/bin/env python3
"""The gate for what goes to a client before a contract: the proposal page.

    python3 code/pitch_check.py page jobs/<id>/proposal.html [--ready]

The page check exists because Upwork bans contact details before a contract,
and a linked page counts: an email, a phone number, a booking link, a WhatsApp
button or a social profile on it is a way to reach the freelancer off Upwork.
"""
import html
import pathlib
import re
import sys

# Every way found so far to reach a freelancer off Upwork. A denylist is only as
# current as the last person who added to it, so the checks below also look for a
# bare address or number, which no new meeting service can rename.
CONTACT_LINKS = re.compile(
    r'(mailto:|tel:|sms:|wa\.me|whatsapp|'
    r'calendly|cal\.com/|tidycal|zcal\.co|savvycal|meetings\.hubspot|hubspot\.com/meetings|'
    r'youcanbook\.me|acuityscheduling|oncehub|koalendar|book\.ms|'
    r'zoom\.us|meet\.google\.com|calendar\.google\.com|teams\.microsoft\.com|teams\.live\.com|'
    r'webex\.com|whereby\.com|gotomeeting|skype:|join\.skype|'
    r'linkedin\.com|instagram\.com|facebook\.com|fb\.me|tiktok\.com|twitter\.com|//x\.com|t\.me/|'
    r'telegram|discord\.gg|signal\.me)', re.I)
EMAIL = re.compile(r'\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b', re.I)
# A phone number, and not two prices in a row: "12.500 - 12.500" used to fail this gate,
# and a gate that cries wolf on a real page is one the member learns to skip. Money is
# removed before the search rather than argued with afterwards.
PHONE = re.compile(r'(?<![\w.])\+?\d[\d ().-]{8,}\d(?![\w.])')
MONEY = re.compile(r'[$€£]\s?[\d.,]+|\b\d{1,3}[.,]\d{3}(?:[.,]\d{2})?\b')


def phone_hit(text):
    """The first digit run that reads as a phone number once money is out of the way."""
    return PHONE.search(MONEY.sub(' ', text))
BOOKING_WORDS = re.compile(r'\b(book a call|schedule a call|book a meeting|email me|call me|whatsapp me)\b', re.I)
# A blank a human is meant to replace, written the way the roadmap templates
# write them: <Your name>, <A result you can back up>.
TEMPLATE_BLANK = re.compile(r'<[A-Za-z][^<>]{3,80}>')


def visible_text(page):
    """What a reader sees: no scripts, styles, comments or embedded images."""
    page = re.sub(r'<(script|style)\b.*?</\1>', ' ', page, flags=re.S | re.I)
    page = re.sub(r'<!--.*?-->', ' ', page, flags=re.S)
    page = re.sub(r'<[^>]+>', ' ', page)
    return html.unescape(page)


def links(page):
    """Every href, however it was quoted. A single-quoted one used to walk past."""
    pairs = re.findall(r"""href\s*=\s*"([^"]*)"|href\s*=\s*'([^']*)'""", page)
    found = [double or single for double, single in pairs]
    return [h for h in found if h and not h.startswith(('#', 'data:'))]


def check_page(path, *, require_hero=False, ready=False):
    page = pathlib.Path(path).read_text(encoding='utf-8')
    problems = []
    from application_check import tracking_target
    for h in links(page):
        target = tracking_target(h) or h
        if CONTACT_LINKS.search(target):
            problems.append(f'links a way to reach you off Upwork: {target[:80]}')
    text = visible_text(page)
    for m in EMAIL.finditer(text):
        problems.append(f'shows an email address: {m.group(0)}')
    for m in PHONE.finditer(MONEY.sub(' ', text)):
        if len(re.sub(r'\D', '', m.group(0))) >= 9:
            problems.append(f'shows what looks like a phone number: {m.group(0).strip()}')
    for m in BOOKING_WORDS.finditer(text):
        problems.append(f'asks for contact off Upwork: "{m.group(0)}"')
    if chr(0x2014) in text:
        problems.append('uses an em-dash in the copy')
    left = re.findall(r'\{\{[A-Z_]+\}\}', page)
    if left:
        problems.append(f'unfilled placeholders: {", ".join(sorted(set(left)))}')
    # The roadmap templates mark their blanks in the prose a client reads, not in
    # the {{BRACES}} the generator fills, so the rule above walked straight past a
    # page still saying "<Your name>" and passed it for publishing.
    for m in TEMPLATE_BLANK.finditer(text):
        problems.append(f'still carries a template blank: {m.group(0)[:60]}')
    for m in re.finditer(r'PUT-YOUR-[A-Z-]+', page):
        # The Loom id is the one blank that cannot be filled before publishing: the
        # walkthrough is a video of this page, so the page has to exist first. It is
        # refused at the moment the link goes to a client, not while it is being built.
        if 'LOOM' in m.group(0) and not ready:
            continue
        problems.append(f'still carries a template blank: {m.group(0)}')
    # write_site copies the HTML and nothing beside it, so any file the page points
    # at by a relative path is a 404 the member only sees after sending the link.
    # Outside comments only: a commented-out tag cannot 404, and the roadmap
    # templates spell the wrong form inside a comment in order to warn against it.
    live = re.sub(r'<!--.*?-->', ' ', page, flags=re.S)
    for src in re.findall(r'(?:src|href)\s*=\s*["\']([^"\']+)["\']', live):
        if re.match(r'(?:https?:)?//|data:|#|mailto:|tel:', src):
            continue
        if re.search(r'\.(?:jpe?g|png|gif|webp|svg|avif|css|js)$', src, re.I):
            problems.append(f'points at a file that is not embedded: {src[:60]}')
    hero = re.search(r'<div class="hero-art"[^>]*>\s*<img\s+[^>]*src="data:image/', page, re.I)
    # Only when the caller says a hero was drawn for this page. The gate exists to
    # catch an image that failed to embed, not to refuse a member who has no way
    # to draw one.
    if require_hero and not hero:
        problems.append('a hero image was expected and is missing or not embedded')
    return problems


def main(argv):
    ready = '--ready' in argv
    args = [arg for arg in argv if arg != '--ready']
    if len(args) != 2 or args[0] != 'page':
        print(__doc__, file=sys.stderr)
        return 2
    problems = check_page(args[1], ready=ready)
    summary = 'no contact details, no placeholders' if ready else 'no contact details; Loom may still be pending'
    for p in problems:
        print(f'FAIL  {p}')
    print(f'\n{"PASS  " + summary if not problems else f"{len(problems)} problem(s)."}')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
