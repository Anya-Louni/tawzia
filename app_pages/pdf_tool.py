"""
PDF to AI text: drop any PDF, get clean Markdown and ready-to-embed chunks.

The engine is core/pdf_ingest.py. Everything runs on this machine: the file is
never sent to an outside service.
"""

import streamlit as st

from core import appdata, company_data as cd, pdf_ingest

appdata.sidebar_controls()

st.markdown(
    '<div class="tz-hero"><div><h1 class="tz-hero-h">PDF to AI text</h1>'
    '<div class="tz-hero-s">Drop a contract, a policy, a payslip or a CV. Tawzia rebuilds '
    'its paragraphs, headings and lists, removes repeated headers and page numbers, '
    'and cuts it into chunks an AI can read. <b>The file never leaves this machine.</b>'
    '</div></div></div>',
    unsafe_allow_html=True,
)

left, right = st.columns([1.6, 1], gap="large")
with right:
    with st.container(border=True):
        st.markdown("**Settings**")
        chunk = st.slider("Chunk size (tokens)", 100, 2000, 800, step=50,
                          help="About 4 characters per token. 500 to 1,000 suits most "
                               "retrieval setups.")
        overlap = st.slider("Overlap (tokens)", 0, 300, 80, step=10,
                            help="Text repeated between neighbouring chunks, so no "
                                 "sentence is cut off from its context.")
        strip = st.toggle("Remove repeated headers and page numbers", value=True)
        redact = st.toggle("Mask personal data (names, phones, NIN, RIB, emails)", value=False,
                           help="Names are matched against the employee file.")
with left:
    files = st.file_uploader("PDF files", type=["pdf"], accept_multiple_files=True,
                             label_visibility="collapsed")
    if not files:
        st.caption("Waiting for a PDF. Several files can be dropped at once.")

for f in files or []:
    try:
        r = pdf_ingest.convert(f.getvalue(), f.name, chunk_tokens=chunk, overlap_tokens=overlap,
                               strip_repeats=strip, redact=redact,
                               redact_names=[e.name for e in cd.people()] if redact else None)
    except ValueError as exc:
        st.error(f"{f.name}: {exc}", icon=":material/error:")
        continue
    s = r["stats"]
    with st.container(border=True):
        st.markdown(f"**{f.name}**")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Pages", s["pages"])
        c2.metric("Tokens (est.)", f"{s['tokens_est']:,}")
        c3.metric("Chunks", s["chunks"])
        c4.metric("Masked values", s["masked_values"])
        if r["scanned_pages"]:
            st.warning(f"Pages {', '.join(map(str, r['scanned_pages']))} have no text layer "
                       f"(scanned images). They need OCR, which is not bundled here.",
                       icon=":material/image_not_supported:")
        tab_md, tab_chunks = st.tabs(["Markdown", "Chunks"])
        with tab_md:
            st.text_area("Markdown", r["markdown"], height=320, label_visibility="collapsed",
                         key=f"md_{f.name}")
        with tab_chunks:
            st.dataframe([{"id": c["id"], "pages": f"{c['page_start']}-{c['page_end']}",
                           "tokens": c["tokens_est"], "text": c["text"][:160]}
                          for c in r["chunks"]], hide_index=True, width="stretch")
        stem = f.name.rsplit(".", 1)[0]
        d1, d2, d3 = st.columns(3)
        d1.download_button("Markdown (.md)", r["markdown"], f"{stem}.md", "text/markdown",
                           icon=":material/description:", width="stretch", key=f"dmd_{f.name}")
        d2.download_button("Chunks (.jsonl)", pdf_ingest.to_jsonl(r), f"{stem}.jsonl",
                           "application/jsonl", icon=":material/data_object:",
                           width="stretch", key=f"djl_{f.name}")
        import json
        d3.download_button("Full result (.json)",
                           json.dumps({k: v for k, v in r.items() if k != "markdown"},
                                      ensure_ascii=False, indent=2),
                           f"{stem}.json", "application/json", icon=":material/download:",
                           width="stretch", key=f"djs_{f.name}")

st.caption("Also available to AI assistants through the Tawzia MCP server "
           "(tool `tawzia_pdf_to_text`).")
