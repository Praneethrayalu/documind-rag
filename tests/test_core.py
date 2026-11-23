import hashlib

import numpy as np
import pymupdf as fitz
import pytest

from documind.core import (
    Chunk,
    HybridIndex,
    Page,
    answer_from_evidence,
    chunk_pages,
    clean_text,
    parse_pdf,
    recursive_split,
)


def pdf_bytes(texts):
    document = fitz.open()
    for text in texts:
        document.new_page().insert_text((72, 72), text)
    return document.tobytes()


class FakeEmbedding:
    def encode(self, sentences, **kwargs):
        return np.array([[s.lower().count("apple") + .01, s.lower().count("ocean") + .01] for s in sentences], dtype="float32")


def test_parse_provenance_and_dedup():
    data = pdf_bytes(["Apple rules", "Apple rules", "Ocean rules"])
    pages = parse_pdf(data, "handbook.pdf")
    assert [p.page for p in pages] == [1, 3]
    assert pages[0].document_id == hashlib.sha256(data).hexdigest()


def test_clean():
    assert clean_text("  foo\x00\n\n\nbar ") == "foo\n\nbar"


@pytest.mark.parametrize("content", [b"bad", b"%PDF-broken"])
def test_bad_pdf(content):
    with pytest.raises(ValueError):
        parse_pdf(content, "bad.pdf")


def test_scanned_pdf_rejected():
    with pytest.raises(ValueError, match="OCR"):
        parse_pdf(pdf_bytes([""]), "scan.pdf")


def test_limits():
    with pytest.raises(ValueError, match="pages"):
        parse_pdf(pdf_bytes(["a", "b"]), "x.pdf", max_pages=1)


def test_chunks_stable_and_bounded():
    page = Page("a.pdf", "abc", 1, "A sentence. " * 300)
    chunks = chunk_pages([page], size=140, overlap=20)
    assert chunks == chunk_pages([page], size=140, overlap=20)
    assert all(len(c.text) <= 141 for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks)


@pytest.mark.parametrize("size,overlap", [(50, 10), (100, 100), (100, -1)])
def test_invalid_chunk_config(size, overlap):
    with pytest.raises(ValueError):
        chunk_pages([], size, overlap)


def test_recursive_hard_fallback():
    assert max(map(len, recursive_split("x" * 1000, 64))) <= 64


def test_index_modes():
    chunks = [Chunk("1", "a.pdf", "a", 1, "apple fruit"), Chunk("2", "b.pdf", "b", 2, "ocean waves")]
    index = HybridIndex(chunks, FakeEmbedding())
    for mode in ["hybrid", "dense", "bm25"]:
        assert index.search("apple", 1, mode)[0].chunk.id == "1"
    assert index.search(" ") == []
    assert index.search("apple", 0) == []
    assert len(index.search("apple", 50)) == 2
    with pytest.raises(ValueError):
        index.search("q", mode="bad")


def test_empty_index():
    with pytest.raises(ValueError):
        HybridIndex([], FakeEmbedding())


def test_answer_citation_and_abstention():
    index = HybridIndex([Chunk("a", "source.pdf", "d", 7, "Apple trees grow in orchards.")], FakeEmbedding())
    hits = index.search("apple")
    result = answer_from_evidence("Where do apple trees grow?", hits)
    assert "[1]" in result["answer"]
    assert result["citations"][0]["page"] == 7
    assert "could not find" in answer_from_evidence("uranium", hits)["answer"]


def test_cross_document_provenance_preserved():
    pages = [Page("a.pdf", "a", 1, "Identical content"), Page("b.pdf", "b", 1, "Identical content")]
    assert len(chunk_pages(pages)) == 2


def test_encrypted_pdf():
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "secret")
    data = doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="test-password")
    with pytest.raises(ValueError, match="Encrypted"):
        parse_pdf(data, "private.pdf")


def test_question_limit():
    index = HybridIndex([Chunk("a", "a.pdf", "a", 1, "apple")], FakeEmbedding())
    with pytest.raises(ValueError, match="4000"):
        index.search("a" * 4001)


def test_bm25_does_not_embed_query():
    embedding = FakeEmbedding()
    index = HybridIndex([Chunk("a", "a.pdf", "a", 1, "apple")], embedding)
    embedding.encode = lambda *a, **kw: (_ for _ in ()).throw(AssertionError("BM25 must not embed"))
    assert index.search("apple", mode="bm25")
