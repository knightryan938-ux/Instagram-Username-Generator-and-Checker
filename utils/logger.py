import sys


def _format_extra(**kwargs):
    if not kwargs:
        return ""
    return " " + " ".join(f"{key}={value}" for key, value in kwargs.items())


def _log(level, message, **kwargs):
    extra = _format_extra(**kwargs)
    print(f"[{level}] {message}{extra}", file=sys.stderr)


def info(message, **kwargs):
    _log("INFO", message, **kwargs)


def err(message, **kwargs):
    _log("ERROR", message, **kwargs)


def debug(message, **kwargs):
    _log("DEBUG", message, **kwargs)
