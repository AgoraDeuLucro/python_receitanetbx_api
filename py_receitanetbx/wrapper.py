"""
Wrapper não oficial do ReceitanetBX (Receita Federal).

Fluxo típico::

    from py_receitanetbx import arquivos, pedidos, SISTEMAS

    arq = arquivos()  # http://localhost:2443/services/ReceitanetBX

    # 1) Pesquisar — retorna IDs dos arquivos encontrados
    r = arq.pesquisar(sistema=2, inicio="2026-03-01", fim="2026-03-31")
    # {"retorno": 1, "saida": "...", "arquivos": ["id1", "id2"], "mensagem": "..."}

    # 2) Solicitar download com os IDs da pesquisa
    r = arq.solicitar(sistema=2, arquivos=r["arquivos"])
    # {"retorno": 1, "saida": "...", "pedido_id": "79242237", "mensagem": "..."}

    # 3) Acompanhar pedidos
    ped = pedidos()
    ped.verificar_situacao(pedido_ids=["79242237"])
    ped.consultar(sistema="2", situacao="processando")
"""

from calendar import monthrange
from html import unescape
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

import requests


# (nome, tipo_arquivo, tipo_pesquisa, periodicidade)
SISTEMAS = {
    1:  ("SPED Contábil (ECD)",  "1601", "porPeriodo",                    "anual"),
    2:  ("EFD ICMS IPI",         "1602", "porCNPJIEPeriodoContribuinte",   "mensal"),
    3:  ("SPED NF-e",            "1603", "porCNPJPeriodo",                 "mensal"),
    7:  ("EFD Contribuições",    "EFD",  "exercicio",                      "mensal"),
    20: ("SPED ECF",             "ECF",  "exercicio",                      "anual"),
    27: ("eSocial",              "1627", "porPeriodo",                     "mensal"),
    33: ("EFD-Reinf",            "1633", "porPeriodo",                     "mensal"),
}


def _local(tag):
    return tag.split("}")[-1] if "}" in tag else tag


def _normalize_date(value, end=False):
    """Aceita YYYY-MM-DD ou YYYY-MM; YYYY-MM vira 1º ou último dia do mês."""
    value = str(value).strip()
    if len(value) == 7 and value[4] == "-":  # YYYY-MM
        year, month = int(value[:4]), int(value[5:7])
        day = monthrange(year, month)[1] if end else 1
        return f"{year:04d}-{month:02d}-{day:02d}"
    return value


def _sistema_info(sistema):
    if sistema not in SISTEMAS:
        raise ValueError(
            f"Sistema {sistema} não reconhecido. "
            f"Sistemas válidos: {list(SISTEMAS)}"
        )
    nome, tipo_arquivo, tipo_pesquisa, periodicidade = SISTEMAS[sistema]
    return {
        "nome": nome,
        "tipoarquivo": tipo_arquivo,
        "tipopesquisa": tipo_pesquisa,
        "periodicidade": periodicidade,
    }


def _build_identificacao(
    sistema,
    perfil="contr",
    nirepresentado=None,
    tiponirepresentado=None,
):
    info = _sistema_info(sistema)
    attrs = [
        f'perfil="{escape(str(perfil).strip())}"',
        f'sistema="{escape(str(sistema))}"',
        f'tipoarquivo="{escape(info["tipoarquivo"])}"',
        f'tipopesquisa="{escape(info["tipopesquisa"])}"',
    ]
    if nirepresentado is not None:
        attrs.append(f'nirepresentado="{escape(str(nirepresentado).strip())}"')
    if tiponirepresentado is not None:
        attrs.append(f'tiponirepresentado="{escape(str(tiponirepresentado).strip())}"')
    return "<identificacao " + " ".join(attrs) + "/>"


def _campo(nome, valor):
    return f'<campo nome="{escape(str(nome))}" valor="{escape(str(valor))}"/>'


def _parse_saida_xml(saida):
    """Extrai mensagem, IDs de arquivo e pedido_id do XML em saida."""
    result = {"mensagem": None, "arquivos": [], "pedido_id": None}
    if not saida:
        return result

    text = unescape(saida).strip()
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        result["mensagem"] = text
        return result

    for elem in root.iter():
        name = _local(elem.tag)
        if name == "mensagem" and elem.text:
            result["mensagem"] = elem.text
        elif name == "arquivo":
            aid = elem.attrib.get("id")
            if aid:
                result["arquivos"].append(aid)
        elif name in ("retornopedido", "pedido"):
            pid = elem.attrib.get("id")
            if pid and pid != "0":
                result["pedido_id"] = pid

    if result["pedido_id"] is None and root.attrib.get("id") not in (None, "0"):
        if _local(root.tag) == "retornopedido":
            result["pedido_id"] = root.attrib.get("id")

    return result


class cliente:
    """Cliente SOAP base para o serviço local ReceitanetBX."""

    _SOAP_NS = "http://ws.apache.org/axis2"
    _SOAPENV_NS = "http://schemas.xmlsoap.org/soap/envelope/"

    def __init__(self, host="localhost", port=2443, timeout=120, print_error=True):
        self.endpoint = f"http://{host}:{port}/services/ReceitanetBX"
        self.timeout = timeout
        self.print_error = print_error

    def _build_envelope(self, operation, entrada):
        """Monta o envelope SOAP 1.1 com entrada em CDATA (formato real do WS)."""
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<soapenv:Envelope xmlns:soapenv="{self._SOAPENV_NS}" '
            f'xmlns:axis="{self._SOAP_NS}">'
            "<soapenv:Header/>"
            "<soapenv:Body>"
            f"<axis:{operation}>"
            f"<axis:entrada><![CDATA[{entrada}]]></axis:entrada>"
            f"</axis:{operation}>"
            "</soapenv:Body>"
            "</soapenv:Envelope>"
        )

    def _parse_response(self, xml_text):
        """Extrai (retorno, saida) do XML de resposta SOAP."""
        root = ET.fromstring(xml_text)

        fault = None
        for elem in root.iter():
            if _local(elem.tag) == "Fault":
                fault = elem
                break

        if fault is not None:
            faultstring = ""
            for child in fault.iter():
                if _local(child.tag) == "faultstring":
                    faultstring = child.text or ""
                    break
            raise RuntimeError(faultstring or "SOAP Fault sem faultstring")

        retorno = None
        saida = ""
        for elem in root.iter():
            name = _local(elem.tag)
            if name == "retorno":
                retorno = int(elem.text) if elem.text is not None else 0
            elif name == "saida":
                saida = elem.text or ""

        if retorno is None:
            raise ValueError("Campo <retorno> não encontrado na resposta SOAP")

        return retorno, saida

    def _enrich(self, retorno, saida):
        parsed = _parse_saida_xml(saida)
        result = {
            "retorno": retorno,
            "saida": unescape(saida) if saida else "",
            "mensagem": parsed["mensagem"],
            "arquivos": parsed["arquivos"],
            "pedido_id": parsed["pedido_id"],
        }
        # retorno == 1: sucesso; == 0: erro de negócio
        if retorno != 1 and self.print_error:
            msg = parsed["mensagem"] or saida or "(sem mensagem)"
            print(f"Erro ReceitanetBX (retorno={retorno}): {msg}")
        return result

    def _call(self, operation, entrada):
        """Envia POST SOAP; retorna dict enriquecido ou {} em falha de transporte."""
        envelope = self._build_envelope(operation, entrada)
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f'"urn:{operation}"',
        }

        try:
            response = requests.post(
                self.endpoint,
                data=envelope.encode("utf-8"),
                headers=headers,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout:
            if self.print_error:
                print(f"Timeout ao chamar {operation} em {self.endpoint}")
            return {}
        except requests.exceptions.ConnectionError as e:
            if self.print_error:
                print(f"Erro de conexão ao chamar {operation} em {self.endpoint}: {e}")
            return {}
        except Exception as e:
            if self.print_error:
                print(f"Erro na requisição SOAP {operation}: {e}")
            return {}

        if response.status_code != 200:
            if self.print_error:
                print(
                    f"HTTP {response.status_code} em {operation}\n"
                    f"Resposta: {response.text}"
                )
            return {}

        try:
            retorno, saida = self._parse_response(response.text)
        except RuntimeError as e:
            if self.print_error:
                print(f"SOAP Fault em {operation}: {e}")
            return {}
        except Exception as e:
            if self.print_error:
                print(f"Erro ao parsear resposta de {operation}: {e}")
            return {}

        return self._enrich(retorno, saida)


class arquivos(cliente):
    """Operações PesquisarArquivos e SolicitarArquivos."""

    def _build_entrada_pesquisa(
        self,
        sistema,
        inicio,
        fim,
        perfil="contr",
        nirepresentado=None,
        tiponirepresentado=None,
        campos=None,
    ):
        inicio = _normalize_date(inicio, end=False)
        fim = _normalize_date(fim, end=True)
        parts = [
            "<pesquisa>",
            _build_identificacao(
                sistema,
                perfil=perfil,
                nirepresentado=nirepresentado,
                tiponirepresentado=tiponirepresentado,
            ),
            _campo("dataInicio", inicio),
            _campo("dataFim", fim),
        ]
        if campos:
            for nome, valor in campos.items():
                if valor is not None:
                    parts.append(_campo(nome, valor))
        parts.append("</pesquisa>")
        return "".join(parts)

    def _build_entrada_pedido(
        self,
        sistema,
        arquivos_ids,
        perfil="contr",
        nirepresentado=None,
        tiponirepresentado=None,
    ):
        if not arquivos_ids:
            raise ValueError("arquivos_ids não pode ser vazio")

        ids = [str(a).strip() for a in arquivos_ids if str(a).strip()]
        if not ids:
            raise ValueError("arquivos_ids não pode ser vazio")

        arqs = "".join(f'<arquivo id="{escape(i)}"/>' for i in ids)
        return (
            "<pedido>"
            + _build_identificacao(
                sistema,
                perfil=perfil,
                nirepresentado=nirepresentado,
                tiponirepresentado=tiponirepresentado,
            )
            + f"<arquivos>{arqs}</arquivos>"
            + "</pedido>"
        )

    def pesquisar(
        self,
        sistema,
        inicio,
        fim,
        perfil="contr",
        nirepresentado=None,
        tiponirepresentado=None,
        **campos,
    ):
        """Chama PesquisarArquivos.

        Args:
            sistema: ID do sistema RFB (ver SISTEMAS).
            inicio: Data inicial (YYYY-MM-DD ou YYYY-MM).
            fim: Data final (YYYY-MM-DD ou YYYY-MM).
            perfil: "contr" (contribuinte, padrão) ou "proc" (procurador).
            nirepresentado: NI do representado (obrigatório se perfil=proc).
            tiponirepresentado: "cpf" ou "cnpj" (com nirepresentado).
            **campos: Campos extras ``<campo nome=... valor=...>`` (ex.: cnpj, ie).

        Returns:
            dict com retorno, saida, mensagem, arquivos (lista de IDs) e pedido_id.
            {} em falha de conexão/HTTP.
        """
        entrada = self._build_entrada_pesquisa(
            sistema,
            inicio,
            fim,
            perfil=perfil,
            nirepresentado=nirepresentado,
            tiponirepresentado=tiponirepresentado,
            campos=campos or None,
        )
        return self._call("PesquisarArquivos", entrada)

    def solicitar(
        self,
        sistema,
        arquivos,
        perfil="contr",
        nirepresentado=None,
        tiponirepresentado=None,
    ):
        """Chama SolicitarArquivos com os IDs retornados por pesquisar().

        Args:
            sistema: ID do sistema RFB (mesmo da pesquisa).
            arquivos: Lista de IDs de arquivo (strings) vindos de pesquisar().
            perfil: "contr" (padrão) ou "proc".
            nirepresentado / tiponirepresentado: ver pesquisar().

        Returns:
            dict com retorno, saida, mensagem e pedido_id (quando sucesso).
        """
        entrada = self._build_entrada_pedido(
            sistema,
            arquivos,
            perfil=perfil,
            nirepresentado=nirepresentado,
            tiponirepresentado=tiponirepresentado,
        )
        return self._call("SolicitarArquivos", entrada)


class pedidos(cliente):
    """Operações VerificarSituacaoPedidos e ConsultarPedidos."""

    def _build_entrada_verificar(self, pedido_ids, atributos=False):
        if not pedido_ids:
            raise ValueError("pedido_ids não pode ser vazio")
        ids = [str(p).strip() for p in pedido_ids if str(p).strip()]
        if not ids:
            raise ValueError("pedido_ids não pode ser vazio")

        atr = ' atributos="true"' if atributos else ""
        itens = "".join(f'<pedido id="{escape(i)}"/>' for i in ids)
        return f"<pedidos{atr}>{itens}</pedidos>"

    def _build_entrada_consultar(self, **criterios):
        """Monta <consulta><criterios .../></consulta> conforme ConsultarPedidos.xsd."""
        allowed = {
            "datadownloadinicial",
            "datadownloadfinal",
            "dataprevistainicial",
            "dataprevistafinal",
            "datasolicitacaoinicial",
            "datasolicitacaofinal",
            "situacao",
            "nisolicitante",
            "tiponisolicitante",
            "sistema",
            "tipoarquivo",
            "pagina",
        }
        attrs = []
        for key, value in criterios.items():
            if value is None:
                continue
            if key not in allowed:
                raise ValueError(
                    f"Critério '{key}' inválido. Permitidos: {sorted(allowed)}"
                )
            attrs.append(f'{key}="{escape(str(value))}"')

        if attrs:
            return f'<consulta><criterios {" ".join(attrs)}/></consulta>'
        return "<consulta><criterios/></consulta>"

    def verificar_situacao(self, pedido_ids, atributos=False):
        """Chama VerificarSituacaoPedidos.

        Args:
            pedido_ids: Lista de IDs de pedido (ex.: do retorno de solicitar).
            atributos: Se True, pede atributos extras na resposta.

        Returns:
            dict com retorno, saida, mensagem, etc.
        """
        if isinstance(pedido_ids, (str, int)):
            pedido_ids = [pedido_ids]
        entrada = self._build_entrada_verificar(pedido_ids, atributos=atributos)
        return self._call("VerificarSituacaoPedidos", entrada)

    def consultar(self, **criterios):
        """Chama ConsultarPedidos.

        Critérios opcionais (atributos de ``<criterios>``):
            datadownloadinicial, datadownloadfinal,
            dataprevistainicial, dataprevistafinal,
            datasolicitacaoinicial, datasolicitacaofinal,
            situacao (processando|disponivel|erro|inativo),
            nisolicitante, tiponisolicitante (cpf|cnpj),
            sistema, tipoarquivo, pagina.
        """
        entrada = self._build_entrada_consultar(**criterios)
        return self._call("ConsultarPedidos", entrada)
