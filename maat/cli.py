"""
Linha de comando do MAAT Monitor: ``python maat.py <comando>``.

Comandos: ``monitorar``, ``painel``, ``consultar <CNJ>``, ``testar``, ``oab``.
Flags globais: ``--sem-navegador``, ``--versao``, ``--preparar``.
Os módulos ``relatorio`` e ``painel`` são importados tardiamente, dentro dos
comandos que os usam, para que os demais funcionem sem eles.

Copyright (c) 2026 Márcio Luis Amorim — Licença MIT
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
import traceback
import webbrowser
from datetime import datetime
from typing import TYPE_CHECKING

from maat import __version__, banco, cnj, config, constantes, datajud, notificacoes

if TYPE_CHECKING:  # pragma: no cover
    from maat.config import Caminhos

URL_ISSUES = "https://github.com/Dramorimrodrigues/maat-monitor/issues"
PORTA_PADRAO = 5000
LARGURA = 60

MSG_CRIADOS = {
    "config.ini": "Arquivo criado: config.ini — edite com sua OAB e nome",
    "processos.txt": "Arquivo criado: processos.txt — cole nele os números CNJ dos seus processos",
}


# ------------------------------------------------------------------
# Utilitários de terminal
# ------------------------------------------------------------------

def log(msg: str, nivel: str = "INFO") -> None:
    """Imprime ``[HH:MM:SS] `` + prefixo (``! `` para AVISO, ``X `` para ERRO) + mensagem."""
    prefixos = {"INFO": "", "OK": "  ", "AVISO": "! ", "ERRO": "X "}
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {prefixos.get(nivel, '')}{msg}")


def banner() -> None:
    print()
    print("=" * LARGURA)
    print(f"  MAAT Monitor v{__version__} — Acompanhamento Judicial")
    print("  © 2026 Márcio Luis Amorim · Dados: API DataJud/CNJ")
    print("=" * LARGURA)
    print()


def _preparar_ambiente() -> tuple[Caminhos, list[str]]:
    """Resolve os caminhos, cria config/processos/pastas se faltarem e avisa o que criou."""
    caminhos = config.caminhos()
    criados = config.garantir_arquivos_iniciais(caminhos)
    for nome in criados:
        log(MSG_CRIADOS.get(nome, f"Arquivo criado: {nome}"), "AVISO")
    return caminhos, criados


def _abrir(caminho, abrir_navegador: bool) -> None:
    if abrir_navegador:
        webbrowser.open(caminho.as_uri())


# ------------------------------------------------------------------
# Comandos
# ------------------------------------------------------------------

def cmd_preparar() -> int:
    caminhos, criados = _preparar_ambiente()
    log(f"Pasta de dados: {caminhos.base}")
    if criados:
        log(f"Criados: {', '.join(criados)}", "OK")
    else:
        log("Nada a criar: config.ini e processos.txt já existem.", "OK")
    log("Pastas de relatórios e backups prontas.", "OK")
    return 0


def cmd_testar() -> int:
    _preparar_ambiente()
    log("Testando conexão com o DataJud...")
    resultado = datajud.testar_conexao()
    if resultado.ok:
        log("Conexão com o DataJud OK!", "OK")
        return 0
    log(f"Erro de conexão: {resultado.erro}", "ERRO")
    log("Verifique sua conexão com a internet.", "ERRO")
    return 1


def cmd_consultar(cnj_bruto: str, abrir_navegador: bool) -> int:
    caminhos, _ = _preparar_ambiente()

    cnj_limpo, erro = cnj.validar(cnj_bruto)
    if cnj_limpo is None:
        log(f"Número CNJ inválido: {cnj_bruto}", "ERRO")
        log(erro or cnj.MSG_TAMANHO, "INFO")
        return 2

    cnj_fmt = cnj.formatar(cnj_limpo)
    log(f"Consultando processo: {cnj_fmt}")

    tribunal = cnj.identificar_tribunal(cnj_limpo)
    if not tribunal:
        log("Não foi possível identificar o tribunal pelo número CNJ.", "ERRO")
        log("Confira os campos J (justiça) e TR (tribunal) do número.", "INFO")
        return 2
    log(f"Tribunal identificado: {constantes.TRIBUNAIS[tribunal]['nome']}")

    resultado = datajud.consultar(cnj_limpo, tribunal)
    if not resultado.ok or resultado.fonte is None:
        log(f"Erro na consulta: {resultado.erro}", "ERRO")
        return 1

    cfg = config.carregar_config(caminhos)
    conn = banco.conectar(caminhos.banco)
    try:
        sucesso, novos = banco.salvar_resultado(conn, cnj_limpo, resultado.fonte)
        if not sucesso:
            log("Falha ao processar o resultado: resposta do DataJud inválida.", "ERRO")
            return 1
        log("Processo consultado e salvo com sucesso!", "OK")
        if novos:
            log(f"{novos} novo(s) andamento(s) detectado(s)!", "OK")

        from maat import relatorio  # importação tardia (ver docstring do módulo)

        estatisticas = {"total": 1, "sucesso": 1, "erros": 0, "novos_andamentos": novos, "lista_erros": []}
        arquivo = relatorio.gerar_relatorio_html(conn, cfg, caminhos, estatisticas, apenas_cnj=cnj_limpo)
    finally:
        conn.close()

    log(f"Relatório gerado: {arquivo.name}", "OK")
    _abrir(arquivo, abrir_navegador)
    return 0


def _resumo_execucao(estatisticas: dict, arq_html, arq_csv_proc, arq_csv_mov) -> None:
    print()
    print("=" * LARGURA)
    print("  RESUMO DA EXECUÇÃO")
    print("=" * LARGURA)
    print(f"  Processos verificados:   {estatisticas['total']}")
    print(f"  Atualizados com sucesso: {estatisticas['sucesso']}")
    print(f"  Erros/não encontrados:   {estatisticas['erros']}")
    print(f"  NOVOS andamentos:        {estatisticas['novos_andamentos']}")
    print()
    print(f"  Relatório HTML:  {arq_html.name}")
    print(f"  Planilha proc.:  {arq_csv_proc.name}")
    print(f"  Planilha mov.:   {arq_csv_mov.name}")
    print()
    if estatisticas["lista_erros"]:
        print("  Detalhes dos erros:")
        for cnj_e, msg_e in estatisticas["lista_erros"][:10]:
            print(f"    - {cnj_e}: {msg_e}")
    print("=" * LARGURA)
    print()


def _notificar(cfg: dict, estatisticas: dict, processos_com_novidade: list) -> None:
    agora_fmt = datetime.now().strftime("%d/%m/%Y às %H:%M")
    if str(cfg.get("email_ativo", "nao")).lower() == "sim":
        corpo = notificacoes.montar_email_html(estatisticas, processos_com_novidade, agora_fmt)
        assunto = f"MAAT — {estatisticas['novos_andamentos']} novo(s) andamento(s) · {agora_fmt}"
        if notificacoes.enviar_email(cfg, assunto, corpo):
            log("E-mail de resumo enviado.", "OK")
        else:
            log("E-mail não enviado (veja config.ini ou a mensagem acima).", "AVISO")
    if str(cfg.get("whatsapp_ativo", "nao")).lower() == "sim" and processos_com_novidade:
        texto = notificacoes.montar_whatsapp_texto(estatisticas, processos_com_novidade, agora_fmt)
        if notificacoes.enviar_whatsapp(cfg, texto):
            log("WhatsApp enviado.", "OK")
        else:
            log("WhatsApp não enviado (veja config.ini ou a mensagem acima).", "AVISO")


def cmd_monitorar(abrir_navegador: bool) -> int:
    caminhos, _ = _preparar_ambiente()
    cfg = config.carregar_config(caminhos)
    log(f"Advogado(a): {cfg['nome']} (OAB {cfg['oab_numero']}/{cfg['oab_uf']})")
    log(f"Tribunais ativos: {', '.join(cfg['tribunais_ativos']).upper()}")

    processos, avisos = config.carregar_processos(caminhos)
    for aviso in avisos:
        log(aviso, "AVISO")
    if not processos:
        log("Nenhum processo em processos.txt para monitorar.", "AVISO")
        log(f"Edite o arquivo {caminhos.processos} e cole os números CNJ,", "INFO")
        log("ou use o painel (painel.bat / ./maat.sh painel) para cadastrar.", "INFO")
        log("Formato: 0000000-00.0000.0.00.0000 | Apelido | Cliente | Área", "INFO")
        return 0

    backup = banco.fazer_backup(caminhos)
    if backup:
        log(f"Backup do banco: {backup.name}")

    log(f"Total de processos a verificar: {len(processos)}")
    print()

    estatisticas: dict = {
        "total": len(processos),
        "sucesso": 0,
        "erros": 0,
        "novos_andamentos": 0,
        "lista_erros": [],
    }
    processos_com_novidade: list[tuple[str, str, int]] = []
    delay = float(cfg.get("delay_segundos") or 0)

    conn = banco.conectar(caminhos.banco)
    try:
        for idx, proc in enumerate(processos, 1):
            cnj_fmt = cnj.formatar(proc.cnj)
            rotulo_txt = f" [{proc.rotulo}]" if proc.rotulo else ""
            log(f"[{idx}/{len(processos)}] {cnj_fmt}{rotulo_txt}")

            tribunal = cnj.identificar_tribunal(proc.cnj)
            if not tribunal:
                log("  Não foi possível identificar o tribunal pelo CNJ", "AVISO")
                estatisticas["erros"] += 1
                estatisticas["lista_erros"].append((cnj_fmt, "Tribunal não identificado"))
            else:
                log(f"  Tribunal: {constantes.TRIBUNAIS[tribunal]['nome']}")
                resultado = datajud.consultar(proc.cnj, tribunal)
                if not resultado.ok or resultado.fonte is None:
                    log(f"  {resultado.erro}", "AVISO")
                    estatisticas["erros"] += 1
                    estatisticas["lista_erros"].append((cnj_fmt, resultado.erro or "Erro desconhecido"))
                else:
                    sucesso, novos = banco.salvar_resultado(
                        conn, proc.cnj, resultado.fonte, proc.rotulo, proc.cliente, proc.area
                    )
                    if sucesso:
                        estatisticas["sucesso"] += 1
                        estatisticas["novos_andamentos"] += novos
                        if novos > 0:
                            log(f"  {novos} novo(s) andamento(s) detectado(s)!", "OK")
                            processos_com_novidade.append((cnj_fmt, proc.rotulo, novos))
                        else:
                            log("  Atualizado (sem novidades)", "OK")
                    else:
                        log("  Resposta do DataJud inválida — não foi salva", "AVISO")
                        estatisticas["erros"] += 1
                        estatisticas["lista_erros"].append((cnj_fmt, datajud.MSG_INVALIDA))

            if idx < len(processos) and delay > 0:
                time.sleep(delay)

        banco.registrar_execucao(
            conn,
            estatisticas["total"],
            estatisticas["sucesso"],
            estatisticas["erros"],
            estatisticas["novos_andamentos"],
        )

        print()
        log("Gerando relatórios...")
        from maat import relatorio  # importação tardia (ver docstring do módulo)

        arq_html = relatorio.gerar_relatorio_html(conn, cfg, caminhos, estatisticas)
        arq_csv_proc, arq_csv_mov = relatorio.gerar_csv(conn, caminhos)
    finally:
        conn.close()

    _resumo_execucao(estatisticas, arq_html, arq_csv_proc, arq_csv_mov)
    _notificar(cfg, estatisticas, processos_com_novidade)
    _abrir(arq_html, abrir_navegador)
    # Erros pontuais (processo não encontrado etc.) já aparecem no resumo e no relatório;
    # o código 1 fica reservado para quando NENHUM processo pôde ser consultado (ex.: sem internet).
    return 0 if estatisticas["sucesso"] > 0 or estatisticas["erros"] == 0 else 1


def cmd_painel(porta: int, abrir_navegador: bool) -> int:
    _preparar_ambiente()
    from maat import painel  # importação tardia (ver docstring do módulo)

    return int(painel.executar(porta=porta, abrir_navegador=abrir_navegador))


def cmd_oab(abrir_navegador: bool) -> int:
    from maat import descoberta_oab

    caminhos, _ = _preparar_ambiente()
    cfg = config.carregar_config(caminhos)
    return descoberta_oab.executar(cfg, caminhos, abrir_navegador=abrir_navegador)


# ------------------------------------------------------------------
# argparse
# ------------------------------------------------------------------

def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="maat",
        description="MAAT Monitor — acompanhamento gratuito e local de processos judiciais via API DataJud/CNJ.",
        epilog="Exemplos: maat monitorar | maat consultar 0000001-05.2025.8.26.0100 | maat painel --porta 5000",
    )
    parser.add_argument("--versao", action="store_true", help="mostra a versão e o copyright e sai")
    parser.add_argument(
        "--preparar", action="store_true",
        help="cria config.ini, processos.txt e as pastas de dados se ainda não existirem",
    )
    parser.add_argument(
        "--sem-navegador", dest="sem_navegador", action="store_true", default=False,
        help="não abre o navegador (útil em agendador de tarefas ou CI)",
    )

    # A mesma flag também é aceita depois do subcomando. default=SUPPRESS evita que o
    # subparser sobrescreva com False um valor já definido antes do subcomando.
    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument(
        "--sem-navegador", dest="sem_navegador", action="store_true", default=argparse.SUPPRESS,
        help="não abre o navegador",
    )

    sub = parser.add_subparsers(dest="comando", metavar="comando")
    sub.add_parser(
        "monitorar", parents=[comum],
        help="consulta todos os processos de processos.txt, atualiza o banco e gera os relatórios",
    )
    p_painel = sub.add_parser("painel", parents=[comum], help="abre o painel local no navegador")
    p_painel.add_argument("--porta", type=int, default=PORTA_PADRAO, help=f"porta HTTP (padrão {PORTA_PADRAO})")
    p_consultar = sub.add_parser("consultar", parents=[comum], help="consulta avulsa de um processo pelo número CNJ")
    p_consultar.add_argument("cnj", help="número CNJ, com ou sem pontuação")
    sub.add_parser("testar", parents=[comum], help="testa a conexão com o DataJud")
    sub.add_parser("oab", parents=[comum], help="gera o guia de descoberta de processos por OAB")
    return parser


def _executar(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.versao:
        print(f"MAAT Monitor v{__version__} — Copyright (c) 2026 Márcio Luis Amorim — Licença MIT")
        return 0

    if not args.comando and not args.preparar:
        parser.print_help()
        return 2

    banner()
    abrir_navegador = not getattr(args, "sem_navegador", False)

    if args.preparar and not args.comando:
        return cmd_preparar()
    if args.preparar:
        cmd_preparar()

    if args.comando == "monitorar":
        return cmd_monitorar(abrir_navegador)
    if args.comando == "painel":
        return cmd_painel(args.porta, abrir_navegador)
    if args.comando == "consultar":
        return cmd_consultar(args.cnj, abrir_navegador)
    if args.comando == "testar":
        return cmd_testar()
    if args.comando == "oab":
        return cmd_oab(abrir_navegador)

    parser.print_help()
    return 2


def _garantir_saida_utf8() -> None:
    """Evita UnicodeEncodeError em consoles Windows com página de código legada."""
    for fluxo in (sys.stdout, sys.stderr):
        reconfigurar = getattr(fluxo, "reconfigure", None)
        if reconfigurar is not None:
            try:
                reconfigurar(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada. Devolve o código de saída (0 ok, 1 erro, 2 uso incorreto, 130 interrompido)."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    _garantir_saida_utf8()
    parser = construir_parser()
    try:
        try:
            args = parser.parse_args(argv)
        except SystemExit as exc:  # --help ou erro de uso: devolve o código em vez de encerrar o processo
            codigo = exc.code
            return codigo if isinstance(codigo, int) else (0 if codigo is None else 2)
        return _executar(args, parser)
    except KeyboardInterrupt:
        print("\nInterrompido.")
        return 130
    except Exception as exc:  # noqa: BLE001 - último recurso: nunca deixar stack trace crua para o usuário
        print()
        print(f"ERRO INESPERADO: {type(exc).__name__}: {exc}")
        print(f"Se o problema persistir, abra uma issue em {URL_ISSUES} com o texto abaixo.", flush=True)
        traceback.print_exc()
        return 1
