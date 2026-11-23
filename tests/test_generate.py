import io
import json
from unittest.mock import patch

import pytest

from documind.core import Chunk, Hit
from documind.generate import ollama_answer


def test_local_only_and_valid_citation():
    hits = [Hit(Chunk("a", "a.pdf", "a", 1, "The sky is blue."), 1)]
    def response(request, timeout):
        assert request.full_url == "http://127.0.0.1:11434/api/chat"
        payload = json.loads(request.data)
        assert payload["options"]["temperature"] == 0
        assert "untrusted" in payload["messages"][0]["content"]
        return io.BytesIO(json.dumps({"message": {"content": "The sky is blue. [1]"}}).encode())
    with patch("urllib.request.urlopen", response):
        assert ollama_answer("What color?", hits) == "The sky is blue. [1]"


@pytest.mark.parametrize("text", ["No citation", "Wrong reference [9]"])
def test_bad_citations_rejected(text):
    response = io.BytesIO(json.dumps({"message": {"content": text}}).encode())
    with patch("urllib.request.urlopen", return_value=response):
        with pytest.raises(ValueError, match="valid citations"):
            ollama_answer("question", [Hit(Chunk("a", "a.pdf", "a", 1, "text"), 1)])


def test_ollama_offline():
    with patch("urllib.request.urlopen", side_effect=OSError()):
        with pytest.raises(RuntimeError, match="unavailable"):
            ollama_answer("question", [])
