from datetime import date
import math
from copy import deepcopy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from configs.lasers import LASER_PRESETS
# from configs.defaults import DEFAULT_CONTEXT 
def fmt_num(value, fmt):
    if isinstance(value, (int, float)):
        return f"{value:{fmt}}"
    return "N/A"


def fmt_with_unit(value, fmt, unit):
    if isinstance(value, (int, float)):
        return f"{value:{fmt}} {unit}"
    return "N/A"

def generate_context(form_data, laser_presets, sections_data, report_no, issue_date):
    """
    Generate context for PDF report based on form data.
    """
    context = deepcopy(form_data)
    context.update({
        "report_no": form_data.get("report_no", "DRAFT"),
        "issue_date": date.today().strftime("%d %B %Y"),
    })
    context["sections"] = []

    # Title Section
    context["sections"].append({
        "title": "Report Identification",
        "items": [
            ["Report Number", context["report_no"]],
            ["Issue Date", context["issue_date"]],
        ],
    })

    # Section 2: Sample Information
    sec2 = sections_data.get("sample_information", {})
    context["sections"].append({
        "title": "Sample Information",
        "items": [
            ["Sample ID", form_data.get("sample", "")],
            ["Description", sec2.get("description", "")],
            ["Date Received", (
                sec2["date_received"].strftime("%d %B %Y")
                if isinstance(sec2.get("date_received"), date)
                else ""
            )],
            ["Preparation", sec2.get("preparation", "")],
        ],
    })

    # Section 3: Laser and Environmental Conditions
    sec3 = sections_data.get("laser_environmental", {})
    laser = sec3.get("laser", {})
    preset_key = form_data.get("laser_preset")
    selected_laser = laser_presets.get(preset_key, {})
    laser_images = selected_laser.get("images", {})
    if not laser_images and sec3.get("laser_images"):
        _manual_items = [{"path": p} for p in sec3["laser_images"] if Path(p).exists()]
        if _manual_items:
            laser_images = {
                "layout": "template3" if len(_manual_items) >= 3 else "stack",
                "items": _manual_items,
                "caption": sec3.get("laser_image_caption", ""),
                "width_pct": 0.7,
            }
    context["sections"].append({
        "title": "Laser and Environmental Conditions",
        "items": [
            ["Laser Type", laser.get("laser_type", "")],
            ["Wavelength (nm)", laser.get("wavelength_nm", "")],
            ["Repetition Frequency", laser.get("pulse_repetition_frequency", "")],
            ["Output Energy/Power", laser.get("output_energy_or_power", "")],
            ["Pulse Duration (1/e²)", laser.get("pulse_duration_1e2", "")],
            ["Effective Pulse Duration", laser.get("effective_pulse_duration", "")],
            ["Polarization", laser.get("polarization_state", "")],
            ["Beam Diameter (1/e²)", laser.get("beam_diameter_1e2", "")],
            ["Beam Profile (Near Field)", laser.get("spatial_beam_profile_near_field", "")],
            ["Beam Delivery", laser.get("beam_delivery", "")],
        ],
        "images": laser_images,
    })

    # Section 4: Test Identification
    sec4 = sections_data.get("test_identification", {})
    context["sections"].append({
        "title": "Test Identification",
        "items": [
            ["Procedure", sec4.get("procedure", "")],
            ["Objective", sec4.get("objective", "")],
            ["Sites / Pulses per Site", sec4.get("sites_pulses", "")],
            ["Damage Detection", sec4.get("damage_detection", "")],
        ],
    })

    # Section 5: Optional Test Setup
    sec5 = sections_data.get("test_setup", {})
    if sec5.get("choice") and sec5["choice"] != "Skip":
        context["sections"].append({
            "title": "Test Setup",
            "images": {
                "layout": "template1",
                "items": [
                    {"path": sec5["image"]},
                ],
                "overlay_color": "black",
                "caption": sec5.get("caption", ""),
                "width_pct": 1,
                "flatten_alpha_to_white": False
            },
        })

    sec6 = sections_data.get("test_procedure", {})
    context["sections"].append({
        "title": "Test and Procedure Specification",
        "items": [
            [
                "Environment",
                f"{sec6.get('environment_choice', '')}, "
                f"{fmt_num(sec6.get('temperature'), '.1f')} °C, "
                f"{fmt_num(sec6.get('humidity'), 'd')}%"
            ],
            [
                "Vacuum",
                (
                    f"Yes, Pressure 10^{fmt_num(sec6.get('vacuum_pressure'), 'd')} mbar"
                    if sec6.get("vacuum") == "Yes"
                    else "No"
                )
            ],
            [
                "Focusing System",
                (
                    f"{sec6.get('focusing_choice', '')}, f = {sec6.get('focusing_distance', '')} mm"
                    if "focusing_distance" in sec6 else
                    f"{sec6.get('focusing_choice', '')}, Radius = {sec6.get('radius of curvature', '')} mm"
                )
            ],
            ["Beam Energy Management", sec6.get("beam_energy_choice", sec6.get("beam_energy_custom", ""))],
            ["Sample Position", sec6.get("sample_position_choice", sec6.get("sample_position_custom", ""))],
            [
                "Spatial Beam Shape",
                f"{sec6.get('spatial_beam_desc', '')}, ellipticity = {sec6.get('ellipticity', 'N/A')}%"
            ],
            ["Measured Beam Surface", fmt_with_unit(sec6.get("measured_surface"), ".6f", "cm²")],
            ["Gaussian Fit Beam Diameter", fmt_with_unit(sec6.get("gaussian_fit_diameter"), ".1f", "µm")],
        ],
        "images": {
            "layout": "template2",
            "items": [{"path": path} for path in sec6.get("uploaded_images", [])],
            "caption": sec6.get("image_captions", ""),
        },
    })

    # Add this inside `generate_context` to handle Section 7 (Error Budget)

# Section 7: Error Budget
    sec7 = sections_data.get("error_budget", {})
    items_sec7 = [
        ["Pulse-to-pulse energy stability",          f'{sec7.get("pulse_to_pulse_energy_sign",     "±")}{sec7.get("pulse_to_pulse_energy",    "N/A")}%'],
        ["Pulse-to-pulse spatial profile stability", f'{sec7.get("pulse_to_pulse_spatial_sign",    "±")}{sec7.get("pulse_to_pulse_spatial",   "N/A")}%'],
        ["Pulse-to-pulse temporal stability",        f'{sec7.get("pulse_to_pulse_temporal_sign",   "<")}{sec7.get("pulse_to_pulse_temporal",  "N/A")}%'],
        ["Energy monitor calibration",               f'{sec7.get("energy_monitor_calibration_sign","±")}{sec7.get("energy_monitor_calibration","N/A")}%'],
        ["Energy monitor accuracy",                  f'{sec7.get("energy_monitor_accuracy",        "N/A")} µJ'],
        ["Beam profiler accuracy",                   f'{sec7.get("beam_profiler_accuracy",         "N/A")} µm'],
        ["Beam profiler calibration",                f'\u00b1{sec7.get("beam_profiler_calibration","N/A")}%'],
    ]
    if sec7.get("fitting_error") is not None:
        items_sec7.append(
            ["Fitting error", f'{sec7.get("fitting_error_sign", "±")}{sec7.get("fitting_error", "N/A")}%']
        )
    context["sections"].append({
        "title": "Error Budget",
        "items": items_sec7,
    })
    # Return the generated context

    # Section 8: Test Results
    sec_res = sections_data.get("results", {})
    if sec_res.get("procedure"):
        proc = sec_res.get("procedure", "")
        proc_display = proc.replace(" Fixed", "").replace(" Range", "")
        lidt = sec_res.get("lidt_values", {})

        def _fmt(v):
            if isinstance(v, (int, float)):
                return f"{v:.2f}"
            return str(v) if v else ""

        stack_items = []
        if sec_res.get("mask1_path"):
            stack_items.append({
                "path":    sec_res["mask1_path"],
                "caption": "Arrangement of test sites",
                "notes":   sec_res.get("mask1_comment", ""),
            })
        if sec_res.get("mask2_path"):
            stack_items.append({
                "path":    sec_res["mask2_path"],
                "caption": "Test sites — damage status",
                "notes":   sec_res.get("mask2_comment", ""),
            })
        if sec_res.get("prob_path"):
            stack_items.append({
                "path":    sec_res["prob_path"],
                "caption": "Damage probability curve",
                "notes":   sec_res.get("prob_comment", ""),
            })

        sample_str = (
            f"{sec_res.get('sample_shape', '')}, {sec_res.get('sample_dim', '')}"
            if sec_res.get("sample_shape") and sec_res.get("sample_dim")
            else str(sec_res.get("sample_dim", ""))
        )
        ap_str = (
            f"{sec_res.get('aperture_shape', '')}, {sec_res.get('aperture_dim', '')}"
            if sec_res.get("aperture_shape") and sec_res.get("aperture_dim")
            else str(sec_res.get("aperture_dim", ""))
        )

        if proc == "R-on-1":
            results_sec = {
                "title": "Test Results",
                "items": [
                    ["Sample dimensions",                    sample_str],
                    ["Tested aperture",                      ap_str],
                    ["Test site size",                       sec_res.get("site_size",          "")],
                    ["Number of test sites",                 str(sec_res.get("n_sites",        ""))],
                    ["Test sites distance (center-center)",  sec_res.get("site_dist",          "")],
                    ["Test site matrix",                     sec_res.get("matrix_type",        "")],
                    ["Test type",                            proc_display],
                    ["Fluence step",  sec_res.get("fluence_step", "")],
                    ["Pulses total",                         sec_res.get("pulses_total",       "")],
                    ["Pulses per fluence",                   sec_res.get("pulses_per_fluence", "")],
                    ["Online damage detection",              sec_res.get("online_detection",   "")],
                    ["Offline damage detection",             sec_res.get("offline_detection",  "")],
                ],
            }
            if stack_items:
                results_sec["images"] = {"layout": "stack", "items": stack_items}
            if sec_res.get("spot_plots"):
                results_sec["ron1_spots"] = sec_res["spot_plots"]
            if sec_res.get("spot_results"):
                results_sec["ron1_table"] = {
                    "spot_results": sec_res["spot_results"],
                    "table_number": 1,
                }
        elif proc == "Raster Scan":
            raster_stack = []
            if sec_res.get("raster_map_path"):
                raster_stack.append({
                    "path":    sec_res["raster_map_path"],
                    "caption": "Damage initiation map",
                    "notes":   sec_res.get("raster_map_comment", ""),
                })
            if sec_res.get("raster_density_path"):
                raster_stack.append({
                    "path":    sec_res["raster_density_path"],
                    "caption": "Total damage density and damage probability curve",
                    "notes":   sec_res.get("raster_density_comment", ""),
                })
            results_sec = {
                "title": "Test Results",
                "items": [
                    ["Sample dimensions",                   sample_str],
                    ["Tested aperture",                     ap_str],
                    ["Test site size",                      sec_res.get("site_size",         "")],
                    ["Number of test sites",                str(sec_res.get("n_sites",       ""))],
                    ["Test sites distance (center-center)", sec_res.get("site_dist",         "")],
                    ["Test site matrix",                    sec_res.get("matrix_type",       "")],
                    ["Test type",                           proc_display],
                    ["Pulses per site",                     sec_res.get("pulses_per_site",   "")],
                    ["Pulses total",                        sec_res.get("pulses_total",      "")],
                    ["Online damage detection",             sec_res.get("online_detection",  "")],
                    ["Offline damage detection",            sec_res.get("offline_detection", "")],
                ],
            }
            if raster_stack:
                results_sec["images"] = {"layout": "stack", "items": raster_stack}
            lidt = sec_res.get("lidt_values", {})
            if lidt:
                results_sec["raster_lidt_table"] = {
                    "n_pulses":     str(sec_res.get("pulses_per_site", "")),
                    "lidt_0":       _fmt(lidt.get("lidt_0")),
                    "lidt_5":       _fmt(lidt.get("lidt_5")),
                    "first_damage": _fmt(lidt.get("first_damage")),
                    "sample":       form_data.get("sample", ""),
                    "table_number": 1,
                }

        else:
            pps          = sec_res.get("pulses_per_site", "")
            n_pulses_str = "1" if proc == "1-on-1" else (str(pps) if pps else "N/A")
            results_sec  = {
                "title": "Test Results",
                "items": [
                    ["Sample dimensions",                   sample_str],
                    ["Tested aperture",                     ap_str],
                    ["Test site size",                      sec_res.get("site_size",        "")],
                    ["Number of test sites",                str(sec_res.get("n_sites",      ""))],
                    ["Test sites distance (center-center)", sec_res.get("site_dist",        "")],
                    ["Test site matrix",                    sec_res.get("matrix_type",      "")],
                    ["Test type",                           proc_display],
                    ["Pulses per site",                     sec_res.get("pulses_per_site",  "")],
                    ["Pulses total",                        sec_res.get("pulses_total",     "")],
                    ["Online damage detection",             sec_res.get("online_detection", "")],
                    ["Offline damage detection",            sec_res.get("offline_detection","")],
                ],
            }
            if stack_items:
                results_sec["images"] = {"layout": "stack", "items": stack_items}
            if lidt:
                results_sec["lidt_table"] = {
                    "n_pulses":     n_pulses_str,
                    "lidt_0":       _fmt(lidt.get("lidt_0")),
                    "lidt_50":      _fmt(lidt.get("lidt_50")),
                    "first_damage": _fmt(lidt.get("first_damage")),
                    "show_50_pct":  lidt.get("show_50_pct", True),
                    "sample":       form_data.get("sample", ""),
                    "table_number": 1,
                }

        context["sections"].append(results_sec)

    # ---------------- Annex ----------------
    annex = form_data.get("annex", {})
    annex_items = [item for item in annex.get("items", []) if item.get("file")]

    if annex_items:
        context["sections"].append({
            "title": "Annex",
            "page_break_before": True,
            "images": {
                "layout": "stack",
                "items": [
                    {
                        "path":    item["file"],
                        "caption": item.get("caption", ""),
                        "notes":   item.get("notes",   "")
                    }
                    for item in annex_items
                ]
            }
        })

    if annex.get("comments"):
        context["sections"].append({
            "title": "Annex – General Comments",
            "items": [["Comments", annex["comments"]]]
        })

    return context