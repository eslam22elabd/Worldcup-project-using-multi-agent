import os
from openai import OpenAI

class OpenRouterClient:
    BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "openai/gpt-4o-mini"

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1500,
    ) -> None:
        self.model = model or os.getenv("OPENROUTER_MODEL", self.DEFAULT_MODEL)
        self.temperature = temperature
        self.max_tokens = max_tokens

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is missing.")

        self._client = OpenAI(
            base_url=self.BASE_URL,
            api_key=api_key,
        )

    def generate(self, prompt: str) -> str:
        try:
            completion = self._client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return completion.choices[0].message.content.strip()
        except Exception as exc:
            raise RuntimeError(f"OpenRouter API call failed: {exc}") from exc