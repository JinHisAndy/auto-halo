from app.services.rewriter.base import BaseRewriter

try:
    from app.services.rewriter.registry import PROVIDER_REGISTRY
except ImportError:
    PROVIDER_REGISTRY = {}


class RewriterFactory:
    @staticmethod
    def create(provider_key: str, api_key: str, base_url: str, model_name: str) -> BaseRewriter:
        if provider_key in PROVIDER_REGISTRY:
            return PROVIDER_REGISTRY[provider_key](api_key, base_url, model_name)
        from app.services.rewriter.openai_rewriter import OpenAIRewriter
        return OpenAIRewriter(api_key, base_url, model_name)