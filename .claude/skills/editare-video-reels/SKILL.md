---
name: editare-video-reels
description: Editează clipuri vorbite (talking-head) pentru Reels, TikTok și Shorts. Taie pauzele, frazele repetate și reluările, pune subtitrări, zoom-uri, poze și clipuri B-roll cu tranziții și efecte sonore. Folosește-l când cineva încarcă un clip filmat cu telefonul și cere să fie editat, tăiat, curățat sau subtitrat.
---

# Editare video pentru Reels (talking-head)

Transformă un clip brut, filmat cu telefonul, într-un Reel curat, gata de postat. Face treaba de zi cu zi a unui editor: tăieturi, subtitrări, zoom-uri, poze și clipuri B-roll, tranziții și efecte sonore.

Nu înlocuiește un editor profesionist. Pentru efecte complexe (Premiere Pro, After Effects), spune-i asta utilizatorului de la început.

Scripturile sunt în `scripts/`. Rulează-le cu `python3 scripts/<nume>.py --help` ca să vezi argumentele. Fontul pentru subtitrări (Inter, licență OFL) e în `assets/`.

## Stilul e al utilizatorului

Fiecare creator are stilul lui. Nu copia stilul altcuiva și nu impune unul anume.

- La început, întreabă scurt (o singură dată, cu variante de ales):
  1. stilul subtitrărilor: `clasic`, `minimal` sau `bold`, ori fără subtitrări;
  2. culoarea de accent (a brandului lor), dacă au una;
  3. ce poze sau clipuri vor să apară, dacă au.
- Dacă utilizatorul nu răspunde sau zice „cum crezi tu”, alege după conținut: clip calm sau educativ → `minimal`; clip energic → `clasic` sau `bold`.
- Dacă utilizatorul are deja clipuri postate, uită-te la ele și păstrează-le stilul: font, culori, ritm.

## Regulile de aur

1. **Calitatea ieșirii este calitatea sursei.** Aceeași rezoluție, același fps, același codec și același tip de culoare. 4K60 intră, 4K60 iese. Nu micșora niciodată fără să fii rugat.
2. **Nu atinge culoarea clipului.** Fără filtre, luminozitate, contrast sau LUT-uri. Dacă sursa e HDR (HLG/PQ, 10-bit), ieșirea rămâne HDR 10-bit cu aceleași etichete de culoare. Grafica și pozele sunt convertite corect în spațiul sursei; `scripts/render.py` face asta automat.
3. **Sunetul:** vocea pe ambele canale (mono → stereo, ca „fill audio channel” din CapCut), fără ecou, reverb sau „îmbunătățiri”. Doar nivelul: `highpass 80Hz + loudnorm -16 LUFS`. Pune fade de 8–12 ms la fiecare tăietură, altfel se aud pocnituri.
4. **Fără pauză la început.** Clipul pornește direct pe prima vorbă.
5. **Pauzele dintre fraze rămân scurte**, ~0,1 s. Clipurile pentru Reels trebuie să fie alerte.

## Tăierea greșelilor (partea cea mai importantă)

1. **Transcrie cu timpi pe cuvânt:** `python3 scripts/transcribe.py clip.mov words.json --lang ro`. Folosește faster-whisper. Dacă modelul nu se poate descărca în mediul tău, cere-i utilizatorului subtitrările automate din CapCut exportate ca `.srt` și rulează `--srt fisier.srt`.
2. **Citește transcrierea ca un editor.** Rulează `python3 scripts/retakes.py words.json`, care îți arată frazele care încep la fel de mai multe ori.
3. **Regula reluărilor:** dacă o frază (sau începutul ei) apare din nou mai târziu, varianta de dinainte e greșită. Păstrează **ultima variantă completă**. Scoate:
   - frazele începute și abandonate;
   - coada unei reluări greșite lipită de varianta bună;
   - bâlbele de tipul „în primul rând că nu… în primul rând că…”.
4. **NU tăia în mijlocul unei fraze ca să scoți câteva cuvinte.** Vocea rămâne pe tonul de mijloc de frază și se aude tăietura. Scoate propoziții întregi sau taie doar în pauzele naturale.
5. **Taie pe liniște.** Verifică ultimele ~150 ms din fiecare bucată, ca să nu tai sfârșitul unui cuvânt („perf…” în loc de „perfect”).
6. **Scrie lista de bucăți păstrate** într-un `edl.json`: `[{"i": start_sec, "o": end_sec}, …]`. Strânge apoi pauzele cu `python3 scripts/pauses.py clip.mov edl.json edl_tight.json`.
7. **Verifică:** după randare, transcrie din nou clipul final și citește-l cap-coadă. Nu trebuie să rămână nicio dublă, niciun cuvânt tăiat și nicio frază fără sens.
8. Înainte de o randare lungă (4K60), trimite-i utilizatorului **doar vocea** (`render.py --audio-only`), ca s-o asculte.

## Subtitrări

- Trei stiluri, toate generice: `--caption-style clasic` (alb cu contur, cuvântul rostit colorat), `minimal` (alb cu umbră, fără evidențiere) și `bold` (majuscule, cuvântul rostit pe o etichetă colorată).
- Schimbă culoarea cu `--accent "#RRGGBB"` (culoarea brandului utilizatorului) și fontul cu `--font font.ttf`, dacă are unul.
- **Poziția:** `--caption-y 0.75` (implicit) le pune pe bărbie, sub gură, deasupra textului pe care Instagram/TikTok îl pun jos. Nu coborî sub ~0,78.
- **Fără dubluri:** când pe ecran scrie deja ce se spune (un titlu, o listă, un preț), scoate subtitrarea pentru cuvintele acelea cu `--hide-captions start-sfârșit,...` (timpul din clipul final). Restul frazei rămâne subtitrat.

## Poze, clipuri B-roll și tranziții

Toate se pun într-un `edits.json` (exemplu complet în `render.py --help`), în timpul clipului final.

- **Ce pui:** pozele și clipurile date de utilizator, capturi de ecran cu ce explică el (o aplicație, un site, un rezultat) sau clipuri cu ce descrie. Pune-le peste fraza care spune exact ce se vede, cât durează fraza (de obicei 1,5–4 s).
- **Pe tot ecranul:** `{"type": "image" | "video", "path": ..., "start": ..., "end": ...}`. Pozele au implicit zoom lent (`kenburns`), ca să nu pară înghețate.
- **Element mic peste video** (logo, captură, sticker PNG cu transparență): adaugă `"w": 0.5, "x": 0.5, "y": 0.25`. Pune-l sus, ca să nu acopere fața sau subtitrarea.
- **Tranziții** (`"in"` și `"out"`, cu durata în `"dur"`, implicit 0,25 s):
  - `fade`: discret, merge oriunde;
  - `slide`: intră din dreapta, potrivit pentru „uite ce urmează”;
  - `slideup`: urcă de jos;
  - `zoom`: intră cu zoom de 115% → 100%, pentru momente importante;
  - `pop`: pentru elemente mici.
- **Flash alb** (`{"type": "flash", "at": T}`): o tranziție scurtă între două idei. Folosește-l rar, maximum 1–2 pe clip.
- **Zoom alternativ** (100% / 115%) la fiecare tăietură, ca jump-cut-urile să pară intenționate: `--zoom-alternate`.
- Variază tranzițiile după ritmul clipului și nu le pune pe toate la fel. Mai puțin înseamnă mai curat: fără etichete decorative puse doar ca să fie.

## Efecte sonore

`scripts/sfx.py` generează un click, un pop și un whoosh fără drepturi de autor. Pune-le subtil (`gain` 0.3–0.6) și doar unde ajută: whoosh pe un slide, pop pe un element care apare, click pe un buton.

## Ce nu se face fără să ceri voie

- Card de final, logo sau „follow” la sfârșit: pune-le doar dacă utilizatorul cere.
- Conținut plătit sau privat (cursuri, ghiduri, poze cu alte persoane) nu se arată fără acordul utilizatorului.
- Nu folosi poze sau clipuri găsite pe internet decât dacă utilizatorul are dreptul să le folosească.

## Flux recomandat

1. `python3 scripts/probe.py clip.mov`: rezoluție, fps, HDR sau SDR, sunet.
2. Întreabă de stil (vezi „Stilul e al utilizatorului”).
3. `transcribe.py`, apoi `retakes.py`, apoi construiești `edl.json`, apoi rulezi `pauses.py`.
4. `render.py clip.mov edl_tight.json out_voice.m4a --audio-only` și i-o trimiți utilizatorului.
5. Faci `edits.json` cu pozele, clipurile, tranzițiile și efectele.
6. `render.py clip.mov edl_tight.json final.mp4 --captions words.json --caption-style <stil> --zoom-alternate --edits edits.json`.
7. Verifici: re-transcriere, câteva cadre extrase (`probe.py --frames final.mp4`) și sunetul pe ambele canale.

## Dacă nu ai ffmpeg

Rulează `pip install imageio-ffmpeg faster-whisper pillow numpy`. Scripturile găsesc singure binarul ffmpeg din `imageio-ffmpeg`. Pentru HDR e nevoie de un ffmpeg cu `zscale` (libzimg); cel din `imageio-ffmpeg` îl are.
