# Ponto — Lista de prospeção

Analisa um CV, procura vagas em várias fontes, guarda empresas numa lista de prospeção, descobre emails de contacto e prepara emails de candidatura com IA local.

## Requisitos
- Python 3.13, Node 20+, Docker
- IA: em local, [Ollama](https://ollama.com) com `qwen2.5:7b-instruct`; em produção, um fornecedor com API compatível com a OpenAI (recomendado: [Mistral](https://console.mistral.ai), servidores na UE)

## Primeira instalação
```powershell
docker compose up -d
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
copy .env.example .env
.\.venv\Scripts\python.exe -m alembic upgrade head
cd ..\frontend
npm install
ollama pull qwen2.5:7b-instruct
```

## Arrancar
```powershell
.\start.ps1
```
Frontend em http://localhost:5173 e API em http://localhost:8000/docs.

## Testes
```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest ..\tests -q
cd ..\frontend
npx tsc -b; npx eslint src
```

## Como funciona
- **Vagas:** Net-Empregos e ITJobs (Portugal), We Work Remotely, Remotive, Remote OK, Jobicy, Himalayas e Arbeitnow, em paralelo. O campo de localização (Portugal, Alemanha, …) define o mercado; as vagas já mostradas só são omitidas nesta sessão; empresas já na lista continuam de fora.
- **Emails:** procura em páginas do site da empresa (careers > geral), segue links de contacto, descodifica emails escondidos e, em último caso, usa um Chromium headless. Respeita o `robots.txt`.
- **IA:** toda a leitura do CV e os rascunhos passam por `backend/app/ai/llm.py`, que fala o formato Chat Completions da OpenAI. Mudar de fornecedor é mudar `LLM_BASE_URL`, `LLM_API_KEY` e `LLM_MODEL`. Em produção: `https://api.mistral.ai/v1` com `mistral-small-latest`.
- **Rascunhos:** a IA avalia a afinidade e escreve o email em PT ou EN, assinado com o nome do CV.
- **Contas:** login com Google (cookie de sessão `httpOnly`, revogável no logout), depois de aceitar os [termos](http://localhost:8000/termos) e a [privacidade](http://localhost:8000/privacidade). Cada utilizador tem a sua lista, o seu CV guardado (na base de dados) e o seu Gmail; o botão **Procurar novas vagas** repete a pesquisa com o CV guardado. No avatar podes exportar os dados (JSON) ou apagar a conta.
- **Limites por utilizador:** 10 análises e 30 rascunhos por hora, 30 procuras de email por hora e 25 envios em 24 horas (`backend/app/services/Quota.py`). Ao passar o limite a API responde 429 com a mensagem para o utilizador.
- **Empresas retiradas:** deixam de aparecer nas sugestões (reposição com «Mostrar de novo»).

## Envio por Gmail
1. Em https://console.cloud.google.com cria um projeto e ativa a **Gmail API**.
2. Ecrã de consentimento OAuth: tipo *Externo*. Deixa em *Testing* e adiciona cada email em *Test users* — `gmail.send` e `gmail.readonly` são âmbitos restritos; publicar o ecrã pede verificação da Google (e auditoria CASA), não basta um domínio HTTPS.
3. Preenche a política de privacidade e os termos com as URLs públicas da API: `https://api.seudominio.com/privacidade` e `https://api.seudominio.com/termos`.
4. Credenciais → *OAuth client ID* → *Web application*. Origens JavaScript autorizadas: o `FRONTEND_URL`. URIs de redirecionamento: em local `http://localhost:8000/google/callback` e `http://127.0.0.1:8000/google/callback`; em produção o valor exacto de `GOOGLE_REDIRECT_URI`.
5. Copia o Client ID e o Client Secret para `backend/.env` e reinicia o backend.
6. Na app, entra com Google e clica em **Ligar Gmail**. Se já estava ligado, desliga e volta a ligar. O CV anexado é o que carregaste na análise.

A app nunca envia sem confirmação. O refresh token fica cifrado (Fernet); a chave vem de `TOKEN_ENCRYPTION_KEY` ou de `backend/data/secret.key` (fora do git). Pedidos que alteram dados vindos de origens fora de `ALLOWED_ORIGINS` são recusados.

Em produção o backend usa `GOOGLE_REDIRECT_URI` (HTTPS) em vez do host interno do processo. URLs `https://` activam o cookie `Secure`; se o site e a API tiverem hosts diferentes, `SameSite=None`. O frontend de produção precisa de `VITE_API_URL` no build.

## Configuração (`backend/.env`)
`DATABASE_URL`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `FRONTEND_URL`, `TOKEN_ENCRYPTION_KEY`, `COOKIE_SECURE`, `COOKIE_SAMESITE`, `ALLOWED_ORIGINS`, `SESSION_DAYS`.

