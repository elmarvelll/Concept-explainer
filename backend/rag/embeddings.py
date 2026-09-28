from fastembed import TextEmbedding
from langchain_core.embeddings import Embeddings

# ONNX-runtime based (via fastembed), not torch — this project's Intel Mac
# dev machine only has PyTorch wheels up to 2.2.2 (Apple dropped x86_64
# builds after that), which is too old for current transformers/
# sentence-transformers. fastembed sidesteps that entirely and is also what
# Qdrant's own examples use.
MODEL_NAME = "BAAI/bge-small-en-v1.5"


class FastEmbedEmbeddings(Embeddings):
    def __init__(self, model_name: str = MODEL_NAME):
        self._model = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(self._model.query_embed(text)).tolist()
