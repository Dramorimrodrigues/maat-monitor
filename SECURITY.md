# Política de Segurança

## Relatar uma vulnerabilidade

Encontrou uma falha de segurança? **Não abra uma issue pública.**

Use o canal privado do GitHub: **Security → Report a vulnerability**
(https://github.com/Dramorimrodrigues/maat-monitor/security/advisories/new).

Respondo em até 7 dias com a confirmação e um prazo estimado de correção.

## O que o MAAT faz para proteger você

| Proteção | Como |
|---|---|
| Dados ficam na sua máquina | SQLite local (`maat.db`); nenhum servidor externo além da API oficial do CNJ |
| Painel inacessível pela rede | Servidor escuta apenas em `127.0.0.1` e rejeita requisições cujo `Host`/`Origin` não seja local |
| Sem credenciais no código | A única chave embutida é a **chave pública oficial** publicada pelo CNJ para a API DataJud |
| HTTPS sempre validado | Nunca desliga a verificação de certificado; usa `truststore` para confiar nos certificados do sistema |
| Injeção | SQL 100% parametrizado; todo texto vindo do tribunal passa por `html.escape` antes de ir para HTML |
| Planilhas | Células que começam com `=`, `+`, `-`, `@` são neutralizadas no CSV (evita execução de fórmulas) |
| Requisições ao painel | Corpo JSON limitado a 1 MB; tipos validados; erros nunca expõem stack trace |
| Número de processo | Dígito verificador validado antes de qualquer consulta externa |

## Responsabilidade do usuário

- `config.ini` pode conter senha de aplicativo do Gmail e token do WhatsApp. Ele está no `.gitignore` — **nunca o envie para um repositório**.
- Faça backup da pasta se o computador for compartilhado.
