import json
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def har_inventory(path: str | Path) -> list[dict]:
    """Summarize a local HAR file without sending requests."""
    counts = Counter()
    for entry in json.loads(Path(path).read_text())["log"]["entries"]:
        req = entry["request"]
        parts = urlsplit(req["url"])
        host = parts.hostname or ""
        if host == "chaoxing.com" or host.endswith(".chaoxing.com"):
            names = tuple(sorted(parse_qs(parts.query, keep_blank_values=True)))
            counts[(req["method"], host, parts.path, names)] += 1
    return [dict(method=m, host=h, path=p, query_keys=k, count=n)
            for (m, h, p, k), n in sorted(counts.items())]
