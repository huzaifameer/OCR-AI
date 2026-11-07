"""DocuDude Streamlit entry point. Run with: streamlit run app.py"""

import streamlit as st

from docudude.config import APP_LOGO_PATH, APP_NAME, PAGES
from docudude.ui.layout import render_footer, render_home, render_navbar
from docudude.ui.styles import PAGE_CSS
from docudude.ui.workspace import render_workspace


def main() -> None:
    st.set_page_config(
        page_title=APP_NAME,
        page_icon=str(APP_LOGO_PATH) if APP_LOGO_PATH.exists() else "📄",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.session_state.setdefault("page", "home")
    if st.session_state["page"] not in PAGES:
        st.session_state["page"] = "home"

    st.markdown(PAGE_CSS, unsafe_allow_html=True)
    page = render_navbar()
    if page == "home":
        render_home()
    else:
        render_workspace(page)
    render_footer()


if __name__ == "__main__":
    main()
