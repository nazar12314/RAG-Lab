import sys
from pathlib import Path

# `streamlit run frontend/app.py` only puts frontend/ on sys.path; screens import `frontend.*`.
# Screens live outside a `pages/` folder so Streamlit's legacy multipage mode never bypasses
# this entry point.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from frontend import layout  # noqa: E402

st.set_page_config(page_title="GraphRAG Lab", layout="wide")
layout.setup()

navigation = st.navigation(
    [
        st.Page("screens/home.py", title="Home", icon=":material/home:", default=True),
        st.Page("screens/data_analysis.py", title="Data Analysis", icon=":material/query_stats:"),
    ],
    position="top",
)
navigation.run()
