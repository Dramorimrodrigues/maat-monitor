# THEMIS Monitor — Especificação de Design (v1.0.0)

Data: 2026-09-16 · Autor: Márcio Luis Amorim (com Claude) · Origem: OGUM v2.0 (uso interno)

## 1. Objetivo

Transformar o OGUM (ferramenta interna do escritório) no **THEMIS Monitor**, produto
open-source de monitoramento de processos judiciais via API pública DataJud/CNJ,
com qualidade de engenharia sênior: um único motor, testes automatizados, CI,
multiplataforma, documentação e apresentação prontas para ganhar adoção no GitHub.

A pasta OGUM original **não é alterada**. O THEMIS nasce em
`_PROJETOS-TECH/themis-monitor/` e vai para o repositório privado
`Dramorimrodrigues/themis-monitor`.

## 2. Decisões já tomadas

| Tema | Decisão |
|---|---|
| Nome público | THEMIS (deusa grega da justiça). Internamente o Márcio continua usando OGUM. |
| Licença | MIT com `Copyright (c) 2026 Márcio Luis Amorim`. |
| Propriedade intelectual | Aviso de copyright no LICENSE, no cabeçalho de todo `.py`, no rodapé do painel/relatório/e-mail e na seção "Autoria" do README. |
| Identidade | Produto da comunidade criado por advogado praticante; o escritório aparece só como crédito. |
| Repositório | Privado agora; o Márcio torna público após revisar. |
| Dados reais | `config.ini`, `processos.txt`, `*.db`, `backups/`, `relatorios/` nunca entram no git. |

## 3. Arquitetura

### 3.1 Estrutura do repositório

```
themis-monitor/
├── themis/                     pacote Python (motor único)
│   ├── __init__.py             __version__, __author__, __copyright__
│   ├── constantes.py           tribunais (TODOS os que o DataJud expõe), palavras-chave, prazos
│   ├── cnj.py                  limpar, formatar, validar dígito verificador, identificar tribunal
│   ├── analise.py              normalizar, urgência, prazo estimado, dias_desde, formatadores
│   ├── config.py               caminhos, carregar_config(), carregar_processos(), adicionar_processos()
│   ├── banco.py                schema, salvar_resultado(), ler_processos(), histórico, backup
│   ├── datajud.py              cliente HTTP da API (verify=True sempre, timeout, erros tipados)
│   ├── notificacoes.py         e-mail SMTP e WhatsApp (CallMeBot)
│   ├── relatorio.py            CSS/JS compartilhados, cards HTML, relatório HTML, CSV
│   ├── painel.py               servidor HTTP local (127.0.0.1), rotas /api/*
│   ├── descoberta_oab.py       guia de descoberta por OAB (portais + extrator de CNJ)
│   └── cli.py                  `python themis.py <comando>`
├── themis.py                   ponto de entrada (`monitorar | painel | consultar | testar | oab`)
├── tests/                      pytest — sem rede, banco em memória
├── monitorar.bat  painel.bat  consultar.bat  testar.bat  buscar-oab.bat  instalar.bat
├── themis.sh                   lançador Mac/Linux (mesmos comandos)
├── config.example.ini          modelo sem dados pessoais
├── processos.example.txt       modelo com CNJ fictício
├── requirements.txt            requests, truststore
├── requirements-dev.txt        pytest, ruff
├── pyproject.toml              metadados + config ruff/pytest
├── .gitignore  .editorconfig
├── .github/workflows/ci.yml    pytest + ruff em Ubuntu e Windows, Python 3.9–3.13
├── .github/ISSUE_TEMPLATE/     bug.yml, feature.yml
├── README.md (pt-BR)  README.en.md  LICENSE  CONTRIBUTING.md  SECURITY.md  CHANGELOG.md
└── docs/screenshots/           painel.png, relatorio.png, demo.gif
```

### 3.2 Fluxo de dados

```
processos.txt ──► config.carregar_processos()
                          │
                          ▼
              cnj.identificar_tribunal() ──► datajud.consultar()  (HTTPS, chave pública CNJ)
                                                      │
                                                      ▼
                                         banco.salvar_resultado()  (SQLite themis.db)
                                                      │  detecta movimentos novos
                          ┌───────────────────────────┼──────────────────────┐
                          ▼                           ▼                      ▼
              relatorio.gerar_html/csv()     painel (HTTP local)     notificacoes (e-mail/WhatsApp)
```

### 3.3 O que muda em relação ao OGUM

1. **Motor único.** `ogum.py` e `servidor.py` duplicavam ~40% do código (CNJ, DataJud,
   banco, urgência, cards). Tudo vai para o pacote `themis/`; painel e relatório
   consomem as mesmas funções. Corrige divergências existentes (listas de palavras-chave
   diferentes nos dois arquivos; `execucao fiscal` e `pericia` só existiam em um deles).
2. **Validação de dígito verificador CNJ** (Resolução CNJ 65/2008, módulo 97). Número
   digitado errado é recusado antes de bater na API, com mensagem clara.
3. **Cobertura completa de tribunais**: todos os TJs (27), TRFs 1–6, TRTs 1–24,
   STF/STJ/TST/TSE/STM, TREs e TJMs — gerados a partir do padrão de alias do DataJud.
4. **Primeira execução amigável**: se `config.ini`/`processos.txt` não existirem, o
   THEMIS cria a partir dos `.example` e avisa.
5. **Multiplataforma**: `.bat` (Windows, clique duplo) e `themis.sh` (Mac/Linux).
6. **Testes + CI**: pytest cobrindo CNJ, análise, banco, DataJud (mock), painel
   (handler em porta efêmera), relatório, CSV. GitHub Actions roda em cada push.
7. **Segurança preservada e documentada**: servidor só em 127.0.0.1 com checagem de
   Host/Origin, JSON limitado a 1 MB, SQL parametrizado, `html.escape` em tudo que
   vem do tribunal, proteção contra fórmulas em CSV, SSL sempre validado,
   chave DataJud documentada como pública oficial do CNJ.
8. **Marca**: THEMIS em todos os textos; rodapé "THEMIS © 2026 Márcio Luis Amorim".

### 3.4 O que NÃO muda (mantido de propósito)

- Zero framework web (http.server da stdlib). Dependências: só `requests` + `truststore`.
- Formato de `config.ini` e `processos.txt` (compatível com o OGUM — o Márcio pode
  copiar os seus quando quiser).
- Esquema do banco (mesmas tabelas; `themis.db` pode ser um `ogum.db` renomeado).
- Visual roxo/ouro do painel e relatório.

## 4. Interfaces

### CLI (`themis.py`)
| Comando | Ação |
|---|---|
| `monitorar` | consulta todos os processos, atualiza banco, gera HTML/CSV, notifica, abre relatório |
| `painel` | sobe o painel em http://127.0.0.1:5000 e abre o navegador |
| `consultar <CNJ>` | consulta avulsa, gera relatório só desse processo |
| `testar` | testa conexão com DataJud |
| `oab` | gera o guia de descoberta por OAB |
| `--versao` | imprime versão e copyright |

Opções globais: `--sem-navegador` (não abre browser; usado em CI/agendador),
`--porta N` (painel).

### API do painel (JSON, POST, somente origem local)
- `/api/consultar` `{cnj}` → dados do processo ou `{erro}`
- `/api/adicionar` `{cnj, rotulo?, cliente?, area?}` → `{ok}`
- `/api/adicionar-lote` `{itens:[...], cliente?, area?}` → `{ok, adicionados, ignorados}`

## 5. Tratamento de erros

- `datajud.consultar()` nunca lança: retorna `Resultado(ok, fonte, erro)` com mensagens
  em português para: não encontrado, timeout, SSL, HTTP 4xx/5xx, resposta malformada,
  número divergente.
- `banco.salvar_resultado()` valida a estrutura inteira antes de escrever e usa
  transação (tudo ou nada).
- CLI retorna código de saída ≠ 0 em erro (agendador de tarefas detecta).
- Painel responde 400/403/404/415/500 com JSON `{erro}`; nunca expõe stack trace.

## 6. Testes

- `tests/test_cnj.py` — limpeza, formatação, dígito verificador (casos válidos reais e inválidos), identificação de tribunal para cada ramo (J = 1,3,4,5,6,7,8,9).
- `tests/test_analise.py` — urgência/alerta/ok, prazos, normalização de acentos.
- `tests/test_banco.py` — banco em memória: inserir, detectar novos, preservar cliente/área, backup.
- `tests/test_datajud.py` — `requests.post` mockado: sucesso, vazio, malformado, timeout, SSL.
- `tests/test_relatorio.py` — HTML contém escape de `<script>` vindo do tribunal; CSV neutraliza `=`.
- `tests/test_painel.py` — sobe servidor em porta 0, testa 403 sem Host local, 415, 400, fluxo adicionar-lote com duplicatas.
- `tests/test_config.py` — parse de `processos.txt` (comentários, campos opcionais, duplicados).

Critério: CI verde em Ubuntu e Windows.

## 7. Apresentação (README)

Dois arquivos, mesmo conteúdo:

- **`README.md` — em inglês** (é o que o GitHub exibe na página do repositório e o
  que alcança o público internacional). Logo abaixo do título, um bloco destacado
  em português:
  > 🇧🇷 **Não lê inglês?** Clique com o botão direito nesta página → *"Traduzir para
  > português"* (Chrome/Edge) — ou leia a versão completa em português:
  > [README.pt-BR.md](README.pt-BR.md).
- **`README.pt-BR.md` — em português**, completo, para o público principal
  (advogados brasileiros).

Conteúdo de ambos: banner em texto, frase-síntese, badges (CI, licença, Python),
screenshot do painel, GIF do fluxo "clique → relatório", "Por que THEMIS" (tabela
vs. serviços pagos), "O que ele NÃO faz" (atraso DataJud 24–48h, sem
partes/advogados, não substitui PJe Push para prazo fatal), instalação em 3 passos,
uso diário, agendamento, notificações, tribunais suportados, segurança e privacidade,
roadmap, contribuição, autoria e licença.

## 8. Fora de escopo (roadmap no README)

Automação da busca por OAB (CAPTCHA), multiusuário, edição de rótulos pelo painel,
exportação PDF, instalador `.exe`.
