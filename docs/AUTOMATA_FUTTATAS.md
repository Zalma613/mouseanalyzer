# Automata kötegelt futtatás – útmutató (AI és ember számára)

Ez a leírás a 2026-10 „diabtea létra” videók elemzéséhez készült (45 videó), de bármely hasonló
vízszintes-létra (horizontal ladder) felvételsorozatra használható. Cél: a futtatás pontosan
megismételhető legyen GUI nélkül.

## 1. Környezet

| Elem | Érték |
|---|---|
| Kód | `/Users/zalma/Dokumentumok/AOK/MouseAnalyzer` (`MouseTracker.py`) |
| Videók | `/Users/zalma/Dokumentumok/AOK/2026-10 diabtea letra videok 0` (45 db `.MOV`) |
| Fő kimenet | `/Users/zalma/Documents/MouseAnalyzer_Eredmenyek` |
| Tükör | `/Users/zalma/Dokumentumok/AOK/2026-10 diabtea letra videok 0_eredmenyek` |
| Gép | macOS, Apple Silicon, GPU: Metal (MPS) |
| Futásidő | ~25 perc teljes futás (45 videó, 6 szál); ~40 perc a 12 leghosszabb újrafuttatása |

**AI-ügynöknek:** a videómappa és a kimeneti mappák a munkaterületen kívül vannak, ezért az ezeket
olvasó/író parancsokat sandbox nélkül kell futtatni (felhasználói jóváhagyás kell).
A tesztek és a lint sandboxban is futnak.

## 2. Futtatás

```bash
cd /Users/zalma/Dokumentumok/AOK/MouseAnalyzer

# Teljes futás (TÖRLI a kimeneti mappa Egyed_* mappáit és a fő CSV-t!)
python3 scripts/batch_analyze.py \
  --videos "/Users/zalma/Dokumentumok/AOK/2026-10 diabtea letra videok 0" \
  --out /Users/zalma/Documents/MouseAnalyzer_Eredmenyek \
  --mirror "/Users/zalma/Dokumentumok/AOK/2026-10 diabtea letra videok 0_eredmenyek" \
  --workers 6

# Csak néhány videó újrafuttatása (a többi egyed érintetlen marad, a fő CSV újraépül)
python3 scripts/batch_analyze.py --videos "..." --only 13_1.MOV diab_2.MOV --mirror "..."

# Ellenőrzés
python3 scripts/verify_exports.py /Users/zalma/Documents/MouseAnalyzer_Eredmenyek

# Áttekintő képlapok a lenyúlásokról (szemrevételezéshez)
python3 scripts/make_audit_sheets.py /Users/zalma/Documents/MouseAnalyzer_Eredmenyek /tmp/audit
```

A futás hosszú: AI-ügynökként háttérfeladatként indítsd, és várd meg az értesítést.

### Beállítások, amiket a szkript használ

| Beállítás | Érték | Megjegyzés |
|---|---|---|
| Kalibráció | videónként automatikus (`auto_calib=True`) | a kamera helyzete videócsoportonként eltér, ezért kötelező |
| Protokoll | 3 futás, csak Bal→Jobb (`lock_lr=True`, `bidirectional=False`) | |
| Kapuk távolsága | 60 cm (`--gate-cm`) | ebből számol px/cm-t |
| Képkocka-lépés | 2 (`--stride`) | |
| Lenyúlás-hűlési idő / min. távolság | 0,50 s / 30 px | |
| YOLO-fúzió, Kalman, zónák, kinematika | be | |
| Review ablak | **ki** (automata mód) | kézi jóváhagyáshoz lásd 6. pont |
| Tizedesjel | `.` | |

## 3. Az adatsor sajátosságai

- **Két kameraállás:** `1`–`17` (kivéve `13_1`) 30 fps, a létra y≈545–575 px.
  `13_1`, `18`–`20`, `diab_1`–`diab_23` 60 fps, a létra y≈595–644 px. Az automatikus kalibráció
  ezt videónként jól kezeli (ROI magasság 280 px, hibavonal 70%).
- **Egyed-azonosító = fájlnév törzse** (`diab_9_folyt`, `13_1`, `5_folyt` stb.).
- **Felbontott felvételek:** `5` + `5_folyt` és `diab_9` + `diab_9_folyt` ugyanannak az ülésnek a
  két része → külön egyedként jelennek meg 1+2, illetve 2+1 futással. Ez helyes.
- **`18.MOV`:** a 215 s-os videóban csak 2 teljes átkelés van.
- Elvárt eredmény: **128 futás, 45 egyed**.

## 4. A kódban (MouseTracker.py) végzett javítások – ezek nélkül hibás az eredmény

1. **Numba összeomlás (exit 134):** `_skin_chromaticity_numba_core` → `parallel=True/prange` helyett
   `nogil=True/range` (párhuzamos szálakból hívva összeomlott).
2. **Egyed-ID ütközés:** `_append_video_list` megtartja a leíró fájlnevet (`diab_1` ≠ `1`);
   csak kamera-előtagoknál (`IMG_`, `VID_`) vesz számot.
3. **Láb vs. farok:** `classify_dip_with_anatomy` / `classify_dip_features` – mély (≥18 px), rózsaszín
   vagy keskeny függőleges hátsó csúszás HÁTSÓ LÁB, nem FAROK.
4. **Hamis lenyúlás szűrése** (`_check_real_dip_below_line`): a lenyúlás csúcsa nem lehet világos
   háttér vagy változatlan létrafok-csúcs (a háttérhez képest ±14 px függőleges, ±3 px vízszintes
   eltolással keres).
5. **Futás-életciklus (a fő hiba, 10 videót érintett):**
   - korábban a kísérletező keze/árnyéka a jobb kapunál 0,03–0,2 s-os „célba érést” okozott; a futás
     nem mentődött, de a számláló lépett → elveszett a valódi 3. futás;
   - most: egyképkockás nagy ugrás (> max(360 px, 750 px/s)) elvetve; a felső sávot nagy területen
     takaró kéz/kar képkocka kihagyva; túl nagy maszk elvetve;
   - futás csak akkor érvényes, ha > 0,4 s **és** az egér a kapuk közti távolság ≥ 40%-át bejárta;
     érvénytelen célba érés nem lépteti a számlálót;
   - ha a startnál megindult egér 4 s-ig nem látszik és alig haladt, visszaáll várakozásra.

Ellenőrzés: `python3 -m unittest discover -s tests` (41 teszt, 1 kihagyva headless Tk miatt) és
`ruff check --select E9,F,B MouseTracker.py tests/test_mousetracker.py scripts/`.

## 5. Automatikus képminőség-szűrés (a szkriptben, export előtt)

Lenyúlásonként, a mentett képkockán:

| Szabály | Feltétel | Művelet |
|---|---|---|
| Elmosódott kép | Laplace-variancia a ROI-ban < 12 | kizár |
| Világos háttér a csúcsnál | csúcsfolt 20. percentilis > 145 és bőrpont < 11,5 | kizár |
| Statikus fokcsúcs | átlagos abs. eltérés az első képkockától < 16,5 és bőrpont < 12 | kizár |
| Kéz/kar a felső sávban | felső 25 px sáv eltérése > 42 | kizár |
| Farok → hátsó láb | FAROK, mélység ≥ 18 és (bőrpont ≥ 10,5 vagy arány ≤ 0,85) | átsorol |

Kizárt lenyúlás nem kerül a CSV-be és nem készül róla kép.

## 6. Ismert korlát – a lábhiba-szám NEM megbízható emberi ellenőrzés nélkül

Az automata futás után a 2026-10-es adatsorban **58 mancshiba** maradt. Az áttekintő lapok
szemrevételezése alapján ennek nagy része hamis volt (a mancs a létrafokon állt, vagy a start-doboz
papírjára esett a pont). Egyszeri, kézi utólagos törléssel 41 lenyúlás lett kivéve → **20 mancshiba**
(3 mellső, 17 hátsó), 126 orr, 4 farok, 150 lenyúlás összesen. Ezt a lépést a
`batch_analyze.py` **nem** ismétli meg – egy újrafuttatás ismét a nyers (~58) értéket adja.

A kézzel kivett lenyúlások listája (egyed, futás: lenyúlás-sorszámok a nyers exportban):
`2` R3: 2 · `5` R1: 1,2 · `7` R2: 1 · `7` R3: 2 · `12` R2: 3 · `17` R1: 1 · `17` R2: 3 · `17` R3: 1,3,5 ·
`18` R1: 6,7,8,9,13 · `diab_1` R2: 2 · `diab_2` R3: 1,4 · `diab_3` R1: 1 · `diab_8` R3: 1 ·
`diab_9` R1: 1,3,4 · `diab_14` R1: 1 · `diab_15` R3: 3,4,5,6 · `diab_16` R1: 1 · `diab_16` R3: 1 ·
`diab_17` R2: 5 · `diab_18` R2: 2 · `diab_20` R3: 1,4 · `diab_21` R1: 1,2 · `diab_21` R3: 1 ·
`diab_23` R1: 2 · `diab_23` R2: 4 · `diab_23` R3: 1.

Ennek a kézi lépésnek a hiányosságai:
- egy AI döntött kicsinyített képek alapján, ember nem hagyta jóvá;
- a kimaradt (fel nem ismert) valódi csúszásokat senki nem kereste;
- 4 futásnál az enyhe/mély besorolás becsült (`18` R1, `diab_1` R2, `diab_15` R3, `diab_23` R2);
- ezeknél a futásoknál a `*_osszefoglalo.jpg` képeken csak a fejléc frissült, a törölt lenyúlások
  piros körei és a halvány hőtérképek nem.

**Ajánlott pontos eljárás:** futtatás a Review ablakkal (GUI, `var_enable_review=True`), ahol a
felhasználó minden lenyúlást maga hagy jóvá (1 = mellső, 2 = hátsó, 3 = orr, 4 = farok,
Space = elvetés, Enter = export). Utána `verify_exports.py`. Kiegészítésként érdemes 5–6 videón kézi
számolással összevetni a CSV-t.

## 7. Kimenet felépítése

```
MouseAnalyzer_Eredmenyek/
  Minden_Egyed_Meresi_Adatai.csv        # minden futás, ';' elválasztó, UTF-8 BOM
  utolso_kalibracio.json
  Egyed_<ID>_eredmenyek/
    egyed_<ID>_meresi_adatok.csv
    egyed_<ID>_futas_<n>_osszefoglalo.jpg
    egyed_<ID>_futas_<n>_heatmap.jpg / _halvany_heatmap.jpg
    egyed_<ID>_futas_<n>_lenyulas_<k>.jpg
    egyed_<ID>_OSSZESITETT_<N>_futas.jpg, _OSSZESITETT_heatmap.jpg, _TELJES_SESSION_heatmap.jpg
```

Konzisztencia-szabályok (a `verify_exports.py` ellenőrzi):
`Mancs = Mellső + Hátsó`, `Mélynyúlások = Mancs + Orr + Farok`, a lenyúlás-képek száma = a CSV
lenyúlásainak összege, a futásszámok egyedenként 1-től folytonosak.

## 8. Hibaelhárítás

| Tünet | Ok / teendő |
|---|---|
| Exit code 134 (SIGABRT) | Numba párhuzamos mag – lásd 4/1 |
| `diab_1` és `1` egy mappába kerül | ID ütközés – lásd 4/2 |
| Egy videó < 3 futás, a naplóban 0,0x s-os „Run completed” | fantom célba érés – lásd 4/5 |
| `Operation not permitted` a kimeneti mappán | sandboxon kívül kell futtatni |
| Ultralytics settings.json írási hiba | ártalmatlan, figyelmen kívül hagyható |
| Python `-c` parancsban f-string idézőjel hiba | írd fájlba a szkriptet |
