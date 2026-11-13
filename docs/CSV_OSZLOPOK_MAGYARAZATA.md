# MouseAnalyzer – Az elemzési CSV oszlopok magyarázata

> **English version:** [CSV_COLUMNS_EXPLANATION.md](CSV_COLUMNS_EXPLANATION.md)

A `MouseTracker.py` által exportált mérési CSV (`Minden_Egyed_Meresi_Adatai.csv`, valamint az egyedenkénti `egyed_<ID>_meresi_adatok.csv`) **42 oszlopot** tartalmaz futásonként (`;`-vel elválasztva, UTF-8 BOM kódolással). Az alábbiakban az összes oszlop biológiai/viselkedéstani jelentése és pontos matematikai definíciója szerepel.

---

## 1. Azonosítás és időzítés

| Oszlopnév | Jelentés / Képlet |
|---|---|
| `Egyed_ID` | Az állat azonosítója (a videólistában megadott vagy fájlnévből kinyert ID). |
| `Video_Fajl` | A forrásvideó fájlneve. |
| `Futas_Sorszam` | Az adott videón belüli érvényes áthaladás sorszáma ($1, 2, \dots$). |
| `Irany` | Az áthaladás iránya: `FORWARD` (balról jobbra) vagy `REVERSE` (jobbról balra). |
| `Belepesi_Ido_mp` | A startkapun való belépés időpontja a videóban ($t_{\text{start}}$, $\text{s}$). |
| `Kilepesi_Ido_mp` | A célkapun való kilépés időpontja a videóban ($t_{\text{end}}$, $\text{s}$). |
| `Teljes_Athaladasi_Ido_mp` | Teljes áthaladási idő: $T_{\text{teljes}} = t_{\text{end}} - t_{\text{start}}$ ($\text{s}$). |
| `Netto_Mozgasi_Ido_mp` | Tényleges mozgással töltött idő (a hosszabb megállások levonásával):<br>$$T_{\text{nettó}} = \max\!\left(0,\; T_{\text{teljes}} - \sum \Delta t_{\text{megállás}}\right)$$ |

---

## 2. Lenyúlások és lábhiba-típusok

A program minden olyan eseményt vizsgál, ahol az állat körvonala vagy kulcspontja a beállított hibavonal (*fault line*) alá nyúlik, majd osztályozza azt.

| Oszlopnév | Jelentés |
|---|---|
| `Melynyulasok_Szama` | Az összes érvényes, a hibavonal alá érő esemény száma a futás során. |
| `Mancs_Labhiba_Db` | A végtagokhoz (`PAW`) tartozó lábhibák száma (`Mellso_Labhiba_Db + Hatso_Labhiba_Db`). |
| `Mellso_Labhiba_Db` | Mellső lábhoz (`FOREPAW`) sorolt hibák száma. (Ha a végtag alosztálya nem dönthető el egyértelműen, a fennmaradó `PAW` események ide kerülnek.) |
| `Hatso_Labhiba_Db` | Hátsó lábhoz (`HINDPAW`) sorolt hibák száma. |
| `Enyhe_Megcsuszas_Db` | Olyan `PAW` események száma, ahol a hibavonal alatti lenyúlási mélység `dip_depth` $< 20\text{ px}$. |
| `Mely_Leleses_Db` | Olyan `PAW` események száma, ahol `dip_depth` $\ge 20\text{ px}$. |
| `Orr_Lenezes_Db` | `NOSE` kódú események száma (orral való lefelé nézés / exploráció – nem valódi lábhiba). |
| `Hatso_Farok_Db` | `HIND_TAIL` kódú események száma (farok vagy hátsó testrész belógása). |
| `Melynyulasok_Idopontjai_mp` | Az egyes érvényes események időpontjai másodpercben felsorolva. |

---

## 3. Megállások és mikro-megtorpanások

Két egymást követő feldolgozott képkocka között az állat akkor számít egy helyben állónak, ha a vízszintes elmozdulása:
$$|\Delta x| < 2.5 \cdot \text{frame-stride} \quad [\text{px}]$$

| Oszlopnév | Jelentés |
|---|---|
| `Megallasok_Szama` | Olyan mozdulatlansági epizódok száma, amelyek időtartama $t_{\text{still}} \ge 0.30\text{ s}$. |
| `Megallasok_OsszIdeje_mp` | A $t_{\text{still}} \ge 0.30\text{ s}$ megállások összideje ($\text{s}$). |
| `Megallasok_Intervallumai_Tol_Ig` | A megállások `[kezdő_mp - vég_mp]` intervallumai szövegesen. |
| `Mikro_Megtorpanas_Db` | Rövid habozások száma, ahol $0.08\text{ s} \le t_{\text{still}} < 0.30\text{ s}$. |
| `Mikro_Megtorpanas_Ido_mp` | A mikro-megtorpanások összideje ($\text{s}$). |

---

## 4. Kinematikai és bizonytalansági mutatók

A kinematikai számítások előtt a nyers $(x_i, y_i)$ trajektóriát egy **5 pontos Gauss-kernellel** ($w = [0.06, 0.24, 0.40, 0.24, 0.06]$) simítja a rendszer. Ebből számolja a lépésenkénti sebességet:
$$v_i = \frac{\sqrt{(\tilde{x}_i - \tilde{x}_{i-1})^2 + (\tilde{y}_i - \tilde{y}_{i-1})^2}}{\Delta t_i \cdot \text{px/cm}} \quad [\text{cm/s}]$$
majd a sebességgörbén még egy **3 pontos simítást** ($[0.25, 0.50, 0.25]$) végez ($\tilde{v}_k$).

### `Sebesseg_Ingadozas_CV` (Variációs együttható, dimenziótlan)
A sebesség egyenletességét méri. Kis érték egyenletes tempót, nagy érték gyakori lassítást-gyorsítást (bizonytalan, akadozó haladást) jelez:
$$\text{CV} = \frac{\sigma(\tilde{v})}{\max(10^{-4},\; \mu(\tilde{v}))}$$
ahol $\mu(\tilde{v})$ a simított sebességek átlaga, $\sigma(\tilde{v})$ pedig a szórása.

### `Mozgas_Darabossag_Jerk` (0–100 skálázott pontszám)
A *jerk* fizikailag a gyorsulás időbeli deriváltja ($j = \frac{da}{dt} = \frac{d^3s}{dt^3}$, rángás / darabosság). A program a simított sebességből előbb gyorsulást, majd jerk-öt számol:
$$a_k = \frac{\tilde{v}_k - \tilde{v}_{k-1}}{\Delta t_{a,k}}, \qquad j_k = \frac{|a_k - a_{k-1}|}{\Delta t_{j,k}}$$
Ezután a medián jerk-et ($j_{\text{med}} = \text{median}(j_k)$) az átlagsebességhez viszonyítva skálázza $0$ és $100$ közé:
$$\text{Jerk}_{\text{score}} = \text{clip}\!\left(\frac{j_{\text{med}}}{\max(100.0,\; 80.0 \cdot \mu(\tilde{v}))} \cdot 35.0,\; 0,\; 100\right)$$
A $0$-hoz közeli érték folyamatos, sima mozgást; a magas érték rángatózó, darabos haladást jelent.

### `Testtartas_Imbolygas_px` (pixelben)
A test függőleges ($y$) irányú kilengését méri a saját mozgóátlagolt pályájához képest. A nyers $y_i$ pozíciókból egy legfeljebb 7 pontos mozgóátlaggal ($\bar{y}_i$) kiszűri a létra esetleges enyhe lejtését vagy ívét, majd a maradék szórását számolja:
$$\text{Imbolygás} = \text{std}\!\left(y_i - \bar{y}_i\right) \quad [\text{px}]$$
Minél nagyobb, annál erősebb a függőleges billegés/imbolygás lépés közben.

### `Bizonytalansagi_Index_Pct` (0–99.5%)
Összetett, súlyozott mutató, amely a sebesség-ingadozást, megtorpanásokat, megállásokat, orr-lenézéseket, imbolygást, jerk-öt és lábhibákat egyetlen százalékos értékbe sűríti:
$$U_{\text{raw}} = 14.0 \cdot \min(1.5, \text{CV}) + 3.5 \cdot N_{\text{mikro}} + 8.0 \cdot N_{\text{megállás}} + 2.5 \cdot N_{\text{orr}} + 2.0 \cdot \max(0, \text{Imbolygás} - 1.2) + 0.45 \cdot \text{Jerk}_{\text{score}} + 12.0 \cdot N_{\text{enyhe}} + 22.0 \cdot N_{\text{mély}}$$
$$\text{Bizonytalanság (\%)} = \text{clip}\!\left(100 \cdot \tanh\!\left(\frac{U_{\text{raw}}}{85.0}\right),\; 0,\; 99.5\right)$$
A $\tanh$ függvény miatt a kisebb hibák közel lineárisan növelik az indexet, míg sok hiba esetén $99.5\%$-hoz tart aszimptotikusan.

---

## 5. Skála, távolság és sebesség

| Oszlopnév | Jelentés / Képlet |
|---|---|
| `Skala_px_per_cm` | A kalibrált átszámítási tényező ($\text{px/cm}$). |
| `Megtett_Ut_px` | A simított 2D trajektória teljes ívhossza pixelben: $L_{\text{px}} = \sum_{i=1}^{n-1} \sqrt{(\tilde{x}_i - \tilde{x}_{i-1})^2 + (\tilde{y}_i - \tilde{y}_{i-1})^2}$. |
| `Megtett_Ut_cm` | A megtett út centiméterben: $L_{\text{cm}} = L_{\text{px}} /$ `Skala_px_per_cm`. |
| `Atlagsebesseg_px_mp` | Átlagsebesség ($\text{px/s}$): $L_{\text{px}} / T_{\text{teljes}}$. |
| `Atlagsebesseg_cm_mp` | Átlagsebesség ($\text{cm/s}$): $L_{\text{cm}} / T_{\text{teljes}}$. |
| `Max_Sebesseg_px_mp` | A lépésenkénti sebességek maximuma ($\text{px/s}$). |
| `Max_Sebesseg_cm_mp` | A lépésenkénti sebességek maximuma ($\text{cm/s}$). |

---

## 6. Zónabontás (Start / Közép / Cél)

A start- és célkapu közötti távolságot a program **3 egyenlő szélességű harmadra** osztja ($w_{\text{zóna}} = (x_{\text{jobb}} - x_{\text{bal}}) / 3$):

| Zóna | Oszlopok | Jelentés |
|---|---|---|
| **Start (1. harmad)** | `Start_Zona_Ido_mp`, `Start_Lenyulas_Db`, `Start_Megallas_Db` | A zónában töltött mozgási idő ($\text{s}$), érvényes lenyúlások száma, megállások száma. |
| **Közép (2. harmad)** | `Kozep_Zona_Ido_mp`, `Kozep_Lenyulas_Db`, `Kozep_Megallas_Db` | Ugyanezek a középső szakaszon. |
| **Cél (3. harmad)** | `Cel_Zona_Ido_mp`, `Cel_Lenyulas_Db`, `Cel_Megallas_Db` | Ugyanezek a cél előtti szakaszon. |
