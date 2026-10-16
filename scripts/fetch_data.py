"""Runs inside GitHub Actions. Writes data/events.json (always) and data/photos.json (every ~4h).
Secrets come from environment variables, never from the repo: CAL_URL (required), ALBUM_URL (optional)."""
import datetime as dt, json, os, re, time, urllib.request, urllib.error
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/London")
UA = {"User-Agent": "Mozilla/5.0 tv-dashboard"}
# Fallback module names, used when an event has no description. The feed's own description is preferred.
NAMES = {"CSC8202": "Information Security and Trust", "CSC8204": "High Integrity Software Development",
         "CSC8207": "Security Analysis of Complex Systems",
         "CSC8208": "Research Methods and Group Project in Security and Resilience",
         "CSC8209": "Project and Dissertation in Computer Security and Resilience",
         "CSC8213": "Advanced Topics in Cyber Security", "CSC8214": "Systems Security",
         "CSC8215": "Network Security and Ethical Hacking", "CSC8216": "Risk and Trust Management",
         "INU6414": "Writing for Postgraduates in Computer Science",
         "INU6424": "Writing for Postgraduates in Computer Science"}


def events():
    import icalendar, recurring_ical_events
    url = os.environ["CAL_URL"].replace("webcal://", "https://", 1)
    raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
    cal = icalendar.Calendar.from_ical(raw)
    now = dt.datetime.now(TZ)
    out = []
    for ev in recurring_ical_events.of(cal).between(now - dt.timedelta(days=1), now + dt.timedelta(days=21)):
        try:
            s, e = ev["DTSTART"].dt, ev.get("DTEND", ev["DTSTART"]).dt
            allday = not isinstance(s, dt.datetime)
            if allday:
                s, e = dt.datetime.combine(s, dt.time(), TZ), dt.datetime.combine(e, dt.time(), TZ)
            else:
                s, e = (x if x.tzinfo else x.replace(tzinfo=TZ) for x in (s, e))
            title = str(ev.get("SUMMARY", ""))
            code = title.split("/")[0].strip()
            lines = [x.strip() for x in str(ev.get("DESCRIPTION", "")).split("\n")]
            name = (lines[0] if lines[0] else NAMES.get(code, "")).replace("Postgaduates", "Postgraduates")
            out.append({"s": int(s.timestamp() * 1000), "e": int(e.timestamp() * 1000), "a": allday,
                        "t": title, "l": str(ev.get("LOCATION", "")), "n": name,
                        "k": lines[1].lower() if len(lines) > 1 else "",
                        "c": code if re.fullmatch(r"[A-Z]{3}\d{4}", code) else ""})
        except Exception as exc:
            print("skipped one event:", exc)
    out.sort(key=lambda x: x["s"])
    json.dump(out, open("data/events.json", "w"), separators=(",", ":"))
    print(f"{len(out)} events written")


B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def b62(s):
    n = 0
    for c in s:
        n = n * 62 + B62.index(c)
    return n


def post(host, tok, path, body):
    for _ in range(3):  # iCloud may answer 330 with a different host to use
        req = urllib.request.Request(f"https://{host}/{tok}/sharedstreams/{path}", json.dumps(body).encode(),
                                     {"Content-Type": "text/plain", **UA})
        try:
            return json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as err:
            if err.code != 330:
                raise
            host = json.load(err)["X-Apple-MMe-Host"]
    raise RuntimeError("too many redirects")


def photos():
    try:
        if time.time() - json.load(open("data/photos.json"))["ts"] < 4 * 3600:
            return
    except Exception:
        pass
    tok = os.environ["ALBUM_URL"].rstrip("/").split("/")[-1].split("#")[-1]
    host = f"p{b62(tok[1]) if tok[0] == 'A' else b62(tok[1:3]):02d}-sharedstreams.icloud.com"
    stream = post(host, tok, "webstream", {"streamCtag": None})
    host = stream.get("X-Apple-MMe-Host", host)
    best = {}  # photoGuid -> checksum of largest photo derivative
    for p in stream["photos"]:
        sizes = [k for k in p["derivatives"] if k.isdigit()]
        if sizes:
            best[p["photoGuid"]] = p["derivatives"][max(sizes, key=int)]["checksum"]
    assets = post(host, tok, "webasseturls", {"photoGuids": list(best)})
    urls = []
    for chk in best.values():
        item = assets["items"].get(chk)
        if item:
            urls.append("https://" + item["url_location"] + item["url_path"])
    json.dump({"ts": int(time.time()), "urls": urls}, open("data/photos.json", "w"))


os.makedirs("data", exist_ok=True)
events()
if os.environ.get("ALBUM_URL"):
    try:
        photos()
    except Exception as exc:  # photos are only a fallback, so never fail the calendar update
        print("photos skipped:", exc)