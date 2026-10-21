import json

import httpx

from app.core.config import settings


class LLMError(RuntimeError):
    pass


def chat_json(system: str, prompt: str) -> dict:
    """Chat Completions compatível com OpenAI: serve o Ollama local e fornecedores alojados (ex.: Mistral)."""
    payload = {
        "model": settings.llm_model,
        "temperature": 0.2,
        "max_tokens": 1024,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"} if settings.llm_api_key else {}
    try:
        response = httpx.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
            timeout=settings.llm_timeout,
        )
        response.raise_for_status()
        return json.loads(response.json()["choices"][0]["message"]["content"])
    except httpx.HTTPError as error:
        raise LLMError("Não foi possível contactar o modelo de IA. Tenta de novo daqui a pouco.") from error
    except (KeyError, IndexError, ValueError) as error:
        raise LLMError("O modelo devolveu uma resposta inválida.") from error
