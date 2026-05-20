import httpx

from app.services.rewriter.base import BaseRewriter
from app.services.rewriter.prompt_builder import build_rewrite_prompt, TAG_SUGGESTION_PROMPT

__all__ = ["OpenAIRewriter", "build_rewrite_prompt"]


class OpenAIRewriter(BaseRewriter):
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

    async def suggest_tags(self, title: str, body_text: str, existing_tags: list[str]) -> list[str]:
        prompt = TAG_SUGGESTION_PROMPT.format(
            existing_tags="\n".join(existing_tags) if existing_tags else "（无已有标签）",
            title=title,
            body_text=body_text[:3000],
        )
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
                    "temperature": 0.5,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return [line.strip() for line in content.strip().split("\n") if line.strip()]
