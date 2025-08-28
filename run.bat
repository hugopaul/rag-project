@echo off
REM Para containers Docker apenas se existirem (para outros serviços)
echo Parando containers Docker existentes...
docker-compose down

REM Inicia apenas serviços Docker necessários (como banco de dados)
echo Iniciando servicos Docker...
docker-compose up -d db redis  # ajuste para seus serviços

REM Aguarda alguns segundos para os serviços Docker iniciarem
ping 127.0.0.1 -n 5 > nul

REM Inicia o backend Flask manualmente
echo Iniciando backend Flask...
start "backend" cmd /k "cd backend && python api.py"

REM Aguarda alguns segundos para o backend subir
ping 127.0.0.1 -n 5 > nul

REM Inicia o frontend Streamlit manualmente
echo Iniciando frontend Streamlit...
start "frontend" cmd /k "python -m streamlit run frontend/app.py"

echo Aplicacao iniciada com sucesso!