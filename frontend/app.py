import streamlit as st
import requests
import os
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
import tempfile

# Configuração da página
st.set_page_config(
    page_title="Sistema RAG - Exploração de Dados JIRA",
    page_icon="🔍",
    layout="wide"
)

# Título e descrição
st.title("🔍 Sistema RAG - Exploração de Dados JIRA com Qdrant")
st.markdown("""
Esta interface permite explorar o funcionamento do sistema RAG (Retrieval Augmented Generation) 
integrado com IA para análise e tomada de decisão baseada em dados do JIRA.
""")

# Sidebar para controles
with st.sidebar:
    st.header("Controles do Sistema")
    
    # Controle de exibição dos dados do Qdrant
    if st.button("🔄 Atualizar Visualização do Qdrant"):
        with st.spinner("Consultando dados do Qdrant..."):
            try:
                response = requests.get("http://localhost:5000/qdrant-data", timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    st.session_state['qdrant_data'] = data
                    st.success("Dados do Qdrant atualizados!")
                else:
                    st.error("Erro ao consultar Qdrant")
            except Exception as e:
                st.error(f"Erro de conexão: {e}")
    
    st.markdown("---")
    st.subheader("Upload de Dados")
    uploaded_file = st.file_uploader("Selecione arquivo JIRA.xml", type=["xml"])
    if uploaded_file is not None and st.button("Processar e Indexar no Qdrant"):
        with st.spinner("Processando e indexando dados..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                response = requests.post("http://localhost:5000/upload-jira", files=files, timeout=120)
                if response.status_code == 200:
                    st.success("Dados processados e indexados com sucesso!")
                    # Limpar estado após upload
                    if 'last_chunks' in st.session_state:
                        del st.session_state['last_chunks']
                    if 'selected_chunk' in st.session_state:
                        del st.session_state['selected_chunk']
                    if 'analysis_result' in st.session_state:
                        del st.session_state['analysis_result']
                else:
                    st.error(f"Erro no processamento: {response.text}")
            except Exception as e:
                st.error(f"Erro de conexão: {e}")

# Abas para diferentes funcionalidades
tab1, tab2, tab3, tab4 = st.tabs(["🔎 Consulta e Análise", "📊 Dados do Qdrant", "🌐 Importar do JIRA", "📋 Sobre o Sistema"])

with tab1:
    st.header("Consulta e Análise de Dados")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        query_input = st.text_area(
            "Digite sua consulta ou chave do card JIRA:",
            height=100,
            placeholder="Ex: 'Quais são os problemas críticos reportados no último mês?' ou 'PROJ-123'"
        )
        
        if st.button("🔍 Executar Consulta", type="primary"):
            if query_input:
                with st.spinner("Processando consulta..."):
                    try:
                        response = requests.post(
                            "http://localhost:5000/chat",
                            json={"question": query_input},
                            timeout=30
                        )
                        if response.status_code == 200:
                            data = response.json()
                            st.session_state['last_chunks'] = data.get("chunks", [])
                            st.session_state['query_mode'] = data.get("mode", "desconhecido")
                            st.session_state['query_input'] = query_input
                        else:
                            st.error(f"Erro na consulta: {response.text}")
                    except Exception as e:
                        st.error(f"Erro de conexão: {e}")
            else:
                st.warning("Por favor, digite uma consulta.")
    
    with col2:
        st.markdown("### Modo de Operação")
        if 'query_mode' in st.session_state:
            mode = st.session_state['query_mode']
            if mode == "similarity":
                st.info("🔍 Modo Similaridade")
                st.caption("Buscando por conteúdo similar à consulta")
            elif mode == "keyword":
                st.info("🔑 Modo Palavra-chave")
                st.caption("Buscando por correspondência exata de termos")
            else:
                st.info(f"Modo: {mode}")
        else:
            st.info("Aguardando consulta...")
    
    # Exibir resultados da consulta
    if 'last_chunks' in st.session_state and st.session_state['last_chunks']:
        chunks = st.session_state['last_chunks']
        st.subheader(f"Resultados Encontrados: {len(chunks)} chunks")
        
        # Análise com IA
        if st.button("🤖 Analisar Resultados com IA"):
            with st.spinner("Solicitando análise da IA..."):
                try:
                    response = requests.post(
                        "http://localhost:5000/chatgpt-rank",
                        json={
                            "question": st.session_state.get('query_input', ''),
                            "chunks": chunks
                        },
                        timeout=60
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state['analysis_result'] = data
                    else:
                        st.error("Erro na análise com IA")
                except Exception as e:
                    st.error(f"Erro de conexão com serviço de IA: {e}")
        
        # Exibir chunks
        for idx, chunk in enumerate(chunks):
            is_selected = st.session_state.get('analysis_result', {}).get('chunk_selecionado') == idx + 1
            
            with st.expander(f"Chunk #{idx+1} | Key: {chunk.get('key', 'N/A')} | Score: {chunk.get('score', 0):.3f}", 
                           expanded=is_selected):
                col_a, col_b = st.columns([3, 1])
                
                with col_a:
                    st.markdown("**Texto:**")
                    st.write(chunk.get('text', ''))
                
                with col_b:
                    st.markdown("**Metadados:**")
                    st.write(f"Key: {chunk.get('key', 'N/A')}")
                    if 'score' in chunk:
                        st.write(f"Score: {chunk['score']:.3f}")
                    st.write(f"ID: {chunk.get('id', 'N/A')}")
        
        # Exibir análise da IA se disponível
        if 'analysis_result' in st.session_state:
            st.markdown("---")
            st.subheader("📋 Análise da IA")
            
            analysis = st.session_state['analysis_result']
            selected_chunk = analysis.get('chunk_selecionado')
            
            if selected_chunk is not None:
                st.success(f"**Chunk mais relevante selecionado:** #{selected_chunk}")
                st.info(f"**Análise:** {analysis.get('analise', '')}")
            else:
                st.warning("A IA não identificou um chunk claramente relevante para esta consulta.")
                st.info(f"**Análise:** {analysis.get('analise', '')}")

with tab2:
    st.header("Dados Armazenados no Qdrant")
    
    if 'qdrant_data' in st.session_state:
        data = st.session_state['qdrant_data']
        
        if not data:
            st.info("Nenhum dado encontrado no Qdrant.")
        else:
            st.json(data)
            
            # Estatísticas básicas
            if isinstance(data, list):
                st.metric("Total de chunks no Qdrant", len(data))
            elif isinstance(data, dict) and 'collections' in data:
                # Supondo estrutura específica de resposta do Qdrant
                collections = data['collections']
                st.metric("Collections no Qdrant", len(collections))
                
                for col_name, col_data in collections.items():
                    with st.expander(f"Collection: {col_name}"):
                        st.json(col_data)
    else:
        st.info("Use o botão 'Atualizar Visualização do Qdrant' na sidebar para carregar os dados.")

with tab3:
    st.header("🌐 Importar Dados Diretamente do JIRA")
    
    st.markdown("""
    ### Importação Automática do JIRA
    Utilize uma consulta JQL para importar dados diretamente do JIRA. 
    O backend já está configurado com as credenciais de conexão.
    """)
    
    # Apenas UM formulário com chave única
    with st.form("jira_direct_import_xml_form"):
        jql_query = st.text_area(
            "Consulta JQL", 
            height=100,
            placeholder="project = PROJ AND status != Done ORDER BY created DESC",
            help="Consulta JQL para filtrar os itens do JIRA"
        )
        
        max_results = st.number_input(
            "Máximo de resultados", 
            min_value=1, 
            max_value=1000, 
            value=100,
            help="Número máximo de issues para importar"
        )
        
        submitted = st.form_submit_button("🚀 Importar do JIRA e Indexar")
        
        if submitted:
            if not jql_query:
                st.error("Por favor, informe uma consulta JQL.")
            else:
                with st.spinner("Conectando ao JIRA e importando dados..."):
                    try:
                        # Chamar o backend para importar do JIRA
                        response = requests.post(
                            "http://localhost:5000/import-jira",
                            json={
                                "jql_query": jql_query,
                                "max_results": max_results
                            },
                            timeout=120
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            st.success(f"✅ Importação concluída com sucesso!")
                            st.info(f"**Resultado:** {result.get('message', 'Dados importados e indexados')}")
                            
                            if 'stats' in result:
                                stats = result['stats']
                                col1, col2, col3 = st.columns(3)
                                col1.metric("Issues Encontradas", stats.get('total_issues', 0))
                                col2.metric("Issues Importadas", stats.get('imported_issues', 0))
                                col3.metric("Chunks Criados", stats.get('chunks_created', 0))
                            
                            # Limpar estado após importação bem-sucedida
                            if 'last_chunks' in st.session_state:
                                del st.session_state['last_chunks']
                            if 'selected_chunk' in st.session_state:
                                del st.session_state['selected_chunk']
                            if 'analysis_result' in st.session_state:
                                del st.session_state['analysis_result']
                                
                        elif response.status_code == 400:
                            error_data = response.json()
                            st.error(f"❌ Erro na consulta JQL: {error_data.get('error', 'Erro desconhecido')}")
                        elif response.status_code == 500:
                            error_data = response.json()
                            st.error(f"🔌 Erro de conexão com JIRA: {error_data.get('error', 'Verifique as configurações do backend')}")
                        else:
                            st.error(f"⚠️ Erro inesperado: {response.status_code} - {response.text}")
                    
                    except requests.exceptions.ConnectionError:
                        st.error("🔌 Não foi possível conectar ao backend. Verifique se o servidor está rodando.")
                    except requests.exceptions.Timeout:
                        st.error("⏰ Timeout na conexão com o backend. A importação pode ter levado muito tempo.")
                    except Exception as e:
                        st.error(f"❌ Erro durante a importação: {str(e)}")
    st.header("🌐 Importar Dados Diretamente do JIRA")
    
    st.markdown("""
    ### Importação Automática do JIRA
    Utilize uma consulta JQL para importar dados diretamente do JIRA. 
    O backend já está configurado com as credenciais de conexão.
    """)
    
    # Usar uma chave única para este formulário específico
    with st.form("jira_direct_import_form"):
        jql_query = st.text_area(
            "Consulta JQL", 
            height=100,
            placeholder="project = PROJ AND status != Done ORDER BY created DESC",
            help="Consulta JQL para filtrar os itens do JIRA"
        )
        
        max_results = st.number_input(
            "Máximo de resultados", 
            min_value=1, 
            max_value=1000, 
            value=100,
            help="Número máximo de issues para importar"
        )
        
        submitted = st.form_submit_button("🚀 Importar do JIRA e Indexar")
        
        if submitted:
            if not jql_query:
                st.error("Por favor, informe uma consulta JQL.")
            else:
                with st.spinner("Conectando ao JIRA e importando dados..."):
                    try:
                        # Chamar o backend para importar do JIRA
                        response = requests.post(
                            "http://localhost:5000/import-jira",
                            json={
                                "jql_query": jql_query,
                                "max_results": max_results
                            },
                            timeout=120
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            st.success(f"✅ Importação concluída com sucesso!")
                            st.info(f"**Resultado:** {result.get('message', 'Dados importados e indexados')}")
                            
                            if 'stats' in result:
                                stats = result['stats']
                                col1, col2, col3 = st.columns(3)
                                col1.metric("Issues Encontradas", stats.get('total_issues', 0))
                                col2.metric("Issues Importadas", stats.get('imported_issues', 0))
                                col3.metric("Chunks Criados", stats.get('chunks_created', 0))
                            
                            # Limpar estado após importação bem-sucedida
                            if 'last_chunks' in st.session_state:
                                del st.session_state['last_chunks']
                            if 'selected_chunk' in st.session_state:
                                del st.session_state['selected_chunk']
                            if 'analysis_result' in st.session_state:
                                del st.session_state['analysis_result']
                                
                        elif response.status_code == 400:
                            error_data = response.json()
                            st.error(f"❌ Erro na consulta JQL: {error_data.get('error', 'Erro desconhecido')}")
                        elif response.status_code == 500:
                            error_data = response.json()
                            st.error(f"🔌 Erro de conexão com JIRA: {error_data.get('error', 'Verifique as configurações do backend')}")
                        else:
                            st.error(f"⚠️ Erro inesperado: {response.status_code} - {response.text}")
                    
                    except requests.exceptions.ConnectionError:
                        st.error("🔌 Não foi possível conectar ao backend. Verifique se o servidor está rodando.")
                    except requests.exceptions.Timeout:
                        st.error("⏰ Timeout na conexão com o backend. A importação pode ter levado muito tempo.")
                    except Exception as e:
                        st.error(f"❌ Erro durante a importação: {str(e)}")
    st.header("🌐 Importar Dados Diretamente do JIRA")
    
    st.markdown("""
    ### Importação Automática do JIRA
    Utilize uma consulta JQL para importar dados diretamente do JIRA. 
    O backend já está configurado com as credenciais de conexão.
    """)
    
    with st.form("jira_import_for_xml_form"):
        jql_query = st.text_area(
            "Consulta JQL", 
            height=100,
            placeholder="project = PROJ AND status != Done ORDER BY created DESC",
            help="Consulta JQL para filtrar os itens do JIRA"
        )
        
        max_results = st.number_input(
            "Máximo de resultados", 
            min_value=1, 
            max_value=1000, 
            value=100,
            help="Número máximo de issues para importar"
        )
        
        submitted = st.form_submit_button("🚀 Importar do JIRA e Indexar")
        
        if submitted:
            if not jql_query:
                st.error("Por favor, informe uma consulta JQL.")
            else:
                with st.spinner("Conectando ao JIRA e importando dados..."):
                    try:
                        # Chamar o backend para importar do JIRA
                        response = requests.post(
                            "http://localhost:5000/import-jira",
                            json={
                                "jql_query": jql_query,
                                "max_results": max_results
                            },
                            timeout=120
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            st.success(f"✅ Importação concluída com sucesso!")
                            st.info(f"**Resultado:** {result.get('message', 'Dados importados e indexados')}")
                            
                            if 'stats' in result:
                                stats = result['stats']
                                col1, col2, col3 = st.columns(3)
                                col1.metric("Issues Encontradas", stats.get('total_issues', 0))
                                col2.metric("Issues Importadas", stats.get('imported_issues', 0))
                                col3.metric("Chunks Criados", stats.get('chunks_created', 0))
                            
                            # Limpar estado após importação bem-sucedida
                            if 'last_chunks' in st.session_state:
                                del st.session_state['last_chunks']
                            if 'selected_chunk' in st.session_state:
                                del st.session_state['selected_chunk']
                            if 'analysis_result' in st.session_state:
                                del st.session_state['analysis_result']
                                
                        elif response.status_code == 400:
                            error_data = response.json()
                            st.error(f"❌ Erro na consulta JQL: {error_data.get('error', 'Erro desconhecido')}")
                        elif response.status_code == 500:
                            error_data = response.json()
                            st.error(f"🔌 Erro de conexão com JIRA: {error_data.get('error', 'Verifique as configurações do backend')}")
                        else:
                            st.error(f"⚠️ Erro inesperado: {response.status_code} - {response.text}")
                    
                    except requests.exceptions.ConnectionError:
                        st.error("🔌 Não foi possível conectar ao backend. Verifique se o servidor está rodando.")
                    except requests.exceptions.Timeout:
                        st.error("⏰ Timeout na conexão com o backend. A importação pode ter levado muito tempo.")
                    except Exception as e:
                        st.error(f"❌ Erro durante a importação: {str(e)}")

    st.header("🌐 Importar Dados Diretamente do JIRA")
    
    st.markdown("""
    ### Importação Automática do JIRA
    Utilize uma consulta JQL para importar dados diretamente do JIRA. 
    O backend já está configurado com as credenciais de conexão.
    """)
    
    with st.form("jira_import_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            jql_query = st.text_area(
                "Consulta JQL", 
                height=100,
                placeholder="project = PROJ AND issuetype = REQ ORDER BY created DESC",
                help="Consulta JQL para filtrar os itens do JIRA"
            )
            
        with col2:
            max_results = st.number_input(
                "Máximo de resultados", 
                min_value=1, 
                max_value=1000, 
                value=100,
                help="Número máximo de issues para importar"
            )
            
            issue_type = st.selectbox(
                "Tipo de Item",
                options=["REQ", "BUG", "TASK", "STORY", "EPIC", "SUB-TASK", "INCIDENT"],
                index=0,
                help="Tipo de item do JIRA para filtrar"
            )
        
        submitted = st.form_submit_button("🚀 Importar do JIRA e Indexar")
        
        if submitted:
            if not jql_query:
                st.error("Por favor, informe uma consulta JQL.")
            else:
                with st.spinner("Conectando ao JIRA e importando dados..."):
                    try:
                        # Chamar o backend para importar do JIRA
                        response = requests.post(
                            "http://localhost:5000/import-jira",
                            json={
                                "jql_query": jql_query,
                                "max_results": max_results,
                                "issue_type": issue_type
                            },
                            timeout=120
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            st.success(f"✅ Importação concluída com sucesso!")
                            st.info(f"**Resultado:** {result.get('message', 'Dados importados e indexados')}")
                            
                            if 'stats' in result:
                                stats = result['stats']
                                col1, col2, col3 = st.columns(3)
                                col1.metric("Issues Encontradas", stats.get('total_issues', 0))
                                col2.metric("Issues Importadas", stats.get('imported_issues', 0))
                                col3.metric("Chunks Criados", stats.get('chunks_created', 0))
                            
                            # Limpar estado após importação bem-sucedida
                            if 'last_chunks' in st.session_state:
                                del st.session_state['last_chunks']
                            if 'selected_chunk' in st.session_state:
                                del st.session_state['selected_chunk']
                            if 'analysis_result' in st.session_state:
                                del st.session_state['analysis_result']
                                
                        elif response.status_code == 400:
                            error_data = response.json()
                            st.error(f"❌ Erro na consulta JQL: {error_data.get('error', 'Erro desconhecido')}")
                        elif response.status_code == 500:
                            error_data = response.json()
                            st.error(f"🔌 Erro de conexão com JIRA: {error_data.get('error', 'Verifique as configurações do backend')}")
                        else:
                            st.error(f"⚠️ Erro inesperado: {response.status_code} - {response.text}")
                    
                    except requests.exceptions.ConnectionError:
                        st.error("🔌 Não foi possível conectar ao backend. Verifique se o servidor está rodando.")
                    except requests.exceptions.Timeout:
                        st.error("⏰ Timeout na conexão com o backend. A importação pode ter levado muito tempo.")
                    except Exception as e:
                        st.error(f"❌ Erro durante a importação: {str(e)}")

with tab4:
    st.header("Sobre o Sistema RAG")
    
    st.markdown("""
    ### Como funciona este sistema:
    
    1. **Upload de Dados**: Os arquivos JIRA.xml são processados e transformados em chunks vetorizados
    2. **Importação Direta**: Conexão direta com JIRA via API para importar dados automaticamente
    3. **Armazenamento**: Os chunks são indexados no Qdrant, um banco de dados vetorial
    4. **Consulta**: As consultas são convertidas para vetores e comparadas com os chunks armazenados
    5. **Recuperação**: Os chunks mais relevantes são recuperados com base na similaridade
    6. **Análise com IA**: Opcionalmente, a IA analisa os resultados para identificar o chunk mais relevante
    
    ### Tecnologias utilizadas:
    - **Qdrant**: Banco de dados vetorial para armazenamento e recuperação semântica
    - **JIRA API**: Integração direta com o JIRA Cloud/Server
    - **Modelos de IA**: Para análise e rankeamento dos resultados
    - **Streamlit**: Interface para exploração e visualização
    - **FastAPI/Flask**: Backend para processamento das requisições
    
    ### Casos de uso:
    - Exploração de dados históricos do JIRA
    - Identificação de problemas similares
    - Análise de tendências e padrões
    - Tomada de decisão baseada em dados históricos
    - Importação automatizada de requisitos e issues
    """)

# Rodapé
st.markdown("---")
st.caption("Sistema RAG para exploração de dados JIRA | Desenvolvido para demonstração de conceito")