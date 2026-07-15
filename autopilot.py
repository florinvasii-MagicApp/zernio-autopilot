#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zernio Autopilot — generează și programează automat postări motivaționale
pe Instagram (ambele conturi), săptămânal, fără intervenție umană.

Sursa conținutului: quotes.json (bancă pre-aprobată). Scriptul NU inventează
citate — doar alege, verifică și publică. Verificări automate incluse:
  - citatul are atribuire
  - fără repetarea citatelor din ultimele 6 săptămâni (history.json)
  - lungimea caption-ului sub limita Instagram (2200)
  - imaginea s-a generat corect

Comenzi:
  python autopilot.py accounts   -> listează ID-urile conturilor din Zernio
  python autopilot.py generate   -> generează postările + imaginile săptămânii
  python autopilot.py schedule   -> programează postările prin API-ul Zernio
"""
import json, os, sys, random, hashlib, math
from datetime import datetime, timedelta

import requests
from PIL import Image, ImageDraw, ImageFont

API = "https://zernio.com/api/v1"
KEY = os.environ.get("ZERNIO_API_KEY", "")
ROOT = os.path.dirname(os.path.abspath(__file__))
MEDIA = os.path.join(ROOT, "media")
PLAN = os.path.join(ROOT, "plan_saptamana.json")

W, H = 1080, 1350
BG, GOLD = (18, 19, 22), (201, 164, 92)
IVORY, MUTED = (233, 230, 223), (150, 148, 142)

# ---------------- utilitare ----------------

def load(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return json.load(f)

def save(name, data):
    with open(os.path.join(ROOT, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def zernio(method, path, **kw):
    if not KEY:
        sys.exit("EROARE: setează secretul ZERNIO_API_KEY")
    r = requests.request(method, API + path,
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"},
        timeout=60, **kw)
    if not r.ok:
        sys.exit(f"EROARE Zernio {r.status_code} la {path}:\n{r.text[:800]}")
    return r.json()

def fonts():
    fdir = os.path.join(ROOT, "fonts")
    os.makedirs(fdir, exist_ok=True)
    urls = {
        "CormorantGaramond.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf",
        "Montserrat.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
    }
    for name, url in urls.items():
        p = os.path.join(fdir, name)
        if not os.path.exists(p):
            open(p, "wb").write(requests.get(url, timeout=60).content)
    return fdir

def font(fdir, fam, size, weight):
    f = ImageFont.truetype(os.path.join(fdir, fam), size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f

def wrap(d, text, fnt, maxw):
    out = []
    for para in text.split("\n"):
        cur = ""
        for w_ in para.split():
            t = (cur + " " + w_).strip()
            if d.textlength(t, font=fnt) <= maxw:
                cur = t
            else:
                out.append(cur); cur = w_
        out.append(cur)
    return out

def spiral(d, cx, cy, scale, color, width=3):
    pts = []
    for i in range(0, 460, 4):
        t = math.radians(i)
        r = 1.4 * math.exp(0.19 * t) * scale
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    d.line(pts, fill=color, width=width)

def render(path, fdir, header, quote, author, handle):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    m = 46
    d.rectangle([m, m, W - m, H - m], outline=GOLD, width=2)
    d.rectangle([m + 10, m + 10, W - m - 10, H - m - 10], outline=(80, 68, 46), width=1)
    spiral(d, W - 230, H - 250, 3.2, (52, 46, 34))
    hf = font(fdir, "Montserrat.ttf", 30, 600)
    d.text(((W - d.textlength(header, font=hf)) / 2, 118), header, font=hf, fill=GOLD)
    d.line([(W / 2 - 70, 178), (W / 2 + 70, 178)], fill=GOLD, width=2)
    size = 84 if len(quote) < 90 else (72 if len(quote) < 160 else 62)
    qf = font(fdir, "CormorantGaramond.ttf", size, 520)
    lines = wrap(d, quote, qf, W - 260)
    lh = int(size * 1.22)
    y = (H - len(lines) * lh) / 2 - 40
    om = font(fdir, "CormorantGaramond.ttf", 150, 600)
    d.text((W / 2 - d.textlength("\u201c", font=om) / 2, y - 150), "\u201c", font=om, fill=GOLD)
    for ln in lines:
        d.text(((W - d.textlength(ln, font=qf)) / 2, y), ln, font=qf, fill=IVORY)
        y += lh
    af = font(fdir, "Montserrat.ttf", 32, 600)
    at = "\u2014 " + author
    d.text(((W - d.textlength(at, font=af)) / 2, y + 55), at, font=af, fill=GOLD)
    bf = font(fdir, "Montserrat.ttf", 28, 500)
    d.text(((W - d.textlength(handle, font=bf)) / 2, H - 150), handle, font=bf, fill=MUTED)
    img.save(path, quality=92)

# ---------------- selecție + verificare ----------------

def qid(q):
    return hashlib.sha1(q["text"].encode()).hexdigest()[:12]

def pick_quotes(cfg_cont, quotes, history, n):
    recent = {h["id"] for h in history["folosite"][-36:]}  # ~6 săptămâni
    pool = []
    for tema in cfg_cont["teme"]:
        for q in quotes.get(tema, []):
            pool.append((tema, q))
    proprii = [(t, q) for t, q in pool if t == "hameleonul" and qid(q) not in recent]
    externe = [(t, q) for t, q in pool if t != "hameleonul" and qid(q) not in recent]
    random.shuffle(proprii); random.shuffle(externe)
    alese = []
    # ~15% citate proprii => max 1 pe săptămână pe cont
    if proprii and random.randint(1, 100) <= cfg_cont["procent_hameleonul"] * n:
        alese.append(proprii.pop())
    while len(alese) < n and externe:
        alese.append(externe.pop())
    while len(alese) < n and proprii:  # fallback dacă banca externă e epuizată
        alese.append(proprii.pop())
    if len(alese) < n:
        sys.exit("EROARE: banca de citate e epuizată — adaugă citate noi în quotes.json")
    return alese

def caption(q, hashtags):
    intro = random.choice([
        "Salvează acest gând pentru zilele grele. \U0001f90d",
        "Citește-l de două ori. A doua oară, cu voce tare.",
        "Un singur gând bun poate schimba direcția unei zile întregi.",
        "Repetă-l 7 dimineți la rând și urmărește ce se schimbă.",
    ])
    text = f"\u201e{q['text']}\u201d \u2014 {q['autor']}\n\n{intro}\n\n{hashtags}"
    # verificări automate
    assert q["autor"].strip(), "citat fără atribuire"
    assert len(text) <= 2200, "caption peste limita Instagram"
    assert text.count("#") >= 3, "prea puține hashtag-uri"
    return text

def next_weekday(start, day_name):
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    delta = (days.index(day_name) - start.weekday()) % 7
    if delta == 0:
        delta = 7
    return start + timedelta(days=delta)

# ---------------- comenzi ----------------

def cmd_accounts():
    data = zernio("GET", "/accounts")
    for a in data.get("accounts", data if isinstance(data, list) else []):
        print(a.get("platform"), "|", a.get("username") or a.get("name"), "| ID:", a.get("_id") or a.get("id"))

def cmd_generate():
    cfg, quotes, history = load("config.json"), load("quotes.json"), load("history.json")
    fdir = fonts()
    os.makedirs(MEDIA, exist_ok=True)
    now = datetime.now()
    tag = now.strftime("%Y%m%d")
    plan = []
    for key, cont in cfg["conturi"].items():
        alese = pick_quotes(cont, quotes, history, len(cont["zile_ore"]))
        for (tema, q), (day, hh) in zip(alese, cont["zile_ore"]):
            when = next_weekday(now, day).strftime("%Y-%m-%d") + "T" + hh + ":00"
            fname = f"{tag}-{key}-{day.lower()}.jpg"
            header = "AFIRMA\u021aIA DIMINE\u021aII" if tema == "afirmatii" else "G\u00c2NDUL ZILEI"
            render(os.path.join(MEDIA, fname), fdir, header, q["text"], q["autor"], cont["handle"])
            url = f"https://raw.githubusercontent.com/{cfg['github_user']}/{cfg['github_repo']}/main/media/{fname}"
            plan.append({
                "account_id": cont["zernio_account_id"],
                "content": caption(q, random.choice(cfg["hashtag_seturi"])),
                "schedule_time": when,
                "timezone": cfg["timezone"],
                "media_url": url,
            })
            history["folosite"].append({"id": qid(q), "data": tag, "cont": key})
    save("history.json", history)
    with open(PLAN, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    print(f"Generat: {len(plan)} postări + imagini în /media")

def cmd_schedule():
    with open(PLAN, encoding="utf-8") as f:
        plan = json.load(f)
    for p in plan:
        # verificare automată finală: imaginea e accesibilă public
        chk = requests.head(p["media_url"], timeout=30, allow_redirects=True)
        if chk.status_code != 200:
            sys.exit(f"EROARE: imaginea nu e publică încă: {p['media_url']}")
        body = {
            "content": p["content"],
            "platforms": [{"platform": "instagram", "accountId": p["account_id"]}],
            "scheduledFor": p["schedule_time"],
            "timezone": p["timezone"],
            "mediaItems": [{"type": "image", "url": p["media_url"]}],
        }
        zernio("POST", "/posts", json=body)
        print("Programat:", p["schedule_time"], "->", p["media_url"].split("/")[-1])
    print("Toate postările au fost programate.")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"accounts": cmd_accounts, "generate": cmd_generate, "schedule": cmd_schedule}.get(
        cmd, lambda: sys.exit("Folosire: autopilot.py accounts|generate|schedule"))()
