import streamlit as st
import requests
import os
import json

# Controle de exibição dos dados do Qdrant
if 'show_qdrant' not in st.session_state:
    st.session_state['show_qdrant'] = False

if st.button("Ver dados do Qdrant"):
    st.session_state['show_qdrant'] = True
if st.session_state['show_qdrant']:
    with st.spinner("Consultando dados do Qdrant..."):
        try:
            response = requests.get("http://localhost:5000/qdrant-data", timeout=30)
            if response.status_code == 200:
                data = response.json()
                st.subheader("Resumo dos dados no Qdrant:")
                if not data:
                    st.info("Nenhum dado encontrado no Qdrant. O banco pode estar zerado ou a collection ainda não foi criada.")
                else:
                    if st.button("Ocultar dados do Qdrant"):
                        st.session_state['show_qdrant'] = False
                    st.code(json.dumps(data, indent=2, ensure_ascii=False), language="json")
            else:
                try:
                    data = response.json()
                    if 'error' in data:
                        st.warning(data['error'])
                    else:
                        st.error(f"Erro: {response.text}")
                except Exception:
                    st.error(f"Erro: {response.text}")
        except Exception as e:
            st.error(f"Erro ao consultar Qdrant: {e}. O banco pode estar zerado ou a collection não existe.")

st.title("Chatbot RAG - JIRA.csv (Qdrant)")

if 'history' not in st.session_state:
    st.session_state['history'] = []

if 'last_chunks' not in st.session_state:
    st.session_state['last_chunks'] = []

if 'chatgpt_response' not in st.session_state:
    st.session_state['chatgpt_response'] = None

if 'selected_chunk' not in st.session_state:
    st.session_state['selected_chunk'] = None

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5000/chat")

user_input = st.text_input("Digite sua pergunta ou chave do card:")

if st.button("Enviar") and user_input:
    with st.spinner("Consultando backend..."):
        try:
            response = requests.post(
                BACKEND_URL,
                json={"question": user_input},
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                chunks = data.get("chunks", [])
                mode = data.get("mode", "?")
                st.session_state['last_chunks'] = chunks
                st.session_state['selected_chunk'] = None  # Resetar seleção anterior
                st.session_state['chatgpt_response'] = None  # Resetar resposta ChatGPT
                answer = f"Modo de busca: {mode}"
            else:
                answer = f"Erro: {response.text}"
                st.session_state['last_chunks'] = []
                st.session_state['selected_chunk'] = None
                st.session_state['chatgpt_response'] = None
        except Exception as e:
            answer = f"Erro de conexão: {e}"
            st.session_state['last_chunks'] = []
            st.session_state['selected_chunk'] = None
            st.session_state['chatgpt_response'] = None
        if 'history' not in st.session_state:
            st.session_state['history'] = []
        st.session_state['history'].append((user_input, answer))

for q, a in reversed(st.session_state['history']):
    st.markdown(f"**Você:** {q}")

# Exibe os chunks como cards grandes
if st.session_state['last_chunks']:
    chunks = st.session_state['last_chunks']
    st.markdown("### Chunks encontrados:")
    cols = st.columns(len(chunks))
    
    for idx, (col, chunk) in enumerate(zip(cols, chunks)):
        is_selected = (idx + 1 == st.session_state.get('selected_chunk', None))
        border_color = "#28a745" if is_selected else "#4F8BF9"
        background = "#f0fff4" if is_selected else "#F5F8FF"
        title_color = "#28a745" if is_selected else "#4F8BF9"
        
        with col:
            with st.container():
                st.markdown(f"""
                <div style='border:2px solid {border_color}; border-radius:12px; padding:18px; margin-bottom:10px; background:{background}; min-height:220px; display:flex; flex-direction:column; justify-content:space-between;'>
                    <div style='font-weight:bold; color:{title_color}; font-size:1.1em;'>Chunk #{idx+1} | Key: {chunk.get('key','')}</div>
                    <div style='margin:10px 0 10px 0; font-size:0.95em; color:#222;'>""" + (chunk.get('text','')[:220] + ("..." if len(chunk.get('text','')) > 220 else "")) + """</div>
                    <div style='font-size:0.85em; color:#888;'>Overlap: """ + (chunk.get('overlap','')[:60] + ("..." if len(chunk.get('overlap','')) > 60 else "")) + """</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Botão para abrir modal
                if st.button(f"Ver detalhes do Chunk #{idx+1}", key=f"chunkbtn_{idx}"):
                    st.session_state['show_modal'] = idx

# Modal detalhado
if 'show_modal' in st.session_state:
    idx = st.session_state['show_modal']
    if idx < len(st.session_state['last_chunks']):
        chunk = st.session_state['last_chunks'][idx]
        st.markdown(f"## Detalhes do Chunk #{idx+1}")
        st.markdown(f"**ID:** {chunk.get('id')}")
        st.markdown(f"**Key:** {chunk.get('key','')}")
        st.markdown(f"**Texto:**\n{chunk.get('text','')}")
        st.markdown(f"**Overlap:**\n{chunk.get('overlap','')}")
        if 'score' in chunk:
            st.markdown(f"**Score:** {chunk['score']:.3f}")
        if st.button("Fechar", key="close_modal"):
            del st.session_state['show_modal']

# Botão para consulta via ChatGPT
if st.session_state['last_chunks'] and user_input:
    if st.button("Perguntar para IA (ChatGPT)"):
        with st.spinner("Consultando ChatGPT..."):
            try:
                response = requests.post(
                    "http://localhost:5000/chatgpt-rank",
                    json={"question": user_input, "chunks": st.session_state['last_chunks']},
                    timeout=60
                )
                
                if response.status_code == 200:
                    data = response.json()
                    st.session_state['chatgpt_response'] = data
                    
                    # Exibe a análise da IA
                    st.success(f"**Análise da IA:** {data.get('analise', 'Sem resposta da IA.')}")
                    
                    # Exibe o chunk selecionado se houver
                    chunk_selecionado = data.get('chunk_selecionado')
                    if chunk_selecionado is not None:
                        st.session_state['selected_chunk'] = chunk_selecionado
                        st.markdown("---")
                        st.markdown(f"### 📌 Chunk Selecionado: #{chunk_selecionado}")
                        
                        # Encontra o chunk correspondente na lista
                        chunk_idx = chunk_selecionado - 1
                        if 0 <= chunk_idx < len(st.session_state['last_chunks']):
                            chunk_original = st.session_state['last_chunks'][chunk_idx]
                            
                            # Exibe como card especial
                            st.markdown(f"""
                            <div style='border:3px solid #28a745; border-radius:12px; padding:18px; margin-bottom:10px; background:#f0fff4; min-height:220px;'>
                                <div style='font-weight:bold; color:#28a745; font-size:1.2em;'>⭐ MELHOR CHUNK #{chunk_selecionado}</div>
                                <div style='margin:10px 0 10px 0; font-size:0.95em; color:#222;'>""" + 
                                (data.get('texto_chunk', '')[:300] + ("..." if len(data.get('texto_chunk', '')) > 300 else "")) + 
                                """</div>
                                <div style='font-size:0.85em; color:#666;'>Key: """ + chunk_original.get('key','N/A') + """</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Botão para ver detalhes completos
                            if st.button(f"Ver texto completo do Chunk #{chunk_selecionado}", key=f"full_chunk_{chunk_selecionado}"):
                                st.text_area(f"Texto completo - Chunk #{chunk_selecionado}", 
                                           data.get('texto_chunk', ''), 
                                           height=300)
                    
                    # Se nenhum chunk foi selecionado
                    elif data.get('analise', '').lower().find('nenhum') != -1:
                        st.warning("A IA não encontrou nenhum chunk relevante para sua pergunta.")
                        st.session_state['selected_chunk'] = None
                        
                else:
                    try:
                        error_data = response.json()
                        st.error(f"Erro: {error_data.get('error', 'Erro desconhecido')}")
                    except:
                        st.error(f"Erro HTTP {response.status_code}: {response.text}")
                    
            except Exception as e:
                st.error(f"Erro de conexão com ChatGPT: {e}")

# Exibir resposta do ChatGPT persistente se existir
if st.session_state['chatgpt_response']:
    data = st.session_state['chatgpt_response']
    st.markdown("---")
    st.markdown("### 📋 Resposta da IA")
    st.info(f"**Análise:** {data.get('analise', '')}")
    
    chunk_selecionado = data.get('chunk_selecionado')
    if chunk_selecionado is not None:
        st.markdown(f"**Chunk Selecionado:** #{chunk_selecionado}")
        
        # Botão para ver texto completo
        if st.button("📄 Ver Texto Completo do Chunk Selecionado", key="show_full_chunk"):
            st.text_area("Texto completo do chunk selecionado", 
                       data.get('texto_chunk', ''), 
                       height=300)

st.markdown("---")
st.markdown("### Carregar novo arquivo JIRA.xml e atualizar base de dados")
uploaded_file = st.file_uploader("Selecione o arquivo JIRA.xml para upload", type=["xml"])
if uploaded_file is not None:
    if st.button("Processar e salvar no banco vetorial"):
        with st.spinner("Enviando arquivo para backend e processando..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                response = requests.post("http://localhost:5000/upload-jira", files=files, timeout=120)
                if response.status_code == 200:
                    st.success("Arquivo processado e base vetorial atualizada com sucesso!")
                    # Limpar estado após upload
                    st.session_state['last_chunks'] = []
                    st.session_state['selected_chunk'] = None
                    st.session_state['chatgpt_response'] = None
                else:
                    st.error(f"Erro ao processar arquivo: {response.text}")
            except Exception as e:
                st.error(f"Erro de conexão ao enviar arquivo: {e}")