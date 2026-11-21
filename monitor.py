"""Reads the Rangsit camera snapshot and writes status.json.
Run:  python monitor.py            (normal)
      python monitor.py --debug    (saves debug.jpg with the boxes drawn)
      python monitor.py --file x.png --debug   (test on a saved screenshot)
"""
import colorsys, io, json, os, sys, urllib.parse, urllib.request
from datetime import datetime, timezone
from PIL import Image, ImageDraw

CFG = json.load(open("config.json"))
STATUS = "status.json"
LABEL = {"green": "Normal", "yellow": "Warning", "orange": "High", "red": "Critical"}


def load_image(path=None):
    if path:
        return Image.open(path).convert("RGB")
    req = urllib.request.Request(CFG["snapshot_url"], headers={
        "User-Agent": "Mozilla/5.0", "Referer": CFG["camera_page"]})
    return Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=30).read())).convert("RGB")


def scaled(box, img):
    k = img.width / CFG["ref_width"]
    return tuple(int(v * k) for v in box)


def fraction(img, band):
    crop = img.crop(scaled(band["box"], img)).resize((40, 40))
    ok = 0
    for r, g, b in crop.get_flattened_data() if hasattr(crop, "get_flattened_data") else crop.getdata():
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        h *= 360
        if s >= band["sat"] and v >= band["val"] and any(lo <= h <= hi for lo, hi in band["hue"]):
            ok += 1
    return ok / 1600


def read_level(img):
    fr = {name: round(fraction(img, b), 2) for name, b in CFG["bands"].items()}
    hidden = {n for n, f in fr.items() if f < CFG["min_fraction"]}
    # the highest band that is no longer visible is where the water is
    for name in ("red", "orange", "yellow"):
        if name in hidden:
            return name, fr
    return "green", fr


def brightness(img):
    return sum(img.resize((32, 18)).convert("L").tobytes()) / (32 * 18)


def notify(text):
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=20)
    except Exception as e:
        print("telegram failed:", e)


def main():
    args = sys.argv[1:]
    path = args[args.index("--file") + 1] if "--file" in args else None
    img = load_image(path)

    if "--debug" in args:
        level, fr = read_level(img)
        d = ImageDraw.Draw(img)
        for n, b in CFG["bands"].items():
            d.rectangle(scaled(b["box"], img), outline="white", width=3)
        img.save("debug.jpg")
        print("level:", level, "visible fractions:", fr, "brightness:", round(brightness(img)))
        return

    try:
        old = json.load(open(STATUS))
    except Exception:
        old = {}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    st = {**old, "ok": True}

    try:
        if brightness(img) < CFG["night_min_brightness"]:
            st.update(ok=False, note="Image too dark to read", checked_at=now)
        else:
            level, fr = read_level(img)
            confirmed = old.get("level")
            # a new level must be seen on two runs in a row before it counts
            if level == confirmed:
                st["pending"] = None
            elif old.get("pending") == level or confirmed is None:
                st["level"], st["pending"] = level, None
                st["changed_at"] = now
                if confirmed is not None:
                    notify(f"Rangsit water level: {LABEL[level]} ({level})")
            else:
                st["pending"] = level
            st.update(checked_at=now, fractions=fr, note="")
            hist = old.get("history", [])
            hist.append({"t": now, "level": st.get("level", level)})
            st["history"] = hist[-288:]
    except Exception as e:
        st.update(ok=False, note=f"Error: {e}", checked_at=now)

    json.dump(st, open(STATUS, "w"), indent=1)
    print(st.get("level"), st.get("note", ""))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # camera unreachable: record it, keep the last known level
        try:
            old = json.load(open(STATUS))
        except Exception:
            old = {}
        old.update(ok=False, note=f"Camera error: {e}",
                   checked_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        json.dump(old, open(STATUS, "w"), indent=1)
        print("error:", e)
