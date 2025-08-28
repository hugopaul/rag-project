import os
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct

# Configurações
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "jira")

# Conecta ao Qdrant
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

# Busca todos os pontos (chunks) da collection
try:
    count = client.count(collection_name=COLLECTION_NAME, exact=True).count
    print(f"Total de chunks na collection '{COLLECTION_NAME}': {count}")
    if count == 0:
        print("Nenhum chunk encontrado.")
    else:
        # Busca todos os pontos (até 10.000 por vez)
        result = client.scroll(collection_name=COLLECTION_NAME, limit=10000)
        points = result[0]
        for idx, point in enumerate(points):
            print(f"\nChunk #{idx+1}:")
            print(f"ID: {point.id}")
            # Tenta acessar o vetor em diferentes campos possíveis
            vector = None
            if hasattr(point, 'vector') and point.vector is not None:
                vector = point.vector
            elif hasattr(point, 'vectors') and point.vectors is not None:
                # Pode ser dict: {'default': [vetor]}
                if isinstance(point.vectors, dict):
                    vector = point.vectors.get('default')
                else:
                    vector = point.vectors
            if vector is not None:
                print(f"Vector (dim={len(vector)}): {vector[:5]} ...")
            else:
                print("Vector: [None]")
            payload = point.payload or {}
            print(f"Texto: {payload.get('text', '[sem texto]')}")
            # Exibe overlaps se existirem
            overlap = payload.get('overlap')
            if overlap is not None:
                print(f"Overlap: {overlap}")
            else:
                print("Overlap: [não informado]")
except Exception as e:
    print(f"Erro ao acessar Qdrant: {e}")
