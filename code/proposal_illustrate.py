#!/usr/bin/env python3
"""The illustrated sheet that travels with the proposal, in the client's own trade.

    python3 code/proposal_illustrate.py <job id> --niche "HVAC company" \\
        --scene "a van, a workshop, a phone that keeps ringing" [--model <kie.ai model>]

The A4 page stays the document: it carries the price, the weeks and the terms, and a client
and a freelancer both point at it later. **This picture carries no number and no sentence
from it.** A generated image invents a digit sooner or later, and a proposal whose figures
argue with each other costs more than a nice drawing is worth, so the prompt forbids text
outright and the sidecar records exactly what was asked for.

It needs `KIE_AI_API_KEY`, in the repo's `.env` or in the environment. Without it the run says
so and stops without spending anything: the proposal is complete without this page.

Writes `jobs/<id>/proposal-sketch.png` and `jobs/<id>/proposal-sketch.json` beside it.
"""
import argparse
import base64
import hashlib
import io
import json
import os
import pathlib
import subprocess
import sys
import time
from pipeline import jobs_dir, shown
from env_file import load_dotenv
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
API = 'https://api.kie.ai'
UPLOAD = 'https://kieai.redpandaai.co/api/file-base64-upload'
MODEL = 'nano-banana-pro'   # kie.ai refuses gpt-image-2 by that name, measured 27.09.2026
# The two macOS paths were the only ones this script looked at, so Chrome on Linux or
# Windows read as "not installed". The other two scripts that need it ask the PATH.
CHROME = ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
          '/Applications/Chromium.app/Contents/MacOS/Chromium')


def configured_env():
    env = dict(os.environ)
    load_dotenv(ROOT / '.env', env)
    load_dotenv(pathlib.Path.home() / '.config' / 'credentials.env', env)
    return env


def chrome_binary():
    """The browser to drive: CHROME_BIN, then the PATH, then the macOS defaults."""
    import shutil
    named = configured_env().get('CHROME_BIN')
    if named and pathlib.Path(named).exists():
        return named
    for command in ('google-chrome', 'chromium', 'chromium-browser', 'chrome'):
        found = shutil.which(command)
        if found:
            return found
    return next((path for path in CHROME if pathlib.Path(path).exists()), None)

STYLE = ('A hand drawn sketch in ink and a light wash, warm sand paper, one terracotta accent, '
         'thin confident lines, generous white space, the calm of an architect s working drawing. '
         'No photographic detail, no gradients, no 3D. The drawing fills the frame edge to edge on plain warm paper: it is the page itself, never a photograph of a sheet lying on a desk.')
RULE = ('The picture contains NO text, NO letters, NO numbers, NO labels, NO signage, NO logos '
        'and NO user interface. Every word belongs on the proposal page, not in this drawing.')


def abort(message):
    print(f'ABORT: {message}', file=sys.stderr)
    raise SystemExit(1)


def api_key():
    value = configured_env().get('KIE_AI_API_KEY', '').strip()
    if value:
        return value
    abort('KIE_AI_API_KEY is missing. Put it in .env and run this again; the proposal page itself '
          'is finished without this drawing.')


def browser():
    found = chrome_binary()
    if found:
        return found
    abort('Chrome is not installed, so the page cannot be rendered as an image. '
          'Set CHROME_BIN if it lives somewhere this cannot find.')


def foundation(job_id):
    """The page as a PNG. It is the palette reference, never the content of the drawing."""
    page = jobs_dir() / job_id / 'proposal.html'
    if not page.is_file():
        abort(f'{shown(page)} does not exist. Run proposal_generate.py first.')
    out = jobs_dir() / job_id / '.proposal-foundation.png'
    subprocess.run([browser(), '--headless=new', '--disable-gpu', '--hide-scrollbars',
                    '--window-size=900,1400', f'--screenshot={out}', '--virtual-time-budget=2500',
                    page.resolve().as_uri()], capture_output=True, timeout=120)
    if not out.is_file():
        abort('Chrome produced no screenshot of the proposal page.')
    return out


def request(url, key, payload=None):
    req = urllib.request.Request(
        url, data=None if payload is None else json.dumps(payload).encode(),
        method='GET' if payload is None else 'POST',
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.load(response)


def upload(path, key):
    try:
        from PIL import Image
    except ImportError:
        abort('Pillow is missing: pip install pillow, or drop --with-foundation.')
    image = Image.open(path).convert('RGB')
    image.thumbnail((2048, 2048))
    buffer = io.BytesIO()
    image.save(buffer, 'JPEG', quality=92)
    encoded = base64.b64encode(buffer.getvalue()).decode()
    answer = request(UPLOAD, key, {'base64Data': f'data:image/jpeg;base64,{encoded}',
                                   'uploadPath': 'upwork-proposal', 'fileName': path.stem + '.jpg'})
    if not answer.get('success', answer.get('code') == 200):
        abort(f'the upload was refused: {answer}')
    return answer['data']['downloadUrl']


def prompt_for(niche, scene, steps, outcome):
    stages = ', then '.join(steps) if steps else 'the work, stage by stage'
    ending = (f'The path ends on what the client is left with: {outcome}, drawn as the largest, '
              'calmest element on the page. ') if outcome else ''
    return (f'One illustrated sheet for a {niche}. {STYLE} '
            f'The drawing shows the way through the work as a path across the page: {stages}. '
            f'{ending}'
            f'Around the path, the everyday of this trade: {scene}. '
            f'One scene, read left to right, nothing decorative that does not carry meaning. {RULE}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('job_id')
    parser.add_argument('--niche', required=True, help='the client\'s trade, in their words')
    parser.add_argument('--scene', default='the everyday objects of that trade',
                        help='what belongs in the picture besides the path')
    parser.add_argument('--step', action='append', default=[],
                        help='a stage of the plan, repeatable, words only and never a number')
    parser.add_argument('--from-proposal', type=pathlib.Path,
                        help='the proposal JSON: its roadmap rows become the stages')
    parser.add_argument('--outcome', default='',
                        help='what the client has at the end, so the drawing lands somewhere')
    parser.add_argument('--model', default=MODEL)
    parser.add_argument('--with-foundation', action='store_true',
                        help='send the page as a palette reference')
    parser.add_argument('--dry-run', action='store_true', help='print the prompt and stop')
    args = parser.parse_args(argv)

    if args.from_proposal:
        try:
            data = json.loads(args.from_proposal.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as error:
            abort(f'the proposal JSON does not read: {error}')
        rows = [r for r in (data.get('rows') or []) if r.get('kind') != 'milestone']
        args.step = args.step or [str(r.get('label') or '').strip() for r in rows if r.get('label')]
        if not args.step:
            abort('the proposal JSON has no roadmap rows to draw.')

    for step in args.step:
        if any(character.isdigit() for character in step):
            abort(f'the stage "{step}" carries a number. Numbers live on the page, not in the drawing.')

    prompt = prompt_for(args.niche, args.scene, args.step, args.outcome)
    out = jobs_dir() / args.job_id / 'proposal-sketch.png'
    if args.dry_run:
        print(prompt)
        return 0
    if out.exists():
        abort(f'{shown(out)} exists already and is never overwritten.')

    key = api_key()
    # Fail closed before the first paid call. Until
    # this ran, a key that had been revoked or mistyped was discovered after the
    # foundation image had already been uploaded.
    import preflight
    trouble = preflight.kie_error({'KIE_AI_API_KEY': key})
    if trouble:
        abort(trouble)
    references = [upload(foundation(args.job_id), key)] if args.with_foundation else []
    task = request(f'{API}/api/v1/jobs/createTask', key, {'model': args.model, 'input': {
        'prompt': prompt, 'image_input': references, 'aspect_ratio': '3:4',
        'resolution': '2K', 'output_format': 'png'}})
    if task.get('code') != 200:
        abort(f'createTask was refused: {task}')
    task_id = task['data']['taskId']

    for _ in range(90):
        time.sleep(4)
        info = request(f'{API}/api/v1/jobs/recordInfo?taskId={task_id}', key)['data']
        if info['state'] == 'success':
            url = json.loads(info['resultJson'])['resultUrls'][0]
            spent = float(info.get('creditsConsumed') or 0)
            out.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(url, timeout=120) as response:
                out.write_bytes(response.read())
            break
        if info['state'] == 'fail':
            abort(f'the image failed: {info.get("failMsg")}')
    else:
        abort(f'timed out waiting for task {task_id}')

    sidecar = out.with_suffix('.json')
    sidecar.write_text(json.dumps({
        'job_id': args.job_id, 'model': args.model, 'task': task_id, 'credits': spent,
        'niche': args.niche, 'steps': args.step, 'outcome': args.outcome, 'prompt': prompt,
        'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
        'rule': 'no text, no numbers: every figure lives on proposal.html',
    }, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'{shown(out)} written, {spent:g} credits, task {task_id}.')
    print('Look at it before it goes out: any letter or digit in the drawing means it is not usable.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
