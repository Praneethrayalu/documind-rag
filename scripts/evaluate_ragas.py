"""Optional real RAGAS judge pass using a local Ollama model. No paid API keys.

Run the retrieval evaluation first. This script evaluates the stored hybrid
extractive answers. It does not silently turn substring checks into RAGAS scores.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge", default="qwen2.5:3b")
    args = parser.parse_args()
    from datasets import Dataset
    from langchain_ollama import ChatOllama, OllamaEmbeddings
    from ragas import RunConfig, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import answer_relevancy, faithfulness
    rows = [json.loads(line) for line in (ROOT / "evaluation/predictions.jsonl").read_text().splitlines()]
    dataset = Dataset.from_list([{"question": r["question"], "answer": r["answer"], "contexts": r["contexts"], "ground_truth": r["reference"]} for r in rows if r["mode"] == "hybrid"])
    judge = LangchainLLMWrapper(ChatOllama(model=args.judge, temperature=0, num_ctx=4096))
    embeddings = LangchainEmbeddingsWrapper(OllamaEmbeddings(model="nomic-embed-text"))
    result = evaluate(dataset, metrics=[faithfulness, answer_relevancy], llm=judge, embeddings=embeddings, run_config=RunConfig(timeout=300, max_retries=1, max_workers=1), raise_exceptions=False)
    frame = result.to_pandas()
    frame.to_json(ROOT / "evaluation/ragas-results.json", orient="records", indent=2)
    summary = {"judge": args.judge, "questions": len(frame), "metrics": {m: {"mean": float(frame[m].mean()) if frame[m].notna().any() else None, "valid_scores": int(frame[m].notna().sum()), "failed_scores": int(frame[m].isna().sum())} for m in ["faithfulness", "answer_relevancy"]}}
    (ROOT / "evaluation/ragas-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    # Kept as a synchronous entry point because ragas owns its evaluation loop.
    main()
