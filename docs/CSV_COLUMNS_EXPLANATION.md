# MouseAnalyzer – Explanation of Analysis CSV Columns

> **Magyar verzió:** [CSV_OSZLOPOK_MAGYARAZATA.md](CSV_OSZLOPOK_MAGYARAZATA.md)

The measurement CSV files exported by `MouseTracker.py` (`Minden_Egyed_Meresi_Adatai.csv` and per-subject `egyed_<ID>_meresi_adatok.csv`) contain **42 columns** per run (semicolon-delimited `;`, UTF-8 with BOM). Below is the behavioral meaning and exact mathematical definition of every column.

---

## 1. Identification and Timing

| Column Name | Meaning / Formula |
|---|---|
| `Egyed_ID` | Subject identifier (entered in the video queue or auto-extracted from the filename). |
| `Video_Fajl` | Source video filename. |
| `Futas_Sorszam` | Sequential index of the valid ladder crossing within the video ($1, 2, \dots$). |
| `Irany` | Crossing direction: `FORWARD` (left-to-right) or `REVERSE` (right-to-left). |
| `Belepesi_Ido_mp` | Timestamp when the subject enters the start gate ($t_{\text{start}}$, $\text{s}$). |
| `Kilepesi_Ido_mp` | Timestamp when the subject reaches the goal gate ($t_{\text{end}}$, $\text{s}$). |
| `Teljes_Athaladasi_Ido_mp` | Total transit duration: $T_{\text{total}} = t_{\text{end}} - t_{\text{start}}$ ($\text{s}$). |
| `Netto_Mozgasi_Ido_mp` | Net active movement time (excluding prolonged stops/freezes):<br>$$T_{\text{net}} = \max\!\left(0,\; T_{\text{total}} - \sum \Delta t_{\text{freeze}}\right)$$ |

---

## 2. Dips and Foot-Fault Classifications

Every event where the animal's contour or anatomical keypoint drops below the calibrated fault line is detected and classified.

| Column Name | Meaning |
|---|---|
| `Melynyulasok_Szama` | Total number of valid below-fault-line dip events during the run. |
| `Mancs_Labhiba_Db` | Total limb foot-faults (`PAW` events: `Mellso_Labhiba_Db + Hatso_Labhiba_Db`). |
| `Mellso_Labhiba_Db` | Forelimb foot-faults (`FOREPAW`). (Any `PAW` event whose limb subtype cannot be unambiguously resolved defaults here.) |
| `Hatso_Labhiba_Db` | Hindlimb foot-faults (`HINDPAW`). |
| `Enyhe_Megcsuszas_Db` | Minor slips: `PAW` events with dip depth below the fault line `dip_depth` $< 20\text{ px}$. |
| `Mely_Leleses_Db` | Deep falls/slips: `PAW` events with `dip_depth` $\ge 20\text{ px}$. |
| `Orr_Lenezes_Db` | Nose-poke / downward exploration events (`NOSE` — not counted as limb foot-faults). |
| `Hatso_Farok_Db` | Posterior/tail dip events (`HIND_TAIL`). |
| `Melynyulasok_Idopontjai_mp` | List of timestamps ($\text{s}$) for each valid dip event. |

---

## 3. Stops (Freezes) and Micro-Hesitations

Between consecutive processed frames, the animal is considered stationary if its horizontal displacement satisfies:
$$|\Delta x| < 2.5 \cdot \text{frame-stride} \quad [\text{px}]$$

| Column Name | Meaning |
|---|---|
| `Megallasok_Szama` | Number of prolonged stillness/freeze episodes with duration $t_{\text{still}} \ge 0.30\text{ s}$. |
| `Megallasok_OsszIdeje_mp` | Total duration of all freeze episodes ($\text{s}$). |
| `Megallasok_Intervallumai_Tol_Ig` | Text list of `[start_s - end_s]` intervals for each freeze. |
| `Mikro_Megtorpanas_Db` | Number of brief hesitations where $0.08\text{ s} \le t_{\text{still}} < 0.30\text{ s}$. |
| `Mikro_Megtorpanas_Ido_mp` | Total duration of micro-hesitations ($\text{s}$). |

---

## 4. Kinematic and Uncertainty Metrics

Before computing kinematics, the raw $(x_i, y_i)$ trajectory is smoothed with a **5-point Gaussian kernel** ($w = [0.06, 0.24, 0.40, 0.24, 0.06]$). Stepwise speeds are computed as:
$$v_i = \frac{\sqrt{(\tilde{x}_i - \tilde{x}_{i-1})^2 + (\tilde{y}_i - \tilde{y}_{i-1})^2}}{\Delta t_i \cdot \text{px/cm}} \quad [\text{cm/s}]$$
followed by a **3-point smoothing pass** ($[0.25, 0.50, 0.25]$) to obtain $\tilde{v}_k$.

### `Sebesseg_Ingadozas_CV` (Coefficient of Variation, dimensionless)
Measures speed consistency. Low values indicate steady locomotion; high values indicate frequent deceleration/acceleration (hesitant, uneven gait):
$$\text{CV} = \frac{\sigma(\tilde{v})}{\max(10^{-4},\; \mu(\tilde{v}))}$$
where $\mu(\tilde{v})$ and $\sigma(\tilde{v})$ are the mean and standard deviation of the smoothed speeds.

### `Mozgas_Darabossag_Jerk` (Scaled 0–100 score)
In physics, *jerk* is the time derivative of acceleration ($j = \frac{da}{dt} = \frac{d^3s}{dt^3}$, measuring abruptness/choppiness of motion). From the smoothed speed curve:
$$a_k = \frac{\tilde{v}_k - \tilde{v}_{k-1}}{\Delta t_{a,k}}, \qquad j_k = \frac{|a_k - a_{k-1}|}{\Delta t_{j,k}}$$
The median jerk ($j_{\text{med}} = \text{median}(j_k)$) is normalized relative to mean speed and clipped to $[0, 100]$:
$$\text{Jerk}_{\text{score}} = \text{clip}\!\left(\frac{j_{\text{med}}}{\max(100.0,\; 80.0 \cdot \mu(\tilde{v}))} \cdot 35.0,\; 0,\; 100\right)$$
Values near $0$ reflect smooth, fluid movement; higher values reflect jerky, fragmented stepping.

### `Testtartas_Imbolygas_px` (in pixels)
Measures vertical ($y$-axis) postural oscillation relative to the animal's own moving-average path. A centered moving average of up to 7 points ($\bar{y}_i$) removes gradual ladder slope/curvature, and the residual standard deviation is computed:
$$\text{Sway} = \text{std}\!\left(y_i - \bar{y}_i\right) \quad [\text{px}]$$
Higher values indicate greater vertical body wobble/sway while crossing.

### `Bizonytalansagi_Index_Pct` (0–99.5%)
A composite weighted index summarizing all motor and behavioral uncertainty signals into a single percentage:
$$U_{\text{raw}} = 14.0 \cdot \min(1.5, \text{CV}) + 3.5 \cdot N_{\text{micro}} + 8.0 \cdot N_{\text{freeze}} + 2.5 \cdot N_{\text{nose}} + 2.0 \cdot \max(0, \text{Sway} - 1.2) + 0.45 \cdot \text{Jerk}_{\text{score}} + 12.0 \cdot N_{\text{minor}} + 22.0 \cdot N_{\text{deep}}$$
$$\text{Uncertainty (\%)} = \text{clip}\!\left(100 \cdot \tanh\!\left(\frac{U_{\text{raw}}}{85.0}\right),\; 0,\; 99.5\right)$$
Because of $\tanh$, small numbers of faults increase the index nearly linearly, while severe impairments asymptotically approach $99.5\%$.

---

## 5. Scale, Distance, and Speed

| Column Name | Meaning / Formula |
|---|---|
| `Skala_px_per_cm` | Calibrated pixel-to-centimeter ratio ($\text{px/cm}$). |
| `Megtett_Ut_px` | Total arc length of the smoothed 2D trajectory in pixels: $L_{\text{px}} = \sum_{i=1}^{n-1} \sqrt{(\tilde{x}_i - \tilde{x}_{i-1})^2 + (\tilde{y}_i - \tilde{y}_{i-1})^2}$. |
| `Megtett_Ut_cm` | Path length in centimeters: $L_{\text{cm}} = L_{\text{px}} /$ `Skala_px_per_cm`. |
| `Atlagsebesseg_px_mp` | Average speed ($\text{px/s}$): $L_{\text{px}} / T_{\text{total}}$. |
| `Atlagsebesseg_cm_mp` | Average speed ($\text{cm/s}$): $L_{\text{cm}} / T_{\text{total}}$. |
| `Max_Sebesseg_px_mp` | Peak stepwise speed ($\text{px/s}$). |
| `Max_Sebesseg_cm_mp` | Peak stepwise speed ($\text{cm/s}$). |

---

## 6. Zone Breakdown (Start / Middle / Goal)

The span between the start and goal gates is divided into **3 equal-width thirds** ($w_{\text{zone}} = (x_{\text{right}} - x_{\text{left}}) / 3$):

| Zone | Columns | Meaning |
|---|---|---|
| **Start (1st third)** | `Start_Zona_Ido_mp`, `Start_Lenyulas_Db`, `Start_Megallas_Db` | Active time ($\text{s}$), valid dips, and stops in the first third. |
| **Middle (2nd third)** | `Kozep_Zona_Ido_mp`, `Kozep_Lenyulas_Db`, `Kozep_Megallas_Db` | Same metrics in the middle third. |
| **Goal (3rd third)** | `Cel_Zona_Ido_mp`, `Cel_Lenyulas_Db`, `Cel_Megallas_Db` | Same metrics in the final third before the goal gate. |
