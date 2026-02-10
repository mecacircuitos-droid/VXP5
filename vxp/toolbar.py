from pathlib import Path
import base64
import streamlit as st

# Orden igual al original
TOOLBAR_ITEMS = [
    ("disconnect", "vxp_btn_disconnect.png", "disconnect", False),
    ("upload",     "vxp_btn_upload.png",     "upload",     False),
    ("download",   "vxp_btn_download.png",   "download",   False),
    ("viewlog",    "vxp_btn_viewlog.png",    "viewlog",    False),
    ("print_au",   "vxp_btn_print_au.png",   "print_au",   False),
    ("print_pc",   "vxp_btn_print_pc.png",   None,         True),   # disabled
    ("help",       "vxp_btn_help.png",       "help",       False),
    ("exit",       "vxp_btn_exit.png",       "exit",       False),
]

def _b64_png(path: Path) -> str:
    data = path.read_bytes()
    return base64.b64encode(data).decode("ascii")

def get_toolbar_b64() -> dict:
    if "vxp_toolbar_b64" in st.session_state:
        return st.session_state.vxp_toolbar_b64

    base = Path(__file__).parent / "assets" / "toolbar"
    out = {}
    for key, filename, _, _ in TOOLBAR_ITEMS:
        p = base / filename
        if p.exists():
            out[key] = _b64_png(p)
        else:
            out[key] = ""  # si falta el archivo, no rompe
    st.session_state.vxp_toolbar_b64 = out
    return out

def render_toolbar(interactive: bool = False) -> None:
    icons = get_toolbar_b64()
    st.markdown("<div class='vxp-toolbar-img'>", unsafe_allow_html=True)

    for key, _, nav, disabled in TOOLBAR_ITEMS:
        b64 = icons.get(key, "")
        if not b64:
            continue
        img = f"<img src='data:image/png;base64,{b64}'/>"

        # Por defecto se pinta como "solo imagen" (sin navegación)
        if (not interactive) or disabled or (not nav):
            st.markdown(f"<div class='vxp-imgbtn disabled'>{img}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<a class='vxp-imgbtn' href='?nav={nav}'>{img}</a>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
