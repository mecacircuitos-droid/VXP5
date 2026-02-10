"""CSS skin for the VXP Streamlit simulator.

Goal: mimic the Windows XP / industrial XGA look while keeping the app reliable
across Streamlit versions.
"""

from __future__ import annotations

import base64
from pathlib import Path


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


_ASSET_BG = Path(__file__).parent / "assets" / "backgrounds" / "rugged_tablet.png"
BG_B64 = _b64(_ASSET_BG) if _ASSET_BG.exists() else ""


XP_CSS = (
    r"""
<style>
/* ---- Hide Streamlit chrome ---- */
[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu { display:none !important; }
footer { visibility:hidden; }

/* ---- Disable Streamlit fade/transition artifacts ----
   Streamlit sometimes fades out replaced elements on reruns.
   In our fixed 1024×768 desktop this can look like a 'ghost' copy
   of the previous window that slowly fades out (the issue you reported).
   We disable animations/transitions inside the app view.
*/
div[data-testid="stAppViewContainer"] *,
div[data-testid="stAppViewContainer"] *::before,
div[data-testid="stAppViewContainer"] *::after{
  transition:none !important;
  animation:none !important;
}

/* ---- Global look (Windows XP-ish) ---- */
/* The page background simulates a ruggedized tablet around the 1024×768 screen. */
html, body, [data-testid="stAppViewContainer"]{
  background-color:#111;
  background-image:
    linear-gradient(rgba(0,0,0,0.40), rgba(0,0,0,0.40)),
    url('data:image/png;base64,__BG__');
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  background-attachment: fixed;
  font-family: "Trebuchet MS", Tahoma, "MS Sans Serif", Verdana, Arial, sans-serif;
  font-size:14px;
  font-weight:700;
}

/* Force 4:3 frame (1024×768) */
.block-container{
  display:flex;
  flex-direction:column;
  padding:0 !important;
  max-width:1024px !important;
  margin:0 auto !important;
  height:768px !important;
  min-height:768px !important;
  overflow:hidden !important;
  position:relative !important;
}

/* Main 4:3 frame */
[data-testid="stAppViewContainer"] .block-container{
  background:#c0c0c0;
  border-radius:10px;
  /* no heavy black outline: the rugged background provides the bezel */
  box-shadow:
    0 0 0 2px rgba(255,255,255,0.25),
    0 0 0 6px rgba(0,0,0,0.55),
    8px 8px 0px rgba(0,0,0,0.35);
}

/* ---- Shell (title/menu/status) ---- */
.vxp-shell-titlebar{
  height:26px;
  background: linear-gradient(90deg, #0a246a 0%, #3a6ea5 100%);
  color:#ffffff;
  display:flex;
  align-items:center;
  justify-content:space-between;
  padding:0 8px;
  box-sizing:border-box;
  font-weight:900;
  letter-spacing:0.2px;
}

.vxp-winbtns{ display:flex; gap:4px; }
.vxp-winbtn{
  width:18px; height:16px;
  background:#d4d0c8;
  border-top:2px solid #ffffff;
  border-left:2px solid #ffffff;
  border-right:2px solid #404040;
  border-bottom:2px solid #404040;
  display:flex;
  align-items:center;
  justify-content:center;
  color:#000;
  font-weight:900;
  font-size:12px;
  line-height:12px;
}

.vxp-shell-menubar{
  height:22px;
  background:#d4d0c8;
  border-top:1px solid #ffffff;
  border-bottom:1px solid #808080;
  display:flex;
  align-items:center;
  gap:14px;
  padding:0 8px;
  box-sizing:border-box;
  font-weight:700;
  font-size:13px;
  color:#000;
}
.vxp-shell-menubar span{ padding:2px 4px; }

.vxp-shell-statusbar{
  height:22px;
  background:#d4d0c8;
  border-top:2px solid #808080;
  box-shadow: inset 1px 1px 0px #ffffff;
  display:flex;
  align-items:center;
  justify-content:space-between;
  padding:0 8px;
  box-sizing:border-box;
  font-size:12px;
  font-weight:700;
  position:static;
}

/* Reduce Streamlit element margins so the status bar sits tight at the bottom */
div[data-testid="stAppViewContainer"] .block-container div.element-container{ margin-bottom:0 !important; margin-top:0 !important; }

/* ---- Left smart icon bar ---- */
.vxp-toolbar-img{ width:81px; padding:0; margin:0; }
.vxp-imgbtn{ display:block; margin:6px 0; text-decoration:none; }
.vxp-imgbtn img{ width:81px; height:auto; image-rendering: pixelated; }
.vxp-imgbtn.disabled{ opacity:0.75; pointer-events:none; }

/* ---- Desktop area (single window, no overlapping popups) ---- */
.vxp-desktop-marker{ display:none; }

@supports selector(:has(*)) {
  div[data-testid="stVerticalBlockBorderWrapper"]:has(.vxp-desktop-marker){
    height:720px !important;         /* 768 - 26 - 22 */
    background:#c0c0c0 !important;
    border:0 !important;
    border-top:2px solid #ffffff !important;
    border-left:2px solid #ffffff !important;
    border-right:2px solid #404040 !important;
    border-bottom:2px solid #404040 !important;
    box-shadow:2px 2px 0px #808080 !important;
    overflow:auto !important;
    padding:8px !important;
    box-sizing:border-box !important;
  }
}

@supports not selector(:has(*)) {
  /* Fallback: if :has() is not available, we assume there's only one bordered container. */
  div[data-testid="stVerticalBlockBorderWrapper"]{
    height:720px !important;
    background:#c0c0c0 !important;
    border:0 !important;
    border-top:2px solid #ffffff !important;
    border-left:2px solid #ffffff !important;
    border-right:2px solid #404040 !important;
    border-bottom:2px solid #404040 !important;
    box-shadow:2px 2px 0px #808080 !important;
    overflow:auto !important;
    padding:8px !important;
    box-sizing:border-box !important;
  }
}

/* Common window skin */
.vxp-win-caption{
  height:22px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  padding:0 6px;
  box-sizing:border-box;
  font-weight:900;
  font-size:13px;
  color:#fff;
}
.vxp-win-caption.active{ background: linear-gradient(90deg, #0a246a 0%, #3a6ea5 100%); }
.vxp-win-caption.inactive{ background:#7f7f7f; }

.vxp-closebox{
  width:18px;
  height:16px;
  background:#d4d0c8;
  border-top:2px solid #ffffff;
  border-left:2px solid #ffffff;
  border-right:2px solid #404040;
  border-bottom:2px solid #404040;
  display:flex;
  align-items:center;
  justify-content:center;
  color:#000;
  font-weight:900;
  font-size:12px;
  line-height:12px;
}

/* Reduce default gaps so content feels like a classic dialog */
div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"]{ gap:0.25rem; }
div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"]{ gap:0.5rem; }

/* Optional pad utility */
.vxp-win-pad{ padding:10px 10px 8px 10px; box-sizing:border-box; }

/* ---- Widgets (classic 3D) ---- */
.stButton > button{
  background:#c0c0c0 !important;
  color:#000 !important;
  border-top:2px solid #ffffff !important;
  border-left:2px solid #ffffff !important;
  border-right:2px solid #404040 !important;
  border-bottom:2px solid #404040 !important;
  border-radius:0px !important;
  font-weight:900 !important;
  font-size:18px !important;
  padding:12px 14px !important;
  letter-spacing:0.2px;
}
.stButton > button:active{
  border-top:2px solid #404040 !important;
  border-left:2px solid #404040 !important;
  border-right:2px solid #ffffff !important;
  border-bottom:2px solid #ffffff !important;
}

/* Inputs */
div[data-testid="stNumberInput"] input,
div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] div[role="combobox"]{
  border-radius:0px !important;
  border-top:2px solid #ffffff !important;
  border-left:2px solid #ffffff !important;
  border-right:2px solid #404040 !important;
  border-bottom:2px solid #404040 !important;
  background:#ffffff !important;
  font-weight:700 !important;
}

/* Text areas (reports) */
div[data-testid="stTextArea"] textarea{
  border-radius:0px !important;
  border-top:2px solid #ffffff !important;
  border-left:2px solid #ffffff !important;
  border-right:2px solid #404040 !important;
  border-bottom:2px solid #404040 !important;
  background:#ffffff !important;
  font-family:"Courier New", Consolas, monospace !important;
  font-weight:700 !important;
  font-size:14px !important;
  line-height:1.15 !important;
}

/* Mono text blocks */
.vxp-mono{
  font-family: "Courier New", Consolas, monospace;
  font-size:14px;
  font-weight:700;
  background:#ffffff;
  border-top:2px solid #404040;
  border-left:2px solid #404040;
  border-right:2px solid #ffffff;
  border-bottom:2px solid #ffffff;
  padding:10px;
  white-space:pre;
}

/* Ensure inline spans used for blade color-coding keep fixed-width alignment */
.vxp-mono span{
  font-family: inherit !important;
  white-space: inherit !important;
}

.vxp-label{ font-weight:900; }

</style>
"""
).replace("__BG__", BG_B64)
