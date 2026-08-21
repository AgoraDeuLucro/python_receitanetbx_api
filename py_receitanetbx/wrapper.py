"""
Wrapper não oficial do ReceitanetBX (Receita Federal).

Fluxo típico::

    from py_receitanetbx import arquivos, pedidos, SISTEMAS

    arq = arquivos()  # http://localhost:2443/services/ReceitanetBX
    # arq = arquivos(debug=True)  # imprime request/response no terminal

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


# Catálogo oficial (banco Derby do ReceitanetBX):
# id_sistema -> {nome, tipos: {id_tipo -> {nome, pesquisas: {id_pesquisa -> ...}}}}
SISTEMAS = {
    1: {
        'nome': 'SPED Contábil',
        'tipos': {
            '1601': {
                'nome': 'Escrituração Contábil Digital',
                'pesquisas': {
                    'porPeriodo': {
                        'nome': 'Por Período da Escrituração',
                        'papeis': ['repr', 'proc', 'contr'],
                        'finalidade': 'listagem',
                    },
                    'porCNPJPeriodo': {
                        'nome': 'Por CNPJ e Período da Escrituração',
                        'papeis': ['fiscente', 'fiscrec', 'b2b'],
                        'finalidade': 'listagem',
                    },
                    'porCNPJPeriodoRequisicaoJudicial': {
                        'nome': 'Requisição Judicial - Por CNPJ e Período da Escrituração',
                        'papeis': ['fiscrec'],
                        'finalidade': 'listagem',
                    },
                    'porCNPJPeriodoEntrega': {
                        'nome': 'Por CNPJ e Período de Entrega',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'listagem',
                    },
                    'porCNPJPeriodoB2B': {
                        'nome': 'Pedido Por CNPJ e Período da Escrituração B2B',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                    },
                    'porCNPJPeriodoEntregaB2B': {
                        'nome': 'Pedido Por CNPJ e Período de Entrega B2B',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '1601-DA': {
                'nome': 'Dados Agregados de Escrituração Contábil Digital',
                'pesquisas': {
                    'porPeriodo': {
                        'nome': 'Por Período da Escrituração',
                        'papeis': ['repr', 'proc', 'contr'],
                        'finalidade': 'listagem',
                    },
                    'porArquivoPeriodoEntrega': {
                        'nome': 'Por Arquivo com CNPJs e Período de Entrega',
                        'papeis': ['fiscente', 'fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                    },
                    'porListaCNPJsPeriodoEntrega': {
                        'nome': 'Por Lista de CNPJs e Período de Entrega',
                        'papeis': ['fiscente', 'fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                    },
                    'porArquivoPeriodoEscrituracao': {
                        'nome': 'Por Arquivo com CNPJs e Período da Escrituração',
                        'papeis': ['fiscente', 'fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                    },
                    'porListaCNPJsPeriodoEscrituracao': {
                        'nome': 'Por Lista de CNPJs e Período da Escrituração',
                        'papeis': ['fiscente', 'fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '1601-TE': {
                'nome': 'Termos Emitidos pelas Juntas Comerciais',
                'pesquisas': {
                    'porPeriodo': {
                        'nome': 'Por Período da Escrituração',
                        'papeis': ['repr', 'proc', 'contr'],
                        'finalidade': 'listagem',
                    },
                },
            },
        },
    },
    2: {
        'nome': 'SPED Fiscal - EFD ICMS IPI',
        'tipos': {
            '1602': {
                'nome': 'Escrituração Fiscal Digital',
                'pesquisas': {
                    'porCNPJIEPeriodoContribuinte': {
                        'nome': 'Por Período da Escrituracao',
                        'papeis': ['repr', 'proc', 'contr'],
                        'finalidade': 'listagem',
                    },
                    'porCNPJPeriodoTransmissao': {
                        'nome': 'Por CNPJ e Período de Transmissão/Recepção',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'listagem',
                    },
                    'porCPFPeriodoTransmissao': {
                        'nome': 'Por CPF (Produtor Rural) e Período de Transmissão/Recepção',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'listagem',
                    },
                    'porCNPJPeriodoEFD': {
                        'nome': 'Por CNPJ e Período da Escrituração',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'listagem',
                    },
                    'porCPFPeriodoEFD': {
                        'nome': 'Por CPF (Produtor Rural) e Período da Escrituração',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'listagem',
                    },
                    'porCNPJPeriodoTransmissaoB2B': {
                        'nome': 'Pedido Por CNPJ e Período de Transmissão B2B',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                    },
                    'porCPFPeriodoTransmissaoB2B': {
                        'nome': 'Pedido Por CPF (Produtor Rural) e Período de Transmissão/Recepção B2B',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                    },
                    'porCNPJPeriodoEFDB2B': {
                        'nome': 'Pedido Por CNPJ e Período da Escrituração B2B',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                    },
                    'porCPFPeriodoEFDB2B': {
                        'nome': 'Pedido Por CPF (Produtor Rural) e Período da Escrituração B2B',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                    },
                    'porCNPJIEPeriodoTransmissao': {
                        'nome': 'Por CNPJ',
                        'papeis': ['IE e Período de Transmissão/Recepção'],
                        'finalidade': 'fiscente',
                    },
                    'porCPFIEPeriodoTransmissao': {
                        'nome': 'Por CPF (Produtor Rural)',
                        'papeis': ['IE e Período de Transmissão/Recepção'],
                        'finalidade': 'fiscente',
                    },
                    'porCNPJIEPeriodoEFD': {
                        'nome': 'Por CNPJ',
                        'papeis': ['IE e Período da Escrituracao'],
                        'finalidade': 'fiscente',
                    },
                    'porCPFIEPeriodoEFD': {
                        'nome': 'Por CPF (Produtor Rural)',
                        'papeis': ['IE e Período da Escrituracao'],
                        'finalidade': 'fiscente',
                    },
                },
            },
            '1602-OutUF': {
                'nome': 'Escrituração Fiscal Digital - Outra UF',
                'pesquisas': {
                    'porCNPJIEPeriodoEFD': {
                        'nome': 'Por CNPJ',
                        'papeis': ['IE e Período da Escrituracao'],
                        'finalidade': 'fiscente',
                    },
                    'porCPFIEPeriodoEFD': {
                        'nome': 'Por CPF (Produtor Rural)',
                        'papeis': ['IE e Período da Escrituracao'],
                        'finalidade': 'fiscente',
                    },
                },
            },
            '1602-OIE': {
                'nome': 'Operações Interestaduais de Escrituração Fiscal Digital',
                'pesquisas': {
                    'porCNPJIEPeriodoTransmissao': {
                        'nome': 'Por CNPJ',
                        'papeis': ['IE e Período de Transmissão/Recepção'],
                        'finalidade': 'fiscente',
                    },
                    'porCPFIEPeriodoTransmissao': {
                        'nome': 'Por CPF (Produtor Rural)',
                        'papeis': ['IE e Período de Transmissão/Recepção'],
                        'finalidade': 'fiscente',
                    },
                    'porCNPJIEPeriodoEFD': {
                        'nome': 'Por CNPJ',
                        'papeis': ['IE e Período da Escrituracao'],
                        'finalidade': 'fiscente',
                    },
                    'porCPFIEPeriodoEFD': {
                        'nome': 'Por CPF (Produtor Rural)',
                        'papeis': ['IE e Período da Escrituracao'],
                        'finalidade': 'fiscente',
                    },
                },
            },
        },
    },
    3: {
        'nome': 'SPED NF-e',
        'tipos': {
            '55': {
                'nome': 'Nota Fiscal Eletronica',
                'pesquisas': {
                    'porChaveAcesso': {
                        'nome': 'Por Chave de Acesso',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                    },
                    'porArquivoChvAcesso': {
                        'nome': 'Por Arquivo com Chaves de Acesso',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                    },
                    'porArquivoListaNFe': {
                        'nome': 'Por Arquivo com lista de UF/CNPJ/Série/Número da NFe',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                    },
                    'porCNPJPeriodo': {
                        'nome': 'Por CNPJ e Periodo',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                    },
                    'porCNPJPeriodoRetornandoLista': {
                        'nome': 'Por CNPJ e Periodo retornando lista de Chaves de Acesso',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                    },
                    'porCNPJDiaCorrente': {
                        'nome': 'Por CNPJ retornando DF-e do dia corrente',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                    },
                },
            },
        },
    },
    4: {
        'nome': 'PER/DCOMP',
        'tipos': {
            '2001': {
                'nome': 'Documentos Fiscais - Transmissão PER/DCOMP',
                'pesquisas': {
                    'porPeriodoArrecadacao': {
                        'nome': 'Por CNPJ e Período',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'listagem_e_pedido',
                    },
                },
            },
        },
    },
    6: {
        'nome': 'SINAC',
        'tipos': {
            '1': {
                'nome': 'Arquivos de Optantes',
                'pesquisas': {
                    'periodo': {
                        'nome': 'Período',
                        'papeis': ['fiscente'],
                        'finalidade': 'pedido',
                    },
                },
            },
        },
    },
    7: {
        'nome': 'SPED Contribuições',
        'tipos': {
            'EFD': {
                'nome': 'Escrituração',
                'pesquisas': {
                    'periodoEntrega': {
                        'nome': 'Período de Entrega',
                        'papeis': ['contr', 'proc', 'repr'],
                        'finalidade': 'listagem_e_pedido',
                    },
                    'periodoEntregaIncorporada': {
                        'nome': 'Período de Entrega da Incorporada',
                        'papeis': ['contr', 'proc', 'repr'],
                        'finalidade': 'listagem_e_pedido',
                    },
                    'exercicio': {
                        'nome': 'Período da Escrituração',
                        'papeis': ['contr', 'proc', 'repr'],
                        'finalidade': 'listagem_e_pedido',
                    },
                    'exercicioIncorporada': {
                        'nome': 'Período de Escrituração da Incorporada',
                        'papeis': ['contr', 'proc', 'repr'],
                        'finalidade': 'listagem_e_pedido',
                    },
                    'cnpjPeriodoEntrega': {
                        'nome': 'CNPJ e Período de Entrega',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'listagem_e_pedido',
                    },
                    'cnpjExercicio': {
                        'nome': 'CNPJ e Período da Escrituração',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'listagem_e_pedido',
                    },
                    'listaCNPJPeriodoEntrega': {
                        'nome': 'Lista de CNPJ e Período de Entrega',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'pedido',
                    },
                    'listaCNPJExercicio': {
                        'nome': 'Lista de CNPJ e Período da Escrituração',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'pedido',
                    },
                },
            },
            'DA': {
                'nome': 'Dados Agregados',
                'pesquisas': {
                    'listaCNPJPeriodoEntrega': {
                        'nome': 'Lista de CNPJ e Período de Entrega',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'pedido',
                    },
                    'CNPJ10PeriodoEntrega': {
                        'nome': 'CNPJ e Período de Entrega',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'pedido',
                    },
                    'listaCNPJExercicio': {
                        'nome': 'Lista de CNPJ e Período da Escrituração',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'pedido',
                    },
                    'CNPJ10Exercicio': {
                        'nome': 'CNPJ e Período da Escrituração',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'pedido',
                    },
                    'Completa': {
                        'nome': 'Completa',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'pedido',
                    },
                    'DataLucroReal': {
                        'nome': 'Lucro Real/Dia de Entrega',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                    },
                    'DataRegimeTributario': {
                        'nome': 'Regime Tributário/Dia de Entrega',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                    },
                },
            },
        },
    },
    11: {
        'nome': 'Dirf',
        'tipos': {
            '1': {
                'nome': 'Extracao Dirf Contagil',
                'pesquisas': {
                    'pesqlista': {
                        'nome': 'Arquivo com Ano-Calendario e Tipo NI e NI',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                    },
                    'pesqunit': {
                        'nome': 'Ano-Calendario e Tipo NI e NI (CPF ou CNPJ)',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                    },
                },
            },
        },
    },
    12: {
        'nome': 'SIEFRDOC',
        'tipos': {
            '1': {
                'nome': 'Pagamento',
                'pesquisas': {
                    'porNIANOARRECADACAO': {
                        'nome': 'por NI e ano de arrecadacao',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                    },
                },
            },
        },
    },
    13: {
        'nome': 'DCTF',
        'tipos': {
            'declaracao': {
                'nome': 'Declaração DCTF',
                'pesquisas': {
                    'cnpjanocalendario': {
                        'nome': 'CNPJ e Ano Calendário',
                        'papeis': ['B2B'],
                        'finalidade': 'pedido',
                    },
                    'arquivocnpjanocalendario': {
                        'nome': 'Arquivo com CNPJ e Ano Calendário',
                        'papeis': ['B2B'],
                        'finalidade': 'pedido',
                    },
                },
            },
        },
    },
    14: {
        'nome': 'DIMOF',
        'tipos': {
            '1': {
                'nome': 'Extração Dimof Contágil',
                'pesquisas': {
                    'P1': {
                        'nome': 'Ano Calendário e NI',
                        'papeis': ['B2B'],
                        'finalidade': 'pedido',
                    },
                    'P2': {
                        'nome': 'Arquivo com Ano Calendário e NI',
                        'papeis': ['B2B'],
                        'finalidade': 'pedido',
                    },
                },
            },
        },
    },
    16: {
        'nome': 'Simples Nacional',
        'tipos': {
            '1': {
                'nome': 'PGDAS_D',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '2': {
                'nome': 'PGDAS',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '3': {
                'nome': 'PGMEI',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '4': {
                'nome': 'DASNSIMEI',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '5': {
                'nome': 'PGDASD_DAS',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '6': {
                'nome': 'DEFIS',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '7': {
                'nome': 'DAS_COBRANCA',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '8': {
                'nome': 'DASN_2008',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '9': {
                'nome': 'DASN_2009',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '10': {
                'nome': 'DASN_2010',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '11': {
                'nome': 'DASN_2011',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '12': {
                'nome': 'DASN_2012',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '13': {
                'nome': 'AINF',
                'pesquisas': {
                    '2': {
                        'nome': 'Por Ente e Período',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '14': {
                'nome': 'PARCSN',
                'pesquisas': {
                    '3': {
                        'nome': 'Por Período',
                        'papeis': [],
                        'finalidade': 'pedido',
                    },
                },
            },
            '15': {
                'nome': 'CONTAGIL',
                'pesquisas': {
                    '4': {
                        'nome': 'Lista Cnpj e Ano',
                        'papeis': [],
                        'finalidade': 'pedido',
                    },
                },
            },
            '16': {
                'nome': 'PARCSNESP',
                'pesquisas': {
                    '3': {
                        'nome': 'Por Período',
                        'papeis': [],
                        'finalidade': 'pedido',
                    },
                },
            },
            '18': {
                'nome': 'PGDASD2018',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '19': {
                'nome': 'PGDASDDAS2018',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '20': {
                'nome': 'DASCOBRANCA2018',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '21': {
                'nome': 'PGDASD2018MALHA',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
        },
    },
    17: {
        'nome': 'Eventos SN',
        'tipos': {
            '1': {
                'nome': 'Arquivos de Optantes',
                'pesquisas': {
                    'periodo': {
                        'nome': 'Período',
                        'papeis': ['fiscente'],
                        'finalidade': 'listagem',
                    },
                },
            },
        },
    },
    18: {
        'nome': 'SPED - CT-e',
        'tipos': {
            '57': {
                'nome': 'Conhecimento de Transporte Eletrônico',
                'pesquisas': {
                    'porChaveAcesso': {
                        'nome': 'Por Chave de Acesso',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                    },
                    'porArquivoChvAcesso': {
                        'nome': 'Por Arquivo com Chaves de Acesso',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                    },
                    'porInscricaoEmitenteEPeriodo': {
                        'nome': 'Por CNPJ/CPF Emitente e Período',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                    },
                    'porInscricaoRemetenteDestinatarioEPeriodo': {
                        'nome': 'Por CNPJ/CPF Remetente/Destinatário e Período',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                    },
                    'porInscricaoEmitenteDiaCorrente': {
                        'nome': 'Por CNPJ/CPF Emitente retornando DF-e do dia corrente',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                    },
                    'porInscricaoRemetenteDestinatarioDiaCorrente': {
                        'nome': 'Por CNPJ/CPF Remetente/Destinatário retornando DF-e do Dia Corrente',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                    },
                },
            },
        },
    },
    20: {
        'nome': 'SPED ECF',
        'tipos': {
            'ECF': {
                'nome': 'Escrituração',
                'pesquisas': {
                    'periodoEntrega': {
                        'nome': 'Período de Entrega',
                        'papeis': ['contr', 'proc', 'repr'],
                        'finalidade': 'listagem_e_pedido',
                    },
                    'exercicio': {
                        'nome': 'Período da Escrituração',
                        'papeis': ['contr', 'proc', 'repr'],
                        'finalidade': 'listagem_e_pedido',
                    },
                    'cnpjPeriodoEntrega': {
                        'nome': 'CNPJ e Período de Entrega',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'listagem_e_pedido',
                    },
                    'cnpjExercicio': {
                        'nome': 'CNPJ e Período da Escrituração',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'listagem_e_pedido',
                    },
                    'listaCNPJPeriodoEntrega': {
                        'nome': 'Lista de CNPJ e Período de Entrega',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'pedido',
                    },
                    'listaCNPJExercicio': {
                        'nome': 'Lista de CNPJ e Período da Escrituração',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'pedido',
                    },
                },
            },
        },
    },
    22: {
        'nome': 'DACON',
        'tipos': {
            '1': {
                'nome': 'Demonstrativo DACON',
                'pesquisas': {
                    'pesqunit': {
                        'nome': 'Ano-Calendário e NI (CNPJ)',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                    },
                    'pesqlista': {
                        'nome': 'Arquivo com Ano-Calendário e NI',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                    },
                },
            },
        },
    },
    23: {
        'nome': 'DIMOB',
        'tipos': {
            '1': {
                'nome': 'Demonstrativo DIMOB',
                'pesquisas': {
                    'pesqunit': {
                        'nome': 'Ano-Calendário e NI (CNPJ)',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                    },
                    'pesqlista': {
                        'nome': 'Arquivo com Ano-Calendário e NI',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                    },
                },
            },
        },
    },
    24: {
        'nome': 'e-Financeira',
        'tipos': {
            '10': {
                'nome': 'Todos',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Número de Recibo',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '1': {
                'nome': 'Evento de Abertura',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Número de Recibo',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '3': {
                        'nome': 'Por CNPJ Declarante e Identificador do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '8': {
                        'nome': 'Por CNPJ Declarante e Tipo do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '2': {
                'nome': 'Evento de Cadastro Empresa Declarante',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Número de Recibo',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '3': {
                        'nome': 'Por CNPJ Declarante e Identificador do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '8': {
                        'nome': 'Por CNPJ Declarante e Tipo do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '3': {
                'nome': 'Evento de Cadastro de Intermediário',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Número de Recibo',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '3': {
                        'nome': 'Por CNPJ Declarante e Identificador do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '4': {
                'nome': 'Evento de Cadastro de Patrocinado',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Número de Recibo',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '3': {
                        'nome': 'Por CNPJ Declarante e Identificador do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '5': {
                'nome': 'Evento de Exclusao',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Número de Recibo',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '3': {
                        'nome': 'Por CNPJ Declarante e Identificador do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '6': {
                'nome': 'Evento de Exclusão e-Financeira',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Número de Recibo',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '3': {
                        'nome': 'Por CNPJ Declarante e Identificador do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '7': {
                'nome': 'Evento de Fechamento',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Número de Recibo',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '3': {
                        'nome': 'Por CNPJ Declarante e Identificador do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '8': {
                        'nome': 'Por CNPJ Declarante e Tipo do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '9': {
                'nome': 'Evento de Movimentação de Previdência Privada',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Número de Recibo',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '2': {
                        'nome': 'Por NI do Declarado e Período das informações',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '6': {
                        'nome': 'Por NI do Declarado e Período de Entrega',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '3': {
                        'nome': 'Por CNPJ Declarante e Identificador do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '13': {
                        'nome': 'Por CNPJ do Declarante e Lista de Recibos',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '8': {
                'nome': 'Evento de Movimentação de Operação Financeira',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Número de Recibo',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '2': {
                        'nome': 'Por NI do Declarado e Período das informações',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '6': {
                        'nome': 'Por NI do Declarado e Período de Entrega',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '3': {
                        'nome': 'Por CNPJ Declarante e Identificador do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '13': {
                        'nome': 'Por CNPJ do Declarante e Lista de Recibos',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '11': {
                'nome': 'Evento de Movimentação de Operação Financeira Anual',
                'pesquisas': {
                    '13': {
                        'nome': 'Por CNPJ do Declarante e Lista de Recibos',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
        },
    },
    25: {
        'nome': 'SIEFCOBR',
        'tipos': {
            'COMPSN': {
                'nome': 'Compensações SN a pedido',
                'pesquisas': {},
            },
        },
    },
    27: {
        'nome': 'eSocial',
        'tipos': {
            '1': {
                'nome': 'Eventos e recibos',
                'pesquisas': {
                    'EVT_NUMREC': {
                        'nome': 'Eventos por número de recibo',
                        'papeis': ['fiscrec', 'fiscente'],
                        'finalidade': 'pedido',
                    },
                    'EVT_TRAB_EMP_PERREC': {
                        'nome': 'Eventos trabalhistas por empregador e período de envio',
                        'papeis': ['fiscrec', 'fiscente'],
                        'finalidade': 'listagem_e_pedido',
                    },
                    'EVT_CAD_TRAB_PER_EMP_PERREC': {
                        'nome': 'Eventos Cadastrais, de tabela, trabalhistas e periódicos por empregador e período de envio',
                        'papeis': ['fiscrec', 'fiscente'],
                        'finalidade': 'listagem_e_pedido',
                    },
                    'EVT_CAD_TRAB_PER_EMP_PERAPUR': {
                        'nome': 'Eventos Cadastrais, de tabela, trabalhistas e periódicos por empregador e período de apuração',
                        'papeis': ['fiscrec', 'fiscente'],
                        'finalidade': 'listagem_e_pedido',
                    },
                },
            },
        },
    },
    32: {
        'nome': 'SPED Fiscal Entes Entrega BX',
        'tipos': {
            'SPED-ICMS-IPI-ENT-BX': {
                'nome': 'Arquivo do SPED Fiscal ICMS-IPI',
                'pesquisas': {},
            },
        },
    },
    33: {
        'nome': 'SPED EFD-Reinf',
        'tipos': {
            '10001070': {
                'nome': 'Eventos de Tabelas',
                'pesquisas': {
                    '2': {
                        'nome': 'Baixar Eventos de Tabelas por Contribuinte',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '1': {
                        'nome': 'Baixar Eventos de Tabelas',
                        'papeis': ['contr', 'proc', 'repr'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '2000': {
                'nome': 'Eventos da família 2000',
                'pesquisas': {
                    '5': {
                        'nome': 'Baixar Eventos série 2000/Previdenciários por Contribuinte e Período de Apuração',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '6': {
                        'nome': 'Baixar Eventos série 2000/Previdenciários por Contribuinte e Data de Recepção',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
            '4000': {
                'nome': 'Eventos da família 4000',
                'pesquisas': {
                    '9': {
                        'nome': 'Baixar Eventos série 4000/Retenção por Contribuinte e Período de Apuração',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                    '10': {
                        'nome': 'Baixar Eventos série 4000/Retenção por Contribuinte e Data de Recepção',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                    },
                },
            },
        },
    },
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
    """Metadados do primeiro tipo/pesquisa (compatibilidade interna)."""
    if sistema not in SISTEMAS:
        raise ValueError(
            f"Sistema {sistema} não reconhecido. "
            f"Sistemas válidos: {list(SISTEMAS)}"
        )
    info = SISTEMAS[sistema]
    tipoarquivo = next(iter(info["tipos"]))
    tipo_info = info["tipos"][tipoarquivo]
    pesquisas = tipo_info["pesquisas"]
    tipopesquisa = next(iter(pesquisas)) if pesquisas else None
    return {
        "nome": info["nome"],
        "tipoarquivo": tipoarquivo,
        "tipopesquisa": tipopesquisa,
        "tipo_nome": tipo_info["nome"],
    }


def _resolve_tipo(sistema, tipoarquivo=None, tipopesquisa=None):
    """Valida e resolve (tipoarquivo, tipopesquisa) com fallback ao primeiro."""
    if sistema not in SISTEMAS:
        raise ValueError(
            f"Sistema {sistema} não reconhecido. "
            f"Sistemas válidos: {list(SISTEMAS)}"
        )
    tipos = SISTEMAS[sistema]["tipos"]
    if not tipos:
        raise ValueError(f"Sistema {sistema} não possui tipos de arquivo definidos")

    if tipoarquivo is None:
        tipoarquivo = next(iter(tipos))
    else:
        tipoarquivo = str(tipoarquivo).strip()
        if tipoarquivo not in tipos:
            raise ValueError(
                f"tipoarquivo {tipoarquivo!r} inválido para sistema {sistema}. "
                f"Válidos: {list(tipos)}"
            )

    pesquisas = tipos[tipoarquivo]["pesquisas"]
    if tipopesquisa is None:
        if not pesquisas:
            raise ValueError(
                f"Sistema {sistema} / tipo {tipoarquivo!r} não possui "
                f"tipopesquisa definido; informe tipopesquisa explicitamente "
                f"ou use outro tipoarquivo"
            )
        tipopesquisa = next(iter(pesquisas))
    else:
        tipopesquisa = str(tipopesquisa).strip()
        if tipopesquisa not in pesquisas:
            raise ValueError(
                f"tipopesquisa {tipopesquisa!r} inválido para sistema {sistema} "
                f"/ tipo {tipoarquivo!r}. Válidos: {list(pesquisas)}"
            )

    return tipoarquivo, tipopesquisa


def _build_identificacao(
    sistema,
    tipoarquivo,
    tipopesquisa,
    perfil="contr",
    nirepresentado=None,
    tiponirepresentado=None,
):
    attrs = [
        f'perfil="{escape(str(perfil).strip())}"',
        f'sistema="{escape(str(sistema))}"',
        f'tipoarquivo="{escape(str(tipoarquivo))}"',
        f'tipopesquisa="{escape(str(tipopesquisa))}"',
    ]
    if nirepresentado is not None:
        attrs.append(f'nirepresentado="{escape(str(nirepresentado).strip())}"')
    if tiponirepresentado is not None:
        attrs.append(
            f'tiponirepresentado="{escape(str(tiponirepresentado).strip())}"'
        )
    return "<identificacao " + " ".join(attrs) + "/>"


def _campo(nome, valor):
    return f'<campo nome="{escape(str(nome))}" valor="{escape(str(valor))}"/>'


def _parse_bool_attr(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ("true", "v", "1"):
        return True
    if text in ("false", "f", "0"):
        return False
    return None


def _parse_arquivo_elem(elem):
    arq = {
        "id": elem.attrib.get("id"),
        "situacao": elem.attrib.get("situacao"),
        "local": elem.attrib.get("local"),
        "datadownload": elem.attrib.get("datadownload"),
        "dataprevista": elem.attrib.get("dataprevista"),
        "hash": elem.attrib.get("hash"),
        "tipohash": elem.attrib.get("tipohash"),
        "tamanho": elem.attrib.get("tamanho"),
        "atributos": [],
    }
    for child in elem:
        if _local(child.tag) == "atributo":
            arq["atributos"].append(
                {
                    "nome": child.attrib.get("nome"),
                    "valor": child.attrib.get("valor"),
                    "tipo": child.attrib.get("tipo"),
                }
            )
    return arq


def _parse_pedido_elem(elem):
    pedido = {
        "id": elem.attrib.get("id"),
        "situacao": elem.attrib.get("situacao"),
        "mensagem": elem.attrib.get("mensagem"),
        "nisolicitante": elem.attrib.get("nisolicitante"),
        "tiponisolicitante": elem.attrib.get("tiponisolicitante"),
        "sistema": elem.attrib.get("sistema"),
        "tipoarquivo": elem.attrib.get("tipoarquivo"),
        "datasolicitacao": elem.attrib.get("datasolicitacao"),
        "dataprevista": elem.attrib.get("dataprevista"),
        "arquivos": [],
    }
    for child in elem:
        if _local(child.tag) == "arquivo":
            pedido["arquivos"].append(_parse_arquivo_elem(child))
    return pedido


def _parse_saida_xml(saida):
    """Extrai mensagem, IDs de arquivo, pedidos e metadados do XML em saida."""
    result = {
        "mensagem": None,
        "arquivos": [],
        "pedido_id": None,
        "pedido_ids": [],
        "ultima_pagina": None,
        "pedidos": [],
    }
    if not saida:
        return result

    text = unescape(saida).strip()
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        result["mensagem"] = text
        return result

    root_name = _local(root.tag)

    # ConsultarPedidos: <retornoconsulta ultimapagina="..."><id>...</id>
    if root_name == "retornoconsulta":
        result["ultima_pagina"] = _parse_bool_attr(root.attrib.get("ultimapagina"))
        for elem in root:
            name = _local(elem.tag)
            if name == "id" and elem.text and elem.text.strip():
                result["pedido_ids"].append(elem.text.strip())
            elif name == "mensagem" and elem.text:
                result["mensagem"] = elem.text

    # VerificarSituacaoPedidos: <retornopedidos><pedidos><pedido ...>
    elif root_name == "retornopedidos":
        for elem in root.iter():
            if _local(elem.tag) != "pedido" or not elem.attrib.get("id"):
                continue
            # Só inclui pedidos de status (com situacao ou filhos arquivo)
            if (
                elem.attrib.get("situacao") is not None
                or any(_local(c.tag) == "arquivo" for c in elem)
            ):
                result["pedidos"].append(_parse_pedido_elem(elem))
            elif result["pedido_id"] is None and elem.attrib.get("id") != "0":
                result["pedido_id"] = elem.attrib.get("id")
        for child in root:
            if _local(child.tag) == "mensagem" and child.text:
                result["mensagem"] = child.text
                break
        for ped in result["pedidos"]:
            for arq in ped.get("arquivos") or []:
                if arq.get("id"):
                    result["arquivos"].append(arq["id"])

    else:
        # PesquisarArquivos / SolicitarArquivos / genérico
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
            elif name == "id" and elem.text and elem.text.strip():
                result["pedido_ids"].append(elem.text.strip())

        if result["pedido_id"] is None and root.attrib.get("id") not in (None, "0"):
            if root_name == "retornopedido":
                result["pedido_id"] = root.attrib.get("id")

    return result


class cliente:
    """Cliente SOAP base para o serviço local ReceitanetBX."""

    _SOAP_NS = "http://ws.apache.org/axis2"
    _SOAPENV_NS = "http://schemas.xmlsoap.org/soap/envelope/"

    def __init__(
        self,
        host="localhost",
        port=2443,
        timeout=120,
        print_error=True,
        debug=False,
    ):
        self.endpoint = f"http://{host}:{port}/services/ReceitanetBX"
        self.timeout = timeout
        self.print_error = print_error
        self.debug = debug

    def _build_envelope(self, operation, entrada):
        """Monta o envelope SOAP 1.1 com entrada em CDATA (formato real do WS)."""
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<soapenv:Envelope xmlns:soapenv="{self._SOAPENV_NS}" '
            f'xmlns:axis="{self._SOAP_NS}"'
            '>'
            "<soapenv:Header/>"
            "<soapenv:Body>"
            f"<axis:{operation}>"
            f"<axis:entrada><![CDATA[{entrada}]]></axis:entrada>"
            f"</axis:{operation}>"
            "</soapenv:Body>"
            "</soapenv:Envelope>"
        )

    def _print_debug_request(self, method, url, headers, body):
        sep = "=" * 72
        print(sep)
        print(f"[DEBUG] REQUEST")
        print(sep)
        print(f"{method} {url}")
        print()
        print("Headers:")
        for key, value in headers.items():
            print(f"  {key}: {value}")
        print()
        print("Body:")
        print(body)
        print(sep)

    def _print_debug_response(self, response):
        sep = "=" * 72
        print(sep)
        print(f"[DEBUG] RESPONSE")
        print(sep)
        print(f"HTTP {response.status_code} {response.reason}")
        print()
        print("Headers:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
        print()
        print("Body:")
        print(response.text)
        print(sep)

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
            "pedido_ids": parsed["pedido_ids"],
            "ultima_pagina": parsed["ultima_pagina"],
            "pedidos": parsed["pedidos"],
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

        if self.debug:
            self._print_debug_request("POST", self.endpoint, headers, envelope)

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
                print(
                    f"Erro de conexão ao chamar {operation} em {self.endpoint}: {e}"
                )
            return {}
        except Exception as e:
            if self.print_error:
                print(f"Erro na requisição SOAP {operation}: {e}")
            return {}

        if self.debug:
            self._print_debug_response(response)

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
        tipoarquivo=None,
        tipopesquisa=None,
        campos=None,
    ):
        inicio = _normalize_date(inicio, end=False)
        fim = _normalize_date(fim, end=True)
        tipoarquivo, tipopesquisa = _resolve_tipo(
            sistema, tipoarquivo=tipoarquivo, tipopesquisa=tipopesquisa
        )
        parts = [
            "<pesquisa>",
            _build_identificacao(
                sistema,
                tipoarquivo,
                tipopesquisa,
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
        arquivos_ids=None,
        perfil="contr",
        nirepresentado=None,
        tiponirepresentado=None,
        tipoarquivo=None,
        tipopesquisa=None,
        pesquisa_campos=None,
        termo_campos=None,
    ):
        has_arquivos = bool(arquivos_ids)
        has_pesquisa = bool(pesquisa_campos)
        if has_arquivos and has_pesquisa:
            raise ValueError(
                "Informe apenas um de: arquivos ou pesquisa_campos "
                "(mutuamente exclusivos conforme a documentação)"
            )
        if not has_arquivos and not has_pesquisa:
            raise ValueError(
                "Informe arquivos (lista de IDs) ou pesquisa_campos (dict de critérios)"
            )

        tipoarquivo, tipopesquisa = _resolve_tipo(
            sistema, tipoarquivo=tipoarquivo, tipopesquisa=tipopesquisa
        )

        parts = [
            "<pedido>",
            _build_identificacao(
                sistema,
                tipoarquivo,
                tipopesquisa,
                perfil=perfil,
                nirepresentado=nirepresentado,
                tiponirepresentado=tiponirepresentado,
            ),
        ]

        if termo_campos:
            parts.append("<termo>")
            for nome, valor in termo_campos.items():
                if valor is not None:
                    parts.append(_campo(nome, valor))
            parts.append("</termo>")

        if has_pesquisa:
            parts.append("<pesquisa>")
            for nome, valor in pesquisa_campos.items():
                if valor is not None:
                    parts.append(_campo(nome, valor))
            parts.append("</pesquisa>")
        else:
            ids = [str(a).strip() for a in arquivos_ids if str(a).strip()]
            if not ids:
                raise ValueError("arquivos_ids não pode ser vazio")
            arqs = "".join(f'<arquivo id="{escape(i)}"/>' for i in ids)
            parts.append(f"<arquivos>{arqs}</arquivos>")

        parts.append("</pedido>")
        return "".join(parts)

    def pesquisar(
        self,
        sistema,
        inicio,
        fim,
        perfil="contr",
        nirepresentado=None,
        tiponirepresentado=None,
        tipoarquivo=None,
        tipopesquisa=None,
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
            tipoarquivo: Código do tipo (default: primeiro do sistema).
            tipopesquisa: Código da pesquisa (default: primeira do tipo).
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
            tipoarquivo=tipoarquivo,
            tipopesquisa=tipopesquisa,
            campos=campos or None,
        )
        return self._call("PesquisarArquivos", entrada)

    def solicitar(
        self,
        sistema,
        arquivos=None,
        perfil="contr",
        nirepresentado=None,
        tiponirepresentado=None,
        tipoarquivo=None,
        tipopesquisa=None,
        pesquisa_campos=None,
        termo_campos=None,
    ):
        """Chama SolicitarArquivos.

        Três modos (doc oficial):
            - ``arquivos``: lista de IDs (retorno de pesquisar).
            - ``pesquisa_campos``: critérios diretos (sem listar antes).
            - ``termo_campos``: campos do termo de requisição (opcional).

        ``arquivos`` e ``pesquisa_campos`` são mutuamente exclusivos.

        Args:
            sistema: ID do sistema RFB (mesmo da pesquisa).
            arquivos: Lista de IDs de arquivo (strings) vindos de pesquisar().
            perfil: "contr" (padrão) ou "proc".
            nirepresentado / tiponirepresentado: ver pesquisar().
            tipoarquivo / tipopesquisa: ver pesquisar().
            pesquisa_campos: dict nome->valor para ``<pesquisa><campo .../>``.
            termo_campos: dict nome->valor para ``<termo><campo .../>``.

        Returns:
            dict com retorno, saida, mensagem e pedido_id (quando sucesso).
        """
        entrada = self._build_entrada_pedido(
            sistema,
            arquivos_ids=arquivos,
            perfil=perfil,
            nirepresentado=nirepresentado,
            tiponirepresentado=tiponirepresentado,
            tipoarquivo=tipoarquivo,
            tipopesquisa=tipopesquisa,
            pesquisa_campos=pesquisa_campos,
            termo_campos=termo_campos,
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
            dict com retorno, saida, mensagem, pedidos (lista enriquecida), etc.
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

        Returns:
            dict com pedido_ids, ultima_pagina, mensagem, etc.
        """
        entrada = self._build_entrada_consultar(**criterios)
        return self._call("ConsultarPedidos", entrada)
