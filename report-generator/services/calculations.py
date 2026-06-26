import io
import pandas as pd
import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Circle
from matplotlib.lines import Line2D
from hexalattice.hexalattice import create_hex_grid
from pathlib import Path

def process_beam_csv(csv_file):

    # Read the CSV file into a DataFrame
    try:
        df = pd.read_csv(csv_file)
        columns_lower = [col.lower() for col in df.columns]

        width_major_col = next((col for col in df.columns if "width major" in col.lower()), None)
        width_minor_col = next((col for col in df.columns if "width minor" in col.lower()), None)

        # Validate required columns
        if not width_major_col or not width_minor_col:
            raise ValueError("CSV file must contain 'width major' and 'width minor' columns.")

        # Calculate averages
        avg_width_major = df[width_major_col].mean()
        avg_width_minor = df[width_minor_col].mean()

        # Ellipticity
        ellipticity = avg_width_minor / avg_width_major *100
        ellipticity = round(ellipticity)

        # Measured beam surface
        measured_surface = math.pi * (avg_width_major / 2) * (avg_width_minor / 2)

        # Gaussian fit beam diameter (equivalent circle diameter based on surface area)
        gaussian_fit_diameter = 2 * math.sqrt(measured_surface / math.pi)*10000
        gaussian_fit_diameter = round(gaussian_fit_diameter)

        return {
            "ellipticity": ellipticity,
            "measured_surface": measured_surface,
            "gaussian_fit_diameter": gaussian_fit_diameter,
        }

    except Exception as e:
        raise ValueError(f"Error processing CSV file: {str(e)}")
    


def expand_indices(spec):
    if isinstance(spec, str) and ":" in spec:
        a, b = map(int, spec.split(":"))
        return set(range(a, b+1))
    return set(spec)

# ─────────────────────────────────────────────────────────────
# MASK GENERATION
# ─────────────────────────────────────────────────────────────


MASK_PASSED  = 0
MASK_DAMAGED = 1
MASK_SKIPPED = None

_MC = {
    "passed_inner":  "#FFD700",
    "damaged_inner": "#CC0000",
    "skipped_inner": "#AAAAAA",
    "blank_inner":   "#FFD700",
}


def parse_labview_mask(filepath):
    filepath = Path(filepath)
    params, rows = {}, []
    section = None
    with open(filepath, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                continue
            if section in ("Spot Matrix Parameters", "Test Parameters"):
                if "=" in line:
                    k, v = line.split("=", 1)
                    params[k.strip()] = v.strip()
            elif section == "Data":
                parts = line.split("\t")
                if len(parts) >= 3:
                    try:
                        rows.append({
                            "spot_id": int(float(parts[0])),
                            "x_mm":   float(parts[1]),
                            "y_mm":   float(parts[2]),
                        })
                    except ValueError:
                        pass
    return params, pd.DataFrame(rows)


def extract_mask_params(params, df):
    is_circular = params.get("Circle pattern", "FALSE").strip().upper() == "TRUE"
    def _f(key, default=0.0):
        try:
            return float(params.get(key, default))
        except (ValueError, TypeError):
            return default
    return {
        "n_spots":                   len(df),
        "test_site_diameter_mm":     _f("Spot Diameter in Target Plane"),
        "beam_diameter_mm":          _f("Beam Diameter in Target Plane"),
        "damage_circle_diameter_mm": _f("Damage circle Diameter (mm)"),
        "matrix_type":               "Circular" if is_circular else "Rectangular",
        "rect_width_mm":             _f("Rectangular  pattern Width, mm"),
        "rect_height_mm":            _f("Rectangular  pattern Height, mm"),
    }


def compute_serpentine_numbers(df, start_from=0):
    df = df.copy()
    df["y_row"] = df.y_mm.round(3)
    rows = sorted(df.y_row.unique())
    number_map, n = {}, start_from
    for i, y_val in enumerate(rows):
        row_df = df[df.y_row == y_val].sort_values("x_mm", ascending=(i % 2 == 0))
        for sid in row_df.spot_id.values:
            number_map[int(sid)] = n
            n += 1
    return number_map


def draw_mask_from_labview(df, params, status=None, figsize=(11, 11), dpi=150):
    if status is None:
        status = {}

    def _fp(key, fallback):
        try:
            return float(params.get(key, fallback))
        except (ValueError, TypeError):
            return float(fallback)

    r_outer = _fp("Spot Diameter in Target Plane", 1.05) / 2
    r_inner = _fp("Beam Diameter in Target Plane", 0.70) / 2

    cx = df.x_mm.mean()
    cy = df.y_mm.mean()
    xs = df.x_mm.values - cx
    ys = df.y_mm.values - cy

    distances  = np.sqrt(xs**2 + ys**2)
    r_boundary = distances.max() + r_outer

    number_map    = compute_serpentine_numbers(df, start_from=0)
    n_digits      = len(str(max(number_map.values())))
    pt_per_mm     = (figsize[0] * 72) / (2 * (r_boundary * 1.05))
    inner_diam_pt = r_inner * 2 * pt_per_mm
    font_size     = max(3.0, min(
        inner_diam_pt / (n_digits * 0.85),
        inner_diam_pt * 0.55,
        14.0
    ))

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.set_aspect("equal")
    lim = r_boundary * 1.05
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)

    ax.add_patch(Circle((0, 0), r_boundary,
                        fill=False, edgecolor="black", linewidth=1.5, zorder=1))

    has_passed = has_damaged = has_skipped = False
    for sid, x, y in zip(df.spot_id.values, xs, ys):
        display_num = number_map.get(int(sid), int(sid))
        s = status.get(display_num, "blank")
        if s == MASK_DAMAGED:
            ic = _MC["damaged_inner"]; has_damaged = True
        elif s == MASK_PASSED:
            ic = _MC["passed_inner"];  has_passed  = True
        elif pd.isna(s):
            ic = _MC["skipped_inner"]; has_skipped = True
        else:
            ic = _MC["blank_inner"]

        ax.add_patch(Circle((x, y), r_outer,
                            facecolor="white", edgecolor="black",
                            linewidth=0.6, zorder=2))
        ax.add_patch(Circle((x, y), r_inner,
                            facecolor=ic, edgecolor="black",
                            linewidth=0.4, zorder=3))
        ax.text(x, y, str(number_map.get(int(sid), int(sid))),
                ha="center", va="center",
                fontsize=font_size, fontweight="bold",
                color="#111111", zorder=4)

    legend_items = []
    if has_passed:
        legend_items.append(mpatches.Patch(facecolor=_MC["passed_inner"],  edgecolor="black", label="Passed"))
    if has_damaged:
        legend_items.append(mpatches.Patch(facecolor=_MC["damaged_inner"], edgecolor="black", label="Damaged"))
    if has_skipped:
        legend_items.append(mpatches.Patch(facecolor=_MC["skipped_inner"], edgecolor="black", label="Skipped"))
    if legend_items:
        ax.legend(handles=legend_items, loc="upper right",
                  fontsize=9, framealpha=0.95, edgecolor="#cccccc")

    ax.axis("off")
    fig.tight_layout(pad=0.2)
    return fig


def mask_fig_to_png_bytes(fig, dpi=150):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    buf.seek(0)
    return buf.getvalue()

def parse_measurement_data(filepath, sheet_name="Measurement"):
    raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None)
    header_row = next(i for i, row in raw.iterrows()
                      if any("spot" in str(v).lower() for v in row.values))
    df = pd.read_excel(filepath, sheet_name=sheet_name, header=header_row)
    df.columns = [str(c).strip() for c in df.columns]

    spot_col   = next(c for c in df.columns if "spot"   in c.lower())
    status_col = next(c for c in df.columns if "status" in c.lower())
    pulses_col = next(c for c in df.columns if "pulse"  in c.lower())

    df = df.dropna(subset=[spot_col]).copy()
    out = pd.DataFrame()
    out["spot_id"]  = df[spot_col].astype(int).values
    out["status"] = df[status_col].apply(lambda v: None if (pd.isna(v) or int(v) == -1) else int(v)).values
    out["n_pulses"] = pd.to_numeric(df[pulses_col], errors="coerce").values
    return out

def plot_damage_probability(fluences, probabilities):
    from scipy.stats import linregress

    slope, intercept, r_value, p_value, std_err = linregress(fluences, probabilities)
    lidt_0        = -intercept / slope
    lidt_50       = (50  - intercept) / slope
    lidt_100      = (100 - intercept) / slope
    first_damage  = fluences[probabilities > 0].min()

    linear_range  = lidt_100 - lidt_0
    x_left        = lidt_0  - linear_range * 0.4
    x_right       = lidt_100 + linear_range * 0.4

    x_ramp  = np.linspace(lidt_0, lidt_100, 200)
    y_ramp  = slope * x_ramp + intercept
    x_curve = np.concatenate([[x_left, lidt_0], x_ramp, [lidt_100, x_right]])
    y_curve = np.concatenate([[0, 0],            y_ramp, [100,      100    ]])

    sign    = "-" if intercept < 0 else "+"
    eq_text = f"y = {slope:.2f}x {sign} {abs(intercept):.3f}"

    color = "#00afee"
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(x_curve, y_curve, color=color, linewidth=2, solid_capstyle="round")
    ax.scatter(fluences, probabilities, marker="x", color=color,
               s=60, linewidths=1.8, zorder=5)
    ax.text(0.97, 0.97, eq_text, transform=ax.transAxes,
            ha="right", va="top", fontsize=9, color=color)
    ax.set_xlabel("Fluence (J/cm²)", fontsize=10)
    ax.set_ylabel("Damage probability (%)", fontsize=10)
    ax.set_xlim(x_left, x_right)
    ax.set_ylim(-8, 112)
    ax.yaxis.set_major_locator(plt.MultipleLocator(10))
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()

    lidt_values = {
        "lidt_0":        round(lidt_0,        3),
        "lidt_50":       round(lidt_50,        3),
        "lidt_100":      round(lidt_100,       3),
        "first_damage":  round(float(first_damage), 3),
    }
    return fig, lidt_values

def parse_fluence_probability(filepath, sheet_name="Sample details"):
    raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None)

    # Find the exact row where the cell value is "fluence"
    header_row = None
    for i, row in raw.iterrows():
        vals = [str(v).strip().lower() for v in row.values if pd.notna(v)]
        if "fluence" in vals:
            header_row = i
            break

    if header_row is None:
        raise ValueError("Could not find 'fluence' column header in sheet — check the sheet name and column names.")

    df = pd.read_excel(filepath, sheet_name=sheet_name, header=header_row)
    df.columns = [str(c).strip().lower() for c in df.columns]

    df["fluence"]     = pd.to_numeric(df["fluence"],     errors="coerce")
    df["probability"] = pd.to_numeric(df["probability"], errors="coerce")
    df = df.dropna(subset=["fluence", "probability"])

    return df["fluence"].values.astype(float), df["probability"].values.astype(float)

def parse_son1_range_data(filepath, sheet_name="Analysis"):
    raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None)
    header_row = None
    for i, row in raw.iterrows():
        vals = [str(v).strip().lower() for v in row.values if pd.notna(v)]
        if "fluence" in vals and "status" in vals:
            header_row = i
            break
    if header_row is None:
        raise ValueError("Could not find header row with 'fluence' and 'status' in Analysis sheet.")

    df = pd.read_excel(filepath, sheet_name=sheet_name, header=header_row)
    df.columns = [str(c).strip().lower() for c in df.columns]

    fluence_col = next(c for c in df.columns if "fluence" in c)
    status_col  = next(c for c in df.columns if "status"  in c)
    pulses_col  = next(c for c in df.columns if "pulse"   in c)

    df[fluence_col] = pd.to_numeric(df[fluence_col], errors="coerce")
    df[status_col]  = pd.to_numeric(df[status_col],  errors="coerce")
    df[pulses_col]  = pd.to_numeric(df[pulses_col],  errors="coerce")
    df = df.dropna(subset=[fluence_col, status_col, pulses_col])

    return pd.DataFrame({
        "fluence":      df[fluence_col].values,
        "status":       df[status_col].astype(int).values,
        "pulses_count": df[pulses_col].astype(int).values,
    })


def plot_son1_range(df):
    from scipy.interpolate import PchipInterpolator

    non_damaged = df[df["status"] == 0]
    damaged     = df[df["status"] == 1]

    fig, ax = plt.subplots(figsize=(7, 4.5))

    ax.scatter(non_damaged["pulses_count"], non_damaged["fluence"],
               marker="o", color="#1f77b4", s=40, label="Non-damaged sites", zorder=5)
    ax.scatter(damaged["pulses_count"], damaged["fluence"],
               marker="x", color="#CC0000", s=60, linewidths=1.8, label="Damaged sites", zorder=5)

    # Threshold: max non-damaged per group (fluence > 0), monotonically decreasing
    threshold = (df[(df["status"] == 0) & (df["fluence"] > 0)]
                 .groupby("pulses_count")["fluence"]
                 .max()
                 .reset_index()
                 .sort_values("pulses_count"))

    threshold["fluence"] = threshold["fluence"].cummin()

    if len(threshold) > 1:
        x_pts    = threshold["pulses_count"].values.astype(float)
        y_pts    = threshold["fluence"].values.astype(float)
        x_log    = np.log10(x_pts)
        x_fine   = np.linspace(x_log[0], x_log[-1], 400)
        y_fine   = PchipInterpolator(x_log, y_pts)(x_fine)
        ax.plot(10 ** x_fine, y_fine,
                color="#64bb2f", linewidth=2, label="Damage probability curve", zorder=4)

    ax.set_xscale("log")
    #ax.set_xlim(left=1)
    ax.set_xlabel("Pulses count [-]", fontsize=10)
    ax.set_ylabel("Fluence [J/cm\u00b2]", fontsize=10)
    #ax.set_title("Characteristic damage curve", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9, framealpha=0.95)
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()

    max_n = int(df["pulses_count"].max())
    min_n = int(df["pulses_count"].min())
    n_pulses_str = f"1-{max_n}" if min_n == 1 else f"{min_n}-{max_n}"

    # 0% threshold = last point the green curve lands on (highest N group)
    lidt_0 = round(float(threshold["fluence"].values[-1]), 3) if len(threshold) > 0 else None

    # First observed damage = lowest fluence among all damaged spots
    damaged_f = df[df["status"] == 1]["fluence"]
    first_damage = round(float(damaged_f.min()), 3) if len(damaged_f) > 0 else None

    return fig, {
        "n_pulses":     n_pulses_str,
        "lidt_0":       lidt_0,
        "lidt_50":      None,
        "first_damage": first_damage,
        "show_50_pct":  False,
    }

def parse_ron1_measurement(filepath, sheet_name="Measurement"):
    raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None)
    all_spots = {}

    for i, row in raw.iterrows():
        # Find which column contains the "spot" keyword
        spot_col_idx = None
        for ci in range(len(row)):
            if str(row.iloc[ci]).strip().lower() == "spot":
                spot_col_idx = ci
                break
        if spot_col_idx is None:
            continue

        # Read fluence columns and find Damage column
        fluences, fluence_cols, damage_col = [], [], None
        for ci in range(spot_col_idx + 1, len(row)):
            val = row.iloc[ci]
            if pd.isna(val) or str(val).strip() == "":
                continue
            if str(val).strip().lower() == "damage":
                damage_col = ci
                break
            try:
                fluences.append(float(val))
                fluence_cols.append(ci)
            except (ValueError, TypeError):
                pass

        # Read spot rows below
        ri = i + 1
        while ri < len(raw):
            data      = raw.iloc[ri]
            spot_cell = data.iloc[spot_col_idx]

            if pd.isna(spot_cell) or str(spot_cell).strip() == "":
                break
            if str(spot_cell).strip().lower() == "spot":
                break

            # Keep spot ID as string to handle ranges like "0-5"
            spot_id = str(spot_cell).strip()

            # Get damage fluence
            damage_fluence = None
            if damage_col is not None:
                dv = data.iloc[damage_col]
                if pd.notna(dv) and str(dv).strip() not in ("", "-"):
                    try:
                        damage_fluence = float(dv)
                    except (ValueError, TypeError):
                        pass

            # Build steps from non-zero shots only
            steps      = []
            cumulative = 0
            for fi, ci in enumerate(fluence_cols):
                sv = data.iloc[ci]
                try:
                    shots = int(float(sv)) if pd.notna(sv) else 0
                except (ValueError, TypeError):
                    shots = 0
                if shots == 0:
                    continue
                cumulative += shots
                fluence     = fluences[fi]
                is_damage   = (damage_fluence is not None and
                               abs(fluence - damage_fluence) < 0.05)
                steps.append({
                    "fluence":    fluence,
                    "shots":      shots,
                    "cumulative": cumulative,
                    "damaged":    is_damage,
                })
                if is_damage:
                    break

            if steps:
                all_spots[spot_id] = {
                    "steps":          steps,
                    "damage_fluence": damage_fluence,
                }
            ri += 1

    return all_spots

def plot_ron1_spot(steps, damage_fluence, spot_label):
    """Bar chart for one R-on-1 spot.
    All bars blue. Damage step gets a red pentagon cap on top + annotation.
    """
    if not steps:
        return None, None

    fluences    = [s["fluence"]    for s in steps]
    cumulatives = [s["cumulative"] for s in steps]
    n           = len(steps)
    x_pos       = np.arange(n)
    top         = max(fluences)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(x_pos, fluences, color="#1f77b4", width=0.75, zorder=3)

    if damage_fluence is not None:
        dmg_idx = next((i for i, s in enumerate(steps) if s["damaged"]), None)
        if dmg_idx is not None:
            ax.plot(dmg_idx, fluences[dmg_idx] + top * 0.07,
                    marker="p", color="#CC0000", markersize=14,
                    zorder=5, linestyle="none")
            ax.text(0.05, 0.90,
                    f"Damage at fluence {damage_fluence:.1f} J/cm\u00b2",
                    transform=ax.transAxes, fontsize=10,
                    fontweight="bold", color="#111111")

    ax.set_xticks(x_pos)
    ax.set_xticklabels([str(c) for c in cumulatives], rotation=90, fontsize=7)
    ax.set_ylim(0, top * 1.25)
    ax.set_xlabel("Shots number [-]", fontsize=10)
    ax.set_ylabel("Fluence [J/cm\u00b2]", fontsize=10)
    #ax.set_title(f"R-on-1 procedure - {spot_label}", fontsize=12, fontweight="bold")
    ax.grid(True, axis="y", linestyle="--", alpha=0.4, zorder=0)
    for spine in ax.spines.values():
        spine.set_edgecolor("#1f77b4")
        spine.set_linewidth(1.5)
    fig.tight_layout()
    return fig, damage_fluence


# ─── Raster Scan ─────────────────────────────────────────────────────────────
def parse_raster_measurement(filepath):
    """Tab-separated 2D grid. 0 = no damage, float = fluence at damage.
    File row 0 = physical bottom row (flipud applied for display)."""
    raw  = np.loadtxt(filepath, delimiter="\t")
    grid = np.flipud(raw)
    total = grid.size
    nz    = raw[raw > 0]
    if len(nz) == 0:
        return {"grid": grid, "fluence_steps": [], "damage_counts": [],
                "damage_probability": [], "total_fields": total, "first_damage": None}
    first_damage  = float(np.min(nz))
    fluence_steps = sorted(set(float(v) for v in nz))
    counts, probs = [], []
    cumulative = 0
    for f in fluence_steps:
        cumulative += int(np.sum(np.isclose(raw, f)))
        counts.append(cumulative)
        probs.append(round(cumulative / total * 100, 4))
    return {"grid": grid, "fluence_steps": fluence_steps, "damage_counts": counts,
            "damage_probability": probs, "total_fields": total, "first_damage": first_damage}

def parse_raster_evolution(filepath):
    """Two-column tab-separated: fluence | total damage density (mm⁻²)."""
    raw = np.loadtxt(filepath, delimiter="\t")
    if raw.ndim == 1:
        raw = raw.reshape(1, -1)
    return {
        "fluences":  [float(r[0]) for r in raw],
        "densities": [float(r[1]) for r in raw],
    }


def compute_raster_lidt(evolution, fluence_steps, damage_probability, first_damage):
    """
    first_damage : min non-zero value from the GRID (not evolution file)
    last_zero    : last evolution fluence NOT present as a damage fluence in the grid
    """
    all_fluences     = evolution["fluences"]
    grid_fluence_set = set(round(f, 4) for f in fluence_steps)

    last_zero = None
    for f in all_fluences:
        if first_damage is not None and f >= first_damage - 0.001:
            break
        if round(f, 4) not in grid_fluence_set:
            last_zero = f

    lidt_0 = ((last_zero + first_damage) / 2
              if last_zero is not None and first_damage is not None
              else first_damage)

    full_prob, j = [], 0
    for f in all_fluences:
        if j < len(fluence_steps) and abs(f - fluence_steps[j]) < 0.001:
            j += 1
        full_prob.append(damage_probability[j - 1] if j > 0 else 0.0)

    lidt_5 = None
    for i in range(len(all_fluences) - 1):
        if full_prob[i] <= 5.0 < full_prob[i + 1]:
            t      = (5.0 - full_prob[i]) / (full_prob[i + 1] - full_prob[i])
            lidt_5 = all_fluences[i] + t * (all_fluences[i + 1] - all_fluences[i])
            break

    return lidt_0, lidt_5, full_prob

def plot_raster_map(grid, site_spacing_mm=1.0, sample_id=""):
    import matplotlib.colors as mcolors

    n_rows, n_cols = grid.shape
    nz           = grid[grid > 0]
    fluence_vals = sorted(set(float(v) for v in nz)) if len(nz) > 0 else []
    n_levels     = len(fluence_vals)

    # Sample evenly from plasma (0.3–1.0) so colors go red → orange → cream
    NO_DMG_COLOR = "#0d0221"
    if n_levels > 0:
        sample_pts    = np.linspace(0.55, 0.92, n_levels)
        damage_colors = [mcolors.to_hex(plt.cm.plasma(p)) for p in sample_pts]
    else:
        damage_colors = []
    all_colors = [NO_DMG_COLOR] + damage_colors
    cmap       = mcolors.ListedColormap(all_colors)
    boundaries = np.arange(-0.5, n_levels + 1.5, 1.0)
    norm       = mcolors.BoundaryNorm(boundaries, cmap.N)

    # map grid values to integer indices
    grid_idx = np.zeros(grid.shape, dtype=int)
    for i, f in enumerate(fluence_vals, 1):
        grid_idx[np.isclose(grid, f)] = i

    # grid from parser is np.flipud(raw) → flip back so row 0 = physical bottom
    display = np.flipud(grid_idx)

    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(display, origin="lower", cmap=cmap, norm=norm, aspect="equal")

    x_step = max(1, n_cols // 7)
    ax.set_xticks(np.arange(0, n_cols, x_step))
    ax.set_xticklabels([f"{i * site_spacing_mm:.1f}" for i in range(0, n_cols, x_step)])

    y_step = max(1, n_rows // 7)
    ax.set_yticks(np.arange(0, n_rows, y_step))
    ax.set_yticklabels([f"{i * site_spacing_mm:.1f}" for i in range(0, n_rows, y_step)])

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_ticks(list(range(n_levels + 1)))
    cbar.set_ticklabels(["no damage"] + [f"{f:.1f} J/cm\u00b2" for f in fluence_vals])
    cbar.set_label("laser fluence (J/cm\u00b2)", fontsize=9)

    ax.set_xlabel("position x-axis (mm)", fontsize=10)
    ax.set_ylabel("position y-axis (mm)", fontsize=10)
    #title = f"Damage initiation map{f', sample {sample_id}' if sample_id else ''}"
    #ax.set_title(title, fontsize=11, fontweight="bold")
    fig.tight_layout()
    return fig
def plot_raster_density(all_fluences, full_density, full_probability, sample_id=""):
    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    ax2 = ax1.twinx()
    ax1.plot(all_fluences, full_density,     "o--", color="#CC0000", markersize=6, linewidth=1.4)
    ax2.plot(all_fluences, full_probability, "s--", color="#1f77b4", markersize=6, linewidth=1.4)
    ax1.set_xlabel("Laser fluence (J/cm\u00b2)", fontsize=10)
    ax1.set_ylabel("Total damage density (mm\u207b\u00b2)", fontsize=10, color="#CC0000")
    ax2.set_ylabel("Damage probability (%)",              fontsize=10, color="#1f77b4")
    ax1.tick_params(axis="y", labelcolor="#CC0000")
    ax2.tick_params(axis="y", labelcolor="#1f77b4")
    ax1.set_ylim(bottom=0)
    ax2.set_ylim(bottom=0)
    ax1.grid(True, linestyle="--", alpha=0.3)
    title = f"Total damage density and damage probability{f', sample {sample_id}' if sample_id else ''}"
    #ax1.set_title(title, fontsize=11, fontweight="bold")
    fig.tight_layout()
    return fig