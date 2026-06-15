import asyncio
import logging

import httpx

from app.services.rewriter.base import BaseRewriter
from app.services.rewriter.prompt_builder import build_rewrite_prompt, TAG_SUGGESTION_PROMPT

__all__ = ["OpenAIRewriter", "build_rewrite_prompt"]

logger = logging.getLogger(__name__)

RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_RETRIES = 3
BASE_DELAY = 2


class OpenAIRewriter(BaseRewriter):
    async def _post_with_retry(self, client: httpx.AsyncClient, url: str, headers: dict, json: dict) -> dict:
        last_exc = None
        for attempt in range(MAX_RETRIES + 1):
            resp = await client.post(url, headers=headers, json=json)
            if resp.status_code not in RETRY_STATUS_CODES:
                resp.raise_for_status()
                return resp.json()
            last_exc = httpx.HTTPStatusError(
                f"Server error '{resp.status_code}' for url '{url}'",
                request=resp.request,
                response=resp,
            )
            if attempt < MAX_RETRIES:
                delay = BASE_DELAY ** attempt
                logger.warning(
                    "LLM API returned %s, retrying in %ss (attempt %s/%s)",
                    resp.status_code, delay, attempt + 1, MAX_RETRIES,
                )
                await asyncio.sleep(delay)
        raise last_exc

    async def list_models(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return [{"id": m["id"], "name": m.get("id", "")} for m in data.get("data", [])]

    async def rewrite(self, text: str, keep_citations: bool = False, urls: list[str] | None = None) -> str:
        prompt = build_rewrite_prompt(text, keep_citations, urls=urls)

        async with httpx.AsyncClient(timeout=900) as client:
            data = await self._post_with_retry(
                client,
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
        async with httpx.AsyncClient(timeout=900) as client:
            data = await self._post_with_retry(
                client,
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
            content = data["choices"][0]["message"]["content"]
            return [line.strip() for line in content.strip().split("\n") if line.strip()]
