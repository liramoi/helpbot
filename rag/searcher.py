from pathlib import Path
import chromadb
from chromadb.utils import embedding_functions

CHROMA_DIR = Path("chroma_db")

embedding_fn = embedding_functions.DefaultEmbeddingFunction()
client = chromadb.PersistentClient(path=str(CHROMA_DIR))

def buscar(pergunta: str, n_resultados: int = 3) -> list[dict]:
    try:
        collection = client.get_collection(
            name="helpbot",
            embedding_function=embedding_fn
        )
        resultados = collection.query(
            query_texts=[pergunta],
            n_results=n_resultados
        )
        itens = []
        for i, doc in enumerate(resultados["documents"][0]):
            itens.append({
                "texto": doc,
                "categoria": resultados["metadatas"][0][i]["categoria"],
                "arquivo": resultados["metadatas"][0][i]["arquivo"],
            })
        return itens
    except Exception as e:
        print(f"Erro na busca: {e}")
        return []