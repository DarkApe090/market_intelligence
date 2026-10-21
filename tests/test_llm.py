import httpx
import pytest

from app.ai import llm
from app.core.config import settings


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("erro", request=httpx.Request("POST", "http://x"), response=None)

    def json(self):
        return self._payload


def test_chat_json_uses_openai_compatible_api(monkeypatch):
    monkeypatch.setattr(settings, "llm_base_url", "https://api.mistral.ai/v1/")
    monkeypatch.setattr(settings, "llm_api_key", "chave")
    monkeypatch.setattr(settings, "llm_model", "mistral-small-latest")
    sent = {}

    def fake_post(url, **kwargs):
        sent.update(url=url, **kwargs)
        return FakeResponse({"choices": [{"message": {"content": '{"ok": true}'}}]})

    monkeypatch.setattr(llm.httpx, "post", fake_post)

    assert llm.chat_json("sistema", "pedido") == {"ok": True}
    assert sent["url"] == "https://api.mistral.ai/v1/chat/completions"
    assert sent["headers"] == {"Authorization": "Bearer chave"}
    assert sent["json"]["model"] == "mistral-small-latest"
    assert sent["json"]["response_format"] == {"type": "json_object"}


def test_chat_json_without_key_sends_no_auth(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
    sent = {}

    def fake_post(url, **kwargs):
        sent.update(kwargs)
        return FakeResponse({"choices": [{"message": {"content": "{}"}}]})

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    llm.chat_json("s", "p")
    assert sent["headers"] == {}


@pytest.mark.parametrize("response", [
    FakeResponse({}, status_code=401),
    FakeResponse({"choices": []}),
    FakeResponse({"choices": [{"message": {"content": "não é json"}}]}),
])
def test_chat_json_errors_become_llm_error(monkeypatch, response):
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: response)
    with pytest.raises(llm.LLMError):
        llm.chat_json("s", "p")
