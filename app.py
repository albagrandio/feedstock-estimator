import os

import streamlit as st

# Bridge Streamlit Cloud secrets -> environment variables so the existing
# os.getenv(...) calls in src/ work both locally (.env) and on Streamlit
# Community Cloud (where secrets live in st.secrets). Must run BEFORE importing
# the layout, since some modules read env vars at import time.
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k, _v)
except Exception:
    pass

from layout.homepage import estimate_cr_nr  # noqa: E402


def main_page():
    if "show_results" not in st.session_state:
        st.session_state.show_results = False
    estimate_cr_nr()


if __name__ == "__main__":
    main_page()
