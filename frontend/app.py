import os

import httpx
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="GraphRAG Lab", layout="wide")
st.title("GraphRAG Lab")

try:
    health = httpx.get(f"{BACKEND_URL}/health", timeout=3).json()
    st.success(f"Backend connected · dataset: {health['dataset_version']}")
except httpx.HTTPError:
    st.error(f"Backend not reachable at {BACKEND_URL}")
