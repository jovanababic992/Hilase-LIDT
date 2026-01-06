from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
CURRENT_YEAR = datetime.now().year

DEFAULT_CONTEXT = {
    
    "lab_image": str(ROOT / "assets/images/lab.jpg"),
    "logo_title": str(ROOT / "assets/logos/logo_white.svg"),
    "logo_inner": str(ROOT / "assets/logos/logo_white.svg"),

  
    "ombre_left": "#00afee",
    "ombre_right": "#64bb2f",
    "ombre_alpha": 0.8,
    "fade_alpha_255": 160,
    "banner_ratio": 0.35,

 
    "margins": {
        "left_mm": 16,
        "right_mm": 16,
        "top_mm": 16,
        "bottom_mm": 20
    },

   
    "title": "Laser-Induced Damage Threshold Test (LIDT) Report",

  
    "copyright": f"© {CURRENT_YEAR} HiLASE Centre"
}
