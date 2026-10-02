"""Checks every link in references.py still opens (DOIs go through doi.org)."""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from resilient_net.references import REFERENCES  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (reference link check)"}


def check(link):
    if link.startswith("https://doi.org/"):
        doi = link[len("https://doi.org/"):]
        url = "https://doi.org/api/handles/" + urllib.parse.quote(doi, safe="/:")
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            ok = json.load(r).get("responseCode") == 1
        return ok, "DOI registered" if ok else "DOI not found"
    try:
        with urllib.request.urlopen(urllib.request.Request(link, headers=UA), timeout=30) as r:
            return True, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        if e.code in (403, 406, 429):
            return True, f"HTTP {e.code} (site blocks scripts; open it in a browser to confirm)"
        return False, f"HTTP {e.code}"


def main():
    bad = 0
    for tag, ref, _, link in REFERENCES:
        if not link:
            print(f"{tag:>5}  --   no link (print source; cite as written)")
            continue
        try:
            ok, msg = check(link)
        except Exception as exc:
            ok, msg = False, str(exc)
        bad += not ok
        print(f"{tag:>5}  {'OK' if ok else 'FAIL':4} {msg}\n        {link}")
    print(f"\n{len(REFERENCES)} references, {bad} broken link(s).")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
