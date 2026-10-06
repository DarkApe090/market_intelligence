# Ponto — Lista de prospeção

Analisa um CV, procura vagas em várias fontes, guarda empresas numa lista de prospeção, descobre emails de contacto e prepara emails de candidatura com IA local.

## Requisitos
- Python 3.13, Node 20+, Docker, [Ollama](https://ollama.com) (modelo `qwen2.5:7b-instruct`)

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
- **Vagas:** 5 fontes pesquisadas em paralelo; só ficam vagas com competências do CV.
- **Emails:** procura em páginas do site da empresa (careers > geral), segue links de contacto, descodifica emails escondidos e, em último caso, usa um Chromium headless. Respeita o `robots.txt`.
- **Rascunhos:** LangGraph + Ollama avaliam a afinidade e escrevem o email em PT ou EN, assinado com o nome do CV.
- **Contas:** login com Google (cookie de sessão `httpOnly`, revogável no logout). Cada utilizador tem a sua lista, o seu CV guardado (na base de dados) e o seu Gmail; o botão **Procurar novas vagas** repete a pesquisa com o CV guardado.
- **Empresas retiradas:** deixam de aparecer nas sugestões (reposição com «Mostrar de novo»).

## Envio por Gmail (opcional)
1. Em https://console.cloud.google.com cria um projeto e ativa a **Gmail API**.
2. Ecrã de consentimento OAuth: tipo *Externo*, estado *Testing*, e adiciona o teu email em *Test users*.
3. Credenciais → *OAuth client ID* → tipo *Web application* → URI de redirecionamento autorizado: `http://localhost:8000/google/callback`.
4. Copia o Client ID e o Client Secret para `backend/.env` (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`) e reinicia o backend.
5. Na app, entra com Google e clica em **Ligar Gmail** (topo) para autorizar o envio. O CV anexado é o que carregaste na análise.
6. Em modo *Testing*, adiciona cada utilizador em *Utilizadores de teste*.

A app só pede permissão para enviar emails e nunca envia sem confirmação. O refresh token fica cifrado (Fernet) na base de dados; a chave vem de `TOKEN_ENCRYPTION_KEY` ou é gerada em `backend/data/secret.key` (fora do git). Pedidos que alteram dados vindos de origens fora de `ALLOWED_ORIGINS` são recusados; em produção define `COOKIE_SECURE=true` (HTTPS).

## Configuração (`backend/.env`)
`DATABASE_URL`, `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `TOKEN_ENCRYPTION_KEY`, `COOKIE_SECURE`, `ALLOWED_ORIGINS`, `SESSION_DAYS`.

