from abc import ABC, abstractmethod


class BaseRewriter(ABC):
    def __init__(self, api_key: str, base_url: str, model_name: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name

    @abstractmethod
    async def list_models(self) -> list[dict]:
        ...

    @abstractmethod
    async def rewrite(self, text: str, keep_citations: bool = False, urls: list[str] | None = None) -> str:
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        ...

    @abstractmethod
    async def suggest_tags(self, title: str, body_text: str, existing_tags: list[str]) -> list[str]:
        ...