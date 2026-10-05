"""Optional school-review layer for the Calgary explorer.

Responsibility: attach a public review signal to each school already listed in
web/data/schools.json. It does NOT change exam scores and is not called by
build_data.py, so the map builds with no API keys.

Credentials (environment variables, never committed):
  GOOGLE_MAPS_API_KEY     Places API (legacy Find Place + Place Details)
  REDDIT_CLIENT_ID        Reddit OAuth app (client credentials)
  REDDIT_CLIENT_SECRET

If neither Google nor Reddit credentials are set, the script prints SKIP and
exits 0 without writing a file. If only one pair is set, that source is
fetched and the other stays null.

Storage follows the platform terms used here: Google keeps place_id, rating
and user_ratings_total only (no review text). Reddit keeps post id, date and
permalink, plus a sentiment number computed locally. Post text is not stored.

Run:  .venv/bin/python scripts/fetch_reviews.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SCHOOLS = ROOT / "web" / "data" / "schools.json"
OUT = ROOT / "web" / "data" / "reviews.json"
CACHE = ROOT / "data" / "raw" / "reviews_cache.json"
USER_AGENT = "school-maps-prototype/0.1 (public school review layer)"
SUBREDDITS = ("Calgary", "alberta", "CalgaryParents")
MIN_GOOGLE = 5
MIN_REDDIT = 3
GOOGLE_PRIOR = 3.7
GOOGLE_PRIOR_N = 10

# Tiny lexicon. Documented as a rough opinion signal, not a validated model.
POSITIVE = {"good", "great", "excellent", "love", "loved", "amazing", "wonderful", "recommend", "best", "supportive", "caring", "safe"}
NEGATIVE = {"bad", "terrible", "awful", "hate", "hated", "worst", "bully", "bullying", "avoid", "disappointing", "unsafe", "overcrowded"}


def bayes_0_100(rating: float | None, count: int | None) -> float | None:
    """Bayesian-smooth a 1-5 Google rating and scale it to 0-100.

    Prior is GOOGLE_PRIOR with weight GOOGLE_PRIOR_N, so a school with a
    handful of reviews cannot sit at 100. None when rating or count is missing.
    """
    if rating is None or count is None:
        return None
    smoothed = (count * rating + GOOGLE_PRIOR_N * GOOGLE_PRIOR) / (count + GOOGLE_PRIOR_N)
    return round((smoothed - 1) / 4 * 100, 1)


def lexicon_sentiment(title: str) -> float:
    """Return -1..1 from a title. 0 when the title has no listed words."""
    words = {w.strip(".,!?:;\"'()[]").lower() for w in title.split()}
    pos = len(words & POSITIVE)
    neg = len(words & NEGATIVE)
    if pos + neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


def sentiment_0_100(value: float | None) -> float | None:
    """Map a -1..1 sentiment onto 0-100. None stays None."""
    if value is None:
        return None
    return round((value + 1) / 2 * 100, 1)


def review_score(google_bayes: float | None, google_count: int, reddit_score: float | None, reddit_n: int) -> tuple[float | None, bool]:
    """Blend the two signals. Returns (score, too_few).

    Below MIN_GOOGLE and MIN_REDDIT the score is null and too_few is true.
    A single source above its minimum is used on its own.
    """
    google_ok = google_bayes is not None and google_count >= MIN_GOOGLE
    reddit_ok = reddit_score is not None and reddit_n >= MIN_REDDIT
    if google_ok and reddit_ok:
        return round(0.7 * google_bayes + 0.3 * reddit_score, 1), False
    if google_ok:
        return google_bayes, False
    if reddit_ok:
        return reddit_score, False
    return None, True


def load_cache() -> dict:
    """Read the raw-data cache. Missing or broken cache starts empty."""
    if not CACHE.exists():
        return {"google": {}, "reddit": {}}
    try:
        data = json.loads(CACHE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"google": {}, "reddit": {}}
    data.setdefault("google", {})
    data.setdefault("reddit", {})
    return data


def save_cache(cache: dict) -> None:
    """Write the raw-data cache. The directory is gitignored."""
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache), encoding="utf-8")


def google_for_school(name: str, key: str, cache: dict) -> dict | None:
    """Place id, rating and rating count for one school. None on an API miss.

    Review text is not requested. Results are cached by school name.
    """
    if name in cache["google"]:
        return cache["google"][name]
    found = requests.get(
        "https://maps.googleapis.com/maps/api/place/findplacefromtext/json",
        params={"input": f"{name} Calgary", "inputtype": "textquery", "fields": "place_id", "key": key},
        timeout=30,
    )
    found.raise_for_status()
    candidates = found.json().get("candidates") or []
    if not candidates:
        cache["google"][name] = None
        return None
    place_id = candidates[0]["place_id"]
    details = requests.get(
        "https://maps.googleapis.com/maps/api/place/details/json",
        params={"place_id": place_id, "fields": "place_id,rating,user_ratings_total", "key": key},
        timeout=30,
    )
    details.raise_for_status()
    result = details.json().get("result") or {}
    record = {
        "place_id": result.get("place_id") or place_id,
        "rating": result.get("rating"),
        "count": result.get("user_ratings_total"),
    }
    cache["google"][name] = record
    time.sleep(0.05)
    return record


def reddit_token(client_id: str, secret: str) -> str:
    """Application-only OAuth token. Raises if Reddit rejects the credentials."""
    resp = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=(client_id, secret),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("Reddit token response had no access_token")
    return token


def reddit_for_school(name: str, token: str, cache: dict) -> list[dict]:
    """Matching posts for one school. Titles are used then discarded.

    A post counts only when its title contains the school name. Short names
    are skipped so street and community names are not treated as the school.
    """
    if name in cache["reddit"]:
        return cache["reddit"][name]
    if len(name) < 8:
        cache["reddit"][name] = []
        return []
    query = f'"{name}"'
    posts: list[dict] = []
    headers = {"Authorization": f"bearer {token}", "User-Agent": USER_AGENT}
    for sub in SUBREDDITS:
        resp = requests.get(
            f"https://oauth.reddit.com/r/{sub}/search",
            params={"q": query, "restrict_sr": 1, "sort": "new", "limit": 5},
            headers=headers,
            timeout=30,
        )
        if resp.status_code == 404:
            continue
        resp.raise_for_status()
        for child in resp.json().get("data", {}).get("children", []):
            data = child.get("data") or {}
            title = data.get("title") or ""
            if name.lower() not in title.lower():
                continue
            created = data.get("created_utc")
            posts.append({
                "id": data.get("id"),
                "date": datetime.fromtimestamp(created, timezone.utc).date().isoformat() if created else None,
                "permalink": "https://www.reddit.com" + (data.get("permalink") or ""),
                "sentiment": round(lexicon_sentiment(title), 2),
            })
        time.sleep(0.4)
    cache["reddit"][name] = posts
    return posts


def main() -> int:
    """CLI entry. Exit 0 on skip or success, 1 when a configured API rejects us."""
    google_key = os.environ.get("GOOGLE_MAPS_API_KEY") or ""
    reddit_id = os.environ.get("REDDIT_CLIENT_ID") or ""
    reddit_secret = os.environ.get("REDDIT_CLIENT_SECRET") or ""
    if not google_key and not (reddit_id and reddit_secret):
        print("SKIP no GOOGLE_MAPS_API_KEY or REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET; reviews not written")
        return 0
    if not SCHOOLS.exists():
        print("FAIL web/data/schools.json is missing; run scripts/build_data.py first", file=sys.stderr)
        return 1
    schools = json.loads(SCHOOLS.read_text(encoding="utf-8"))
    cache = load_cache()
    token = None
    if reddit_id and reddit_secret:
        try:
            token = reddit_token(reddit_id, reddit_secret)
        except Exception as exc:  # noqa: BLE001 - surface the auth failure and stop
            print(f"FAIL Reddit auth: {exc}", file=sys.stderr)
            return 1
    out_schools = {}
    for school in schools:
        google = None
        if google_key:
            try:
                google = google_for_school(school["name"], google_key, cache)
            except Exception as exc:  # noqa: BLE001
                print(f"WARN google {school['name']}: {exc}", file=sys.stderr)
        posts: list[dict] = []
        if token:
            try:
                posts = reddit_for_school(school["name"], token, cache)
            except Exception as exc:  # noqa: BLE001
                print(f"WARN reddit {school['name']}: {exc}", file=sys.stderr)
        count = int(google["count"]) if google and google.get("count") is not None else 0
        bayes = bayes_0_100(google.get("rating") if google else None, count if google else None)
        reddit_mean = None
        if posts:
            reddit_mean = sentiment_0_100(sum(p["sentiment"] for p in posts) / len(posts))
        dates = [p["date"] for p in posts if p.get("date")]
        score, too_few = review_score(bayes, count, reddit_mean, len(posts))
        out_schools[str(school["id"])] = {
            "google": None if not google else {"place_id": google["place_id"], "rating": google["rating"], "count": count, "bayes": bayes},
            "reddit": {"n": len(posts), "sentiment": reddit_mean, "posts": posts},
            "review_score": score,
            "too_few": too_few,
            "date_range": [min(dates), max(dates)] if dates else None,
        }
        save_cache(cache)
    payload = {
        "as_of": datetime.now(timezone.utc).date().isoformat(),
        "min_google": MIN_GOOGLE,
        "min_reddit": MIN_REDDIT,
        "schools": out_schools,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.name} for {len(out_schools)} schools")
    return 0


if __name__ == "__main__":
    sys.exit(main())
