import openai
import os
import re
from flask import request, jsonify, current_app
from api import app
import logging

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Configura logger
logger = logging.getLogger("chatgpt_api")
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

def montar_prompt(question, chunks):
    prompt = f"""Você é um assistente especializado em análise de tickets JIRA. 
Seu objetivo é analisar uma pergunta e 4 trechos de texto (chunks) de tickets JIRA 
e identificar qual chunk é MAIS RELEVANTE para responder à pergunta.

CRITÉRIOS DE ANÁLISE:
1. Similaridade semântica com a pergunta
2. Contexto da aplicação mencionada
3. Informações técnicas relevantes
4. Detalhes de implementação/resolução

PERGUNTA: "{question}"

CHUNKS PARA ANALISAR:
"""
    
    for idx, chunk in enumerate(chunks, 1):
        chunk_text = chunk.get('text', '')[:500]  # Limita para não exceder tokens
        prompt += f"\n--- CHUNK {idx} ---\n{chunk_text}\n"
    
    prompt += """
\nINSTRUÇÕES FINAIS:
- Responda APENAS no formato: "Chunk X - [justificativa breve]"
- Seja específico na justificativa, mencionando palavras-chave relevantes
- Se nenhum chunk for relevante, responda: "Nenhum chunk relevante"
- Justificativa máxima: 1 frase concisa
"""
    return prompt

def extrair_numero_chunk(resposta_openai):
    """Extrai o número do chunk da resposta da OpenAI"""
    padrao = r'Chunk\s*(\d+)'
    correspondencia = re.search(padrao, resposta_openai, re.IGNORECASE)
    
    if correspondencia:
        return int(correspondencia.group(1))
    
    # Verifica se não há chunk relevante
    if "nenhum" in resposta_openai.lower():
        return None
        
    return None

def consultar_openai(prompt):
    logger.info("Enviando prompt para OpenAI")
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.1,  # Pouca criatividade, mais focado
            timeout=30  # Timeout para evitar bloqueios
        )
        resposta = response.choices[0].message.content.strip()
        logger.info(f"Resposta OpenAI: {resposta}")
        return resposta
    except Exception as e:
        logger.error(f"Erro na API OpenAI: {e}")
        raise

@app.route('/chatgpt-rank', methods=['POST'])
def chatgpt_rank():
    try:
        logger.info("Recebida requisição para /chatgpt-rank")
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Dados JSON ausentes'}), 400
            
        question = data.get('question', '').strip()
        chunks = data.get('chunks', [])
        
        logger.info(f"Pergunta: {question}")
        logger.info(f"Quantidade de chunks: {len(chunks)}")
        
        if not question:
            logger.warning("Pergunta ausente na requisição!")
            return jsonify({'error': 'Pergunta é obrigatória'}), 400
            
        if not chunks or len(chunks) < 4:
            logger.warning("Quantidade insuficiente de chunks!")
            return jsonify({'error': 'São necessários 4 chunks'}), 400

        prompt = montar_prompt(question, chunks)
        resposta_openai = consultar_openai(prompt)
        
        # Extrai o número do chunk selecionado
        numero_chunk = extrair_numero_chunk(resposta_openai)
        
        # Prepara a resposta para o frontend
        resposta_final = {
            'analise': resposta_openai,
            'chunk_selecionado': None,
            'texto_chunk': None
        }
        
        # Se um chunk foi selecionado, adiciona suas informações
        if numero_chunk and 1 <= numero_chunk <= len(chunks):
            chunk_escolhido = chunks[numero_chunk - 1]  # -1 porque os arrays começam em 0
            resposta_final['chunk_selecionado'] = numero_chunk
            resposta_final['texto_chunk'] = chunk_escolhido.get('text', '')
            resposta_final['metadata'] = chunk_escolhido.get('metadata', {})
        
        logger.info(f"Resposta final para frontend: Chunk {numero_chunk} selecionado")
        return jsonify(resposta_final)
        
    except Exception as e:
        logger.error(f"Erro interno: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500