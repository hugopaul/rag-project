
# --- Dependências ---
import os
from lxml import etree
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
import spacy
import re
import html
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams

# Caminho robusto, relativo ao local do script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
XML_PATH = os.path.join(BASE_DIR, "base", "JIRA.xml")

def carregar_documentos_xml(xml_path):
    try:
        tree = etree.parse(xml_path)
    except Exception as e:
        print(f"Erro ao ler XML: {e}")
        return []
    items = tree.xpath('//item')
    documentos = []
    textos_puros = []
    for item in items:
        title = item.findtext('title') or ''
        description = item.findtext('description') or ''
        summary = item.findtext('summary') or ''
        texto_puro = f"{title}\n{summary}\n{description}"
        documentos.append(Document(page_content=texto_puro))
        textos_puros.append(texto_puro)
    return documentos, textos_puros

# Função de normalização
def normalizar_texto(texto):
    texto = html.unescape(texto)
    texto = re.sub(r'<[^>]+>', ' ', texto)  # remove HTML tags
    texto = texto.replace('\n', ' ').replace('\r', ' ')
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip().lower()


def criar_db():
    documentos, textos_puros = carregar_documentos_xml(XML_PATH)
    if not documentos:
        print("Nenhum documento carregado do XML. Abortando.")
        return


    # Chunking
    separador = RecursiveCharacterTextSplitter(
        chunk_size=4000,
        chunk_overlap=500,
        length_function=len,
        add_start_index=True
    )
    chunks = separador.split_documents(documentos)
    if not chunks:
        print("Nenhum chunk gerado. Abortando.")
        return

    print(f"Chunks gerados para indexação: {len(chunks)}")
    for i, chunk in enumerate(chunks, 1):
        print(f"\n--- Chunk {i} ---\n{chunk.page_content}\n")

    # Salvar texto puro correspondente a cada chunk
    # Como estamos chunkando os documentos, associar texto puro ao chunk pode ser feito por índice
    # (assume chunking 1:1 com documentos, se não, salva só o texto processado)

    # Carregar modelo spaCy offline
    try:
        nlp = spacy.load("pt_core_news_md")
    except Exception as e:
        print("Erro ao carregar modelo spaCy. Rode: python -m spacy download pt_core_news_md")
        print(e)
        return

    # Gerar embeddings spaCy para cada chunk (usando texto normalizado)
    vectors = []
    for idx, chunk in enumerate(chunks):
        texto_norm = normalizar_texto(chunk.page_content)
        if not texto_norm.strip():
            print(f"[AVISO] Chunk {idx} está vazio após normalização!")
        vec = nlp(texto_norm).vector
        if vec is None or len(vec) == 0:
            print(f"[ERRO] Vetor não gerado para chunk {idx}!")
        vectors.append(vec)
    # Checagem de dimensão
    dim = vectors[0].shape[0]
    for idx, vec in enumerate(vectors):
        if vec is None or len(vec) != dim:
            print(f"[ERRO] Chunk {idx} tem vetor inválido ou dimensão errada: {vec}")
    if not vectors or any(vec is None or len(vec) != dim for vec in vectors):
        print("Erro ao gerar embeddings spaCy: vetor inválido ou dimensão inconsistente.")
        return

    # Salvar no Qdrant manualmente
    client = QdrantClient(host="localhost", port=6333)
    collection_name = "jira"
    dim = vectors[0].shape[0]

    # Cria a collection apenas se não existir
    if not client.collection_exists(collection_name=collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=dim, distance="Cosine")
        )

    # Indexar os chunks
    payloads = []
    for i, chunk in enumerate(chunks):
        texto_puro = chunk.page_content
        texto_normalizado = normalizar_texto(texto_puro)
        # Extrair chave do card (ex: GMUD-16765) do início do texto
        key = None
        match = re.match(r"\[(\w+-\d+)\]", texto_puro.strip())
        if match:
            key = match.group(1)
        # Calcular overlap: trecho em comum com chunk anterior
        overlap = None
        if i > 0:
            prev = chunks[i-1].page_content
            overlap_size = 500  # mesmo valor do chunk_overlap
            overlap = prev[-overlap_size:] if len(prev) >= overlap_size else prev
            if not texto_puro.startswith(overlap):
                for j in range(overlap_size, 0, -1):
                    if texto_puro.startswith(prev[-j:]):
                        overlap = prev[-j:]
                        break
        payloads.append({
            "text": texto_normalizado,
            "text_raw": texto_puro,
            "overlap": overlap if overlap else "",
            "key": key if key else ""
        })
    try:
        client.upsert(
            collection_name=collection_name,
            points=[
                {
                    "id": i,
                    "vector": vec.tolist(),
                    "payload": payload
                }
                for i, (vec, payload) in enumerate(zip(vectors, payloads))
            ]
        )
        print(f"Banco de Dados criado no Qdrant com embeddings spaCy 100% offline! Total de chunks: {len(chunks)}")
    except Exception as e:
        print(f"Erro ao salvar no Qdrant: {e}")

criar_db()