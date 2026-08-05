# Instagram Username Generator + Checker

A simple Python utility that generates Instagram username candidates and checks their availability.

## Requirements

- Python 3.9+
- `tls-client`
- `toml`
- `colorama`

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Configure the tool in `data/config.toml`.
3. Optionally add proxy entries to `data/proxies.txt`, one proxy per line, e.g. `127.0.0.1:8080`.

## Usage

Run the checker script:

```bash
python checker.py
```

You can choose:
- `1` to generate usernames and check them
- `2` to check usernames loaded from a text file

### Output

Results are saved under `output/instagram-usernames/<timestamp>/`:
- `available.txt`
- `taken.txt`
- `errors.txt`
- `unknown.txt`
- `all_usernames.txt`

## Configuration

Example `data/config.toml`:

```toml
[main]
threads = 20
proxyless = true
```

## Notes

- The script creates the output folder automatically when it runs.
- If you want to use proxies, add them to `data/proxies.txt` and confirm when prompted.
