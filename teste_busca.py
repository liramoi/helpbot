from rag.searcher import buscar

pergunta = "Como resetar a senha do Windows?" # Ou algo que esteja no seu PDF
resultados = buscar(pergunta)

for res in resultados:
    print(f"\nFonte: {res['arquivo']} ({res['categoria']})")
    print(f"Conteúdo: {res['texto'][:200]}...")