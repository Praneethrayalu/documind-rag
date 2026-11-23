"""Measured retrieval / excerpt baseline, not RAGAS or an LLM benchmark."""
import hashlib
import importlib.metadata
import json
import platform
import statistics
import time
from pathlib import Path

from documind.core import HybridIndex, answer_from_evidence, chunk_pages, load_embedder, parse_pdf

ROOT = Path(__file__).resolve().parents[1]


def main():
    questions = json.loads((ROOT / "evaluation/questions.json").read_text())
    pdf = (ROOT / "data/sample/documind-handbook.pdf").read_bytes()
    start = time.perf_counter()
    model = load_embedder()
    chunks = chunk_pages(parse_pdf(pdf, "documind-handbook.pdf"))
    index = HybridIndex(chunks, model)
    setup = time.perf_counter() - start
    results, records = {}, []
    # Warm up inference before timing.
    index.search("incident response", 4)
    for mode in ["bm25", "dense", "hybrid"]:
        rows, latencies = [], []
        for item in questions:
            tick = time.perf_counter()
            hits = index.search(item["question"], 4, mode)
            result = answer_from_evidence(item["question"], hits)
            elapsed = (time.perf_counter() - tick) * 1000
            latencies.append(elapsed)
            row = {**item, "mode": mode, "answer": result["answer"], "retrieved_pages": [h.chunk.page for h in hits],
                   "contexts": [h.chunk.text for h in hits], "latency_ms": round(elapsed, 3)}
            row["hit_at_1"] = hits[0].chunk.page == item["expected_page"]
            row["recall_at_4"] = item["expected_page"] in row["retrieved_pages"]
            row["answer_contains_expected"] = item["expected_substring"].casefold() in row["answer"].casefold()
            rows.append(row)
        results[mode] = {key: round(statistics.mean(r[key] for r in rows), 4) for key in ["hit_at_1", "recall_at_4", "answer_contains_expected"]}
        results[mode].update(latency_median_ms=round(statistics.median(latencies), 3), latency_p95_ms=round(sorted(latencies)[47], 3))
        records.extend(rows)
    report = {"dataset": "50 hand-authored synthetic QA pairs over 10 authored handbook pages; same-corpus sanity check, not external generalization", "questions": len(questions), "chunks": len(chunks), "pdf_sha256": hashlib.sha256(pdf).hexdigest(), "python": platform.python_version(), "platform": platform.platform(), "cpu": platform.processor(), "threads": __import__('torch').get_num_threads(), "model": "sentence-transformers/all-MiniLM-L6-v2", "versions": {p: importlib.metadata.version(p) for p in ["sentence-transformers", "torch", "faiss-cpu", "numpy"]}, "setup_seconds": round(setup, 3), "metrics": results, "ragas": {"status": "not_run", "reason": "Requires a local LLM judge, separate install and explicit run. Retrieval and substring checks are not faithfulness or answer relevancy."}}
    (ROOT / "evaluation/results.json").write_text(json.dumps(report, indent=2) + "\n")
    (ROOT / "evaluation/predictions.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
