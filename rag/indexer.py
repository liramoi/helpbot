import os
from pathlib import Path
from pypdf import PdfReader
import chromadb
from chromadb.utils import embedding_functions

PDFS_DIR = Path("pdfs")
CHROMA_DIR = Path("chroma_db")

embedding_fn = embedding_functions.DefaultEmbeddingFunction()
client = chromadb.PersistentClient(path=str(CHROMA_DIR))
collection = client.get_or_create_collection(
    name="helpbot",
    embedding_function=embedding_fn
)

def extrair_texto_pdf(caminho: Path) -> str:
    reader = PdfReader(caminho)
    texto = ""
    for pagina in reader.pages:
        texto += pagina.extract_text() or ""
    return texto

def dividir_em_chunks(texto: str, tamanho: int = 80) -> list[str]:
    palavras = texto.split()
    chunks = []
    for i in range(0, len(palavras), tamanho):
        chunk = " ".join(palavras[i:i + tamanho])
        if chunk.strip():
            chunks.append(chunk)
    return chunks

def indexar_todos_pdfs():
    # Limpa o banco antes de reindexar
    try:
        client.delete_collection("helpbot")
    except:
        pass
    
    col = client.get_or_create_collection(
        name="helpbot",
        embedding_function=embedding_fn
    )

    total = 0
    for categoria in PDFS_DIR.iterdir():
        if not categoria.is_dir():
            continue
        for pdf in categoria.glob("*.pdf"):
            print(f"Indexando: {pdf.name} [{categoria.name}]")
            texto = extrair_texto_pdf(pdf)
            chunks = dividir_em_chunks(texto)
            ids = [f"{categoria.name}_{pdf.stem}_{i}" for i in range(len(chunks))]
            metadatas = [{"categoria": categoria.name, "arquivo": pdf.name} for _ in chunks]
            col.add(documents=chunks, ids=ids, metadatas=metadatas)
            total += len(chunks)
            print(f"  {len(chunks)} chunks indexados")
    
    print(f"\nConcluído! Total: {total} chunks no banco.")

if __name__ == "__main__":
    indexar_todos_pdfs()