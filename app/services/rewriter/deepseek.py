import httpx

from app.services.rewriter.base import BaseRewriter
from app.services.rewriter.prompt_builder import build_rewrite_prompt


class DeepSeekRewriter(BaseRewriter):
    async def list_models(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return [{"id": m["id"], "name": m.get("id", "")} for m in data.get("data", [])]

    async def rewrite(self, text: str, keep_citations: bool = False) -> str:
        prompt = build_rewrite_prompt(text, keep_citations)

        async with httpx.AsyncClient(timeout=600) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def test_connection(self) -> bool:
        try:
            models = await self.list_models()
            return len(models) > 0
        except Exception:
            return False
