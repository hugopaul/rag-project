from flask import Flask, request, jsonify
from qdrant_client import QdrantClient
import spacy
import re
import html
import os
from werkzeug.utils import secure_filename
import tempfile
import shutil

app = Flask(__name__)

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "jira")
EMBEDDING_MODEL = os.getenv("SPACY_MODEL", "pt_core_news_md")
TOP_K = 4

nlp = spacy.load(EMBEDDING_MODEL)
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

def normalizar_texto(texto):
    texto = html.unescape(texto)
    texto = re.sub(r'<[^>]+>', ' ', texto)
    texto = texto.replace('\n', ' ').replace('\r', ' ')
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip().lower()

def embed_text(text):
    doc = nlp(text)
    return doc.vector.tolist()

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    query = data.get('question', '')
    query_norm = normalizar_texto(query)
    # Busca exata no campo key
    result = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter={
            "must": [
                {"key": "key", "match": {"value": query.strip().upper()}},
            ]
        },
        limit=TOP_K
    )[0]
    if result:
        chunks = [
            {
                "id": point.id,
                "text": point.payload.get('text_raw', ''),
                "overlap": point.payload.get('overlap', ''),
                "key": point.payload.get('key', '')
            }
            for point in result
        ]
        return jsonify({"chunks": chunks, "mode": "key"})
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
        chunks = [
            {
                "id": point.id,
                "text": point.payload.get('text_raw', ''),
                "overlap": point.payload.get('overlap', ''),
                "key": point.payload.get('key', '')
            }
            for point in result
        ]
        return jsonify({"chunks": chunks, "mode": "text_raw"})
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
        chunks = [
            {
                "id": point.id,
                "text": point.payload.get('text_raw', ''),
                "overlap": point.payload.get('overlap', ''),
                "key": point.payload.get('key', '')
            }
            for point in result
        ]
        return jsonify({"chunks": chunks, "mode": "text"})
    # Busca vetorial (fallback)
    query_vector = embed_text(query_norm)
    search_result = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=TOP_K
    )
    if not search_result:
        return jsonify({"chunks": [], "mode": "none"})
    chunks = [
        {
            "id": hit.id,
            "text": hit.payload.get('text_raw', ''),
            "overlap": hit.payload.get('overlap', ''),
            "key": hit.payload.get('key', ''),
            "score": hit.score
        }
        for hit in search_result
    ]
    return jsonify({"chunks": chunks, "mode": "vector"})

@app.route('/qdrant-data', methods=['GET'])
def qdrant_data():
    try:
        result = client.scroll(collection_name=COLLECTION_NAME, limit=100)
        points = result[0]
        data = [
            {
                "id": point.id,
                "text": point.payload.get('text_raw', ''),
                "overlap": point.payload.get('overlap', ''),
                "key": point.payload.get('key', '')
            }
            for point in points
        ]
        return jsonify(data)
    except Exception as e:
        msg = str(e)
        if 'Not found: Collection' in msg and 'doesn' in msg:
            return jsonify({"error": "Nenhuma base encontrada. Carregue um arquivo JIRA.xml para iniciar a base vetorial."}), 404
        return jsonify({"error": f"Erro ao consultar Qdrant: {msg}"}), 404

@app.route('/upload-jira', methods=['POST'])
def upload_jira():
    if 'file' not in request.files:
        return jsonify({'error': 'Arquivo não enviado'}), 400
    file = request.files['file']
    if not file.filename.endswith('.xml'):
        return jsonify({'error': 'Arquivo deve ser .xml'}), 400
    # Salva arquivo temporariamente
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, secure_filename(file.filename))
    file.save(temp_path)
    # Substitui o JIRA.xml original
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dest_path = os.path.join(base_dir, 'base', 'JIRA.xml')
    shutil.copy(temp_path, dest_path)
    # Reprocessa a base vetorial
    try:
        from cria_db import criar_db
        criar_db()
        shutil.rmtree(temp_dir)
        return jsonify({'status': 'Arquivo processado e base vetorial atualizada com sucesso!'})
    except Exception as e:
        shutil.rmtree(temp_dir)
        return jsonify({'error': str(e)}), 500

# No final do arquivo, antes do if __name__ == "__main__":
try:
    from chatgpt_api import *
except ImportError:
    pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
