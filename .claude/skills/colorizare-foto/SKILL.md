---
name: colorizare-foto
description: Colorizează fotografii vechi alb-negru (sau color decolorate) cu fidelitate istorică — analizează și datează poza, cercetează culorile reale ale epocii, colorizează cu GPT Image 2 (OpenAI API direct, fallback Higgsfield sau Gemini) păstrând strict fețele și compoziția, apoi face QA obligatoriu pe comparația side-by-side. Trigger - «colorizează poza/fotografia», «fă poza asta color», «adaugă culoare la o poză veche», «restaurează și colorizează», "colorize this old photo", o poză veche + «fă-o color». NU pentru generat imagini noi din text.
---

# /colorizare-foto

Colorizare de arhivă, nu reinterpretare creativă. Ținta e „cât mai aproape de realitatea
acelor vremuri": culorile vin din cercetare (epocă, loc, obiecte), nu din imaginația
modelului, iar fețele și compoziția rămân intacte — asta e diferența față de un simplu
„make it color" aruncat într-un model de imagini.

**Nu e un generator de imagini noi.** Aici restaurăm poza cuiva: rezultatul se salvează
**lângă original**, cu log sidecar JSON — nu într-o galerie de generări.

## Setup (o singură dată)

Skill-ul e portabil: tot ce-i trebuie stă în folderul lui. Verifică la prima rulare
și, dacă lipsește ceva, dă-i utilizatorului pașii de mai jos.

1. **Instalare**: copiază folderul `colorizare-foto/` în `.claude/skills/` al
   proiectului, sau în `~/.claude/skills/` ca să fie disponibil din orice proiect.
2. **Python 3.10+** cu **Pillow**: `pip install pillow` (sau `pip3`). Atât pentru
   ruta implicită — scripturile folosesc doar biblioteca standard + Pillow.
3. **Cheia OpenAI** (ruta implicită): `OPENAI_API_KEY` — ca variabilă de mediu sau
   într-un fișier `.env` (`OPENAI_API_KEY=sk-...`). Scripturile caută `.env` în
   folderul curent, în folderul skill-ului și în părinții lor (deci un `.env` la
   rădăcina proiectului merge). Cheia se face la `platform.openai.com/api-keys`;
   contul are nevoie de credite (`platform.openai.com/settings/organization/billing`).
4. **Opțional, fallback Higgsfield**: CLI-ul `higgsfield` instalat și logat, în PATH.
   Verifică cu `command -v higgsfield`. Dacă nu există, sari peste Ruta 2.
5. **Opțional, ruta Gemini**: `pip install google-genai` + `GEMINI_API_KEY`
   (din `aistudio.google.com/apikey`), în env sau în același `.env`.

Minimul funcțional = pașii 1–3. Fără nicio cheie configurată, skill-ul nu poate
colora — oprește-te și dă utilizatorul pașii de mai sus, nu improviza altă rută.

## Pasul 0 — Context de la utilizator

**Întrebările către utilizator se pun în limba lui** (doar promptul de engine
rămâne în engleză, la Pasul 3).

O singură rundă de întrebări, la început (nu pe parcurs): **când** e făcută poza (an /
deceniu, chiar aproximativ), **unde**, **cine** apare / cu ce ocazie, și — cel mai
valoros — **culori știute din memoria familiei** („rochia bunicii era albastră",
„casa era văruită verde"). O culoare confirmată de familie bate orice cercetare.

Dacă nu există detalii sau rulezi autonom: mergi mai departe pe estimări și marchează-le
explicit ca estimări în raportul final.

## Pasul 1 — Analiza pozei

Citește imaginea (Read) și fă inventarul a tot ce va primi culoare: persoane (haine,
piele, păr, accesorii), uniforme și însemne, obiecte, vehicule, clădiri, vegetație,
inscripții. Apoi datează poza din indicii: croiala hainelor, coafuri, tehnica din cadru,
tipul de hârtie/margini/ștampile, stilul de studio. Notează și defectele (zgârieturi,
îndoituri, pete) — se pot repara în aceeași trecere.

Atenție la tipul de film: pe **ortocromatic** (până prin anii '30) roșul iese aproape
negru — buze foarte închise nu înseamnă ruj închis. Detaliile sunt în
[references/istoric-culori.md](references/istoric-culori.md).

## Pasul 2 — Cercetarea culorilor

1. Începe cu [references/istoric-culori.md](references/istoric-culori.md) — perioade,
   uniforme, vehicule, interioare, plus capcanele AI de interzis în prompt. (Referința
   e focusată pe România; pentru alte țări, cercetează echivalentele pe web.)
2. Pentru orice element marcat **⚠ verifică** acolo — și în general pentru **uniforme,
   steaguri, steme, insigne, decorații** — fă WebSearch înainte de a colora. Regula de
   aur: obiectele purtătoare de simbol nu se ghicesc niciodată.
3. Ce rămâne estimat (moda zonei, culoarea unei case) se notează ca estimare în raport.

## Pasul 3 — Promptul

Promptul de engine e **în engleză**. Șablonul — blocul de conservare e nenegociabil
și se trimite întotdeauna întreg:

```
Colorize this old black-and-white photograph. This is an archival restoration of a
real historical photo, not a creative reinterpretation.

STRICT PRESERVATION (non-negotiable):
- Keep the exact composition, framing, geometry and every detail of the original.
- Do not alter faces, expressions, apparent age, body shape or identity in any way.
- Do not add, remove or move any object, person or background element.
- Do not beautify: no skin smoothing, no teeth whitening, no sharpening, nothing modernized.
- Keep the original film grain and soft-focus character.
[- Repair the visible scratches, creases and dust spots, changing nothing else.]

COLOR DIRECTION (era: {epoca}, place: {loc}):
- {element}: {culoarea + de unde vine — cercetat / confirmat de familie / estimat}
- ... (un rând per element din inventarul Pasului 1)
- Overall palette: natural and slightly muted, consistent with {epoca} color
  photography; varied realistic skin tones (not uniform orange); white stays white.
- Forbidden: teal-orange grading, modern digital saturation, turquoise skies,
  blue-tinted shadows.
```

Rândul de reparat zgârieturi intră doar dacă poza are defecte și utilizatorul vrea și
restaurare, nu doar culoare.

Dacă poza e o fotografie recentă A UNUI print (printul pe o masă, ținut în mână):
adaugă în prompt o notă de framing — masa și marginea de hârtie sunt deja în culoare
reală și rămân neatinse; se colorizează doar imaginea monocromă din print.

## Pasul 4 — Generarea

**Model implicit: GPT Image 2** — look-ul cel mai bun pe testele comparative, dar
driftează fețele mai des decât Gemini; de-asta QA-ul de la Pasul 5 e obligatoriu.

Scripturile stau în `scripts/` în folderul skill-ului (calea de bază a skill-ului
e afișată la încărcare — folosește-o, nu ghici căi absolute).

**Ruta 1 (implicită): OpenAI API direct** — `OPENAI_API_KEY` din env/`.env`,
endpoint `images/edits` cu poza atașată. Scriptul face tot (aspect, versionare, sidecar):

```bash
G="<folderul-skill-ului>/scripts/colorize_gpt.py"
python3 "$G" run "poza.jpg" --prompt "…"                 # quality high (implicit)
python3 "$G" run "poza.jpg" --prompt "…" --quality medium  # iterații mai ieftine
```

Cost: ~$0.05/imagine la `medium`, ~$0.15 la `high`. Dacă API-ul răspunde **429
`insufficient_quota`** (scriptul iese cu **exit code 3**) = zero credite pe cont —
spune-i utilizatorului să încarce la `platform.openai.com/settings/organization/billing`
și, dacă există CLI-ul, treci pe Ruta 2.

**Ruta 2 (fallback, doar dacă `command -v higgsfield` există): Higgsfield
`gpt_image_2`** — 7 credite/imagine, același prompt, același model de bază:

```bash
higgsfield generate create gpt_image_2 --prompt "…" --image-references "poza.jpg" \
  --aspect_ratio 3:4 --quality high --json --wait --wait-timeout 10m
# --aspect_ratio = cel mai apropiat de proporția pozei (3:4, 2:3, 1:1 …)
# descarcă imediat `result_url` (link-urile expiră) și salvează lângă original
# cu aceeași convenție de nume + sidecar JSON ca scriptul
```

**Ruta 3 (alternativă): Gemini**, prin `colorize.py` — util când vrei fidelitate
maximă de fețe (Gemini 3 Pro și Nano Banana Pro păstrează fețele mai bine decât
GPT Image 2). Cere `google-genai` + `GEMINI_API_KEY` (vezi Setup):

```bash
C="<folderul-skill-ului>/scripts/colorize.py"
python3 "$C" run "poza.jpg" --prompt "…" --tier pro
```

Rulează pozele **una câte una**, nu în paralel.

## Pasul 5 — QA de fidelitate (obligatoriu, la fiecare variantă)

Colorizarea generativă poate „ajusta" fețe și detalii — de-asta QA-ul nu e opțional:

```bash
C="<folderul-skill-ului>/scripts/colorize.py"
python3 "$C" compare "poza.jpg" "poza - colorizata.png"
```

Atenție specială cu modelul implicit: GPT Image 2 redesenează fețele mai des decât
Gemini/Nano Banana — punctul 1 (identitate) se verifică cu zoom pe fețe (crop mărit
cu Pillow, apoi Read), nu doar pe imaginea întreagă.

Citește comparația (Read) și verifică punct cu punct:

1. **Identitate**: aceleași fețe, aceleași expresii, aceeași vârstă aparentă. Cel mai
   frecvent drift și cel mai grav — o bunică cu altă față nu e o restaurare.
2. **Compoziție**: nimic adăugat, șters sau mutat; același număr de persoane; fundal identic.
3. **Inscripții**: orice text din cadru a rămas neatins.
4. **Culori**: consistente cu spec-ul cercetat; fără saturație modernă; albul alb.
5. **Fără înfrumusețare**: granulația păstrată, pielea nefiltrată.

Dacă ceva a driftat: reîncearcă cu blocul de conservare întărit punctual („the third
person's face must remain pixel-identical…"). Maximum 3 încercări; dacă driftul
persistă, livrează cea mai bună variantă și spune exact ce nu a ieșit — nu ascunde.

## Pasul 6 — Livrarea

Lângă original rămân: `- colorizata.png` (+ sidecar JSON) și `- comparatie.png`.
Deschide folderul pentru utilizator (`open <folder>` pe macOS, `explorer` pe Windows,
`xdg-open` pe Linux). Raportul final, scurt, per poză: epoca presupusă și pe ce
indicii, ce culori sunt **cercetate / confirmate de familie / estimate**, și orice
compromis de fidelitate rămas. Spune întotdeauna pe ce rută a mers generarea.

Notă de publicare: dacă poza colorizată se publică public, menționează în
descriere/caption că e o colorizare AI a unei fotografii reale (în UE, obligație
de transparență — EU AI Act art. 50).

Opțional, doar la cerere (ex. pentru print mare): upscale printr-un serviciu de
upscaling la alegerea utilizatorului (ex. Higgsfield, dacă are CLI-ul).

## Variantă: poza e deja color, dar decolorată

Print-urile color vechi (Orwo, Kodak anii '70–'90) virează spre magenta/roșu. Acolo nu
se reinventează culorile — se recuperează. Înlocuiește secțiunea COLOR DIRECTION cu:

```
This is a faded color print with a strong magenta/red cast from dye deterioration.
Restore the original colors: neutralize the cast, recover the faded dyes, keep the
period-correct muted palette. Do not re-imagine or re-colorize anything — only
restore what the print originally showed. (+ același bloc STRICT PRESERVATION)
```

## Batch (folder de poze)

Aceiași pași, secvențial, poză cu poză — analiza și spec-ul de culori sunt per poză,
nu se reciclează un prompt generic pe tot folderul. La final: un singur raport cu
tabelul epocă / culori cercetate vs. estimate / probleme, per poză.

## Fallback și costuri

- Lanțul de rute: **OpenAI API (gpt-image-2)** → la exit code 3 (`insufficient_quota`)
  → **Higgsfield `gpt_image_2`** (7 credite/imagine, doar dacă CLI-ul există) →
  **Gemini** (`colorize.py`, dacă există cheia). Spune întotdeauna pe ce rută a mers.
- Cost imagine OpenAI: ~$0.05 la `medium`, ~$0.15 la `high`.
- Din testele comparative: GPT Image 2 = look-ul cel mai plăcut (default), dar
  redesenează fețele cel mai des; Nano Banana Pro și Gemini 3 Pro = fețele cele mai
  fidele. La drift de fețe persistent după 3 încercări, propune-i utilizatorului
  ruta Gemini.
