#!/usr/bin/env python3
"""The hard cap on Upwork calls, shared by every chat and subagent in this folder.

    python3 code/upwork_limit.py            the hook: reads one tool call on stdin
    python3 code/upwork_limit.py status     what is used and what is left

Claude Code runs the first form before every Upwork connector call, through the
PreToolUse hook in .claude/settings.json. A rule in a prompt binds one chat: a
subagent or a second window never read it, and each believes its own handful of
calls is small. So the count lives in one file under data/ and every caller,
whoever it is, takes its turn at the same lock.

Two windows, both rolling. The last minute stops a burst, the last 24 hours
stops a slow loop. Exit 0 lets the call through and records it. Exit 2 refuses
it, and the reason on stderr goes back to Claude. Whatever this script cannot
check is refused as well: an unknown count is not a low one.
"""
import argparse
import contextlib
import json
import math
import os
import pathlib
import re
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]

WINDOWS = ('minute', 'day')
SECONDS = {'minute': 60, 'day': 86400}
LABEL = {'minute': 'minute', 'day': '24 hours'}
SETTING = {'minute': 'UPWORK_CALLS_PER_MINUTE', 'day': 'UPWORK_CALLS_PER_DAY'}
# What a member's day needs, with room: one /find-jobs run stays under 60 calls.
DEFAULT = {'minute': 30, 'day': 500}
# Upwork's own published limits (references/upwork-compliance.md, "Rate limits").
# No setting lifts a cap past these: above them the call itself is the violation.
CEILING = {'minute': 300, 'day': 40000}
# Both spellings exist: `mcp__upwork__...` from .mcp.json and
# `mcp__claude_ai_Upwork__...` from a connector added in claude.ai.
UPWORK_TOOL = re.compile(r'^mcp__.*upwork', re.I)
LOCK_WAIT = 10  # seconds, well inside the time Claude Code gives a hook
SCOPE = 'across every chat and subagent in this folder'


def ledger_path():
    """One line per call: a time, a tool name and a chat id. No Upwork content."""
    return ROOT / 'data' / 'upwork-calls.jsonl'


def setting(name):
    """One value from the environment, else from .env. Read here and not through
    another module: this runs before every Upwork call and must not fail with a module
    it has no use for."""
    raw = os.environ.get(name)
    if raw is None:
        try:
            lines = (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines()
        except FileNotFoundError:
            lines = []
        for line in lines:
            key, _, value = line.partition('=')
            if re.sub(r'^export\s+', '', key.strip()) == name:
                raw = value
    return (raw or '').split('#', 1)[0].strip().strip('"\'').strip()


def caps():
    """Each window's cap: the member's own number, never above Upwork's.

    A value that is set and is not a whole number raises. Falling back to the default
    there could hand the member a higher cap than the one they meant to set.
    """
    limits = {}
    for window in WINDOWS:
        raw = setting(SETTING[window])
        if not raw:
            limits[window] = DEFAULT[window]
        elif raw.isascii() and raw.isdigit():
            limits[window] = min(int(raw), CEILING[window])
        else:
            raise ValueError(f'{SETTING[window]} is set to {raw!r}, which is not a whole number')
    return limits


def acquire(handle):
    """Takes the lock, or raises after LOCK_WAIT seconds.

    Waiting forever would fail open: Claude Code treats a hook that runs past its own
    timeout as a passing error, and the call would go out uncounted.
    """
    if os.name == 'nt':
        import msvcrt
        handle.write(b'0')
        handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)  # gives up by itself after ten tries
        return
    import fcntl
    deadline = time.monotonic() + LOCK_WAIT
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f'another process held the count for {LOCK_WAIT} seconds') from None
            time.sleep(0.02)


def release(handle):
    if os.name == 'nt':
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def locked(path):
    """One caller at a time through read, decide and write, across every process."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a+b') as handle:
        acquire(handle)
        try:
            yield
        finally:
            release(handle)


def read_calls(path, since):
    """Calls no older than `since`. A line that cannot be read raises, on purpose."""
    if not path.is_file():
        return []
    calls = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    # json reads NaN and Infinity as numbers. One would slip out of every window unseen.
    if not all(math.isfinite(float(call['t'])) for call in calls):
        raise ValueError('a counted call has no usable time')
    return [call for call in calls if float(call['t']) >= since]


def write_calls(path, calls):
    """Writes through a temp file, so a crash mid-write never leaves half a count."""
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix='.upwork-calls-', suffix='.tmp', delete=False) as handle:
        tmp = pathlib.Path(handle.name)
        handle.writelines(json.dumps(call) + '\n' for call in calls)
        # Without this a power cut can leave an empty file, and an empty count reads as zero.
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def used(calls, window, now):
    """The times of the calls inside one window, oldest first."""
    return sorted(float(call['t']) for call in calls if float(call['t']) >= now - SECONDS[window])


def full_window(calls, limits, now):
    """The first full window as (window, cap, seconds until a slot frees), or None."""
    for window in WINDOWS:
        times, cap = used(calls, window, now), limits[window]
        if len(times) >= cap:
            # A slot frees when the oldest of the newest `cap` calls leaves the window.
            return window, cap, (times[-cap] + SECONDS[window] - now) if cap else None
    return None


def refusal(window, cap, frees):
    if not cap:
        return (f'Upwork calls are switched off: {SETTING[window]} is 0. '
                'Call nothing on Upwork and tell the member.')
    if window == 'minute':
        return (f'Upwork call cap reached: {cap} calls in the last minute, {SCOPE}. '
                f'A slot frees in {math.ceil(frees)} seconds. Wait that long once, then go on '
                'one call at a time. Never retry in a loop.')
    hours = max(1, math.ceil(frees / 3600))
    return (f'Upwork call cap reached: {cap} calls in the last 24 hours, {SCOPE}. '
            f'The next slot frees in about {hours} hour{"s" if hours > 1 else ""}. '
            'Stop calling Upwork, finish from what is saved and tell the member. '
            'Never reset this count and never reach Upwork another way.')


def take(tool, session, path=None, now=None, limits=None):
    """Counts one call or refuses it. Returns (allowed, reason)."""
    path = path or ledger_path()
    now = time.time() if now is None else now
    limits = limits or caps()
    with locked(path):
        calls = read_calls(path, now - SECONDS['day'])
        full = full_window(calls, limits, now)
        if full:
            return False, refusal(*full)
        write_calls(path, calls + [{'t': round(now, 3), 'tool': tool, 'session': session}])
    return True, ''


def hook(stream=None):
    """Exit 0 lets the call through, exit 2 refuses it. A failure in here refuses too."""
    try:
        event = json.load(stream or sys.stdin)
        tool = str(event.get('tool_name') or '')
        if tool and not UPWORK_TOOL.search(tool):
            return 0
        if not tool:
            raise ValueError('the hook input names no tool')
        allowed, reason = take(tool, str(event.get('session_id') or ''))
    except Exception as error:  # an unknown check stops the run
        print(f'The Upwork call cap could not be checked ({type(error).__name__}: {error}), so this '
              f'call is refused. Tell the member: the count is in {ledger_path()} and the caps are in '
              f'{ROOT / ".env"}, and only they repair or remove either. Never reach Upwork another way.',
              file=sys.stderr)
        return 2
    if not allowed:
        print(reason, file=sys.stderr)
        return 2
    return 0


def status(path=None, now=None, limits=None):
    path = path or ledger_path()
    now = time.time() if now is None else now
    limits = limits or caps()
    calls = read_calls(path, now - SECONDS['day'])
    for window in WINDOWS:
        count, cap = len(used(calls, window, now)), limits[window]
        print(f'{count} of {cap} Upwork calls in the last {LABEL[window]}, {max(0, cap - count)} left.')
    chats = len({call.get('session') for call in calls})
    print(f'Counted {SCOPE}: {chats} chat{"" if chats == 1 else "s"} in the last 24 hours.')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0])
    parser.add_argument('command', nargs='?', choices=['status'])
    args = parser.parse_args()
    if args.command == 'status':
        try:
            return status()
        except (ValueError, TypeError, KeyError, OSError) as error:
            print(f'ABORT: the cap cannot be read ({error}). Until {ledger_path()} and .env are '
                  'repaired, every Upwork call is refused.', file=sys.stderr)
            return 1
    if sys.stdin.isatty():
        parser.print_help()
        return 1
    return hook()


if __name__ == '__main__':
    sys.exit(main())
