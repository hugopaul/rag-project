
import os
from qdrant_client import QdrantClient

import spacy
import re
import html

# Configurações
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "jira")
EMBEDDING_MODEL = os.getenv("SPACY_MODEL", "pt_core_news_md")
TOP_K = 4

# Carrega spaCy (offline)

nlp = spacy.load(EMBEDDING_MODEL)

# Função de normalização igual à do cria_db.py
def normalizar_texto(texto):
    texto = html.unescape(texto)
    texto = re.sub(r'<[^>]+>', ' ', texto)  # remove HTML tags
    texto = texto.replace('\n', ' ').replace('\r', ' ')
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip().lower()

# Conecta ao Qdrant
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

def embed_text(text):
    doc = nlp(text)
    return doc.vector.tolist()

def buscar_chunks(query):
    # Busca exata (normalizada) no campo text_raw e text
    query_norm = normalizar_texto(query)
    # Busca exata no campo text_raw
    result = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter={
            "must": [
                {"key": "text_raw", "match": {"value": query.strip()}},
            ]
        },
        limit=TOP_K
    )[0]
    if result:
        print("\n[Busca exata no campo text_raw]")
        for idx, point in enumerate(result):
            print(f"Chunk exato #{idx+1}:\n{point.payload.get('text_raw', '[sem texto]')}\n{'-'*40}")
        return
    # Busca exata no campo text (normalizado)
    result = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter={
            "must": [
                {"key": "text", "match": {"value": query_norm}},
            ]
        },
        limit=TOP_K
    )[0]
    if result:
        print("\n[Busca exata no campo text normalizado]")
        for idx, point in enumerate(result):
            print(f"Chunk exato #{idx+1}:\n{point.payload.get('text_raw', '[sem texto]')}\n{'-'*40}")
        return
    # Busca vetorial (fallback)
    query_vector = embed_text(query_norm)
    search_result = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=TOP_K
    )
    if not search_result:
        print("Nenhum chunk relevante encontrado.")
        return
    print(f"\n[Busca vetorial - Top {TOP_K} chunks mais similares à consulta]:\n")
    for idx, hit in enumerate(search_result):
        payload = hit.payload or {}
        texto = payload.get('text_raw', '[sem texto]')
        score = hit.score
        print(f"Chunk #{idx+1} (score={score:.3f}):\n{texto}\n{'-'*40}")

def main():
    query = input("Digite sua pergunta ou texto de busca: ")
    buscar_chunks(query)

if __name__ == "__main__":
    main()
    # perguntar()  # Removido, pois não existe mais