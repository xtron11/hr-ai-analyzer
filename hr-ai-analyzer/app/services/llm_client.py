import requests
import logging
from app.config import settings

logger = logging.getLogger("hr.llm")


def ask_llm(prompt: str) -> str:
    try:
        response = requests.post(
            settings.OLLAMA_URL,
            json={
                "model": settings.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.ConnectionError:
        logger.error(f"Ollama недоступен по адресу {settings.OLLAMA_URL}")
        raise
    except Exception as e:
        logger.error(f"Ошибка LLM: {e}")
        raise
