import httpx
from app.services.rewriter.base import BaseRewriter

REWRITE_PROMPT = """你是一位资深博客作者。请将以下文章内容用你自己的话重写一遍。
要求：
- 保持原文的核心信息和观点不变
- 用博客的轻松自然口吻表达
- 不得直接复制粘贴原文的句子
- 可以调整文章结构和段落顺序
{extra}

原文内容：
{text}"""

CITATION_EXTRA = "保留以下原文引用内容（blockquote中的内容需要保留原样）：\n"


class MiniMaxRewriter(BaseRewriter):
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
        extra = CITATION_EXTRA if keep_citations else ""
        prompt = REWRITE_PROMPT.format(extra=extra, text=text)

        async with httpx.AsyncClient(timeout=120) as client:
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