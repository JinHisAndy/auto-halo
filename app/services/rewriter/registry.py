from app.services.rewriter.deepseek import DeepSeekRewriter
from app.services.rewriter.mofi import MofiRewriter
from app.services.rewriter.minimax import MiniMaxRewriter
from app.services.rewriter.openai_rewriter import OpenAIRewriter

PROVIDER_REGISTRY = {
    "deepseek": DeepSeekRewriter,
    "mofi": MofiRewriter,
    "minimax": MiniMaxRewriter,
    "openai": OpenAIRewriter,
}