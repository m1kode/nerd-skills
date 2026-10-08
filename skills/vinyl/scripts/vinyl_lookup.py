#!/usr/bin/env python3
"""Fetch pressing data for a vinyl record from Discogs, and optionally a shop page.

Usage:
    vinyl_lookup.py <barcode | discogs url/id | shop url>
    vinyl_lookup.py --search "artist title"
    vinyl_lookup.py <barcode> --shop <url>
    vinyl_lookup.py --release <discogs id>

Everything runs against public endpoints with no API key. Discogs allows 25
anonymous requests per minute, which is why this sleeps between releases.

Output is JSON on stdout. A missing field means "the source did not state it",
never "the record does not have it" - Discogs is volunteer-maintained and its
coverage is uneven.
"""
import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BROWSER_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
# Discogs refuses generic agents and asks callers to identify themselves.
DISCOGS_UA = "nerd-skills-vinyl/1.0 (+https://github.com/m1kode/nerd-skills)"

# Who physically pressed the record and who cut the lacquer are the two facts
# that separate a careful reissue from a cheap repress.
KEY_CREDITS = ("Pressed By", "Manufactured By", "Lacquer Cut At",
               "Mastered At", "Remastered At", "Recorded At")

BLOCK_MARKERS = ("captcha", "automated access", "unusual traffic",
                 "are you a robot", "access denied", "enable javascript and cookies")


# --------------------------------------------------------------------------
# Shop pages
# --------------------------------------------------------------------------

def fetch_shop(url):
    """Best-effort read of any retailer product page.

    Shops vary wildly. Most webshops publish schema.org Product JSON-LD, which
    carries the barcode - that is all this needs, since every quality fact
    comes from Discogs afterwards. Some retailers (Amazon above all) block
    scripted clients or render everything client-side; those return
    blocked/no_data so the caller can fall back to asking for the barcode.
    """
    cmd = [
        "curl", "-sL", "--compressed", "-m", "45",
        "-H", f"User-Agent: {BROWSER_UA}",
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "-H", "Accept-Language: en-US,en;q=0.9",
        "-H", "Upgrade-Insecure-Requests: 1",
        "-H", "Sec-Fetch-Dest: document",
        "-H", "Sec-Fetch-Mode: navigate",
        "-H", "Sec-Fetch-Site: none",
        "-H", "Sec-Fetch-User: ?1",
        "-w", "\n__META__%{http_code}|%{url_effective}",
        url,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as exc:
        return {"url": url, "error": f"fetch failed: {exc}"}
    if proc.returncode != 0:
        return {"url": url, "error": f"curl exited {proc.returncode}"}

    html, _, meta = proc.stdout.rpartition("__META__")
    status, _, final_url = meta.partition("|")
    out = {"url": final_url.strip() or url, "http_status": status.strip()}

    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        for node in (data if isinstance(data, list) else [data]):
            if not isinstance(node, dict) or node.get("@type") != "Product":
                continue
            out["name"] = node.get("name")
            for key in ("gtin13", "gtin12", "gtin14", "gtin", "productID", "sku"):
                val = str(node.get(key) or "")
                # 11 digits happens when a leading zero was dropped from a
                # UPC-A; 8 is a short EAN. Discogs tolerates both.
                if re.fullmatch(r"\d{8,14}", re.sub(r"\D", "", val) or "x"):
                    out["barcode"] = re.sub(r"\D", "", val)
                    break
            brand = node.get("brand")
            if isinstance(brand, dict):
                out["brand"] = brand.get("name")
            elif isinstance(brand, str):
                out["brand"] = brand
            offers = node.get("offers")
            if isinstance(offers, list) and offers:
                offers = offers[0]
            if isinstance(offers, dict):
                out["price"] = offers.get("price")
                out["currency"] = offers.get("priceCurrency")
                out["availability"] = str(offers.get("availability") or "").rsplit("/", 1)[-1]

    if "barcode" not in out:
        # Many shops print the barcode in a spec table instead of JSON-LD.
        near = re.search(r"(?:EAN|UPC|GTIN|Barcode|Strichcode)[^0-9]{0,40}(\d[\d\s-]{10,16}\d)",
                         html, re.I)
        if near:
            digits = re.sub(r"\D", "", near.group(1))
            if 8 <= len(digits) <= 14:
                out["barcode"] = digits

    if "name" not in out:
        title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        if title:
            out["page_title"] = " ".join(title.group(1).split())[:160]

    if "barcode" not in out:
        # Only call it a block once extraction has failed: plenty of ordinary
        # pages mention "captcha" or "access denied" somewhere in their markup,
        # and a page that yielded a barcode plainly was not blocked.
        low = html[:200000].lower()
        blocked = status.strip() in ("403", "503") or any(m in low for m in BLOCK_MARKERS)
        out["blocked" if blocked else "no_data"] = True
        out["hint"] = ("This retailer blocks scripted requests. " if blocked else
                       "No barcode found on the page - it may be rendered client-side. ")
        out["hint"] += ("Ask the user for the barcode printed on the sleeve, or read "
                        "the page with your own web-fetch tool.")
    return out


# --------------------------------------------------------------------------
# Discogs
# --------------------------------------------------------------------------

def discogs_get(path):
    url = f"https://api.discogs.com{path}"
    req = urllib.request.Request(url, headers={"User-Agent": DISCOGS_UA,
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code} for {path}"}
    except Exception as exc:
        return {"error": f"{exc} for {path}"}


def parse_format(formats):
    """Pull the facts that hide in Discogs' free-text format field: gram
    weight, gatefold, colour, disc count."""
    info = {"discs": None, "weight_g": None, "gatefold": False,
            "colour": None, "descriptions": [], "raw": []}
    for fmt in formats or []:
        if fmt.get("name") != "Vinyl" and info["discs"] is None:
            continue
        info["discs"] = int(fmt.get("qty") or 1)
        info["descriptions"] = fmt.get("descriptions") or []
        text = fmt.get("text") or ""
        info["raw"].append(" / ".join(filter(None, [fmt.get("name"), text])))
        blob = f"{text} {' '.join(info['descriptions'])}"
        weight = re.search(r"(\d{3})\s*(?:g|gram|gr)\b", blob, re.I)
        if weight:
            info["weight_g"] = int(weight.group(1))
        if re.search(r"gatefold", blob, re.I):
            info["gatefold"] = True
        colour = [p.strip() for p in text.split(",")
                  if p.strip() and not re.search(r"gatefold|\d{3}\s*g", p, re.I)]
        if colour:
            info["colour"] = ", ".join(colour)
    return info


def fetch_release(release_id):
    d = discogs_get(f"/releases/{release_id}")
    if "error" in d:
        return d
    credits = {}
    for c in d.get("companies", []):
        role = c.get("entity_type_name")
        if role in KEY_CREDITS:
            credits.setdefault(role, []).append(c.get("name"))
    community = d.get("community") or {}
    rating = community.get("rating") or {}
    return {
        "release_id": d.get("id"),
        "url": d.get("uri"),
        "title": d.get("title"),
        "artists": [a.get("name") for a in d.get("artists", [])],
        "labels": [f"{l.get('name')} - {l.get('catno')}" for l in d.get("labels", [])],
        "country": d.get("country"),
        "released": d.get("released") or d.get("year") or None,
        "format": parse_format(d.get("formats")),
        "credits": credits,
        "rating_avg": rating.get("average"),
        "rating_count": rating.get("count"),
        "have": community.get("have"),
        "want": community.get("want"),
        "data_quality": community.get("data_quality"),
        # Marketplace figures are a worldwide secondhand price signal. The
        # anonymous API ignores curr_abbr, so these are always USD.
        "lowest_price_usd": d.get("lowest_price"),
        "num_for_sale": d.get("num_for_sale"),
        "notes": (d.get("notes") or "")[:1200] or None,
        "barcodes": [i.get("value") for i in d.get("identifiers", [])
                     if i.get("type") == "Barcode"],
    }


def search(params, limit):
    query = urllib.parse.urlencode(params)
    res = discogs_get(f"/database/search?{query}&type=release")
    if "error" in res:
        return res, []
    hits = res.get("results", [])
    # One barcode often covers several pressings - the CD and the LP, or the
    # same album pressed for different regions. Vinyl first, then the
    # widely-owned ones, because those have enough reports to judge.
    hits.sort(key=lambda r: (0 if "Vinyl" in (r.get("format") or []) else 1,
                             -(r.get("community", {}).get("have") or 0)))
    return None, hits[:limit]


# --------------------------------------------------------------------------

def classify(raw):
    """Decide what the user handed us."""
    m = re.search(r"discogs\.com/(?:[a-z]{2}/)?(?:.*/)?release/(\d+)", raw, re.I)
    if m:
        return "release", m.group(1)
    if re.match(r"^https?://", raw, re.I):
        return "shop_url", raw
    digits = re.sub(r"\D", "", raw)
    if 11 <= len(digits) <= 14:
        return "barcode", digits
    if digits and len(digits) == len(raw.strip()):
        return "release", digits          # a bare number that is not a barcode
    return "text", raw.strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="?", help="barcode, Discogs url/id, or shop url")
    ap.add_argument("--search", metavar="TEXT", help='artist and title, e.g. "daft punk discovery"')
    ap.add_argument("--shop", metavar="URL", help="also read this retailer page for price")
    ap.add_argument("--release", type=int, help="use this Discogs release id directly")
    ap.add_argument("--max-releases", type=int, default=5)
    args = ap.parse_args()

    if not (args.query or args.search or args.release):
        ap.error("give a barcode, a URL, --search TEXT, or --release ID")

    out = {}
    barcode = None
    kind = None

    if args.query:
        kind, value = classify(args.query)
        out["query"] = args.query
        out["input_type"] = kind
        if kind == "barcode":
            barcode = value
        elif kind == "release":
            args.release = args.release or int(value)
        elif kind == "shop_url":
            out["shop"] = fetch_shop(value)
            barcode = out["shop"].get("barcode")

    if args.shop and "shop" not in out:
        out["shop"] = fetch_shop(args.shop)
        barcode = barcode or out["shop"].get("barcode")

    out["barcode"] = barcode

    if args.release:
        out["releases"] = [fetch_release(args.release)]
    else:
        if barcode:
            err, hits = search({"barcode": barcode}, args.max_releases)
        elif args.search or kind == "text":
            term = args.search or args.query
            out["search_term"] = term
            err, hits = search({"q": term, "format": "Vinyl"}, args.max_releases)
        else:
            err, hits = {"error": "nothing to look up"}, []

        if err:
            out["discogs_error"] = err["error"]
        else:
            out["discogs_matches"] = len(hits)
            releases = []
            for h in hits:
                releases.append(fetch_release(h["id"]))
                time.sleep(1.2)   # stay under the 25 req/min anonymous limit
            out["releases"] = releases
            if not hits:
                out["warning"] = ("Discogs has nothing under that. Search Discogs by "
                                  "artist and title, then re-run with --release ID. "
                                  "Unregistered barcodes are common on older reissues "
                                  "and are not a quality signal.")

    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
