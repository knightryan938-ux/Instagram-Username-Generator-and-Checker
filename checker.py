# -*- coding: utf-8 -*-
import os
import sys
import time
import random
import string
import threading
import concurrent.futures

import tls_client
import toml
import utils.logger as logger
from colorama import init

init()

CONFIG_PATH = "data/config.toml"
PROXIES_PATH = "data/proxies.txt"
OUTPUT_ROOT = "output/instagram-usernames"
DEFAULT_THREADS = 20

CHARSET = string.ascii_lowercase

LOCK = threading.Lock()


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            config = toml.load(CONFIG_PATH)
            return config.get("main", {})
        except Exception:
            pass
    return {"threads": DEFAULT_THREADS, "proxyless": True}


def load_proxies():
    if not os.path.exists(PROXIES_PATH):
        return []
    with open(PROXIES_PATH, "r", encoding="utf-8", errors="ignore") as file:
        return [line.strip() for line in file if line.strip()]


def safe_input(prompt, default=None):
    try:
        answer = input(prompt).strip()
        if answer == "" and default is not None:
            return default
        return answer
    except KeyboardInterrupt:
        logger.err("Interrupted")
        sys.exit(1)


def ask_int(prompt, default):
    while True:
        answer = safe_input(f"{prompt} [{default}]: ", default)
        try:
            return int(answer)
        except ValueError:
            logger.err("Please enter a valid integer")


def ask_float(prompt, default):
    while True:
        answer = safe_input(f"{prompt} [{default}]: ", default)
        try:
            return float(answer)
        except ValueError:
            logger.err("Please enter a valid number")


def ask_yes_no(prompt, default=False):
    default_text = "y" if default else "n"
    answer = safe_input(f"{prompt} (y/n) [{default_text}]: ", default_text).lower()
    return answer.startswith("y")


def create_output_folder():
    folder = os.path.join(OUTPUT_ROOT, time.strftime("%Y-%m-%d %H-%M-%S"))
    os.makedirs(folder, exist_ok=True)
    return folder


def generate_username(length, prefix="", suffix=""):
    core_length = length - len(prefix) - len(suffix)
    if core_length < 1:
        return ""
    return prefix + "".join(random.choice(CHARSET) for _ in range(core_length)) + suffix


def build_usernames(count, min_len, max_len, prefix="", suffix=""):
    names = set()
    while len(names) < count:
        length = random.randint(min_len, max_len)
        username = generate_username(length, prefix, suffix)
        if not username:
            continue
        if username.startswith(".") or username.endswith("."):
            continue
        names.add(username)
    return list(names)


def load_usernames_from_file(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Username file not found: {path}")
    names = []
    with open(path, "r", encoding="utf-8", errors="ignore") as file:
        for line in file:
            name = line.strip().lower()
            if name:
                names.append(name)
    return list(dict.fromkeys(names))


def hunt_available_username(checker, folder, min_len, max_len, prefix, suffix, interval):
    attempts = 0
    while True:
        attempts += 1
        length = random.randint(min_len, max_len)
        username = generate_username(length, prefix, suffix)
        if not username:
            continue
        if username.startswith(".") or username.endswith("."):
            continue

        result = checker.check_username(username)
        if interval > 0:
            time.sleep(interval)

        with LOCK:
            with open(os.path.join(folder, "hunt_attempts.txt"), "a", encoding="utf-8") as out_file:
                out_file.write(f"{attempts}: {username} -> {result}\n")

        if result == "available":
            with LOCK:
                with open(os.path.join(folder, "found_username.txt"), "w", encoding="utf-8") as found_file:
                    found_file.write(username + "\n")
            logger.debug("Found available username", username=username, attempts=attempts)
            return username, attempts
        if result == "taken":
            logger.err("Taken", username=username, attempt=attempts)
        else:
            logger.err("Check result", username=username, status=result, attempt=attempts)


class InstagramChecker:
    def __init__(self, proxies, proxyless, interval=0.3):
        self.proxies = proxies
        self.proxyless = proxyless
        self.interval = interval
        self.session = tls_client.Session(client_identifier="chrome_104")
        self.session.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        }
        self.update_proxy()
        self.stats = {"checked": 0, "available": 0, "taken": 0, "errors": 0, "rate_limited": 0}

    def update_proxy(self):
        if self.proxyless or not self.proxies:
            self.session.proxies = None
            return
        self.session.proxies = f"http://{random.choice(self.proxies)}"

    def check_username(self, username, attempt=1):
        url = f"https://www.instagram.com/{username}/?__a=1&__d=dis"
        try:
            response = self.session.get(url, timeout_seconds=15, allow_redirects=True)
            status_code = response.status_code
            if status_code == 404:
                return "available"
            if status_code == 200:
                return "taken"
            if status_code == 429 and attempt < 3:
                self.stats["rate_limited"] += 1
                logger.err("Rate limited", username=username)
                self.update_proxy()
                time.sleep(1)
                return self.check_username(username, attempt + 1)
            logger.err("Unexpected HTTP response", username=username, status_code=status_code)
            return "unknown"
        except Exception as exc:
            if attempt < 3:
                self.update_proxy()
                time.sleep(1)
                return self.check_username(username, attempt + 1)
            logger.err("Error", username=username, error=exc)
            return "error"

    def worker(self, username, folder):
        result = self.check_username(username)
        if self.interval > 0:
            time.sleep(self.interval)
        file_name = {
            "available": "available.txt",
            "taken": "taken.txt",
            "unknown": "unknown.txt",
            "error": "errors.txt",
        }.get(result, "unknown.txt")

        with LOCK:
            self.stats["checked"] += 1
            if result in self.stats:
                self.stats[result] += 1
            with open(os.path.join(folder, file_name), "a", encoding="utf-8") as out_file:
                out_file.write(username + "\n")
        if result == "available":
            logger.debug("Available", username=username)
        elif result == "taken":
            logger.err("Taken", username=username)
        else:
            logger.err("{status}", username=username, status=result)


def main():
    logger.info("Instagram Username Generator and Checker")
    config = load_config()
    proxies = load_proxies()
    threads = config.get("threads", DEFAULT_THREADS)
    proxyless = config.get("proxyless", True)

    mode = safe_input("Choose mode: [1] Generate names + check, [2] Check names from file (1/2): ", "1")
    if mode not in {"1", "2"}:
        mode = "1"

    if mode == "2":
        path = safe_input("Path to username list file: ")
        usernames = load_usernames_from_file(path)
        interval = ask_float("Request interval in seconds", 0.3)
    else:
        count = ask_int("How many usernames to generate", 100)
        min_len = ask_int("Minimum username length", 3)
        max_len = ask_int("Maximum username length", 4)
        prefix = safe_input("Optional prefix (leave blank for none): ", "").lower()
        suffix = safe_input("Optional suffix (leave blank for none): ", "").lower()
        interval = ask_float("Request interval in seconds", 0.3)
        hunt_until_available = ask_yes_no("Hunt until one available username is found?", True)
        if hunt_until_available:
            usernames = []
        else:
            usernames = build_usernames(count, min_len, max_len, prefix, suffix)

    if mode == "2" and not usernames:
        logger.err("No usernames to check")
        sys.exit(1)
    if mode == "1" and not hunt_until_available and not usernames:
        logger.err("No usernames to check")
        sys.exit(1)
        logger.err("No usernames to check")
        sys.exit(1)

    if proxies:
        use_proxies = ask_yes_no("Proxies found in data/proxies.txt. Use proxies?", not proxyless)
        if use_proxies:
            proxyless = False
        else:
            proxyless = True

    folder = create_output_folder()
    if usernames:
        with open(os.path.join(folder, "all_usernames.txt"), "w", encoding="utf-8") as all_file:
            all_file.write("\n".join(usernames))

    checker = InstagramChecker(proxies, proxyless, interval=interval)

    if mode == "1" and hunt_until_available:
        logger.info("Hunting until an available username is found", proxyless=proxyless, interval=interval)
        found_username, attempts = hunt_available_username(checker, folder, min_len, max_len, prefix, suffix, interval)
        logger.info("Hunt complete", username=found_username, attempts=attempts, output=folder)
    else:
        logger.info("Starting check", total=len(usernames), threads=threads, proxyless=proxyless, interval=interval)
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            futures = [executor.submit(checker.worker, username, folder) for username in usernames]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    logger.err("Worker exception", error=exc)

        logger.info("Finished Instagram username check")
        logger.info(
            ">", Total=checker.stats["checked"], Available=checker.stats["available"], Taken=checker.stats["taken"], Errors=checker.stats["errors"], RateLimited=checker.stats["rate_limited"]
        )
        logger.info(">", Output=folder)


if __name__ == "__main__":
    main()
