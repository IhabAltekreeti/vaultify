"""Groq LLM runtime helpers for Vaultify."""

from groq import Groq

from vaultify.config import LLM_MODEL


def create_groq_client(*, api_key: str) -> Groq:
    """Create the Groq client without reading secrets from platform-specific APIs."""
    if not api_key:
        raise ValueError("Groq API key is required.")
    return Groq(api_key=api_key)


def probe_groq_connection(client: Groq, *, model: str = LLM_MODEL) -> str:
    """Run the same small live connectivity probe used by the golden notebook."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": "Answer in one word: is this test successful?",
            }
        ],
        max_tokens=10,
    )
    return (response.choices[0].message.content or "").strip()
