"""PDF ingestion, deterministic chunking, hybrid retrieval and evidence-only answers."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

import faiss
import numpy as np
import pymupdf as fitz
from rank_bm25 import BM25Okapi


@dataclass(frozen=True)
class Page:
    source: str
    document_id: str
    page: int
    text: str
    title: str = ""


@dataclass(frozen=True)
class Chunk:
    id: str
    source: str
    document_id: str
    page: int
    text: str
    title: str = ""


def clean_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\u00ad", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def parse_pdf(content: bytes, filename: str, max_pages: int = 300) -> list[Page]:
    if len(content) > 25 * 1024 * 1024:
        raise ValueError("PDF exceeds the 25 MiB limit")
    if not content.lstrip().startswith(b"%PDF-"):
        raise ValueError("This is not a PDF")
    document_id = hashlib.sha256(content).hexdigest()
    try:
        with fitz.open(stream=content, filetype="pdf") as pdf:
            if pdf.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported; upload an unlocked copy")
            if pdf.page_count > max_pages:
                raise ValueError(f"PDF exceeds {max_pages} pages")
            title = (pdf.metadata or {}).get("title", "") or Path(filename).stem
            seen, pages = set(), []
            for number, page in enumerate(pdf, start=1):
                text = clean_text(page.get_text(sort=True))
                fingerprint = re.sub(r"\s+", " ", text).casefold()
                if text and fingerprint not in seen:
                    pages.append(Page(Path(filename).name, document_id, number, text, title))
                    seen.add(fingerprint)
            if not pages:
                raise ValueError("No selectable text found. OCR is not included; use a text PDF")
            return pages
    except (fitz.FileDataError, RuntimeError) as exc:
        raise ValueError("Could not parse PDF") from exc


def recursive_split(text: str, size: int, separators: tuple = ("\n\n", "\n", ". ", " ")) -> list[str]:
    """Split at progressively smaller boundaries, with a hard character-limit fallback."""
    if len(text) <= size:
        return [text] if text.strip() else []
    if not separators:
        return [text[start:start + size] for start in range(0, len(text), size)]
    separator, *rest = separators
    pieces = text.split(separator)
    result, current = [], ""
    for part in pieces:
        candidate = current + separator + part if current else part
        if len(candidate) <= size:
            current = candidate
        else:
            if current:
                result.extend(recursive_split(current, size, tuple(rest)))
            current = part
    if current:
        result.extend(recursive_split(current, size, tuple(rest)))
    return result


def chunk_pages(pages: list[Page], size: int = 900, overlap: int = 120) -> list[Chunk]:
    if not 0 <= overlap < size or size < 64:
        raise ValueError("Require size >= 64 and 0 <= overlap < size")
    chunks, seen = [], set()
    for page in pages:
        tail = ""
        for index, body in enumerate(recursive_split(page.text, size - overlap)):
            text = (tail + " " + body).strip() if tail else body.strip()
            fingerprint = re.sub(r"\s+", " ", text).casefold()
            # Include document ID: identical evidence in different sources keeps its provenance.
            key = (page.document_id, fingerprint)
            if fingerprint and key not in seen:
                uid = hashlib.sha256(f"{page.document_id}:{page.page}:{index}:{text}".encode()).hexdigest()[:20]
                chunks.append(Chunk(uid, page.source, page.document_id, page.page, text, page.title))
                seen.add(key)
            tail = body[-overlap:] if overlap else ""
    return chunks


class Embedder(Protocol):
    def encode(self, sentences: list[str], **kwargs) -> np.ndarray: ...


def load_embedder(model: str = "sentence-transformers/all-MiniLM-L6-v2"):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(model, device="cpu")


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.casefold())


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


class HybridIndex:
    def __init__(self, chunks: list[Chunk], embedder: Embedder):
        if not chunks:
            raise ValueError("Cannot index an empty corpus")
        self.chunks, self.embedder = chunks, embedder
        vectors = np.asarray(embedder.encode([c.text for c in chunks], normalize_embeddings=True), dtype="float32")
        if vectors.ndim != 2 or len(vectors) != len(chunks) or not np.isfinite(vectors).all():
            raise ValueError("Embedder returned invalid vectors")
        faiss.normalize_L2(vectors)
        self.dense = faiss.IndexFlatIP(vectors.shape[1])
        self.dense.add(vectors)
        self.bm25 = BM25Okapi([tokenize(c.text) or ["empty"] for c in chunks])

    def search(self, query: str, k: int = 4, mode: str = "hybrid") -> list[Hit]:
        if not query.strip() or k <= 0:
            return []
        if len(query) > 4000:
            raise ValueError("Question exceeds 4000 characters")
        if mode not in {"hybrid", "dense", "bm25"}:
            raise ValueError("Unknown retrieval mode")
        n = min(len(self.chunks), max(k * 5, 20))
        dense_ids = np.array([[]], dtype="int64")
        if mode != "bm25":
            query_vector = np.asarray(self.embedder.encode([query], normalize_embeddings=True), dtype="float32")
            faiss.normalize_L2(query_vector)
            _, dense_ids = self.dense.search(query_vector, n)
        sparse_scores = self.bm25.get_scores(tokenize(query))
        sparse_ids = sorted(range(len(self.chunks)), key=lambda i: (-sparse_scores[i], i))[:n]
        rankings = [dense_ids[0].tolist(), sparse_ids] if mode == "hybrid" else [dense_ids[0].tolist() if mode == "dense" else sparse_ids]
        scores: dict[int, float] = {}
        for ranking in rankings:
            for rank, chunk_id in enumerate(ranking, 1):
                scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (60 + rank)
        ordered = sorted(scores, key=lambda i: (-scores[i], i))[:k]
        return [Hit(self.chunks[i], scores[i]) for i in ordered]


def answer_from_evidence(query: str, hits: list[Hit], limit: int = 1) -> dict:
    """Return exact source sentences, never pretend this is a generative LLM answer."""
    stop = {"what", "is", "the", "a", "an", "of", "to", "for", "and", "how", "in", "does", "are", "which", "when"}
    terms = set(tokenize(query)) - stop
    candidates = []
    for citation, hit in enumerate(hits, 1):
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", hit.chunk.text):
            score = len(terms.intersection(tokenize(sentence)))
            if score:
                candidates.append((score, citation, sentence.strip()))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    selected, seen = [], set()
    for _, citation, sentence in candidates:
        if sentence and sentence.casefold() not in seen:
            selected.append(f"{sentence} [{citation}]")
            seen.add(sentence.casefold())
        if len(selected) == limit:
            break
    return {"answer": "\n\n".join(selected) if selected else "I could not find supporting text in these documents.",
            "mode": "extractive", "citations": [{"number": n, **asdict(hit.chunk)} for n, hit in enumerate(hits, 1)]}
