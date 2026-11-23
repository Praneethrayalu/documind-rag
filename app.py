"""Streamlit entry point. Session-isolated documents, no disk uploads or remote APIs."""
import hashlib

import streamlit as st

from documind.core import HybridIndex, answer_from_evidence, chunk_pages, load_embedder, parse_pdf
from documind.generate import ollama_answer

st.set_page_config(page_title="DocuMind | Evidence first", page_icon="📚", layout="wide")
st.title("DocuMind")
st.caption("LOCAL PDF WORKSPACE · HYBRID SEARCH · PAGE-LEVEL CITATIONS")
st.write("Ask your documents. Inspect the evidence.")

@st.cache_resource
def model():
    return load_embedder()

with st.sidebar:
    st.header("Your documents")
    files = st.file_uploader("Upload text PDFs", type=["pdf"], accept_multiple_files=True)
    st.caption("25 MiB / 300 pages per file. Scanned PDFs need OCR first. Uploads stay in this session's memory.")
    k = st.slider("Evidence chunks", 1, 8, 4)
    answer_mode = st.selectbox("Answer mode", ["Source excerpts (no LLM)", "Local Ollama"])
    local_model = st.text_input("Ollama model", "qwen2.5:1.5b") if answer_mode == "Local Ollama" else ""
    if st.button("Clear documents and answers"):
        st.session_state.clear()
        st.rerun()

if not files:
    st.info("Upload a PDF to begin. Try data/sample/documind-handbook.pdf from the repository.")
    st.subheader("Evidence you can check")
    a, b, c = st.columns(3)
    a.metric("Retrieval", "FAISS + BM25")
    b.metric("Cloud API keys", "None")
    c.metric("Default answers", "Exact excerpts")
    st.stop()

if len(files) > 5 or sum(f.size for f in files) > 50 * 1024 * 1024:
    st.error("Use at most five PDFs and 50 MiB total per session.")
    st.stop()
contents = [(f.name, f.getvalue()) for f in files]
fingerprint = hashlib.sha256(b"".join(name.encode() + hashlib.sha256(data).digest() for name, data in contents)).hexdigest()
if st.session_state.get("fingerprint") != fingerprint:
    st.session_state.pop("last_result", None)
    try:
        with st.spinner("Parsing PDFs and building the local index..."):
            pages, seen_docs = [], set()
            for name, data in contents:
                digest = hashlib.sha256(data).hexdigest()
                if digest not in seen_docs:
                    pages.extend(parse_pdf(data, name))
                    seen_docs.add(digest)
            chunks = chunk_pages(pages)
            index = HybridIndex(chunks, model())
            st.session_state.update(index=index, fingerprint=fingerprint, pages=len(pages), chunks=len(chunks), docs=len(seen_docs))
    except (ValueError, RuntimeError, OSError) as exc:
        st.error(str(exc))
        st.stop()
a, b, c = st.columns(3)
a.metric("Documents", st.session_state.docs)
b.metric("Unique text pages", st.session_state.pages)
c.metric("Evidence chunks", st.session_state.chunks)
question = st.text_input("Question", placeholder="What is the incident escalation procedure?", max_chars=4000)
if st.button("Find evidence", type="primary", disabled=not question.strip()):
    with st.spinner("Searching your documents..."):
        hits = st.session_state.index.search(question, k=k)
        result = answer_from_evidence(question, hits)
        if answer_mode == "Local Ollama":
            try:
                result["answer"] = ollama_answer(question, hits, local_model)
                result["mode"] = "local LLM"
            except (RuntimeError, ValueError) as exc:
                st.warning(f"{exc} Showing exact excerpts instead.")
        st.session_state.last_result = result
if "last_result" in st.session_state:
    result = st.session_state.last_result
    st.subheader("Answer")
    st.text(result["answer"])
    st.caption(f"Mode: {result['mode']}. Retrieval is not proof. Verify claims against the source text. Local LLM citation checks validate IDs, not truth.")
    st.subheader("Source evidence")
    for citation in result["citations"]:
        with st.expander(f"[{citation['number']}] {citation['source']} · page {citation['page']}", expanded=True):
            st.text(citation["text"])
            st.caption(f"Chunk {citation['id']} · {citation['title']}")
