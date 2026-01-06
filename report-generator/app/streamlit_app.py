import json
from base64 import b64encode
from copy import deepcopy
from pathlib import Path
import sys
from datetime import date

import streamlit as st
import base64
import io
import tempfile
import uuid




ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.defaults import DEFAULT_CONTEXT
from pdf.generate_report import generate_report
from configs.lasers import LASER_PRESETS
from configs.test_setup import TEST_SETUP_PRESETS


# ---------------- Page config ----------------
st.set_page_config(
    page_title="LIDT Report Generator",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------- Paths ----------------
TEMPLATE_DRAFT = ROOT / "assets" / "templates" / "test_draft.json"
BANNER_LOGO_SVG = ROOT / "assets" / "logos" / "logo_white.svg"
OUT_DIR = ROOT / "data" / "generated"
OUT_PDF = OUT_DIR / "latest.pdf"
DRAFTS_DIR = ROOT / "data" / "drafts"

UPLOAD_FOLDER = Path(__file__).resolve().parent.parent / "data" / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# ---------------- Fixed top banner (SVG) ----------------
if BANNER_LOGO_SVG.exists():
    svg_b64 = b64encode(BANNER_LOGO_SVG.read_bytes()).decode("utf-8")
    st.markdown(
        f"""
        <style>
        .hdr{{position:fixed;top:0;left:0;right:0;width:100%;z-index:10000;margin:0;
             display:flex;align-items:center;gap:12px;padding:14px 16px;
             border-bottom:1px solid rgba(255,255,255,.15);
             background:linear-gradient(90deg,#00afee,#64bb2f);
             box-shadow:0 1px 8px rgba(0,0,0,.15)}}
        .hdr img{{height:52px}}
        .hdr .t{{color:#fff;font-weight:700; font-size:22px;letter-spacing:.4px;line-height:1;display:flex;align-items:center;transform: translateY(1px)}}
        .hdr .t .dot{{font-size:26px;line-height:1;margin-top:1px;}}
        .hdr .b{{margin-left:auto;font-size:12px;padding:2px 8px;border-radius:12px;
                background:rgba(255,255,255,.15);color:#fff;border:1px solid rgba(255,255,255,.25)}}
        .stApp{{padding-top:76px}}
        header[data-testid="stHeader"]{{height:0;visibility:hidden}}
        section.main>div.block-container{{padding-top:.5rem}}
        </style>

        <div class="hdr">
          <img src="data:image/svg+xml;base64,{svg_b64}" alt="logo"/>
          <div class="t"><span class="dot">•</span>&nbsp;LIDT Report Generator</div>
          <div class="b">ALPHA</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.warning(f"Banner SVG not found: {BANNER_LOGO_SVG}")

# ---------------- Session init ----------------
if "form" not in st.session_state:
    st.session_state["form"] = None
if st.session_state["form"] is not None:
    st.session_state["form"].setdefault("sections_data", {})

if "show_draft_picker" not in st.session_state:
    st.session_state["show_draft_picker"] = False
if "people_list" not in st.session_state:
    st.session_state["people_list"] = [
        "Mihai-George Mureșan, Ph.D. (mihai@hilase.cz)",
        "Priyadarshani Narayanasamy, Ph.D. (priya@hilase.cz)",
        "Mgr. Liliia Uvarova, Ph.D. (liliia.uvarova@hilase.cz)",
        "Arindom Phukan, Ph.D. (arindom.phukan@hilase.cz)",
        "Ing. Martin Mydlář (martin.mydlar@hilase.cz)",
        "Ing. František Novák (frantisek.novak@hilase.cz)"
    ]
if "show_add_person" not in st.session_state:
    st.session_state["show_add_person"] = False
if "new_person_input" not in st.session_state:
    st.session_state["new_person_input"] = ""





# ---------------- Start screen ----------------
if st.session_state["form"] is None:
    
    c1, c2 = st.columns(2)

    with c1:
        if st.button("Start new report", use_container_width=True):
            ctx = deepcopy(DEFAULT_CONTEXT)
            ctx.update({
                "report_no": "",
                "standard": "ISO 21254",
                "sample": "",
                "prepared_by": [],
                "approved_by": "",
                # prefill but editable
                "institute": "HiLASE Centre, Institute of Physics ASCR",
                "inst_address": "Za Radnici 828, 252 41 Dolni Brezany, Czech Republic",
                "customer": "",
                "cust_address": "",
                "cust_contact": "",
                "sections": []
            })
            st.session_state["form"] = ctx
            st.rerun()

    with c2:
        if st.button("Load existing draft", use_container_width=True):
            st.session_state["show_draft_picker"] = True

        if st.session_state.get("show_draft_picker", False):
            st.markdown("#### Select a draft")

            draft_files = []
            if DRAFTS_DIR.exists():
                draft_files = sorted([p.name for p in DRAFTS_DIR.glob("*.json")])

            selected_draft = st.selectbox(
                "Draft file",
                options=draft_files,
                disabled=not draft_files
            )

            if st.button("Load selected draft", disabled=not draft_files):
                draft_path = DRAFTS_DIR / selected_draft
                draft = json.loads(draft_path.read_text(encoding="utf-8"))

                ctx = deepcopy(DEFAULT_CONTEXT)
                ctx.update(draft)
                st.session_state["form"] = ctx

                # --- hydrate session_state from draft sections ---
                form = st.session_state["form"]
                form["sections_data"] = {}

                for section in draft.get("sections", []):
                    title = section.get("title", "")
                    items = dict(section.get("items", []))

                    if title == "Sample Information":
                        form["sections_data"]["sample_information"] = {
                            "description": items.get("Description", ""),
                            "date_received": (
                                date.fromisoformat(items["Date Received"])
                                if items.get("Date Received") else date.today()
                            ),
                            "preparation": items.get("Preparation", ""),
                        }

                    elif title == "Test Identification":
                        form["sections_data"]["test_identification"] = {
                            "procedure": items.get("Procedure", ""),
                            "objective": items.get("Objective", ""),
                            "sites_pulses": items.get("Sites / Pulses per Site", ""),
                            "damage_detection": items.get("Damage Detection", ""),
                        }



                for k in ["lab_image", "logo_title", "logo_inner"]:
                    p = Path(ctx[k])
                    if not p.is_absolute():
                        ctx[k] = str((ROOT / p).resolve())

                st.session_state["form"] = ctx
                st.session_state["show_draft_picker"] = False
                st.rerun()


    st.stop()


ctx = st.session_state["form"]


# ---------------- Tabs ----------------
tab1, tab2, tab3, tab4  = st.tabs(["Basics (Title + Section 1)","sections 2-4", "section 5-6", "Generate"])

with tab1:
    st.subheader("Title page")

    col_left, col_right = st.columns([2, 2])

    with col_left:
        st.session_state["form"]["title"] = st.text_input(
            "Report title",
            value=st.session_state["form"].get("title", "")
        )
    with col_right:
        c_std, c_sample = st.columns(2)
        with c_std:
            st.session_state["form"]["standard"] = st.text_input(
                "Standard",
                value=st.session_state["form"].get("standard", "ISO 21254"),
            )
        with c_sample:
            st.session_state["form"]["sample"] = st.text_input(
                "Sample ID",
                value=st.session_state["form"].get("sample", ""),
            )

    col_prep, col_appr = st.columns([1, 1])

    with col_prep:
        st.session_state["form"]["prepared_by"] = st.multiselect(
            "Prepared by",
            options=st.session_state["people_list"],
            default=st.session_state["form"].get("prepared_by", []),
            key="prepared_by_multiselect",
        )

    with col_appr:
        approved = st.session_state["form"].get("approved_by")

        st.session_state["form"]["approved_by"] = st.selectbox(
            "Approved by",
            options=st.session_state["people_list"],
            index=(
                st.session_state["people_list"].index(approved)
                if approved in st.session_state["people_list"]
                else 0
            ),
        )

    add_btn_col, add_input_col = st.columns([1, 4])

    with add_btn_col:
        if st.button("＋ Add person"):
            st.session_state["show_add_person"] = True

    with add_input_col:
        if st.session_state["show_add_person"]:
            def _add_person():
                name = st.session_state["new_person_input"].strip()
                if name and name not in st.session_state["people_list"]:
                    st.session_state["people_list"].append(name)
                st.session_state["new_person_input"] = ""
                st.session_state["show_add_person"] = False

            st.text_input(
                "New person",
                placeholder="Name Surname (email)",
                label_visibility="collapsed",
                key="new_person_input",
                on_change=_add_person,
            )




    st.markdown("---")
    st.subheader("Institute / Customer")
    form = st.session_state["form"]
    colC, colD = st.columns(2)
    with colC:
        form["institute"] = st.text_input("Institute", value=form.get("institute", ""))
        form["inst_address"] = st.text_area("Institute address", value=form.get("inst_address", ""), height=90)
    with colD:
        form["customer"] = st.text_input("Customer name", value=form.get("customer", ""))
        form["cust_address"] = st.text_area("Customer address", value=form.get("cust_address", ""), height=90)
        form["cust_contact"] = st.text_input("Customer contact", value=form.get("cust_contact", ""))

    st.markdown("---")
 


with tab2:
    st.subheader("Section 2: Sample Information")

    form = st.session_state["form"]
    sec2 = form["sections_data"].setdefault("sample_information", {})

    c1, c2, c3 = st.columns([3, 1, 3])

    with c1:
        sec2["description"] = st.text_input(
            "Description",
            value=sec2.get("description", ""),
        )

    with c2:
        sec2["date_received"] = st.date_input(
            "Date Received",
            value=sec2.get("date_received", date.today()),
        )

    with c3:
        sec2["preparation"] = st.text_input(
            "Preparation",
            value=sec2.get("preparation", ""),
        )

    st.subheader("Section 3: Laser and Environmental Conditions")
    form = st.session_state["form"]
    sec3 = form["sections_data"].setdefault("laser_environmental", {})

    sec3.setdefault(
        "laser",
        LASER_PRESETS["manual"]["data"].copy()
        )
    preset_labels = {
        k: v["label"] for k, v in LASER_PRESETS.items()}

    def _on_laser_change():
        key = st.session_state["laser_preset"]
        sec3["laser"] = LASER_PRESETS[key]["data"].copy()

    selected_key = st.selectbox(
        "Which laser will be used?",
        options=list(LASER_PRESETS.keys()),
        format_func=lambda k: preset_labels[k],
        key="laser_preset",
        on_change=_on_laser_change,
    )

    laser = sec3["laser"]

    # --- Row 1: identity (2) ---
    c1, c2 = st.columns(2)
    laser["laser_type"] = c1.text_input(
        "Laser type", laser.get("laser_type", "")
    )
    laser["output_energy_or_power"] = c2.text_input(
        "Output energy / power", laser.get("output_energy_or_power", "")
    )

    # --- Row 2: core physics (4) ---
    c1, c2, c3, c4 = st.columns(4)
    laser["wavelength_nm"] = c1.text_input(
        "Wavelength [nm]", laser.get("wavelength_nm", "")
    )
    laser["pulse_repetition_frequency"] = c2.text_input(
        "Rep. frequency", laser.get("pulse_repetition_frequency", "")
    )
    laser["pulse_duration_1e2"] = c3.text_input(
        "Pulse duration (1/e²)", laser.get("pulse_duration_1e2", "")
    )
    laser["effective_pulse_duration"] = c4.text_input(
        "Effective pulse duration", laser.get("effective_pulse_duration", "")
    )

    # --- Row 3: spatial / polarization (3) ---
    c1, c2, c3 = st.columns(3)
    laser["polarization_state"] = c1.text_input(
        "Polarization", laser.get("polarization_state", "")
    )
    laser["beam_diameter_1e2"] = c2.text_input(
        "Beam diameter (1/e²)", laser.get("beam_diameter_1e2", "")
    )
    laser["spatial_beam_profile_near_field"] = c3.text_input(
        "Beam profile (near field)", laser.get("spatial_beam_profile_near_field", "")
    )

    # --- Row 4: delivery (1) ---
    laser["beam_delivery"] = st.text_input(
        "Beam delivery", laser.get("beam_delivery", "")
    )


    st.subheader("Section 4: Test Identification")

    form = st.session_state["form"]
    sec4 = form["sections_data"].setdefault("test_identification", {})

    c1, c2 = st.columns(2)
    with c1:
        sec4["procedure"] = st.text_input(
            "Procedure",
            value=sec4.get("procedure", ""),
        )

    with c2:
        sec4["objective"] = st.text_input(
            "Objective",
            value=sec4.get("objective", ""),
        )

    c3, c4 = st.columns(2)
    with c3:
        sec4["sites_pulses"] = st.text_input(
            "Sites / Pulses per Site",
            value=sec4.get("sites_pulses", ""),
        )

    with c4:
        sec4["damage_detection"] = st.text_input(
            "Damage Detection",
            value=sec4.get("damage_detection", ""),
        )
 

with tab3:

    st.subheader("Optional Test Setup")
    form = st.session_state["form"]
    sec5 = form["sections_data"].setdefault("test_setup", {})

 
 

    sec5["choice"] = st.radio(
        "Choose a Test Setup option",
        options=["E4", "L1-LIDT", "Manual Upload", "Skip"],
        index=3,
    )

    if sec5["choice"] in ["E4", "L1-LIDT"]:
        sec5["selected_preset"] = sec5["choice"]
        sec5["image"] = TEST_SETUP_PRESETS[
            "preset_1" if sec5["choice"] == "E4" else "preset_2"
        ]["image_path"]
    elif sec5["choice"] == "Manual Upload":
        uploaded_image = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg"])
        if uploaded_image:
            file_extension = uploaded_image.name.split('.')[-1]
            unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
            upload_path = UPLOAD_FOLDER / unique_filename
            with open(upload_path, "wb") as f:
                f.write(uploaded_image.read())
            sec5["image"] = str(upload_path)
        else:
            sec5.pop("image", None)  # Remove image entry if none uploaded
    else:
        sec5.clear()  # Skip clears the setup state

 
        


with tab4:
    st.subheader("Generate")

    c1, c2 = st.columns([1, 1])

    with c1:
        if st.button("Generate PDF", type="primary", use_container_width=True):
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            ctx["report_no"] = "DRAFT"
            ctx["issue_date"] = date.today().strftime("%d %B %Y")
            ctx["sections"] = []
        
            form = st.session_state["form"]
            sections_data = form.get("sections_data", {})
            ctx["sections"].append({
                "title": "Report Identification",
                "items": [
                    ["Report Number", ctx["report_no"]],
                    ["Issue Date", ctx["issue_date"]],
                ],
            })
            # Section 2
            sec2 = sections_data.get("sample_information", {})
            ctx["sections"].append({
                "title": "Sample Information",
                "items": [
                    ["Sample ID", form.get("sample", "")],
                    ["Description", sec2.get("description", "")],
                    ["Date Received", (
                        sec2["date_received"].strftime("%d %B %Y")
                        if isinstance(sec2.get("date_received"), date)
                        else ""
                    )],
                    ["Preparation", sec2.get("preparation", "")],
                ],
            })

            sec3 = sections_data.get("laser_environmental", {})
            laser = sec3.get("laser", {})
            selected_laser = LASER_PRESETS.get(st.session_state.get("laser_preset"), {})
            laser_images = selected_laser.get("images", {})
            ctx["sections"].append({
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

            sec4 = sections_data.get("test_identification", {})
            ctx["sections"].append({
                "title": "Test Identification",
                "items": [
                    ["Procedure", sec4.get("procedure", "")],
                    ["Objective", sec4.get("objective", "")],
                    ["Sites / Pulses per Site", sec4.get("sites_pulses", "")],
                    ["Damage Detection", sec4.get("damage_detection", "")],
                ],
            })

            sec5 = sections_data.get("test_setup", {})
 
            if sec5.get("choice") and sec5["choice"] != "Skip":
                ctx["sections"].append({
                    "title": "Test Setup",
                    "images": {
                        "layout": "template1",
                        "items": [
                            {"path": sec5["image"]},
                        ],
                    "overlay_color": "black",
                    "caption": "Test setup.",
                    "width_pct": 1,
                    "flatten_alpha_to_white": False}
                })


            generate_report(ctx, output_path=str(OUT_PDF))
            st.success(f"Generated: {OUT_PDF}")

        if OUT_PDF.exists():
            st.download_button(
                "Download latest PDF",
                data=OUT_PDF.read_bytes(),
                file_name="LIDT_report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    with c2:
        with st.expander("Context preview (debug)", expanded=False):
            st.json(ctx)

