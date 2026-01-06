LASER_PRESETS = {
    "manual": {
        "label": "Manual entry",
        "data": {
            "laser_name": "",
            "laser_type": "",
            "wavelength_nm": "",
            "pulse_repetition_frequency": "",
            "output_energy_or_power": "",
            "polarization_state": "",
            "spatial_beam_profile_near_field": "",
            "pulse_duration_1e2": "",
            "effective_pulse_duration": "",
            "beam_diameter_1e2": "",
            "beam_delivery": "",
        },
    },

    "nd_yag_e4": {
        "label": "Nd:YAG (E4)",
        "data": {
            "laser_name": "Nd:YAG (E4)",
            "laser_type": "Flash-pumped, rod-type Nd:YAG",
            "wavelength_nm": "1064",
            "pulse_repetition_frequency": "10 Hz",
            "output_energy_or_power": "up to 450 mJ",
            "polarization_state": "Linear, P-polarized",
            "spatial_beam_profile_near_field": "Circular, 5 mm",
            "pulse_duration_1e2": "8.5 ns",
            "effective_pulse_duration": "8.5 ns",
            "beam_diameter_1e2": "",
            "beam_delivery": "Free space folding mirrors",
        },
        "images": {
            "layout": "template3",
            "items": [
                {"path": r"C:\Users\jovana.babic\OneDrive - Centrum HiLASE\Desktop\LIDT REPORT\report-generator\assets\images\laser1.png"},
                {"path": r"C:\Users\jovana.babic\OneDrive - Centrum HiLASE\Desktop\LIDT REPORT\report-generator\assets\images\laser2.png"},
                {"path": r"C:\Users\jovana.babic\OneDrive - Centrum HiLASE\Desktop\LIDT REPORT\report-generator\assets\images\laser3.png"}
            ],
            "overlay_color": "black",
            "caption": "Spatial and temporal beam profile and the emission spectra at the selected wavelength.",
            "width_pct": 0.7,
            "flatten_alpha_to_white": False
        }
    },

    "tm_futonics_e4": {
        "label": "Tm Laser (Futonics) (E4)",
        "data": {
            "laser_name": "Tm Laser (Futonics) (E4)",
            "laser_type": "Thulium fiber laser",
            "wavelength_nm": "1940",
            "pulse_repetition_frequency": "CW",
            "output_energy_or_power": "200 W",
            "polarization_state": "",
            "spatial_beam_profile_near_field": "",
            "pulse_duration_1e2": "",
            "effective_pulse_duration": "",
            "beam_diameter_1e2": "",
            "beam_delivery": "",
        },
    },

    "perla_b": {
        "label": "Perla B",
        "data": {
            "laser_name": "Perla B",
            "laser_type": "",
            "wavelength_nm": "1030",
            "pulse_repetition_frequency": "1 kHz or 10 kHz",
            "output_energy_or_power": "10 mJ or 1 mJ",
            "polarization_state": "Linear",
            "spatial_beam_profile_near_field": "",
            "pulse_duration_1e2": "1.2 ps",
            "effective_pulse_duration": "",
            "beam_diameter_1e2": "7.5 mm",
            "beam_delivery": "",
        },
    },

    "bivoj": {
        "label": "Bivoj",
        "data": {
            "laser_name": "Bivoj",
            "laser_type": "",
            "wavelength_nm": "1030",
            "pulse_repetition_frequency": "10 Hz",
            "output_energy_or_power": "10 J",
            "polarization_state": "",
            "spatial_beam_profile_near_field": "",
            "pulse_duration_1e2": "10 ns",
            "effective_pulse_duration": "",
            "beam_diameter_1e2": "",
            "beam_delivery": "",
        },
    },
}
