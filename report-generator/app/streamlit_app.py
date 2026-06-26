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
import matplotlib.pyplot as plt



ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.defaults import DEFAULT_CONTEXT
from pdf.generate_report import generate_report
from configs.lasers import LASER_PRESETS
from configs.test_setup import TEST_SETUP_PRESETS
from services.context_manager import generate_context

from services.database import (
    init_db, authenticate_user, list_drafts, load_draft,
    save_draft, update_draft, save_final, list_finals,
    get_final_pdf, get_customer_by_name, list_customers,
    add_customer, next_report_number, change_password,
)
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
        "Liliia Uvarova, Ph.D. (liliia.uvarova@hilase.cz)",
        "Arindom Phukan, Ph.D. (arindom.phukan@hilase.cz)",
        "Ing. Martin Mydlář (martin.mydlar@hilase.cz)",
        "Ing. František Novák (frantisek.novak@hilase.cz)",
        "Msc. Fauzul Rizal (fauzul.rizal@hilase.cz)"

    ]
if "show_add_person" not in st.session_state:
    st.session_state["show_add_person"] = False
if "new_person_input" not in st.session_state:
    st.session_state["new_person_input"] = ""

if "user" not in st.session_state:
    st.session_state["user"] = None
if "current_draft_id" not in st.session_state:
    st.session_state["current_draft_id"] = None

# ---------------- Database init ----------------
from services.database import (
    init_db, authenticate_user, list_drafts, load_draft,
    save_draft, update_draft, save_final, list_finals,
    get_final_pdf, get_customer_by_name, list_customers, add_customer,
)
init_db()

# ---------------- Login gate ----------------
# ---------------- Change password dialog ----------------
@st.dialog("Change Password", width="small")
def change_password_dialog():
    current = st.text_input("Current password", type="password", key="cp_current")
    new_pw  = st.text_input("New password",     type="password", key="cp_new")
    confirm = st.text_input("Confirm new password", type="password", key="cp_confirm")
    if st.button("Update Password", use_container_width=True):
        if not current or not new_pw:
            st.error("Please fill in all fields")
        elif new_pw != confirm:
            st.error("New passwords don't match")
        elif len(new_pw) < 6:
            st.error("Password must be at least 6 characters")
        else:
            ok = change_password(st.session_state["user"]["id"], current, new_pw)
            if ok:
                st.success("Password updated!")
                st.rerun()
            else:
                st.error("Current password is incorrect")

# ---------------- Login gate ----------------
if st.session_state["user"] is None:
    if BANNER_LOGO_SVG.exists():
        svg_b64 = b64encode(BANNER_LOGO_SVG.read_bytes()).decode()
        logo_html = f'<img src="data:image/svg+xml;base64,{svg_b64}" style="height:52px">'
    else:
        logo_html = ""

    st.markdown("""
    <style>
    header[data-testid="stHeader"] {visibility: hidden;}
    .stApp {background: linear-gradient(135deg, #e8f7ff 0%, #f0ffe8 100%);}
    div.stButton>button {
        width:100%;color:#fff;font-weight:600;
        background:linear-gradient(90deg,#0a714e,#0a714e);
        border:none;border-radius:6px;padding:10px 0;font-size:1rem;
    }
    div.stButton>button:hover {filter:brightness(1.1)}
    </style>
    """, unsafe_allow_html=True)

    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        st.markdown(f"""
        <div style="background:linear-gradient(90deg,#0a714e,#0a714e);
            border-radius:14px;padding:24px 20px 16px;
            text-align:center;margin-bottom:1.5rem;margin-top:3rem;">
            {logo_html}
            <div style="color:white;font-size:1.1rem;font-weight:700;margin-top:8px;">
                LIDT Report Generator
            </div>
        </div>
        """, unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("#### Sign in")
            login_username = st.text_input("Username", key="login_username")
            login_password = st.text_input("Password", type="password", key="login_password")
            st.write("")
            if st.button("Sign In", use_container_width=True, key="login_btn"):
                user = authenticate_user(login_username, login_password)
                if user:
                    st.session_state["user"] = user
                    st.session_state["login_error"] = ""
                    st.rerun()
                else:
                    st.session_state["login_error"] = "Invalid username or password"
            if st.session_state.get("login_error"):
                st.error(st.session_state["login_error"])
    st.stop()

# ---------------- Header banner ----------------
# ── Banner ────────────────────────────────────────────────────────────────
if BANNER_LOGO_SVG.exists():
    svg_b64 = b64encode(BANNER_LOGO_SVG.read_bytes()).decode("utf-8")
    st.markdown(
        f"""
        <style>
        .hdr{{position:fixed;top:0;left:0;right:0;width:100%;z-index:10000;margin:0;
             display:flex;align-items:center;gap:12px;padding:14px 16px;
             border-bottom:1px solid rgba(255,255,255,.15);
             background:linear-gradient(90deg,#0a714e,#0a714e);
             box-shadow:0 1px 8px rgba(0,0,0,.15)}}
        .hdr img{{height:52px}}
        .hdr .t{{color:#fff;font-weight:700;font-size:22px;letter-spacing:.4px;line-height:1;
                display:flex;align-items:center;transform:translateY(1px)}}
        .hdr .t .dot{{font-size:26px;line-height:1;margin-top:1px}}
        .hdr .b{{margin-left:auto;font-size:12px;padding:2px 8px;border-radius:12px;
                background:rgba(255,255,255,.15);color:#fff;border:1px solid rgba(255,255,255,.25)}}
        .stApp{{padding-top:76px}}
        header[data-testid="stHeader"]{{height:0;visibility:hidden}}
        section.main>div.block-container{{padding-top:.5rem}}
        button[data-testid="stPopoverButton"]{{background:rgba(255,255,255,0.15)!important;
            border:1px solid rgba(255,255,255,0.35)!important;font-size:13px!important;
            border-radius:20px!important;width:auto!important;font-weight:500!important;
            padding:3px 14px!important}}
        button[data-testid="stPopoverButton"]:hover{{background:rgba(255,255,255,0.25)!important;
            filter:none!important}}
        </style>
        <div class="hdr">
          <img src="data:image/svg+xml;base64,{svg_b64}" alt="logo"/>
          <div class="t"><span class="dot">•</span>&nbsp;LIDT Report Generator</div>
          <div class="b">ALPHA</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
# ---------------- User popover ----------------
_col_space, _col_user = st.columns([10, 2])
with _col_user:
    with st.popover(f"👤 {st.session_state['user']['username']}"):
        st.divider()
        if st.button("🔑 Change Password", use_container_width=True, key="open_cp"):
            change_password_dialog()
        if st.button("Logout", use_container_width=True, key="logout_btn"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
# ---------------- Start screen ----------------
if st.session_state["form"] is None:
    
    c1, c2 = st.columns(2)

    with c1:
        if st.button("Start new report", use_container_width=True):
            ctx = deepcopy(DEFAULT_CONTEXT)
            ctx.update({
                "report_no": "",  # Initialize to empty or dynamically fetch later if needed
                "standard": "ISO 21254",
                "sample": "",
                "prepared_by": [],
                "approved_by": "",
                # Prefill but editable
                "institute": "HiLASE Centre, Institute of Physics ASCR",
                "inst_address": "Za Radnici 828, 252 41 Dolni Brezany, Czech Republic",
                "customer": "",
                "cust_address": "",
                "cust_contact": "",
                "sections": [],  # Start with empty sections
            })
            st.session_state["form"] = ctx  # Store initialized form in session state
            st.rerun()
        
    with c2:
        if st.button("Load existing draft", use_container_width=True):
            st.session_state["show_draft_picker"] = True

        if st.session_state.get("show_draft_picker", False):
            st.markdown("#### Select a draft")
            drafts = list_drafts()
            if not drafts:
                st.info("No drafts saved yet.")
            else:
                draft_options = {
                    f"{d['name']}  —  {d['created_by']}  ({d['updated_at'][:10]})": d["id"]
                    for d in drafts
                }
                selected_label = st.selectbox("Draft", options=list(draft_options.keys()))
                if st.button("Load selected draft"):
                    draft_id   = draft_options[selected_label]
                    draft_data = load_draft(draft_id)
                    if draft_data:
                        ctx = deepcopy(DEFAULT_CONTEXT)
                        ctx.update(draft_data)
                        for k in ["lab_image", "logo_title", "logo_inner"]:
                            p = Path(ctx.get(k, ""))
                            if p and not p.is_absolute():
                                ctx[k] = str((ROOT / p).resolve())
                        st.session_state["form"]              = ctx
                        st.session_state["current_draft_id"]  = draft_id
                        st.session_state["show_draft_picker"] = False

                        # Merge saved people into people_list so multiselect doesn't crash
                        for _person in ctx.get("prepared_by", []):
                            if _person and _person not in st.session_state["people_list"]:
                                st.session_state["people_list"].append(_person)
                        _appr = ctx.get("approved_by", "")
                        if _appr and _appr not in st.session_state["people_list"]:
                            st.session_state["people_list"].append(_appr)

                        # Restore test results widget state from draft
                        # Restore test results widget state from draft
                        _r = ctx.get("sections_data", {}).get("results", {})
                        if _r:
                            if _r.get("procedure"):
                                st.session_state["results_test_type"] = _r["procedure"]
                            _rmap = {
                                # 1-on-1 / S-on-1
                                "res_sample_shape":           _r.get("sample_shape"),
                                "res_sample_dim":             _r.get("sample_dim"),
                                "res_ap_shape":               _r.get("aperture_shape"),
                                "res_ap_dim":                 _r.get("aperture_dim"),
                                "res_site_size":              _r.get("site_size"),
                                "res_n_sites":                _r.get("n_sites"),
                                "res_site_dist":              _r.get("site_dist"),
                                "res_matrix":                 _r.get("matrix_type"),
                                "res_online":                 _r.get("online_detection"),
                                "res_offline":                _r.get("offline_detection"),
                                "res_pps":                    _r.get("pulses_per_site"),
                                "res_pulses_total":           _r.get("pulses_total"),
                                "res_mask1_comment":          _r.get("mask1_comment"),
                                "res_mask2_comment":          _r.get("mask2_comment"),
                                "res_prob_comment":           _r.get("prob_comment"),
                                # R-on-1
                                "res_sample_shape_r":         _r.get("sample_shape"),
                                "res_sample_dim_r":           _r.get("sample_dim"),
                                "res_ap_shape_r":             _r.get("aperture_shape"),
                                "res_ap_dim_r":               _r.get("aperture_dim"),
                                "res_site_size_r":            _r.get("site_size"),
                                "res_n_sites_r":              _r.get("n_sites"),
                                "res_site_dist_r":            _r.get("site_dist"),
                                "res_matrix_r":               _r.get("matrix_type"),
                                "res_online_r":               _r.get("online_detection"),
                                "res_offline_r":              _r.get("offline_detection"),
                                "res_ppf":                    _r.get("pulses_per_fluence"),
                                "res_pulses_total_r":         _r.get("pulses_total"),
                                "res_fluence_step":           _r.get("fluence_step"),
                                "res_mask1_comment_r":        _r.get("mask1_comment"),
                                "res_mask2_comment_r":        _r.get("mask2_comment"),
                                "res_spots_comment_r":        _r.get("spots_comment"),
                                # Raster Scan
                                "res_sample_shape_rs":        _r.get("sample_shape"),
                                "res_sample_dim_rs":          _r.get("sample_dim"),
                                "res_ap_shape_rs":            _r.get("aperture_shape"),
                                "res_ap_dim_rs":              _r.get("aperture_dim"),
                                "res_site_size_rs":           _r.get("site_size"),
                                "res_n_sites_rs":             _r.get("n_sites"),
                                "res_site_dist_rs":           _r.get("site_dist"),
                                "res_matrix_rs":              _r.get("matrix_type"),
                                "res_online_rs":              _r.get("online_detection"),
                                "res_offline_rs":             _r.get("offline_detection"),
                                "res_pps_rs":                 _r.get("pulses_per_site"),
                                "res_pulses_total_rs":        _r.get("pulses_total"),
                                "res_raster_map_comment":     _r.get("raster_map_comment"),
                                "res_raster_density_comment": _r.get("raster_density_comment"),
                            }
                        # Restore sec6 keyed selectboxes + laser preset
                        _s6 = ctx.get("sections_data", {}).get("test_procedure", {})
                        _s6map = {
                            "environment_choice":     _s6.get("environment_choice"),
                            "focusing_choice":        _s6.get("focusing_choice"),
                            "beam_energy_choice":     _s6.get("beam_energy_choice"),
                            "sample_position_choice": _s6.get("sample_position_choice"),
                            "laser_preset":           ctx.get("laser_preset"),
                        }
                        for _k, _v in _s6map.items():
                            if _v is not None:
                                st.session_state[_k] = _v
                        for _k, _v in _rmap.items():
                            if _v is not None:
                                st.session_state[_k] = _v
                        _s7 = ctx.get("sections_data", {}).get("error_budget", {})
                        if _s7.get("camera"):
                            st.session_state["eb_camera"] = _s7["camera"]

                        st.rerun()

    st.stop()


ctx = st.session_state["form"]


# ---------------- Tabs ----------------
#tab1, tab2, tab3, tab4, tab5, tab6  = st.tabs(["Basics (Title + Section 1)","sections 2-4", "sections 5-6","sections 7-9", "Annex", "Generate"])
tab_home, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Home", "Basics (Title + Section 1)", "sections 2-4", "sections 5-6", "sections 7-9", "Annex", "Generate"])

with tab_home:
    st.write("")
    draft_id = st.session_state.get("current_draft_id")
    if draft_id:
        st.info(f"Currently editing draft ID: {draft_id}")
    if st.button("← Back to start screen", use_container_width=False):
        st.session_state["form"] = None
        st.session_state["current_draft_id"] = None
        st.rerun()

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
        form["institute"]    = st.text_input("Institute",        value=form.get("institute",    ""))
        form["inst_address"] = st.text_area("Institute address", value=form.get("inst_address", ""), height=90)

    with colD:
        customers    = list_customers()
        cust_names   = [c["name"] for c in customers]
        options      = ["— select —"] + cust_names + ["＋ Add new customer"]
        current_name = form.get("customer", "")
        default_idx  = (cust_names.index(current_name) + 1) if current_name in cust_names else 0

        chosen = st.selectbox("Customer", options=options, index=default_idx, key="cust_select")

        if chosen == "＋ Add new customer":
            new_n = st.text_input("Name",    placeholder="Company / institution", key="new_cust_n")
            new_a = st.text_area( "Address", height=90,                           key="new_cust_a")
            new_c = st.text_input("Contact", placeholder="Name Surname",          key="new_cust_c")
            if st.button("Save customer to database"):
                if new_n.strip():
                    add_customer(new_n.strip(), new_a.strip(), new_c.strip())
                    form["customer"]     = new_n.strip()
                    form["cust_address"] = new_a.strip()
                    form["cust_contact"] = new_c.strip()
                    st.success(f"Customer '{new_n}' saved.")
                    st.rerun()
                else:
                    st.warning("Customer name is required.")

        elif chosen != "— select —":
            if st.session_state.get("_last_customer") != chosen:
                cust_data = get_customer_by_name(chosen)
                if cust_data:
                    form["customer"]              = cust_data["name"]
                    form["cust_address"]          = cust_data.get("address", "")
                    form["cust_contact"]          = cust_data.get("contact", "")
                    st.session_state["cust_addr"] = cust_data.get("address", "")
                    st.session_state["cust_cont"] = cust_data.get("contact", "")
                st.session_state["_last_customer"] = chosen
            form["cust_address"] = st.text_area("Customer address", height=90, key="cust_addr")
            form["cust_contact"] = st.text_input("Customer contact", key="cust_cont")
        else:
            form["customer"]     = ""
            form["cust_address"] = st.text_area("Customer address", height=90, key="cust_addr")
            form["cust_contact"] = st.text_input("Customer contact", key="cust_cont")
 
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
    form["laser_preset"] = selected_key

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

    # --- Laser beam profile images (manual upload) ---
    _has_preset_images = bool(LASER_PRESETS.get(selected_key, {}).get("images", {}).get("items"))
    if not _has_preset_images:
        st.markdown("#### Laser Beam Profile Images")
        lc1, lc2, lc3 = st.columns(3)
        with lc1:
            _li1 = st.file_uploader("Beam profile", type=["png", "jpg", "jpeg"], key="laser_img_1")
        with lc2:
            _li2 = st.file_uploader("Cross section", type=["png", "jpg", "jpeg"], key="laser_img_2")
        with lc3:
            _li3 = st.file_uploader("Pointing / spectra", type=["png", "jpg", "jpeg"], key="laser_img_3")

        _prev_laser_imgs = list(sec3.get("laser_images", []))
        sec3["laser_images"] = []
        for _idx, _limg in enumerate([_li1, _li2, _li3]):
            if _limg:
                _ext = _limg.name.split(".")[-1]
                _lname = f"{uuid.uuid4().hex}_laser_{_idx}.{_ext}"
                _lpath = UPLOAD_FOLDER / _lname
                with open(_lpath, "wb") as f:
                    f.write(_limg.read())
                sec3["laser_images"].append(str(_lpath))
        if not sec3["laser_images"] and _prev_laser_imgs:
            sec3["laser_images"] = _prev_laser_imgs
        _n_laser = sum(1 for p in sec3.get("laser_images", []) if Path(p).exists())
        if _n_laser:
            st.caption(f"✓ {_n_laser} laser image(s) already uploaded — re-upload to replace")

        sec3["laser_image_caption"] = st.text_input(
            "Image caption",
            value=sec3.get("laser_image_caption", "Spatial and temporal beam profile and the emission spectra at the selected wavelength."),
            key="laser_img_caption",
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

 
 
    _setup_opts = ["E4", "L1-LIDT", "Manual Upload", "Skip"]
    sec5["choice"] = st.radio(
        "Choose a Test Setup option",
        options=_setup_opts,
        index=_setup_opts.index(sec5.get("choice", "Skip")),
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
        if not uploaded_image and sec5.get("image") and Path(sec5["image"]).exists():
            st.caption("✓ Image already uploaded — re-upload to replace")
        elif not uploaded_image:
            sec5.pop("image", None)
    else:
        sec5.clear()  # Skip clears the setup state
    sec5["caption"] = "Test setup."

    # --- Test and Procedure Specification ---
    st.subheader("Test and Procedure Specification")
    form = st.session_state["form"]
    sec6 = form["sections_data"].setdefault("test_procedure", {})

    # --- Environment Inputs ---
    st.markdown("#### Environment")
    env1, env2, env3 = st.columns(3)  

    sec6["environment_choice"] = env1.selectbox(
        "Environment Type",
        ["Standard laboratory", "Class ISO 7", "Manual"],
        key="environment_choice"
    )
    if sec6["environment_choice"] == "Manual":
        sec6["environment_custom"] = env1.text_input("Specify environment manually")
    sec6["temperature"] = env2.number_input("Temperature (°C)", value=float(sec6.get("temperature", 22.0)), step=0.1, format="%.1f")
    #sec6["temperature"] = env2.number_input("Temperature (°C)", value=22.0,step=0.1, format="%.1f")
    #sec6["humidity"] = env3.number_input("Relative Humidity (%)", value=40)
    sec6["humidity"] = env3.number_input("Relative Humidity (%)", value=int(sec6.get("humidity", 40)))
    # --- Vacuum ---
    st.markdown("#### Vacuum Conditions")
    vac1, vac2 = st.columns([1, 2])  # Optimize layout to fit toggle and input together
    #sec6["vacuum"] = vac1.radio("Vacuum required?", ["No", "Yes"], index=0)
    sec6["vacuum"] = vac1.radio("Vacuum required?", ["No", "Yes"], index=["No", "Yes"].index(sec6.get("vacuum", "No")) if sec6.get("vacuum") in ["No", "Yes"] else 0)
    if sec6["vacuum"] == "Yes":
        sec6["vacuum_pressure"] = vac2.number_input("Pressure Level (10^X)", value=int(sec6.get("vacuum_pressure", 3)), format="%d")
        #sec6["vacuum_pressure"] = vac2.number_input("Pressure Level (10^X)", value=3, format="%d")

    # --- Focusing System ---
    st.markdown("#### Focusing System")
    fs1, fs2 = st.columns([1, 2])  # Optimize layout for dropdown and additional inputs
    sec6["focusing_choice"] = fs1.selectbox(
        "Focusing System",
        ["Spherical lens", "Plano convex lens",
        "Spherical mirror", "Manual"],
        key="focusing_choice"
    )
    if sec6["focusing_choice"] == "Manual":
        sec6["focusing_custom"] = fs2.text_input("Specify focusing system manually")
    elif sec6["focusing_choice"] == "Spherical lens" or sec6["focusing_choice"] == "Plano convex lens":
        sec6["focusing_distance"] = fs2.number_input("Focusing distance [mm]", value=int(sec6.get("focusing_distance", 500)), format="%d")
        #sec6["focusing_distance"] = fs2.number_input("Focusing distance [mm]", value=500, format="%d")
    elif sec6["focusing_choice"] == "Spherical mirror":
        sec6["radius of curvature"] = fs2.number_input("Radius of curvature [mm]", value=int(sec6.get("radius of curvature", 500)), format="%d")
        #sec6["radius of curvature"] = fs2.number_input("Radius of curvature [mm]", value=500, format="%d")



    # --- Beam Energy Management ---
    st.markdown("#### Beam Energy Management")
    beam1, beam2 = st.columns([1, 2])  # Optimize dropdown and additional details
    sec6["beam_energy_choice"] = beam1.selectbox(
        "Beam Energy Management",
        ["Attenuator (polarization-based, motorized)", "Manual"],
        key="beam_energy_choice"
    )
    if sec6["beam_energy_choice"] == "Manual":
        sec6["beam_energy_custom"] = beam2.text_input("Specify beam energy manually")

    # --- Sample Position ---
    st.markdown("#### Sample Position")
    sample1, sample2 = st.columns([1, 2])  # Fit position choices and manual input together
    sec6["sample_position_choice"] = sample1.selectbox(
        "Sample Position",
        ["In focus", "Behind focus", "Manual"],
        key="sample_position_choice"
    )
    if sec6["sample_position_choice"] == "Manual":
        sec6["sample_position_custom"] = sample2.text_input("Specify sample position manually")

    # --- Spatial Beam Shape + Ellipticity (from CSV) ---
    st.markdown("#### Spatial Beam Shape and Ellipticity")
    ell1, ell2 = st.columns([1, 1])  # Optimize file upload and text input
    #sec6["spatial_beam_desc"] = ell1.text_input("Beam Shape Description")
    sec6["spatial_beam_desc"] = ell1.text_input("Beam Shape Description", value=sec6.get("spatial_beam_desc", ""))
    sec6["beam_csv"] = ell2.file_uploader(
        "Upload Beam Profile CSV",
        type=["csv"],
        help="Major/Minor widths will be calculated from this file."
    )
    # --- Images (Upload Multiple Images for Template Display) ---
    st.markdown("#### Test Setup Images")
    _img_labels = [
        "a) 3D beam profile",
        "b) 2D beam profile sigma",
        "c) Gaussian profile fit 1/e²",
        "d) Pointing stability",
    ]
    ic1, ic2, ic3, ic4 = st.columns(4)
    uploaded_images_tab3 = [
        col.file_uploader(label, type=["png", "jpg"], key=f"sec6_img_{i}")
        for i, (col, label) in enumerate(zip([ic1, ic2, ic3, ic4], _img_labels))
    ]

    _prev_images = list(sec6.get("uploaded_images", []))
    sec6["uploaded_images"] = []
    for i, img in enumerate(uploaded_images_tab3):
        if img:
            file_extension = img.name.split('.')[-1]
            unique_filename = f"{uuid.uuid4().hex}_{i}.{file_extension}"
            upload_path = UPLOAD_FOLDER / unique_filename
            with open(upload_path, "wb") as f:
                f.write(img.read())
            sec6["uploaded_images"].append(str(upload_path))
    if not sec6["uploaded_images"] and _prev_images:
        sec6["uploaded_images"] = _prev_images
    _n_existing = sum(1 for p in sec6.get("uploaded_images", []) if Path(p).exists())
    if _n_existing:
        st.caption(f"✓ {_n_existing} test setup image(s) already uploaded — re-upload to replace")

    if sec6["beam_csv"]:
        try:
            from services.calculations import process_beam_csv

            csv_results = process_beam_csv(sec6["beam_csv"])
            sec6["ellipticity"] = csv_results["ellipticity"]
            sec6["measured_surface"] = csv_results["measured_surface"]
            sec6["gaussian_fit_diameter"] = csv_results["gaussian_fit_diameter"]
        except ValueError as e:
            st.error(f"CSV processing failed: {e}")
    if not sec6["beam_csv"] and sec6.get("gaussian_fit_diameter"):
        st.caption("✓ Beam profile CSV already processed — re-upload to update")
        
    _default_caption = "Spatial profile in target plane: a) 3D beam profile, b) 2D beam profile sigma, c) Gaussian profile fit 1/e² and d) pointing stability."
    sec6["image_captions"] = st.text_area(
        "Set captions",
        value=sec6.get("image_captions", _default_caption),
        height=80,
    )
with tab4:
    st.subheader("Error Budget")
    form = st.session_state["form"]
    sec7 = form["sections_data"].setdefault("error_budget", {})

    # ---- First Row ----
    c1, c2, c3, c4, c5, c6 = st.columns([0.5, 1.5, 0.5, 1.5, 0.5, 1.5])  # Ensure sign columns are smaller

    # Column 1 and 2: First Input (Pulse-to-pulse energy stability)
    sec7["pulse_to_pulse_energy_sign"] = c1.selectbox(
        "Sign",
        options=["+", "-", "±", ">", "<", "≥", "≤"],
        index=2,  # Default to "±"
        key="pulse_to_pulse_energy_sign_dropdown",
    
    )
    sec7["pulse_to_pulse_energy"] = c2.number_input(
        "Pulse-to-pulse energy stability [%]",
        value=5,
        key="pulse_to_pulse_energy_number_input",
    )

    # Column 3 and 4: Second Input (Pulse-to-pulse spatial profile stability)
    sec7["pulse_to_pulse_spatial_sign"] = c3.selectbox(
        "Sign",
        options=["+", "-", "±", ">", "<", "≥", "≤"],
        index=2,  # Default to "±"
        key="pulse_to_pulse_spatial_sign_dropdown",
   
    )
    sec7["pulse_to_pulse_spatial"] = c4.number_input(
        "Pulse-to-pulse spatial profile stability [%]",
        value=12,
        key="pulse_to_pulse_spatial_number_input",
    )

    # Column 5 and 6: Third Input (Pulse-to-pulse temporal stability)
    sec7["pulse_to_pulse_temporal_sign"] = c5.selectbox(
        "Sign",
        options=["+", "-", "±", ">", "<", "≥", "≤"],
        index=4,  # Default to "<"
        key="pulse_to_pulse_temporal_sign_dropdown",
   
    )
    sec7["pulse_to_pulse_temporal"] = c6.number_input(
        "Pulse-to-pulse temporal stability [%]",
        value=1,
        key="pulse_to_pulse_temporal_number_input",
    )

    st.markdown("---")

    CAMERA_PIXELS = {
        "LUCID PHX120S-MC":   3.45,
        "iDS UI-5280CP-M-GL": 3.45,
        "iDS UI-5370CP-M-GL": 5.5,
        "WinCamD-IR-BB":      17.0,
    }

    col_cam, col_ec = st.columns(2)
    with col_cam:
        camera = st.selectbox(
            "Camera",
            options=list(CAMERA_PIXELS.keys()),
            index=None,
            placeholder="Select camera used...",
            key="eb_camera",
        )
    sec7["camera"] = camera
    with col_ec:
        ec_file = st.file_uploader("Upload EC.txt", type=["txt"], key="eb_ec_txt")

    if ec_file:
        try:
            import pandas as _pd
            ec_df = _pd.read_csv(ec_file, sep=None, engine="python", header=None)
            ec_df.columns = ["attenuator", "energy", "error"]
            ec_df = ec_df[ec_df["attenuator"] != 0].dropna()
            sec7["energy_monitor_accuracy"]         = round(float(ec_df["error"].abs().max()), 4)
            sec7["energy_monitor_calibration"]      = round(float((ec_df["error"].abs() / ec_df["energy"]).max() * 100), 2)
            sec7["energy_monitor_calibration_sign"] = "±"
        except Exception as e:
            st.error(f"EC.txt error: {e}")
    if not ec_file and sec7.get("energy_monitor_accuracy") is not None:
        st.caption("✓ EC.txt already processed — re-upload to update")

    if camera:
        import math as _math
        pixel_size                     = CAMERA_PIXELS[camera]
        sec7["beam_profiler_accuracy"] = pixel_size
        gauss_diam = form["sections_data"].get("test_procedure", {}).get("gaussian_fit_diameter")
        if gauss_diam:
            sec7["beam_profiler_calibration"] = round(pixel_size / _math.sqrt(30) / gauss_diam * 100, 2)
        else:
            sec7["beam_profiler_calibration"] = None
            st.warning("Beam profiler calibration needs beam profile CSV uploaded in Section 6.")


    proc_selected = form["sections_data"].get("results", {}).get("procedure", "")
    if proc_selected in ["1-on-1", "S-on-1 Fixed"]:
        st.markdown("---")
        _fe = sec7.get("fitting_error")
        if _fe is not None:
            st.info(f"Fitting error: ± {_fe} %  *(from damage probability linear fit)*")
        else:
            st.caption("Fitting error will be calculated automatically when Excel is processed below.")

    st.subheader("Test Results")
    form    = st.session_state["form"]
    results = form["sections_data"].setdefault("results", {})

    test_type = st.selectbox(
        "Test type",
        ["1-on-1", "S-on-1 Fixed", "S-on-1 Range", "R-on-1", "Raster Scan"],
        index=None,
        placeholder="Select test type...",
        key="results_test_type"
    )
    results["procedure"] = test_type

    if test_type in ["1-on-1", "S-on-1 Fixed", "S-on-1 Range"]:

        # Row 1 — Sample shape/dim + Aperture shape/dim
        c1, c2, c3, c4 = st.columns(4)
        sample_shape = c1.selectbox("Sample shape", ["Round", "Rectangular", "Other"], key="res_sample_shape")
        results["sample_shape"] = sample_shape
        if sample_shape == "Round":
            results["sample_dim"] = c2.text_input("Sample diameter", placeholder="e.g. 25 mm", key="res_sample_dim")
        else:
            results["sample_dim"] = c2.text_input("Sample dimensions", placeholder="e.g. 25×25 mm²", key="res_sample_dim")

        ap_shape = c3.selectbox("Aperture shape", ["Round", "Rectangular"], key="res_ap_shape")
        results["aperture_shape"] = ap_shape
        if ap_shape == "Round":
            results["aperture_dim"] = c4.text_input("Aperture diameter", placeholder="e.g. 5 mm", key="res_ap_dim")
        else:
            results["aperture_dim"] = c4.text_input("Aperture dimensions", placeholder="e.g. 5×5 mm²", key="res_ap_dim")

        # Row 2 — Site info + Matrix
        c1, c2, c3, c4 = st.columns(4)
        results["site_size"]   = c1.text_input("Test site size",         placeholder="e.g. 1.05 mm", key="res_site_size")
        n_sites                = c2.number_input("Number of test sites",  min_value=1, step=1, key="res_n_sites")
        results["n_sites"]     = int(n_sites)
        results["site_dist"]   = c3.text_input("Site distance (c-to-c)", placeholder="e.g. 3.0 mm", key="res_site_dist")
        results["matrix_type"] = c4.selectbox("Test site matrix", ["Circular", "Rectangular"], key="res_matrix")

        # Row 3 — Detection + Pulses
        c1, c2, c3, c4 = st.columns(4)
        online_opts = ["Online camera", "Online He-Ne imaging system", "Online He-Ne scattering system", "Other"]
        results["online_detection"]  = c1.selectbox("Online detection",  online_opts,                            key="res_online")
        results["offline_detection"] = c2.selectbox("Offline detection", ["Laser scanning microscope", "Other"], key="res_offline")
        results["pulses_per_site"] = c3.text_input("Number of pulses per site", placeholder="e.g. 1 or 1-1000", key="res_pps")
        results["pulses_total"]    = c4.text_input("Pulses total",               placeholder="e.g. 100",         key="res_pulses_total")
        if results["online_detection"] == "Other":
            results["online_detection_custom"] = st.text_input("Specify online detection", key="res_online_custom")
        if results["offline_detection"] == "Other":
            results["offline_detection_custom"] = st.text_input("Specify offline detection", key="res_offline_custom")

        st.markdown("---")

        # === FILE UPLOADS ===
        c_txt, c_excel = st.columns(2)
        with c_txt:
            txt_file = st.file_uploader("Upload mask TXT (LabView)", type=["txt"], key="res_txt")
        with c_excel:
            excel_file = st.file_uploader("Upload Results Excel (.xlsx)", type=["xlsx"], key="res_excel")

        # === COMMENTS ===
        cc1, cc2, cc3 = st.columns(3)
        results["mask1_comment"] = cc1.text_input("Comment (mask 1)", key="res_mask1_comment")
        results["mask2_comment"] = cc2.text_input("Comment (mask 2)", key="res_mask2_comment")
        prob_label = "Comment (characteristic curve)" if test_type == "S-on-1 Range" else "Comment (damage probability)"
        results["prob_comment"] = cc3.text_input(prob_label, key="res_prob_comment")

        # === MASK 1 ===
        if txt_file and not (results.get("mask1_path") and Path(results["mask1_path"]).exists() and st.session_state.get("_mask_params") is not None):
            try:
                from services.calculations import parse_labview_mask, draw_mask_from_labview
                import os as _os
                with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
                    tmp.write(txt_file.read())
                    tmp_path = tmp.name
                params, df_mask = parse_labview_mask(tmp_path)
                _os.unlink(tmp_path)
                mask1_fig = draw_mask_from_labview(df_mask, params)
                _m1_path = str(UPLOAD_FOLDER / "result_mask1.png")
                mask1_fig.savefig(_m1_path, dpi=150, bbox_inches="tight")
                plt.close(mask1_fig)
                results["mask1_path"] = _m1_path
                st.session_state["_mask_params"] = params
                st.session_state["_mask_df"]     = df_mask
                st.success("Mask file processed.")
            except Exception as e:
                st.error(f"Mask error: {e}")
        if results.get("mask1_path") and Path(results["mask1_path"]).exists():
            st.caption("✓ Mask 1 already processed — re-upload to update")

        # === EXCEL ===
        if excel_file and not (results.get("prob_path") and Path(results["prob_path"]).exists()):
            excel_bytes = excel_file.read()
            try:
                from services.calculations import (
                    parse_measurement_data, draw_mask_from_labview,
                    parse_fluence_probability, plot_damage_probability,
                    parse_son1_range_data, plot_son1_range,
                )

                # Mask 2 (same for all test types — uses Measurement sheet)
                if st.session_state.get("_mask_df") is not None:
                    meas_df   = parse_measurement_data(io.BytesIO(excel_bytes))
                    status    = dict(zip(meas_df.spot_id, meas_df.status))
                    txt_ids   = set(st.session_state["_mask_df"]["spot_id"].astype(int))
                    excel_ids = set(meas_df["spot_id"].astype(int))
                    matched   = txt_ids & excel_ids
                    only_excel = excel_ids - txt_ids
                    only_txt   = txt_ids  - excel_ids
                    if only_excel or only_txt:
                        st.warning(
                            f"Spot ID mismatch — {len(matched)} matched, "
                            f"{len(only_excel)} Excel IDs not in mask, "
                            f"{len(only_txt)} mask IDs not in Excel."
                        )
                    else:
                        st.success(f"All {len(matched)} spot IDs matched.")
                    mask2_fig = draw_mask_from_labview(
                        st.session_state["_mask_df"],
                        st.session_state["_mask_params"],
                        status=status
                    )
                    _m2_path = str(UPLOAD_FOLDER / "result_mask2.png")
                    mask2_fig.savefig(_m2_path, dpi=150, bbox_inches="tight")
                    plt.close(mask2_fig)
                    results["mask2_path"] = _m2_path

                # Plot — branch by test type
                if test_type in ["1-on-1", "S-on-1 Fixed"]:
                    fluences, probs = parse_fluence_probability(io.BytesIO(excel_bytes))
                    fig3, lidt_vals = plot_damage_probability(fluences, probs)
                else:  # S-on-1 Range
                    son1_df         = parse_son1_range_data(io.BytesIO(excel_bytes))
                    fig3, lidt_vals = plot_son1_range(son1_df)

                _p_path = str(UPLOAD_FOLDER / "result_prob.png")
                fig3.savefig(_p_path, dpi=150, bbox_inches="tight")
                plt.close(fig3)
                results["prob_path"]   = _p_path
                results["lidt_values"] = lidt_vals
                if test_type in ["1-on-1", "S-on-1 Fixed"] and lidt_vals.get("fitting_error") is not None:
                    sec7["fitting_error"]      = lidt_vals["fitting_error"]
                    sec7["fitting_error_sign"] = "±"
                st.success("Excel processed.")

            except Exception as e:
                st.error(f"Analysis error: {e}")
        if results.get("mask2_path") and Path(results["mask2_path"]).exists():
            st.caption("✓ Mask 2 already processed — re-upload to update")
        if results.get("prob_path") and Path(results["prob_path"]).exists():
            st.caption("✓ Damage probability plot already processed — re-upload to update")

    elif test_type == "R-on-1":

        # Row 1 — Sample + Aperture
        c1, c2, c3, c4 = st.columns(4)
        sample_shape = c1.selectbox("Sample shape", ["Round", "Rectangular", "Other"], key="res_sample_shape_r")
        results["sample_shape"] = sample_shape
        if sample_shape == "Round":
            results["sample_dim"] = c2.text_input("Sample diameter", placeholder="e.g. 50.8 mm", key="res_sample_dim_r")
        else:
            results["sample_dim"] = c2.text_input("Sample dimensions", placeholder="e.g. 25×25 mm²", key="res_sample_dim_r")
        ap_shape = c3.selectbox("Aperture shape", ["Round", "Rectangular"], key="res_ap_shape_r")
        results["aperture_shape"] = ap_shape
        if ap_shape == "Round":
            results["aperture_dim"] = c4.text_input("Aperture diameter", placeholder="e.g. 41 mm", key="res_ap_dim_r")
        else:
            results["aperture_dim"] = c4.text_input("Aperture dimensions", placeholder="e.g. 5×5 mm²", key="res_ap_dim_r")

        # Row 2 — Site info + Matrix
        c1, c2, c3, c4 = st.columns(4)
        results["site_size"]   = c1.text_input("Test site size", placeholder="e.g. 4 mm", key="res_site_size_r")
        n_sites                = c2.number_input("Number of test sites", min_value=1, step=1, key="res_n_sites_r")
        results["n_sites"]     = int(n_sites)
        results["site_dist"]   = c3.text_input("Site distance (c-to-c)", placeholder="e.g. 4 mm", key="res_site_dist_r")
        results["matrix_type"] = c4.selectbox("Test site matrix", ["Circular", "Rectangular", "Hexagonal, close packed"], key="res_matrix_r")

        # Row 3 — Detection + pulse params
        c1, c2, c3, c4 = st.columns(4)
        online_opts = ["Online camera", "Online He-Ne imaging system", "Online He-Ne scattering system", "Other"]
        results["online_detection"]   = c1.selectbox("Online detection",  online_opts, key="res_online_r")
        results["offline_detection"]  = c2.selectbox("Offline detection", ["Laser scanning microscope", "Other"], key="res_offline_r")
        results["pulses_per_fluence"] = c3.text_input("Pulses per fluence", placeholder="e.g. 500", key="res_ppf")
        results["pulses_total"]       = c4.text_input("Pulses total", placeholder="e.g. up to 38000", key="res_pulses_total_r")
        if results["online_detection"] == "Other":
            results["online_detection_custom"] = st.text_input("Specify online detection", key="res_online_custom_r")
        if results["offline_detection"] == "Other":
            results["offline_detection_custom"] = st.text_input("Specify offline detection", key="res_offline_custom_r")

        # Row 4 — Fluence steps
        c1, c2 = st.columns(2)
        results["fluence_step"] = st.text_input("Fluence step", placeholder="e.g. 1 J/cm²", key="res_fluence_step")

        st.markdown("---")

        # Mask TXT + Excel side by side
        c_txt, c_xl = st.columns(2)
        with c_txt:
            txt_file_r = st.file_uploader("Upload mask TXT (LabView)", type=["txt"], key="res_txt_r")
        with c_xl:
            ron1_excel = st.file_uploader("Upload R-on-1 Excel (Measurement sheet)", type=["xlsx", "xls"], key="res_ron1_excel")

        # Comments
        cc1, cc2, cc3 = st.columns(3)
        results["mask1_comment"] = cc1.text_input("Comment (mask 1)", key="res_mask1_comment_r")
        results["mask2_comment"] = cc2.text_input("Comment (mask 2)", key="res_mask2_comment_r")
        results["spots_comment"] = cc3.text_input("Comment (spot plots)", key="res_spots_comment_r")

        # Process mask TXT → mask 1
        if txt_file_r and not (results.get("mask1_path") and Path(results["mask1_path"]).exists() and st.session_state.get("_mask_params_r") is not None):
            try:
                from services.calculations import parse_labview_mask, draw_mask_from_labview
                import os as _os
                with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
                    tmp.write(txt_file_r.read())
                    tmp_path = tmp.name
                params, df_mask = parse_labview_mask(tmp_path)
                _os.unlink(tmp_path)
                mask1_fig = draw_mask_from_labview(df_mask, params)
                _m1_path = str(UPLOAD_FOLDER / "result_mask1.png")
                mask1_fig.savefig(_m1_path, dpi=150, bbox_inches="tight")
                plt.close(mask1_fig)
                results["mask1_path"] = _m1_path
                st.session_state["_mask_params_r"] = params
                st.session_state["_mask_df_r"]     = df_mask
                st.success("Mask file processed.")
            except Exception as e:
                st.error(f"Mask error: {e}")
        if results.get("mask1_path") and Path(results["mask1_path"]).exists():
            st.caption("✓ Mask 1 already processed — re-upload to update")
        # Process R-on-1 Excel
        if ron1_excel and not results.get("spot_plots"):
            try:
                from services.calculations import parse_ron1_measurement, plot_ron1_spot, draw_mask_from_labview

                all_spots = parse_ron1_measurement(io.BytesIO(ron1_excel.read()))

                spot_plots_list, spot_results_list = [], []
                def _sort_key(k):
                    try:
                        return float(str(k).split("-")[0])
                    except Exception:
                        return 0.0

                for spot_no in sorted(all_spots.keys(), key=_sort_key):
                    spot      = all_spots[spot_no]
                    steps     = spot["steps"]
                    dmg_f     = spot["damage_fluence"]
                    prefix    = "spots" if "-" in str(spot_no) else "spot"
                    spot_label = f"{prefix} {spot_no}"

                    spot_results_list.append({"spot": str(spot_no), "damage_fluence": dmg_f})

                    fig_sp, _ = plot_ron1_spot(steps, dmg_f, spot_label)
                    safe_name = str(spot_no).replace("-", "_")
                    sp_path   = str(UPLOAD_FOLDER / f"result_spot_{safe_name}.png")
                    fig_sp.savefig(sp_path, dpi=150, bbox_inches="tight")
                    plt.close(fig_sp)
                    spot_plots_list.append({
                        "path":    sp_path,
                        "caption": f"Sketch of the R-on-1 procedure - {spot_label}",
                    })

                results["spot_plots"]   = spot_plots_list
                results["spot_results"] = spot_results_list

                # Mask 2 colored by damage status
                if st.session_state.get("_mask_df_r") is not None:
                    status_map = {}
                    for r in spot_results_list:
                        try:
                            idx = int(float(str(r["spot"]).split("-")[0])) - 1
                            status_map[idx] = 1 if r["damage_fluence"] is not None else 0
                        except (ValueError, TypeError):
                            pass
                    mask2_fig = draw_mask_from_labview(
                        st.session_state["_mask_df_r"],
                        st.session_state["_mask_params_r"],
                        status=status_map
                    )
                    _m2_path = str(UPLOAD_FOLDER / "result_mask2.png")
                    mask2_fig.savefig(_m2_path, dpi=150, bbox_inches="tight")
                    plt.close(mask2_fig)
                    results["mask2_path"] = _m2_path

                st.success(f"{len(all_spots)} spots loaded.")
            except Exception as e:
                st.error(f"R-on-1 processing error: {e}")
        if results.get("mask2_path") and Path(results["mask2_path"]).exists():
            st.caption("✓ Mask 2 already processed — re-upload to update")
        if results.get("spot_plots"):
            _n = sum(1 for sp in results["spot_plots"] if Path(sp["path"]).exists())
            if _n:
                st.caption(f"✓ {_n} spot plot(s) already processed — re-upload to update")

    elif test_type == "Raster Scan":

        # Row 1 — Sample + Aperture
        c1, c2, c3, c4 = st.columns(4)
        sample_shape = c1.selectbox("Sample shape", ["Round", "Rectangular", "Other"], key="res_sample_shape_rs")
        results["sample_shape"] = sample_shape
        if sample_shape == "Round":
            results["sample_dim"] = c2.text_input("Sample diameter", placeholder="e.g. 25 mm", key="res_sample_dim_rs")
        else:
            results["sample_dim"] = c2.text_input("Sample dimensions", placeholder="e.g. 25×25 mm²", key="res_sample_dim_rs")
        ap_shape = c3.selectbox("Aperture shape", ["Round", "Rectangular"], key="res_ap_shape_rs")
        results["aperture_shape"] = ap_shape
        if ap_shape == "Round":
            results["aperture_dim"] = c4.text_input("Aperture diameter", placeholder="e.g. 5 mm", key="res_ap_dim_rs")
        else:
            results["aperture_dim"] = c4.text_input("Aperture dimensions", placeholder="e.g. 5×5 mm²", key="res_ap_dim_rs")

        # Row 2 — Site info + Matrix
        c1, c2, c3, c4 = st.columns(4)
        results["site_size"]   = c1.text_input("Test site size",        placeholder="e.g. 1.05 mm", key="res_site_size_rs")
        n_sites                = c2.number_input("Number of test sites", min_value=1, step=1,         key="res_n_sites_rs")
        results["n_sites"]     = int(n_sites)
        results["site_dist"]   = c3.text_input("Site distance (c-to-c)", placeholder="e.g. 0.4 mm", key="res_site_dist_rs")
        results["matrix_type"] = c4.selectbox("Test site matrix", ["Rectangular", "Circular", "Hexagonal, close packed"], key="res_matrix_rs")

        # Row 3 — Detection + Pulses
        c1, c2, c3, c4 = st.columns(4)
        online_opts = ["Online camera", "Online He-Ne imaging system", "Online He-Ne scattering system", "Other"]
        results["online_detection"]  = c1.selectbox("Online detection",  online_opts,                             key="res_online_rs")
        results["offline_detection"] = c2.selectbox("Offline detection", ["Laser scanning microscope", "Other"],  key="res_offline_rs")
        results["pulses_per_site"]   = c3.text_input("Pulses per site", placeholder="e.g. 1",     key="res_pps_rs")
        results["pulses_total"]      = c4.text_input("Pulses total",    placeholder="e.g. 3375",  key="res_pulses_total_rs")
        if results["online_detection"] == "Other":
            results["online_detection_custom"] = st.text_input("Specify online detection",  key="res_online_custom_rs")
        if results["offline_detection"] == "Other":
            results["offline_detection_custom"] = st.text_input("Specify offline detection", key="res_offline_custom_rs")

        # Row 4 — Site spacing for map display
        c1, _ = st.columns(2)
        #results["site_spacing_mm"] = c1.number_input(
        #    "Site spacing (mm)", min_value=0.01, value=1.0, step=0.01, key="res_site_spacing_rs"
        #)
        spacing = 1.0

        st.markdown("---")

        # File uploads
        c1, c2 = st.columns(2)
        with c1:
            raster_grid_file = st.file_uploader("Upload damage grid TXT (tab-separated)", type=["txt"], key="res_raster_grid")
        with c2:
            raster_evo_file  = st.file_uploader("Upload damage evolution TXT (fluence | density)", type=["txt"], key="res_raster_evo")

        cc1, cc2 = st.columns(2)
        results["raster_map_comment"]     = cc1.text_input("Comment (damage map)",              key="res_raster_map_comment")
        results["raster_density_comment"] = cc2.text_input("Comment (density/probability plot)", key="res_raster_density_comment")

        if raster_grid_file and raster_evo_file and not (results.get("raster_map_path") and Path(results["raster_map_path"]).exists() and results.get("raster_density_path") and Path(results["raster_density_path"]).exists()):
            try:
                from services.calculations import (
                    parse_raster_measurement, parse_raster_evolution,
                    compute_raster_lidt, plot_raster_map, plot_raster_density,
                )
                import os as _os

                with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
                    tmp.write(raster_grid_file.read())
                    grid_tmp = tmp.name
                with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
                    tmp.write(raster_evo_file.read())
                    evo_tmp = tmp.name

                parsed    = parse_raster_measurement(grid_tmp)
                evolution = parse_raster_evolution(evo_tmp)
                _os.unlink(grid_tmp)
                _os.unlink(evo_tmp)

                spacing   = results.get("site_spacing_mm", 1.0)
                sample_id = form.get("sample", "")

                lidt_0, lidt_5, full_prob = compute_raster_lidt(
                    evolution, parsed["fluence_steps"], parsed["damage_probability"],
                    parsed["first_damage"]
                )
                fig_map  = plot_raster_map(parsed["grid"], site_spacing_mm=spacing, sample_id=sample_id)
                map_path = str(UPLOAD_FOLDER / "result_raster_map.png")
                fig_map.savefig(map_path, dpi=150, bbox_inches="tight")
                plt.close(fig_map)

                fig_den  = plot_raster_density(
                    evolution["fluences"], evolution["densities"], full_prob, sample_id=sample_id
                )
                den_path = str(UPLOAD_FOLDER / "result_raster_density.png")
                fig_den.savefig(den_path, dpi=150, bbox_inches="tight")
                plt.close(fig_den)

                results["raster_map_path"]     = map_path
                results["raster_density_path"] = den_path
                results["lidt_values"] = {
                    "lidt_0":       lidt_0,
                    "lidt_5":       lidt_5,
                    "first_damage": parsed["first_damage"],
                    "show_50_pct":  False,
                }

                msg = f"Raster scan processed. First damage: {parsed['first_damage']:.2f} J/cm²,  0% LIDT: {lidt_0:.2f} J/cm²"
                if lidt_5:
                    msg += f",  5% LIDT: {lidt_5:.2f} J/cm²"
                st.success(msg)

            except Exception as e:
                import traceback
                st.error(f"Raster scan processing error: {e}")
                st.code(traceback.format_exc())
        if results.get("raster_map_path") and Path(results["raster_map_path"]).exists():
            st.caption("✓ Damage map already processed — re-upload to update")
        if results.get("raster_density_path") and Path(results["raster_density_path"]).exists():
            st.caption("✓ Density/probability plot already processed — re-upload to update")

    elif test_type is not None:
        st.info(f"{test_type} — coming soon.")
with tab5:
    st.subheader("Annex")

    form = st.session_state["form"]

    annex = form.setdefault("annex", {})
    annex.setdefault("items", [])
    annex.setdefault("comments", "")

    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

    # ---------------- Add Annex Button ----------------
    if st.button("＋ Add annex item", use_container_width=False):
        annex["items"].append({
            "id": uuid.uuid4().hex,
            "file": None,
            "caption": ""
        })
        st.rerun()

    st.markdown("---")

    # ---------------- Annex Items ----------------
    for i, item in enumerate(annex["items"], start=1):
        uid = item["id"]

        st.markdown(f"##### Annex {i}")

        col1, col2 = st.columns([2, 3])

        with col1:
            upload = st.file_uploader(
                "Upload file",
                type=["png", "jpg", "jpeg"],
                key=f"annex_upload_{uid}"
            )
            if upload:
                ext = upload.name.split(".")[-1]
                filename = f"{uuid.uuid4().hex}.{ext}"
                path = UPLOAD_FOLDER / filename

                with open(path, "wb") as f:
                    f.write(upload.read())

                item["file"] = str(path)
            if not upload and item.get("file") and Path(item["file"]).exists():
                st.caption("✓ File already uploaded — re-upload to replace")

        with col2:
            item["caption"] = st.text_input(
                "Caption",
                value=item.get("caption", ""),
                key=f"annex_caption_{uid}"
            )
            item["notes"] = st.text_input(
                "Comment",
                value=item.get("notes", ""),
                key=f"annex_notes_{uid}"
            )

        # Remove button
        if st.button(
            "Remove annex",
            key=f"annex_remove_{uid}",
            use_container_width=False
        ):
            annex["items"] = [
                x for x in annex["items"] if x["id"] != uid
            ]
            st.rerun()

        #st.markdown("---")


with tab6:
    st.subheader("Generate")
    form = st.session_state["form"]

    col_draft, col_final = st.columns(2)

    # ── Save as Draft ───────────────────────────────────────────────────────
    with col_draft:
        st.markdown("#### Save as Draft")
        current_draft_id = st.session_state.get("current_draft_id")
        if current_draft_id:
            new_name = st.text_input("Rename draft (optional)", placeholder="Leave blank to keep current name", key="gen_draft_name")
            if st.button("Update Draft", use_container_width=True):
                update_draft(current_draft_id, form_data=form, name=new_name.strip() or None)
                st.success("Draft updated.")
        else:
            draft_name = st.text_input("Draft name", placeholder="e.g. Sample S5 – 1030 nm", key="gen_draft_name")
            if st.button("Save as Draft", use_container_width=True):
                if not draft_name.strip():
                    st.warning("Please enter a draft name.")
                else:
                    draft_id = save_draft(
                        name=draft_name.strip(),
                        user_id=st.session_state["user"]["id"],
                        form_data=form,
                    )
                    st.session_state["current_draft_id"] = draft_id
                    st.success(f"Draft '{draft_name}' saved.")

    # ── Generate Final ──────────────────────────────────────────────────────
    with col_final:
        st.markdown("#### Generate Final Report")
        st.write("")  # align button with draft section
        if st.button("Generate Final", type="primary", use_container_width=True):
            try:
                OUT_DIR.mkdir(parents=True, exist_ok=True)
                report_number      = next_report_number()
                _sample_id = form.get("sample", "").strip()
                if _sample_id:
                    report_number = f"{report_number}-{_sample_id}"
                form["report_no"]  = report_number
                form["issue_date"] = date.today().strftime("%d %B %Y")

                ctx_final = generate_context(
                    form_data=form,
                    laser_presets=LASER_PRESETS,
                    sections_data=form.get("sections_data", {}),
                    report_no=report_number,
                    issue_date=form["issue_date"],
                )
                generate_report(ctx_final, output_path=str(OUT_PDF))
                pdf_bytes = OUT_PDF.read_bytes()

                assigned = save_final(
                    user_id=st.session_state["user"]["id"],
                    form_data=form,
                    pdf_bytes=pdf_bytes,
                    report_number=report_number,
                )
                st.success(f"Final report published: **{assigned}**")
            except Exception as e:
                import traceback
                st.error(f"Generation error: {e}")
                st.code(traceback.format_exc())

    st.markdown("---")

    # ── Published Reports ───────────────────────────────────────────────────
    st.markdown("#### Published Reports")
    finals = list_finals()
    if not finals:
        st.info("No final reports published yet.")
    else:
        for f_doc in finals:
            c_info, c_dl = st.columns([3, 1])
            c_info.markdown(
                f"**{f_doc['report_number']}** &nbsp;·&nbsp; {f_doc['created_by']} &nbsp;·&nbsp; {f_doc['created_at'][:10]}"
            )
            pdf_bytes, rep_no = get_final_pdf(f_doc["id"])
            if pdf_bytes:
                c_dl.download_button(
                    "Download",
                    data=pdf_bytes,
                    file_name=f"{rep_no}.pdf",
                    mime="application/pdf",
                    key=f"dl_{f_doc['id']}",
                )