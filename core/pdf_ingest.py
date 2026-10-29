"""
core/pdf_ingest.py
------------------
Turn any PDF into text an AI or a search index can read.

A PDF stores glyphs at positions, not paragraphs: extracted raw, it comes out
with words split across lines, headers and page numbers repeated on every page,
and no structure. This module rebuilds what a model needs:

1. text per page (pypdf);
2. cleanup: hyphenated line breaks rejoined, paragraph lines merged, repeated
   headers, footers and page numbers removed, whitespace normalised;
3. structure: headings and bullet lists marked in Markdown, page markers kept
   so every chunk can cite its page;
4. chunks sized for a context window (about 4 characters per token), with a
   small overlap so no sentence is lost at a boundary;
5. optional masking of personal data (core/pii.py) before anything leaves.

Scanned pages carry no text layer. They are reported by number, never guessed:
an OCR engine is needed for them and none is bundled here.
"""

from __future__ import annotations

import io
import json
import re
import unicodedata
from collections import Counter

from pypdf import PdfReader

CHARS_PER_TOKEN = 4
_BULLET = re.compile(r"^\s*([•▪◦·●■\-–*]|\d{1,2}[.)])\s+")
_PAGE_NO = re.compile(r"^\s*(page\s*)?\d{1,4}(\s*(/|sur|of)\s*\d{1,4})?\s*$", re.I)


def _norm(line: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", line)).strip()


def _repeated_lines(pages: list) -> set:
    """Lines found at the top or bottom of most pages: headers and footers."""
    if len(pages) < 3:
        return set()
    edges = Counter()
    for lines in pages:
        kept = [l for l in lines if l]
        for l in set(kept[:2] + kept[-2:]):
            edges[re.sub(r"\d+", "#", l)] += 1
    return {k for k, n in edges.items() if n >= max(3, len(pages) * 0.5)}


def _is_heading(line: str, nxt: str) -> bool:
    if not line or len(line) > 80 or line.endswith((".", ",", ";", ":")) or _BULLET.match(line):
        return False
    words = line.split()
    if len(words) > 12 or not nxt:
        return False
    letters = [c for c in line if c.isalpha()]
    caps = letters and sum(c.isupper() for c in letters) / len(letters) > 0.7
    title = sum(w[:1].isupper() for w in words) / len(words) >= 0.6
    numbered = bool(re.match(r"^(\d+(\.\d+)*|[IVX]+|Article\s+\d+|Chapitre|Chapter|Section)\b", line))
    return bool(caps or numbered or (title and len(words) <= 8))


def _page_markdown(lines: list) -> str:
    """Rebuild paragraphs, headings and bullets from one page's lines."""
    out, para = [], ""

    def flush():
        nonlocal para
        if para:
            out.append(para.strip())
            para = ""

    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if not line:
            flush()
            continue
        if _is_heading(line, nxt):
            flush()
            out.append(f"## {line}")
            continue
        if _BULLET.match(line):
            flush()
            para = "- " + _BULLET.sub("", line)
            continue
        if para.endswith("-") and line[:1].islower():
            para = para[:-1] + line           # mot coupé en fin de ligne
        elif para:
            para += " " + line
        else:
            para = line
        if line.endswith((".", "!", "?", ":")) and len(line) < 60:
            flush()
    flush()
    return "\n\n".join(out)


def convert(data: bytes, name: str = "document.pdf", *, chunk_tokens: int = 800,
            overlap_tokens: int = 80, strip_repeats: bool = True,
            redact_names: list | None = None, redact: bool = False) -> dict:
    """
    PDF bytes -> {"markdown", "chunks", "pages", "scanned_pages", "stats",
    "metadata"}. Raises ValueError with a plain message for a bad or locked file.
    """
    if not data[:5] == b"%PDF-":
        raise ValueError("This file is not a PDF (it does not start with %PDF-).")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:  # noqa: BLE001
                raise ValueError("This PDF is password protected. Remove the password and try again.")
        raw_pages = [(p.extract_text() or "") for p in reader.pages]
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 , a broken file gets a plain message
        raise ValueError(f"This PDF could not be read ({type(exc).__name__}).") from exc

    pages = [[_norm(l) for l in txt.splitlines()] for txt in raw_pages]
    repeats = _repeated_lines(pages) if strip_repeats else set()
    scanned = [i + 1 for i, txt in enumerate(raw_pages) if len(txt.strip()) < 20]

    md_pages = []
    for i, lines in enumerate(pages):
        kept = [l for l in lines
                if not (strip_repeats and (re.sub(r"\d+", "#", l) in repeats or _PAGE_NO.match(l or "x")))]
        md_pages.append(_page_markdown(kept))

    table = {}
    if redact:
        from . import pii
        red = []
        for txt in md_pages:
            r, t = pii.redact(txt, redact_names or [])
            red.append(r)
            table.update(t)
        md_pages = red

    markdown = "\n\n".join(f"<!-- page {i + 1} -->\n{txt}" for i, txt in enumerate(md_pages) if txt)
    chunks = _chunk(md_pages, chunk_tokens, overlap_tokens)
    meta = {}
    try:
        info = reader.metadata or {}
        meta = {k.strip("/").lower(): str(v) for k, v in info.items() if v}
    except Exception:  # noqa: BLE001
        pass
    chars = sum(len(t) for t in md_pages)
    return {
        "source": name, "markdown": markdown, "chunks": chunks,
        "pages": [{"page": i + 1, "text": t} for i, t in enumerate(md_pages)],
        "scanned_pages": scanned, "metadata": meta,
        "stats": {"pages": len(md_pages), "characters": chars,
                  "tokens_est": chars // CHARS_PER_TOKEN, "chunks": len(chunks),
                  "headers_removed": len(repeats), "masked_values": len(table)},
    }


def _chunk(md_pages: list, chunk_tokens: int, overlap_tokens: int) -> list:
    """Paragraph-aligned chunks of about `chunk_tokens`, each citing its pages."""
    limit = max(chunk_tokens, 50) * CHARS_PER_TOKEN
    overlap = max(min(overlap_tokens, chunk_tokens // 2), 0) * CHARS_PER_TOKEN
    paras = [(i + 1, p) for i, txt in enumerate(md_pages) for p in txt.split("\n\n") if p.strip()]
    chunks, buf, pages = [], "", []
    for page, p in paras:
        while len(p) > limit:                        # a huge paragraph is cut on spaces
            cut = p.rfind(" ", 0, limit) or limit
            paras_piece, p = p[:cut], p[cut:].lstrip()
            if buf:
                chunks.append((buf, pages))
                buf, pages = "", []
            chunks.append((paras_piece, [page]))
        if buf and len(buf) + len(p) + 2 > limit:
            chunks.append((buf, pages))
            tail = buf[-overlap:] if overlap else ""
            buf = (tail[tail.find(" ") + 1:] + "\n\n" if tail else "")
            pages = [pages[-1]] if tail else []
        buf += ("\n\n" if buf and not buf.endswith("\n\n") else "") + p
        if page not in pages:
            pages.append(page)
    if buf.strip():
        chunks.append((buf, pages))
    return [{"id": f"c{n + 1:04d}", "page_start": pg[0], "page_end": pg[-1],
             "text": txt.strip(), "tokens_est": len(txt) // CHARS_PER_TOKEN}
            for n, (txt, pg) in enumerate(chunks)]


def to_jsonl(result: dict) -> str:
    """One chunk per line: the format embedding and RAG pipelines ingest."""
    return "\n".join(json.dumps({"source": result["source"], **c}, ensure_ascii=False)
                     for c in result["chunks"])


def _demo_pdf(pages: list) -> bytes:
    """A minimal valid PDF with one text line per entry, for tests."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None,
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for lines in pages:
        body = "BT /F1 11 Tf 50 780 Td 14 TL " + " ".join(
            "(" + l.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") '" for l in lines) + " ET"
        objs.append(f"<< /Length {len(body)} >>\nstream\n{body}\nendstream")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                    f"/Resources << /Font << /F1 3 0 R >> >> /Contents {len(objs)} 0 R >>")
        kids.append(f"{len(objs)} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offs = b"%PDF-1.4\n", []
    for n, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{n} 0 obj\n{o}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offs).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


if __name__ == "__main__":
    pdf = _demo_pdf([
        ["ACME SARL - Internal rules", "CHAPTER 1 GENERAL", "Every employee receives a con-",
         "tract before the first day.", "Leave is accrued monthly.", "- Annual leave", "- Sick leave", "1"],
        ["ACME SARL - Internal rules", "CHAPTER 2 PAY", "Salaries are paid on the 27th.",
         "Call Amina Belkacem at 0551234567.", "2"],
        ["ACME SARL - Internal rules", "CHAPTER 3 SAFETY", "Wear protective shoes.", "3"],
    ])
    r = convert(pdf, "rules.pdf", redact=True, redact_names=["Amina Belkacem"])
    md = r["markdown"]
    assert "contract before" in md, md                      # hyphen rejoined
    assert "ACME SARL - Internal rules" not in md          # header removed
    assert "## CHAPTER 2 PAY" in md and "- Annual leave" in md
    assert "Amina" not in md and "0551234567" not in md    # masked
    assert r["stats"]["pages"] == 3 and not r["scanned_pages"]
    assert r["chunks"] and r["chunks"][0]["page_start"] == 1
    small = convert(pdf, chunk_tokens=50, overlap_tokens=10)
    assert len(small["chunks"]) >= 2
    try:
        convert(b"not a pdf")
        raise AssertionError("accepted a non-PDF")
    except ValueError:
        pass
    print(f"  pdf to AI text: {r['stats']} ok")
