from app.services.summarize_model import summarize_model_from_health


def test_summarize_model_from_model_field():
    assert summarize_model_from_health({"model": "qwen2.5:7b"}) == "qwen2.5:7b"


def test_summarize_model_from_llm_model_field():
    assert summarize_model_from_health({"llm_model": "gpt-oss"}) == "gpt-oss"


def test_summarize_model_from_llm_when_not_status():
    assert summarize_model_from_health({"llm": "Qwen/Qwen2.5-7B-Instruct"}) == "Qwen/Qwen2.5-7B-Instruct"


def test_summarize_model_ignores_llm_ready():
    assert summarize_model_from_health({"llm": "ready"}) is None
    assert summarize_model_from_health({"llm": "ready", "model": "local-llm"}) == "local-llm"
