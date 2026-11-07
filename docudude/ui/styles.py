"""Global CSS. Colours are defined once as tokens and reused everywhere."""

PAGE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
  --ink: #14283a;
  --muted: #5b6e7e;
  --line: #e2e8ee;
  --brand: #0f766e;
  --brand-dark: #0b5c56;
  --brand-soft: #e6f3f1;
  --surface: #ffffff;
  --page: #f5f7f9;
  --warn-soft: #fff4d6;
  --warn-ink: #7a5600;
  --radius: 12px;
}

html, body, .stApp, [class*="css"] {
  font-family: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif;
}
html, body { overflow-x: hidden; }
.stApp { background: var(--page); color: var(--ink); }

/* Hide Streamlit chrome so the app reads as a normal website */
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stHeader"], [data-testid="stSidebar"],
[data-testid="collapsedControl"] { display: none !important; }

.block-container {
  max-width: 1180px;
  padding: 0 1.25rem 5rem !important;
}

/* ---------- Navigation ---------- */
.st-key-navbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(245,247,249,.96); backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--line);
  padding: .4rem 0; margin-bottom: .5rem;
}
.st-key-navbar [data-testid="stHorizontalBlock"] { align-items: center; flex-wrap: nowrap !important; }
.st-key-navbar [data-testid="stColumn"] { min-width: 0 !important; }
.brand { display: flex; align-items: center; gap: .6rem; }
.brand-name { font-weight: 800; font-size: 1.15rem; color: var(--ink); line-height: 1.1; }
.brand-tag { font-size: .75rem; color: var(--muted); }
[class*="st-key-nav_"] button {
  width: 100%; min-height: 38px; border-radius: 9px; white-space: nowrap; font-weight: 600;
}
[class*="st-key-nav_"] button:not([kind="primary"]) {
  color: var(--muted); background: transparent; border-color: transparent;
}
[class*="st-key-nav_"] button:not([kind="primary"]):hover {
  color: var(--brand-dark); background: var(--brand-soft); border-color: transparent;
}

/* ---------- Headings ---------- */
.hero { padding: 3.2rem 0 2rem; max-width: 760px; }
.kicker { margin: 0 0 .6rem; color: var(--brand); font-size: .76rem; font-weight: 800;
          letter-spacing: .14em; text-transform: uppercase; }
.hero h1 { font-size: 2.8rem; line-height: 1.1; font-weight: 800; letter-spacing: -.025em;
           color: var(--ink); margin: 0 0 1rem; padding: 0; }
.hero p { font-size: 1.12rem; line-height: 1.65; color: var(--muted); margin: 0; max-width: 640px; }
.page-head { padding: 1.6rem 0 1rem; }
.page-head h2 { font-size: 1.85rem; font-weight: 800; letter-spacing: -.02em; margin: 0 0 .35rem; padding: 0; color: var(--ink); }
.page-head p { margin: 0; color: var(--muted); font-size: 1rem; max-width: 700px; line-height: 1.6; }
.section-label { display: flex; align-items: center; gap: .55rem; font-weight: 700;
                 font-size: 1rem; color: var(--ink); margin: 0 0 .4rem; }
.section-label .num { display: inline-grid; place-items: center; width: 24px; height: 24px;
                      border-radius: 50%; background: var(--brand-soft); color: var(--brand-dark);
                      font-size: .8rem; font-weight: 800; }
.section-title { font-size: 1.4rem; font-weight: 800; letter-spacing: -.015em; margin: 2.4rem 0 1rem; }

/* ---------- Cards / widgets ---------- */
[data-testid="stVerticalBlockBorderWrapper"] {
  border-radius: var(--radius); border-color: var(--line); background: var(--surface);
  box-shadow: 0 1px 2px rgba(20,40,58,.04);
}
[data-testid="stMetric"] {
  background: var(--surface); padding: .8rem 1rem;
  border: 1px solid var(--line); border-radius: var(--radius);
}
[data-testid="stMetricLabel"] p { color: var(--muted); font-size: .82rem; }
[data-testid="stFileUploader"] section {
  background: #fbfcfd; border: 1.5px dashed #9bb7bf; border-radius: var(--radius);
}
[data-testid="stExpander"] details { border-radius: var(--radius); border-color: var(--line); }
.stButton > button, .stDownloadButton > button { border-radius: 8px; font-weight: 600; }
.stButton > button[kind="primary"] { background: var(--brand); border-color: var(--brand); }
.stButton > button[kind="primary"]:hover { background: var(--brand-dark); border-color: var(--brand-dark); }
.stTextArea textarea { font-family: 'JetBrains Mono', Consolas, 'Courier New', monospace;
                       font-size: .86rem; line-height: 1.5; }

.step { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
        padding: 1.15rem 1.25rem; height: 100%; }
.step h4 { margin: 0 0 .35rem; padding: 0; font-size: 1rem; color: var(--ink); }
.step p { margin: 0; color: var(--muted); font-size: .93rem; line-height: 1.55; }
.step .num { display: inline-grid; place-items: center; width: 28px; height: 28px; border-radius: 50%;
             background: var(--brand-soft); color: var(--brand-dark); font-weight: 700;
             font-size: .85rem; margin-bottom: .65rem; }
.notice { margin-top: 1rem; padding: 1rem 1.2rem; border-radius: var(--radius);
          background: var(--brand-soft); border: 1px solid #cfe5e2; color: #25494a;
          line-height: 1.6; font-size: .9rem; }

/* ---------- Results ---------- */
.doc-head { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem .75rem; }
.doc-name { font-weight: 700; font-size: 1.08rem; color: var(--ink); word-break: break-all; }
.badge { display: inline-block; padding: .14rem .55rem; border-radius: 999px;
         font-size: .75rem; font-weight: 700; white-space: nowrap; }
.badge-good { background: #dcf3e6; color: #17603b; }
.badge-fair { background: var(--warn-soft); color: var(--warn-ink); }
.badge-poor { background: #fde2e1; color: #8f1d1a; }
.badge-neutral { background: #e9eef2; color: #3f5263; }
.review-text { background: #fbfcfd; border: 1px solid var(--line); border-radius: 8px;
               padding: .9rem 1rem; max-height: 520px; overflow-y: auto;
               font-family: 'JetBrains Mono', Consolas, monospace; font-size: .86rem;
               line-height: 1.7; white-space: pre-wrap; color: var(--ink); }
.review-text mark.low { background: #ffd8a8; color: inherit; border-radius: 3px; padding: 0 2px; }
.review-text mark.very-low { background: #ffb3b0; color: inherit; border-radius: 3px; padding: 0 2px; }
.page-sep { display: block; margin: .6rem 0 .3rem; color: var(--muted); font-weight: 700; }
.summary-box { background: var(--brand-soft); border-left: 4px solid var(--brand);
               padding: .9rem 1.1rem; border-radius: 8px; line-height: 1.65; color: var(--ink); }

/* ---------- Footer ---------- */
.st-key-site_footer {
  margin-top: 4rem; padding: 2rem 2rem 1.1rem;
  background: var(--ink); border-radius: 16px; color: #c4d2dd;
}
.st-key-site_footer p, .st-key-site_footer li, .st-key-site_footer span { color: #c4d2dd; font-size: .9rem; }
.st-key-site_footer .footer-brand { color: #fff; font-weight: 800; font-size: 1.1rem; margin-bottom: .5rem; }
.st-key-site_footer .footer-heading { color: #fff; font-weight: 700; font-size: .93rem; margin-bottom: .6rem; }
.st-key-site_footer ul { list-style: none; margin: 0; padding: 0; }
.st-key-site_footer li { margin: 0 0 .35rem; }
.st-key-site_footer a { color: #8ee0d6; text-decoration: none; font-weight: 600; }
.st-key-site_footer a:hover { text-decoration: underline; }
.st-key-site_footer button {
  background: transparent !important; border: none !important; box-shadow: none !important;
  color: #c4d2dd !important; padding: .1rem 0 !important; min-height: 0 !important;
  justify-content: flex-start;
}
.st-key-site_footer button p { color: inherit !important; font-weight: 500; }
.st-key-site_footer button:hover p { color: #8ee0d6 !important; text-decoration: underline; }
.footer-bottom {
  display: flex; flex-wrap: wrap; justify-content: space-between; gap: .5rem;
  margin-top: 1.2rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,.14);
}
.footer-bottom span { color: #98aab8 !important; font-size: .84rem !important; }

.whatsapp-float {
  position: fixed; right: 22px; bottom: 22px; z-index: 1000; display: inline-flex; align-items: center;
  height: 52px; min-width: 52px; padding: 0 14px; border-radius: 26px; background: #20a86b; color: #fff !important;
  text-decoration: none !important; font-weight: 700; box-shadow: 0 8px 24px rgba(18,101,68,.3);
  transition: background .18s ease, gap .18s ease; gap: 0;
}
.whatsapp-float:hover { background: #168653; gap: 8px; }
.whatsapp-icon { font-size: 1.4rem; line-height: 1; }
.whatsapp-label { max-width: 0; overflow: hidden; white-space: nowrap; opacity: 0;
                  transition: max-width .2s ease, opacity .15s ease; }
.whatsapp-float:hover .whatsapp-label { max-width: 180px; opacity: 1; }

@media (max-width: 760px) {
  .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
  .hero { padding: 2rem 0 1.3rem; }
  .hero h1 { font-size: 2rem; }
  .page-head h2 { font-size: 1.5rem; }
  .brand-text { display: none; }
  [class*="st-key-nav_"] button { padding: .35rem .2rem; font-size: .74rem; min-height: 34px; }
  .st-key-site_footer { padding: 1.4rem 1.1rem 1rem; }
  .whatsapp-float { right: 14px; bottom: 14px; }
}
</style>
"""
