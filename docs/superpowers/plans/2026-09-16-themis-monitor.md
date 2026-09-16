# THEMIS Monitor v1.0.0 — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir o THEMIS Monitor — versão pública, testada e multiplataforma do OGUM — e publicá-lo no repositório privado `Dramorimrodrigues/themis-monitor`.

**Architecture:** Pacote Python `themis/` com módulos de responsabilidade única (CNJ, análise, config, banco, DataJud, notificações, relatório, painel, descoberta OAB, CLI). Painel e relatório consomem o mesmo motor. Sem framework web; SQLite local; testes pytest sem rede.

**Tech Stack:** Python ≥ 3.9, `requests`, `truststore`; dev: `pytest`, `ruff`; GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-16-themis-monitor-design.md`

## Global Constraints

- Python ≥ 3.9; dependências de runtime: apenas `requests>=2.31`, `truststore>=0.9`.
- Cabeçalho em todo `.py`: `THEMIS Monitor — Copyright (c) 2026 Márcio Luis Amorim — Licença MIT`.
- Servidor do painel escuta somente em `127.0.0.1`; checagem de Host/Origin mantida.
- `verify=True` sempre; nunca `verify=False`.
- Nenhum dado real: `config.ini`, `processos.txt`, `*.db`, `backups/`, `relatorios/` no `.gitignore`.
- Nome do banco: `themis.db`; backups `themis_backup_*.db`.
- Textos de interface em português (pt-BR); README principal em inglês com aviso em português.
- A pasta OGUM original não é modificada.

---

### Task 1: Esqueleto do repositório e pacote

**Files:** `themis/__init__.py`, `themis.py`, `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `.gitignore`, `.editorconfig`, `LICENSE`, `tests/__init__.py`, `tests/conftest.py`

**Produces:** `themis.__version__ = "1.0.0"`, `themis.__author__`, `themis.__copyright__`; fixture `tmp_home` (define `THEMIS_HOME` para diretório temporário).

- [ ] `git init`, criar arquivos, `pip install -r requirements-dev.txt`, `pytest` roda (0 testes) e `ruff check .` passa. Commit `chore: scaffold`.

### Task 2: `themis/constantes.py` + `themis/cnj.py`

**Produces:**
- `TRIBUNAIS: dict[str, dict]` chave = código (`tjrj`, `trf2`, `trt1`, `stf`, `tre-rj`, `tjmsp`…) → `{"nome", "alias", "tipo"}`; `PALAVRAS_URGENTES`, `PALAVRAS_ALERTA`, `PRAZOS_TIPICOS`, `DATAJUD_BASE_URL`, `DATAJUD_API_KEY_PUBLICA`.
- `cnj.limpar(s) -> str`, `cnj.formatar(s) -> str`, `cnj.validar_digito(cnj_limpo) -> bool`, `cnj.identificar_tribunal(cnj_limpo) -> str | None`, `cnj.validar(s) -> tuple[str|None, str|None]` (retorna `(cnj_limpo, erro)`), `cnj.extrair_todos(texto) -> list[str]`.

**Tests (`tests/test_cnj.py`):** formatar 20 dígitos; dígito válido para `08292298220248190209` e `08000867020258190255`; inválido para `08292298320248190209`; identificar: J=1→stf, 3→stj, 4/02→trf2, 5/00→tst, 5/01→trt1, 6/19→tre-rj, 8/19→tjrj, 8/26→tjsp, 9/26→tjmsp; `validar` retorna erro "20 dígitos" e "dígito verificador"; `extrair_todos` de texto com ruído e duplicatas.

- [ ] Testes → falham → implementar → passam → commit `feat: cnj e constantes`.

### Task 3: `themis/analise.py`

**Produces:** `normalizar(t)`, `detectar_urgencia(movs) -> "urgente"|"alerta"|"ok"` (movs = tuplas `(data_hora, nome, complemento, novo)`), `urgencia_movimento(nome)`, `calcular_prazo(nome, data_iso) -> (str|None, int|None)`, `dias_desde(iso) -> int`, `formatar_data(iso)`, `formatar_data_hora(iso)`, `formatar_valor(v)`.

**Tests (`tests/test_analise.py`):** acentos removidos; "Penhora" → urgente; "Intimação" → alerta; vazio → ok; prazo de intimação = +15 dias; valor `1234.5` → `R$ 1.234,50`; datas inválidas → `—` / 9999.

- [ ] Testes → implementar → commit `feat: analise`.

### Task 4: `themis/config.py`

**Produces:** `Caminhos` (dataclass: `base`, `config`, `processos`, `banco`, `relatorios`, `backups`, `exemplos`), `caminhos() -> Caminhos` (respeita env `THEMIS_HOME`, padrão = raiz do repo), `garantir_arquivos_iniciais(c) -> list[str]` (copia `.example` quando faltam; retorna nomes criados), `carregar_config(c) -> dict`, `carregar_processos(c) -> list[Processo]` (namedtuple `cnj, rotulo, cliente, area`), `adicionar_processos(c, itens) -> (adicionados, ignorados)` com lock e detecção de duplicatas.

**Tests (`tests/test_config.py`):** comentários e linhas vazias ignorados; campos opcionais; CNJ inválido ignorado com aviso; duplicado descartado; `adicionar_processos` acrescenta newline quando o arquivo termina sem `\n`; `garantir_arquivos_iniciais` cria `config.ini` a partir do exemplo.

- [ ] Também criar `config.example.ini` e `processos.example.txt`. Commit `feat: config`.

### Task 5: `themis/banco.py`

**Produces:** `conectar(caminho) -> sqlite3.Connection` (cria schema, `row_factory=Row`), `salvar_resultado(conn, cnj, fonte, rotulo="", cliente="", area="") -> (bool, int)`, `ler_processos(conn, dias_parado) -> list[dict]` (com `movimentos`, `tem_novo`, `urgencia`, `parado`, `dias_sem`, `cnj_fmt`, `rotulo_exibir`, `prazo_txt`, formatações), `ler_historico(conn, limite=15) -> list[dict]`, `registrar_execucao(conn, stats)`, `fazer_backup(caminhos) -> Path|None` (mantém 10).

**Tests (`tests/test_banco.py`):** primeira gravação → 0 novos; segunda com movimento extra → 1 novo e `tem_novo`; cliente/área preservados se vazios na segunda chamada; `fonte` malformada → `(False, 0)` sem escrever; backup cria arquivo e limita a 10.

- [ ] Commit `feat: banco`.

### Task 6: `themis/datajud.py`

**Produces:** `@dataclass Resultado(ok: bool, fonte: dict|None, erro: str|None)`, `consultar(cnj_limpo, tribunal, timeout=30) -> Resultado`, `testar_conexao() -> Resultado`.

**Tests (`tests/test_datajud.py`):** mock `requests.post`: hit válido; hits vazio → "não encontrado"; número divergente → erro; `Timeout` → erro amigável; `SSLError` → erro amigável; HTTP 429 → erro com status; tribunal desconhecido → erro sem chamada de rede. Asserção de que `verify` nunca é `False`.

- [ ] Commit `feat: datajud`.

### Task 7: `themis/notificacoes.py`

**Produces:** `enviar_email(config, assunto, corpo_html, texto="") -> bool`, `enviar_whatsapp(config, mensagem) -> bool`, `montar_email_html(stats, novidades, agora_fmt) -> str`.

**Tests (`tests/test_notificacoes.py`):** desativado → False sem chamar SMTP; mock `smtplib.SMTP` → True; e-mail HTML escapa rótulo `<b>`.

- [ ] Commit `feat: notificacoes`.

### Task 8: `themis/relatorio.py`

**Produces:** `CSS`, `JS_FILTROS`, `html_cards(processos) -> str`, `html_historico(hist) -> str`, `rodape_html()`, `gerar_relatorio_html(conn, config, caminhos, stats, apenas_cnj=None) -> Path`, `gerar_csv(conn, caminhos) -> (Path, Path)`, `celula_csv(v)`.

**Tests (`tests/test_relatorio.py`):** classe `<script>alert(1)</script>` aparece escapada; relatório contém "THEMIS" e "Márcio Luis Amorim"; `apenas_cnj` filtra; CSV prefixa `=SOMA()` com `'`; delimitador `;` e BOM.

- [ ] Commit `feat: relatorio`.

### Task 9: `themis/painel.py`

**Produces:** `criar_servidor(host="127.0.0.1", porta=5000, caminhos=None) -> HTTPServer`, `Handler`, `executar(porta, abrir_navegador=True)`.

**Tests (`tests/test_painel.py`):** servidor em porta 0 numa thread; GET `/` 200 com "THEMIS"; Host externo → 403; POST sem JSON → 415; JSON inválido → 400; `/api/adicionar-lote` grava e detecta duplicata; `/api/consultar` com `datajud.consultar` mockado → 200 com dados; `/api/consultar` com dígito inválido → `{erro}` sem chamar rede.

- [ ] Commit `feat: painel`.

### Task 10: `themis/descoberta_oab.py` + `themis/cli.py` + `themis.py`

**Produces:** `gerar_guia(config, caminhos) -> Path`; CLI `monitorar | painel | consultar <CNJ> | testar | oab`, flags `--sem-navegador`, `--porta`, `--versao`; `main(argv) -> int`.

**Tests (`tests/test_cli.py`):** `--versao` imprime versão e copyright; `monitorar --sem-navegador` com `datajud.consultar` mockado gera HTML/CSV e registra execução; `consultar` com CNJ inválido retorna 2.

- [ ] Commit `feat: cli`.

### Task 11: Lançadores

**Files:** `instalar.bat`, `monitorar.bat`, `painel.bat`, `consultar.bat`, `testar.bat`, `buscar-oab.bat`, `themis.sh` (chmod +x, usa `python3`, cria venv opcional).

- [ ] Executar cada `.bat` numa cópia limpa (THEMIS_HOME temporário) e confirmar. Commit `feat: lancadores`.

### Task 12: CI e comunidade

**Files:** `.github/workflows/ci.yml` (matrix ubuntu/windows × 3.9, 3.11, 3.13: ruff + pytest), `.github/ISSUE_TEMPLATE/bug.yml`, `feature.yml`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`.

- [ ] Commit `ci: github actions e templates`.

### Task 13: Screenshots e GIF

- [ ] Rodar painel com `THEMIS_HOME` temporário populado com dados fictícios (fixture) e capturar `docs/screenshots/painel.png`, `relatorio.png`, `demo.gif` via Chrome. Commit `docs: screenshots`.

### Task 14: README.md (EN + aviso PT) e README.pt-BR.md

- [ ] Escrever conforme spec §7. Commit `docs: readme`.

### Task 15: Verificação de ponta a ponta e publicação

- [ ] `pytest -q` e `ruff check .` verdes; cópia limpa em pasta temporária: `instalar.bat` → `testar.bat` (rede real) → `consultar.bat` com CNJ real → `painel.bat`; `git tag v1.0.0`; `gh repo create Dramorimrodrigues/themis-monitor --private`; push; CI verde no GitHub; relatório final.
