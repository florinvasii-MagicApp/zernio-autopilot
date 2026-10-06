#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Înlocuiește postările cu citate deja programate în Zernio (din plan_saptamana.json)
cu postări noi, în formatul cu explicație („Pe scurt” + „Azi”), pe aceleași
zile și ore.

  python inlocuieste.py sterge     -> șterge din Zernio postările viitoare din plan
  python inlocuieste.py genereaza  -> generează postări noi doar pentru sloturile șterse

Siguranță: se șterg DOAR postările programate a căror imagine e una din planul
curent. Se generează postări noi DOAR pentru sloturile efectiv șterse, deci nu
pot apărea dubluri.
"""
import json, os, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import autopilot as a

STARE = os.path.join(a.ROOT, "inlocuire", "stare.json")
MARJA_MIN = 30  # nu atingem postările care pleacă în mai puțin de 30 de minute


def lista_programate():
    posts, page = [], 1
    while page <= 20:
        data = a.zernio("GET", f"/posts?status=scheduled&limit=100&page={page}")
        batch = data.get("posts") if isinstance(data, dict) else data
        batch = batch or (data.get("data") if isinstance(data, dict) else []) or []
        posts += batch
        if len(batch) < 100:
            break
        page += 1
    return posts


def media_urls(p):
    out = []
    for m in p.get("mediaItems") or p.get("media") or []:
        if isinstance(m, dict):
            out.append(m.get("url") or "")
        else:
            out.append(str(m))
    return out


def cmd_sterge():
    cfg = a.load("config.json")
    tz = ZoneInfo(cfg["timezone"])
    limita = datetime.now(tz) + timedelta(minutes=MARJA_MIN)
    with open(a.PLAN, encoding="utf-8") as f:
        plan = json.load(f)
    viitoare = {}
    for p in plan:
        cand = datetime.fromisoformat(p["schedule_time"]).replace(tzinfo=tz)
        if cand > limita:
            viitoare[p["media_url"].split("/")[-1]] = p
    print("Sloturi viitoare în plan:", len(viitoare))

    sterse = []
    for post in lista_programate():
        pid = post.get("_id") or post.get("id")
        for url in media_urls(post):
            nume = url.split("/")[-1]
            if nume in viitoare and pid:
                a.zernio("DELETE", f"/posts/{pid}")
                p = viitoare.pop(nume)
                sterse.append({"account_id": p["account_id"],
                               "schedule_time": p["schedule_time"],
                               "vechi": nume, "zernio_post_id": pid})
                print("Șters:", nume, p["schedule_time"])
                break
    if viitoare:
        print("ATENȚIE: negăsite în Zernio (rămân neatinse):", ", ".join(viitoare))
    os.makedirs(os.path.dirname(STARE), exist_ok=True)
    with open(STARE, "w", encoding="utf-8") as f:
        json.dump({"sterse": sterse}, f, ensure_ascii=False, indent=2)
    if not sterse:
        sys.exit("EROARE: nicio postare găsită de înlocuit — nu generez nimic nou.")


def cmd_genereaza():
    cfg, quotes, history = a.load("config.json"), a.load("quotes.json"), a.load("history.json")
    with open(STARE, encoding="utf-8") as f:
        sterse = json.load(f)["sterse"]
    fdir = a.fonts()
    tag = datetime.now().strftime("%Y%m%d")
    plan = []
    for key, cont in cfg["conturi"].items():
        sloturi = sorted(s["schedule_time"] for s in sterse
                         if s["account_id"] == cont["zernio_account_id"])
        if not sloturi:
            continue
        alese = a.pick_quotes(cont, quotes, history, len(sloturi))
        for (tema, q), when in zip(alese, sloturi):
            day = datetime.fromisoformat(when).strftime("%a").lower()
            fname = f"{tag}-{key}-{day}-v2.jpg"
            header = "AFIRMAȚIA DIMINEȚII" if tema == "afirmatii" else "GÂNDUL ZILEI"
            a.render(os.path.join(a.MEDIA, fname), fdir, header, q["text"], q["autor"],
                     cont["handle"], q["pe_scurt"], q["azi"])
            url = (f"https://raw.githubusercontent.com/{cfg['github_user']}/"
                   f"{cfg['github_repo']}/main/media/{fname}")
            plan.append({
                "account_id": cont["zernio_account_id"],
                "content": a.caption(q, a.random.choice(cfg["hashtag_seturi"])),
                "schedule_time": when,
                "timezone": cfg["timezone"],
                "media_url": url,
            })
            history["folosite"].append({"id": a.qid(q), "data": tag, "cont": key})
    a.save("history.json", history)
    with open(a.PLAN, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    print(f"Generat: {len(plan)} postări noi pentru sloturile șterse")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"sterge": cmd_sterge, "genereaza": cmd_genereaza}.get(
        cmd, lambda: sys.exit("Folosire: inlocuieste.py sterge|genereaza"))()
