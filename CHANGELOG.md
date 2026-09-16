# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [1.0.0] — 2026-09-16

Primeira versão pública, evolução de uma ferramenta de uso interno do escritório do autor.

### Adicionado
- Pacote `maat/` com motor único compartilhado por painel, relatório e linha de comando.
- Validação do dígito verificador CNJ (Resolução CNJ 65/2008) antes de qualquer consulta.
- Catálogo completo de tribunais do DataJud: 27 TJs, 6 TRFs, 24 TRTs, 27 TREs, TJMs, STF, STJ, TST, TSE, STM.
- Linha de comando `maat.py` (`monitorar`, `painel`, `consultar`, `testar`, `oab`).
- Lançadores para Windows (`.bat`) e macOS/Linux (`maat.sh`).
- Criação automática de `config.ini` e `processos.txt` na primeira execução.
- Suíte de testes (pytest, sem rede) e CI no GitHub Actions (Ubuntu + Windows, Python 3.9–3.13).
- Documentação: README (EN/PT-BR), SECURITY, CONTRIBUTING, templates de issue.

### Alterado
- Nome do banco: `maat.db` (compatível com o esquema anterior).
- Listas de palavras-chave de urgência unificadas (antes divergiam entre painel e relatório).
