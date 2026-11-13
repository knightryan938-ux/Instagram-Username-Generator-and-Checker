#!/usr/bin/env python3
"""Small-scale, conservative Instagram public-profile diagnostics.

Does not authenticate, bypass access controls, or claim a username is available.
"""
import argparse
import csv
import itertools
import json
import random
import re
import string
import time
import urllib.error
import urllib.request
from pathlib import Path

VALID = re.compile(r"^[a-z0-9._]{1,30}$")


def generate(path: Path, count: int, seed: int):
    if not 1 <= count <= 100000:
        raise ValueError("count must be 1..100000")
    rng = random.Random(seed)
    alphabet = string.ascii_lowercase + string.digits
    # Sample without replacement from the 36^4 possible candidates.
    ids = rng.sample(range(36**4), count)
    with path.open('w', encoding='utf-8') as f:
        for number in ids:
            chars = []
            for _ in range(4):
                number, remainder = divmod(number, 36)
                chars.append(alphabet[remainder])
            f.write(''.join(reversed(chars)) + '\n')
    print(f"Generated {count:,} unique four-character candidates in {path}")


def read_names(path: Path):
    seen = set()
    for line in path.read_text(encoding='utf-8').splitlines():
        name = line.strip().lower()
        if name and name not in seen:
            if not VALID.fullmatch(name):
                print(f"Skipping invalid username: {name!r}")
                continue
            seen.add(name)
            yield name


def check(name: str):
    url = f'https://www.instagram.com/{name}/'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; UsernameDiagnostic/1.0)',
        'Accept': 'text/html',
    })
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            code = response.status
            final_url = response.geturl()
            content_type = response.headers.get('Content-Type', '')
    except urllib.error.HTTPError as exc:
        code = exc.code
        final_url = exc.geturl()
        content_type = exc.headers.get('Content-Type', '')
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {'username': name, 'http_status': '', 'result': 'unknown', 'reason': type(exc).__name__, 'final_url': '', 'content_type': ''}

    # A visible profile page is not the same as a username registration check.
    if code == 200 and final_url.rstrip('/') == url.rstrip('/') and 'html' in content_type.lower():
        result, reason = 'profile_page_returned', 'HTTP 200 HTML; may be a login/challenge page, verify manually'
    elif code == 404:
        result, reason = 'not_found_unconfirmed', 'HTTP 404 does not prove the handle can be claimed'
    else:
        result, reason = 'unknown', f'HTTP {code}; not a reliable availability signal'
    return {'username': name, 'http_status': code, 'result': result, 'reason': reason, 'final_url': final_url, 'content_type': content_type}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    g = sub.add_parser('generate', help='Generate a random, unique candidate list offline')
    g.add_argument('--count', type=int, default=1000)
    g.add_argument('--seed', type=int, default=42)
    g.add_argument('--output', type=Path, default=Path('candidates.txt'))
    c = sub.add_parser('check', help='Diagnose up to 10 public profiles; no availability guarantees')
    c.add_argument('--input', type=Path, default=Path('usernames.txt'))
    c.add_argument('--output', type=Path, default=Path('results.csv'))
    c.add_argument('--limit', type=int, default=5)
    c.add_argument('--delay', type=float, default=5)
    args = p.parse_args()
    if args.command == 'generate':
        generate(args.output, args.count, args.seed)
        return
    if not 1 <= args.limit <= 10 or args.delay < 5:
        p.error('For safety and reliability, --limit must be 1..10 and --delay >= 5 seconds')
    names = list(itertools.islice(read_names(args.input), args.limit))
    if not names:
        p.error('No valid usernames in input')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['username','http_status','result','reason','final_url','content_type'])
        writer.writeheader()
        for i, name in enumerate(names):
            if i:
                time.sleep(args.delay)
            row = check(name)
            writer.writerow(row)
            print(f"{name}: {row['result']} (HTTP {row['http_status'] or 'error'})")
            if row['http_status'] in (403, 429):
                print('Access limited; stopping without retrying.')
                break
    print(f'Results saved to {args.output}. Confirm claimability only inside Instagram.')


if __name__ == '__main__':
    main()
