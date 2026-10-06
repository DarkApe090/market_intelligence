import json

import httpx

from app.core.config import settings


class LLMError(RuntimeError):
    pass


def chat_json(system: str, prompt: str) -> dict:
    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }
    try:
        response = httpx.post(
            f"{settings.ollama_url.rstrip('/')}/api/chat",
            json=payload,
            timeout=settings.ollama_timeout,
        )
        response.raise_for_status()
        return json.loads(response.json()["message"]["content"])
    except httpx.HTTPError as error:
        raise LLMError("Não foi possível contactar o modelo de IA. Confirma que o Ollama está a correr.") from error
    except (KeyError, ValueError) as error:
        raise LLMError("O modelo devolveu uma resposta inválida.") from error
