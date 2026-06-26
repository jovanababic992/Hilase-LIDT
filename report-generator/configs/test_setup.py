from pathlib import Path

_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "images"

TEST_SETUP_PRESETS = {
    "preset_1": {
        "label": "E4",
        "image_path": str(_ASSETS / "setup_scheme_E4.png"),
    },
    "preset_2": {
        "label": "L1-LIDT",
        "image_path": str(_ASSETS / "setup_scheme_L1_LIDT.png"),
    },
}