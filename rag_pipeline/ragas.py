from ragas.embeddings.base import BaseRagasEmbeddings
from sentence_transformers import SentenceTransformer


class SentenceTransformerRagasEmbeddings(BaseRagasEmbeddings):

    def __init__(self, model, model_name):
        self.client = model
        self.model = model_name

    def embed_query(self, text):
        return self.client.encode(
            text,
            convert_to_numpy=True
        ).tolist()

    def embed_documents(self, texts):
        return self.client.encode(
            texts,
            convert_to_numpy=True
        ).tolist()

    async def aembed_query(self, text):
        return self.embed_query(text)

    async def aembed_documents(self, texts):
        return self.embed_documents(texts)
    
