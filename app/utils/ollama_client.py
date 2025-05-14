import httpx
from typing import List, Dict

class OllamaClient:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip('/')
        self.model = model

    async def chat(self, messages: List[Dict], temperature: float = 0.5) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{self.base_url}/chat/completions", json=payload, timeout=60.0)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()