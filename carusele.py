#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Programează în Zernio caruselele din carusele/coada.json.
Slide-urile stau în carusele/<slug>/01.jpg ... NN.jpg și sunt publice prin
raw.githubusercontent.com. Scriptul verifică fiecare imagine înainte de
programare și oprește rularea la orice eroare.
"""
import json, os, sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

API = "https://zernio.com/api/v1"
KEY = os.environ.get("ZERNIO_API_KEY", "")
ROOT = os.path.dirname(os.path.abspath(__file__))
COADA = os.path.join(ROOT, "carusele", "coada.json")
BRANCH = os.environ.get("GITHUB_REF_NAME") or "main"


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def zernio_post(body):
    r = requests.post(API + "/posts",
                      headers={"Authorization": "Bearer " + KEY,
                               "Content-Type": "application/json"},
                      json=body, timeout=60)
    if not r.ok:
        sys.exit(f"EROARE Zernio {r.status_code}:\n{r.text[:800]}")
    return r.json()


def main():
    if not KEY:
        sys.exit("EROARE: lipsește secretul ZERNIO_API_KEY")
    cfg = load(os.path.join(ROOT, "config.json"))
    coada = load(COADA)
    tz = ZoneInfo(cfg["timezone"])
    acum = datetime.now(tz)
    schimbat = False

    for c in coada["carusele"]:
        if c.get("status") != "de_programat":
            continue
        cand = datetime.fromisoformat(c["schedule_time"]).replace(tzinfo=tz)
        if cand <= acum:
            c["status"] = "expirat"
            c["nota"] = f"ora {c['schedule_time']} trecuse la rulare"
            schimbat = True
            print("Sărit (ora a trecut):", c["slug"])
            continue

        base = (f"https://raw.githubusercontent.com/{cfg['github_user']}/"
                f"{cfg['github_repo']}/{BRANCH}/carusele/{c['slug']}")
        urls = [f"{base}/{i:02d}.jpg" for i in range(1, int(c["slides"]) + 1)]
        for u in urls:
            chk = requests.head(u, timeout=30, allow_redirects=True)
            if chk.status_code != 200:
                sys.exit(f"EROARE: imaginea nu e publică: {u}")

        assert len(c["caption"]) <= 2200, "caption peste limita Instagram"
        assert 2 <= len(urls) <= 10, "un carusel are între 2 și 10 imagini"

        rezultate = []
        for cheie in c["conturi"]:
            cont = cfg["conturi"][cheie]
            body = {
                "content": c["caption"],
                "platforms": [{"platform": "instagram",
                               "accountId": cont["zernio_account_id"]}],
                "scheduledFor": c["schedule_time"],
                "timezone": cfg["timezone"],
                "mediaItems": [{"type": "image", "url": u} for u in urls],
            }
            raspuns = zernio_post(body)
            pid = (raspuns.get("post") or {}).get("_id") or raspuns.get("_id") or raspuns.get("id")
            rezultate.append({"cont": cheie, "zernio_post_id": pid})
            print("Programat:", c["slug"], "->", cont["handle"], c["schedule_time"])

        c["status"] = "programat"
        c["zernio"] = rezultate
        schimbat = True

    if schimbat:
        with open(COADA, "w", encoding="utf-8") as f:
            json.dump(coada, f, ensure_ascii=False, indent=2)
    print("Gata.")


if __name__ == "__main__":
    main()
