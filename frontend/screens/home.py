import httpx
import streamlit as st

from frontend.analysis.api import BACKEND_URL

st.title("GraphRAG Lab")
st.markdown(
    "An interactive workspace for comparing retrieval strategies over one engineering-operations "
    "corpus. Start with **Data Analysis** to see what the retrievers will search."
)

try:
    health = httpx.get(f"{BACKEND_URL}/health", timeout=3).json()
    st.success(f"Backend connected · dataset: {health['dataset_version']}")
except httpx.HTTPError:
    st.error(f"Backend not reachable at {BACKEND_URL}")

st.page_link("screens/data_analysis.py", label="Open Data Analysis", icon=":material/query_stats:")
st.page_link("screens/playground.py", label="Open Playground", icon=":material/manage_search:")
