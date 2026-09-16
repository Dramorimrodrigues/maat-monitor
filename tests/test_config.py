"""Testes do módulo config — THEMIS Monitor. Copyright (c) 2026 Márcio Luis Amorim — MIT."""

from pathlib import Path

from themis import config
from themis.config import Processo

# CNJs fictícios com dígito verificador válido (módulo 97)
CNJ_A = "00000010520258260100"  # 0000001-05.2025.8.26.0100
CNJ_B = "08292298220248190209"  # 0829229-82.2024.8.19.0209
CNJ_A_FMT = "0000001-05.2025.8.26.0100"
CNJ_B_FMT = "0829229-82.2024.8.19.0209"
CNJ_DIGITO_ERRADO = "0829229-83.2024.8.19.0209"


def escrever_processos(c: config.Caminhos, texto: str, encoding: str = "utf-8") -> None:
    c.processos.write_text(texto, encoding=encoding)


def test_caminhos_respeita_themis_home(tmp_home):
    c = config.caminhos()
    assert c.base == Path(tmp_home).resolve()
    assert c.config == c.base / "config.ini"
    assert c.processos == c.base / "processos.txt"
    assert c.banco == c.base / "themis.db"
    assert c.relatorios == c.base / "relatorios"
    assert c.backups == c.base / "backups"
    # Exemplos ficam sempre na raiz do repositório, não em THEMIS_HOME
    assert (c.exemplos / "config.example.ini").exists()
    assert (c.exemplos / "processos.example.txt").exists()
    assert c.exemplos != c.base


def test_garantir_arquivos_iniciais_copia_exemplos(tmp_home):
    c = config.caminhos()
    criados = config.garantir_arquivos_iniciais(c)
    assert sorted(criados) == ["config.ini", "processos.txt"]
    assert c.config.exists() and c.processos.exists()
    assert c.relatorios.is_dir() and c.backups.is_dir()
    # Segunda chamada não sobrescreve nem relata nada
    c.config.write_text("[advogado]\nnome = Teste\n", encoding="utf-8")
    assert config.garantir_arquivos_iniciais(c) == []
    assert "Teste" in c.config.read_text(encoding="utf-8")


def test_exemplo_de_processos_tem_cnj_valido(tmp_home):
    c = config.caminhos()
    config.garantir_arquivos_iniciais(c)
    processos, avisos = config.carregar_processos(c)
    assert avisos == []
    assert processos == [Processo(CNJ_A, "Exemplo de apelido", "Cliente Exemplo", "Civel")]


def test_carregar_config_sem_arquivo_devolve_fallbacks(tmp_home):
    cfg = config.carregar_config(config.caminhos())
    assert cfg["oab_numero"] == ""
    assert cfg["dias_alerta_parado"] == 30
    assert cfg["delay_segundos"] == 1.5
    assert cfg["email_ativo"] == "nao"
    assert cfg["email_porta"] == 587
    assert cfg["whatsapp_ativo"] == "nao"
    assert isinstance(cfg["tribunais_ativos"], list) and cfg["tribunais_ativos"]


def test_carregar_config_le_valores(tmp_home):
    c = config.caminhos()
    c.config.write_text(
        "[advogado]\noab_numero = 123456\noab_uf = rj\nnome = Dra. Teste\n"
        "[tribunais]\nativos = TJRJ, trf2 ,trt1\n"
        "[execucao]\ndias_alerta_parado = 45\ndelay_segundos = abc\n"
        "[notificacoes]\nemail_ativo = sim\nemail_porta = 465\n",
        encoding="utf-8",
    )
    cfg = config.carregar_config(c)
    assert cfg["oab_numero"] == "123456"
    assert cfg["oab_uf"] == "RJ"
    assert cfg["nome"] == "Dra. Teste"
    assert cfg["tribunais_ativos"] == ["tjrj", "trf2", "trt1"]
    assert cfg["dias_alerta_parado"] == 45
    assert cfg["delay_segundos"] == 1.5  # valor inválido cai no fallback
    assert cfg["email_ativo"] == "sim"
    assert cfg["email_porta"] == 465


def test_carregar_processos_ignora_comentarios_e_vazias(tmp_home):
    c = config.caminhos()
    escrever_processos(c, f"# comentário\n\n   \n{CNJ_A_FMT}\n# outro\n")
    processos, avisos = config.carregar_processos(c)
    assert avisos == []
    assert processos == [Processo(CNJ_A, "", "", "")]


def test_carregar_processos_campos_opcionais(tmp_home):
    c = config.caminhos()
    escrever_processos(c, f"{CNJ_A_FMT} | Apelido\n{CNJ_B_FMT}|Rótulo|Cliente X|Trabalhista\n")
    processos, _ = config.carregar_processos(c)
    assert processos[0] == Processo(CNJ_A, "Apelido", "", "")
    assert processos[1] == Processo(CNJ_B, "Rótulo", "Cliente X", "Trabalhista")


def test_carregar_processos_aceita_bom(tmp_home):
    c = config.caminhos()
    escrever_processos(c, f"{CNJ_A_FMT}\n", encoding="utf-8-sig")
    processos, avisos = config.carregar_processos(c)
    assert avisos == []
    assert processos[0].cnj == CNJ_A


def test_carregar_processos_cnj_invalido_gera_aviso(tmp_home):
    c = config.caminhos()
    escrever_processos(c, f"123\n{CNJ_DIGITO_ERRADO} | Errado\n{CNJ_A_FMT}\n")
    processos, avisos = config.carregar_processos(c)
    assert [p.cnj for p in processos] == [CNJ_A]
    assert len(avisos) == 2
    assert avisos[0].startswith("Linha 1 ignorada:")
    assert avisos[1].startswith("Linha 2 ignorada:")
    assert "dígito" in avisos[1].lower()


def test_carregar_processos_duplicado_descartado(tmp_home):
    c = config.caminhos()
    escrever_processos(c, f"{CNJ_A_FMT} | Primeiro\n{CNJ_A} | Segundo\n")
    processos, avisos = config.carregar_processos(c)
    assert processos == [Processo(CNJ_A, "Primeiro", "", "")]
    assert len(avisos) == 1 and "Linha 2" in avisos[0]


def test_carregar_processos_sem_arquivo(tmp_home):
    processos, avisos = config.carregar_processos(config.caminhos())
    assert processos == []
    assert len(avisos) == 1


def test_adicionar_processos_acrescenta_newline_quando_falta(tmp_home):
    c = config.caminhos()
    escrever_processos(c, f"{CNJ_A_FMT} | Existente")  # sem \n no final
    adicionados, ignorados = config.adicionar_processos(c, [Processo(CNJ_B, "Novo", "", "")])
    assert adicionados == [CNJ_B_FMT]
    assert ignorados == []
    conteudo = c.processos.read_text(encoding="utf-8")
    assert conteudo == f"{CNJ_A_FMT} | Existente\n{CNJ_B_FMT} | Novo\n"
    processos, _ = config.carregar_processos(c)
    assert [p.cnj for p in processos] == [CNJ_A, CNJ_B]


def test_adicionar_processos_apara_campos_finais_vazios(tmp_home):
    c = config.caminhos()
    config.adicionar_processos(
        c,
        [Processo(CNJ_A_FMT, "", "", ""), Processo(CNJ_B, "", "Cliente", "")],
    )
    linhas = c.processos.read_text(encoding="utf-8").splitlines()
    assert linhas == [CNJ_A_FMT, f"{CNJ_B_FMT} |  | Cliente"]


def test_adicionar_processos_duplicatas(tmp_home):
    c = config.caminhos()
    escrever_processos(c, f"# cabeçalho\n{CNJ_A_FMT}\n")
    adicionados, ignorados = config.adicionar_processos(
        c,
        [
            Processo(CNJ_A, "contra o arquivo", "", ""),
            Processo(CNJ_B, "primeiro do lote", "", ""),
            Processo(CNJ_B_FMT, "repetido no lote", "", ""),
        ],
    )
    assert adicionados == [CNJ_B_FMT]
    assert len(ignorados) == 2
    assert all("já existe" in msg for msg in ignorados)
    assert c.processos.read_text(encoding="utf-8").count(CNJ_B_FMT) == 1


def test_adicionar_processos_rejeita_campos_com_pipe_e_quebra(tmp_home):
    c = config.caminhos()
    adicionados, ignorados = config.adicionar_processos(
        c,
        [
            Processo(CNJ_A, "a | b", "", ""),
            Processo(CNJ_B, "ok", "linha\nquebrada", ""),
            Processo("123", "", "", ""),
        ],
    )
    assert adicionados == []
    assert len(ignorados) == 3
    assert "barra vertical" in ignorados[0]
    assert "barra vertical" in ignorados[1]
    assert not c.processos.exists()


def test_adicionar_processos_cria_arquivo_se_nao_existe(tmp_home):
    c = config.caminhos()
    adicionados, _ = config.adicionar_processos(c, [Processo(CNJ_A, "Novo", "Cliente", "Civel")])
    assert adicionados == [CNJ_A_FMT]
    assert c.processos.read_text(encoding="utf-8") == f"{CNJ_A_FMT} | Novo | Cliente | Civel\n"
