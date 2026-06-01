import os

from langchain_mistralai import ChatMistralAI


DEFAULT_MISTRAL_MODEL = "mistral-small-latest"


def get_llm(temperature: float = 0.2) -> ChatMistralAI:
    return ChatMistralAI(
        model=os.getenv("MISTRAL_MODEL", DEFAULT_MISTRAL_MODEL),
        mistral_api_key=os.getenv("MISTRAL_API_KEY"),
        temperature=temperature,
    )
