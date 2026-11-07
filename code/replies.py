#!/usr/bin/env python3
"""Validate the machine file that /dashboard writes for the cockpit.

    python3 code/replies.py check <job_id>

The model chooses the words. This script checks the fixed contract around them:
valid JSON, two or three labeled non-empty options, distinct text, no em-dashes,
no unfilled placeholder such as [Loom_Video], no "just checking in", no number the
evidence sections of context/me.md cannot back, and no way of reaching the member
off Upwork. It never sends or changes a reply.

A draft is the one client-facing artifact that leaves this repo as a message, and
it used to be the only one with no gate on its content: the cover letter was
scanned for unproven numbers and contact details while the
reply, which goes straight into a client's inbox, was checked for shape alone.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
import pipeline  # noqa: E402  (jobs_dir only)

ID = re.compile(r'^[0-9]{6,25}$')
# A draft goes out exactly as it stands, so a slot nobody filled reaches the client as
# "[Loom_Video]" or "Hey [first name]". Words in square, curly or angle brackets, a bare
# TBD or TODO and a run of underscores all count. A link in angle brackets is a link.
PLACEHOLDER = re.compile(r'\[[^\[\]\n]*[A-Za-z][^\[\]\n]*\]|\[[ ._…]*\]|\{\{?[^{}\n]*[A-Za-z][^{}\n]*\}\}?'
                         r'|<(?!(?i:https?)://)[A-Za-z][^<>\n]*>|\b(?:TBD|TODO)\b|_{3,}')


def placeholders(text: str) -> list[str]:
    """Every unfilled slot in a draft, as the client would read it."""
    return sorted({hit.group(0) for hit in PLACEHOLDER.finditer(text)})


# The receiver test in references/follow-ups.md asks whether the client would be glad they
# opened the message. Most of it is judgement. These phrases are the part a script can see:
# each asks for a reply and hands over nothing, so a draft built on one never passes.
CHECK_IN = re.compile(r"\b(?:checking in|check in with you|following up|follow up on my|circling back"
                      r"|touching base|bumping this|any updates?\b|did you (?:get|have) a chance"
                      r"|have you had a chance|haven't heard back|wanted to see if)", re.I)


def check_ins(text: str) -> list[str]:
    """Every check-in phrase in a draft: a message that asks and gives nothing."""
    return sorted({hit.group(0).lower() for hit in CHECK_IN.finditer(text)})


def unbacked_numbers(text, proof_text):
    """Every result number in a draft that the member's evidence does not carry."""
    import profile_checks as pc  # noqa: E402  (same folder, imported where it is used)
    missing = set()
    for hit in pc.RESULT_NUMBER.finditer(text):
        core = re.search(r'\d[\d.,]*', hit.group(0)).group(0).rstrip('.,')
        if not re.search(r'(?<![\d.,])' + re.escape(core) + r'(?!\d)', proof_text):
            missing.add(hit.group(0).strip())
    return sorted(missing)


def off_upwork(text):
    """Contact details and invitations to move the conversation, as the letter gate reads them."""
    import application_check  # noqa: E402  (same folder, imported where it is used)
    return [problem.replace('in the letter', 'in the draft').replace('the letter asks', 'the draft asks')
            for problem in application_check.pc_contacts(text)]


def proof_text():
    """The evidence sections of the member's own file, and nothing else from it."""
    import context_check  # noqa: E402  (same folder, imported where it is used)
    me = ROOT / 'context' / 'me.md'
    return context_check.proof_only(me.read_text(encoding='utf-8')) if me.is_file() else ''


def validate(value, proof=None):
    problems = []
    if not isinstance(value, dict):
        return ['the root must be an object']
    if not isinstance(value.get('generated_at'), str) or not value['generated_at'].strip():
        problems.append('generated_at must be a non-empty string')
    drafts = value.get('drafts')
    if not isinstance(drafts, list) or len(drafts) not in (2, 3):
        problems.append('drafts must contain two or three options')
        return problems
    texts = []
    for index, draft in enumerate(drafts, 1):
        if not isinstance(draft, dict):
            problems.append(f'draft {index} must be an object')
            continue
        label, text = draft.get('label'), draft.get('text')
        if not isinstance(label, str) or not label.strip():
            problems.append(f'draft {index} needs a label')
        if not isinstance(text, str) or not text.strip():
            problems.append(f'draft {index} needs reply text')
        elif '\u2014' in text:
            problems.append(f'draft {index} contains an em-dash')
        else:
            texts.append(text.strip())
            for slot in placeholders(text):
                problems.append(f'draft {index} still carries the placeholder "{slot}": '
                                f'fill it in or cut the line')
            for phrase in check_ins(text):
                problems.append(f'draft {index} says "{phrase}", which asks for a reply and gives '
                                f'nothing: lead with the idea instead')
            for number in unbacked_numbers(text, proof if proof is not None else proof_text()):
                problems.append(f'draft {index} claims "{number}", which the evidence sections of '
                                f'context/me.md do not carry: omit it or record where it can be checked')
            for problem in off_upwork(text):
                problems.append(f'draft {index}: {problem}')
    if len(texts) != len(set(texts)):
        problems.append('draft texts must be meaningfully different')
    return problems


def cmd_check(args):
    if not ID.fullmatch(args.job_id):
        print('ABORT: that job id is not valid.', file=sys.stderr)
        return 1
    file = pipeline.jobs_dir() / args.job_id / 'replies.json'
    try:
        value = json.loads(file.read_text(encoding='utf-8'))
    except FileNotFoundError:
        print('ABORT: replies.json is missing.', file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f'ABORT: replies.json is not valid JSON at line {exc.lineno}.', file=sys.stderr)
        return 1
    problems = validate(value)
    if problems:
        for problem in problems:
            print(f'FAIL: {problem}', file=sys.stderr)
        return 1
    print(f'PASS: {len(value["drafts"])} reply drafts are valid.')
    return 0


def cmd_sent(args):
    """Record which draft went to the client, in the draft's own words.

    The send itself is one connector call and leaves no trace here, so a week later
    nobody can say what was sent or whether it was the text the member approved.
    Taking the record from replies.json rather than from a retyped summary is the
    whole point: what is logged is provably the option they chose.
    """
    if not ID.fullmatch(args.job_id):
        print('ABORT: that job id is not valid.', file=sys.stderr)
        return 1
    file = pipeline.jobs_dir() / args.job_id / 'replies.json'
    try:
        value = json.loads(file.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        print('ABORT: replies.json is missing or not valid JSON.', file=sys.stderr)
        return 1
    drafts = [d for d in value.get('drafts') or [] if isinstance(d, dict)]
    picked = [d for d in drafts if str(d.get('label', '')).strip().lower() == args.label.strip().lower()]
    if not picked:
        labels = ', '.join(repr(str(d.get('label', ''))) for d in drafts) or 'none'
        print(f'ABORT: no draft labelled {args.label!r}. Labels present: {labels}', file=sys.stderr)
        return 1
    text = ' '.join(str(picked[0].get('text', '')).split())
    out = subprocess.run([sys.executable, str(ROOT / 'code' / 'pipeline.py'), 'acted', args.job_id,
                          '--note', f'sent to the client: {text}'], capture_output=True, text=True)
    if out.returncode:
        print(out.stderr.strip(), file=sys.stderr)
        return 1
    print(f'Recorded the "{picked[0].get("label")}" draft as sent.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check', help='Validate jobs/<id>/replies.json.')
    check.add_argument('job_id')
    check.set_defaults(func=cmd_check)
    sent = sub.add_parser('sent', help='Record which draft the member sent, from its own text.')
    sent.add_argument('job_id')
    sent.add_argument('--label', required=True, help='the label of the draft that went out')
    sent.set_defaults(func=cmd_sent)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
