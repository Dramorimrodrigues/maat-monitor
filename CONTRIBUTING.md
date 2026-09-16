# Contribuindo com o THEMIS

Obrigado pelo interesse. Toda contribuição é bem-vinda: correções, tribunais novos, traduções, documentação.

## Preparar o ambiente

```bash
git clone https://github.com/Dramorimrodrigues/themis-monitor.git
cd themis-monitor
python -m venv venv
venv\Scripts\activate        # Windows  |  source venv/bin/activate  (macOS/Linux)
pip install -r requirements-dev.txt
python -m pytest
```

## Regras do projeto

1. **Testes primeiro.** Toda função nova ou correção vem com teste em `tests/`. Os testes não acessam a internet (use `monkeypatch`/`mock`).
2. **Só stdlib + `requests` + `truststore`.** Não adicione dependências sem abrir uma issue antes.
3. **Python 3.9+.** Use `from __future__ import annotations`; nada de `match`.
4. **Lint limpo:** `python -m ruff check .` sem avisos.
5. **Textos ao usuário em português**, com acentos.
6. **Nunca inclua dados reais** — números de processo de clientes, OAB, senhas.
7. **Um assunto por pull request.**

## Fluxo

1. Abra uma issue descrevendo o problema/ideia (pule para PR se for trivial).
2. Crie um branch: `git checkout -b feat/nome-curto`.
3. Faça commits pequenos com mensagens no estilo `feat: ...`, `fix: ...`, `docs: ...`.
4. Abra o PR preenchendo o template. O CI precisa ficar verde.

## Estrutura do código

| Módulo | Responsabilidade |
|---|---|
| `themis/cnj.py` | limpar, formatar, validar dígito verificador e identificar tribunal |
| `themis/constantes.py` | catálogo de tribunais do DataJud, palavras-chave, prazos |
| `themis/analise.py` | urgência, prazos estimados, formatação de datas/valores |
| `themis/config.py` | `config.ini`, `processos.txt`, caminhos |
| `themis/banco.py` | SQLite: schema, gravação, leitura, backup |
| `themis/datajud.py` | cliente HTTP da API pública do CNJ |
| `themis/notificacoes.py` | e-mail e WhatsApp |
| `themis/relatorio.py` | HTML e CSV |
| `themis/painel.py` | servidor web local |
| `themis/descoberta_oab.py` | guia de descoberta por OAB |
| `themis/cli.py` | linha de comando |

## Licença

Ao contribuir, você concorda que sua contribuição será licenciada sob a licença MIT do projeto, mantendo o aviso de copyright de Márcio Luis Amorim.
