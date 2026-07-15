# Zernio Autopilot — postări Instagram 100% automate

În fiecare duminică la 18:00, robotul: alege citate din banca pre-aprobată
(`quotes.json`), generează imaginile aurii, le publică pe GitHub ca linkuri
publice și programează postările săptămânii prin API-ul Zernio, pe ambele
conturi. Fără nicio intervenție umană.

## Instalare (o singură dată, ~15 minute)

1. **Creează repository-ul** pe github.com: `New repository` → nume
   `zernio-autopilot` → **Public** (obligatoriu, ca imaginile să aibă linkuri
   publice) → Create. Încarcă toate fișierele din acest pachet
   (`Add file → Upload files`, inclusiv folderul `.github/workflows/`).

2. **Adaugă cheia Zernio ca secret**: în repo → Settings → Secrets and
   variables → Actions → New repository secret → nume `ZERNIO_API_KEY`,
   valoare = cheia ta `sk_...` (cea regenerată!).

3. **Completează `config.json`**:
   - `github_user` = numele tău de utilizator GitHub
   - ID-urile conturilor Instagram din Zernio: rulează local
     `ZERNIO_API_KEY=sk_... python autopilot.py accounts`
     sau ia ID-urile din dashboard-ul Zernio → Accounts.
   - Contul „Hameleonul Invizibil" trebuie să fie deja conectat în Zernio.

4. **Test manual**: repo → Actions → „Zernio Autopilot" → Run workflow.
   Dacă totul e verde, verifică în Zernio → Posts că au apărut 6 postări
   programate. De aici încolo rulează singur, duminica.

## Cum îl controlezi fără să-l atingi

- **Adaugi citate noi** (inclusiv din carte): editezi `quotes.json` direct
  din browser, pe GitHub. Robotul le ia automat.
- **Schimbi zilele/orele**: `config.json` → `zile_ore`.
- **Îl oprești**: Actions → Zernio Autopilot → ⋯ → Disable workflow.

## Verificările automate (centura de siguranță)

- citatele vin DOAR din quotes.json — robotul nu inventează conținut
- fără repetări în ultimele ~6 săptămâni (history.json)
- atribuire obligatorie, caption sub 2200 caractere, minim 3 hashtag-uri
- înainte de programare, verifică că fiecare imagine e accesibilă public
- dacă orice verificare pică, rularea se oprește cu eroare vizibilă în
  Actions (primești email de la GitHub) și NU se postează nimic greșit

## Notă despre API

Formatul exact al câmpurilor `POST /posts` (mediaItems / scheduledFor) poate
diferi ușor de documentația Zernio. Dacă primele rulări dau eroare 400,
mesajul complet apare în log-ul din Actions — trimite-l lui Claude și
ajustează payload-ul din `cmd_schedule()` în consecință.
