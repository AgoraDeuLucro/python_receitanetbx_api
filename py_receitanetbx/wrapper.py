"""
Wrapper não oficial do ReceitanetBX (Receita Federal).

Fluxo típico::

    from py_receitanetbx import arquivos, pedidos, SISTEMAS, campos_da_pesquisa

    arq = arquivos()  # http://localhost:2443/services/ReceitanetBX
    # arq = arquivos(debug=True)  # imprime request/response no terminal

    # Campos esperados de uma pesquisa (schema do Derby):
    campos_da_pesquisa(27, "1", "EVT_CAD_TRAB_PER_EMP_PERAPUR")
    # -> cpf, iniPer, fimPer

    # 1) Pesquisar — inicio/fim são mapeados aos nomes corretos (iniPer/fimPer, etc.)
    r = arq.pesquisar(
        sistema=27,
        tipopesquisa="EVT_CAD_TRAB_PER_EMP_PERAPUR",
        inicio="2025-07-01",
        fim="2026-06-30",
        cpf="00000000000",
    )

    # 2) Solicitar download com os IDs da pesquisa
    r = arq.solicitar(sistema=27, arquivos=r["arquivos"])

    # 3) Acompanhar pedidos
    ped = pedidos()
    ped.verificar_situacao(pedido_ids=["79242237"])
    ped.consultar(sistema="27", situacao="processando")
"""

from calendar import monthrange
from html import unescape
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

import requests


# Catálogo oficial (Derby ReceitanetBX) com campos por pesquisa:
# id_sistema -> {nome, tipos: {id_tipo -> {nome, pesquisas: {id_pesquisa -> {..., campos}}}}}
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
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data de início',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data de fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCNPJPeriodo': {
                        'nome': 'Por CNPJ e Período da Escrituração',
                        'papeis': ['fiscente', 'fiscrec', 'b2b'],
                        'finalidade': 'listagem',
                        'campos': {
                            'cnpj': {
                                'nome': 'CNPJ',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': '00000000000000',
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpjSucedida': {
                                'nome': 'CNPJ Empresa Sucedida',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data de início',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data de fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCNPJPeriodoRequisicaoJudicial': {
                        'nome': 'Requisição Judicial - Por CNPJ e Período da Escrituração',
                        'papeis': ['fiscrec'],
                        'finalidade': 'listagem',
                        'campos': {
                            'cnpj': {
                                'nome': 'CNPJ',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': '00000000000000',
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data de início',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data de fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'numeroEProcesso': {
                                'nome': 'Número do e-Processo',
                                'tipo': 'texto',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 30,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCNPJPeriodoEntrega': {
                        'nome': 'Por CNPJ e Período de Entrega',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'listagem',
                        'campos': {
                            'cnpj': {
                                'nome': 'CNPJ',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': '00000000000000',
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpjSucedida': {
                                'nome': 'CNPJ Empresa Sucedida',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data de início',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data de fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCNPJPeriodoB2B': {
                        'nome': 'Pedido Por CNPJ e Período da Escrituração B2B',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'cnpj': {
                                'nome': 'CNPJ',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': '00000000000000',
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpjSucedida': {
                                'nome': 'CNPJ Empresa Sucedida',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data de início',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data de fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCNPJPeriodoEntregaB2B': {
                        'nome': 'Pedido Por CNPJ e Período de Entrega B2B',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'cnpj': {
                                'nome': 'CNPJ',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': '00000000000000',
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpjSucedida': {
                                'nome': 'CNPJ Empresa Sucedida',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data de início',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data de fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
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
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data de início',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data de fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porArquivoPeriodoEntrega': {
                        'nome': 'Por Arquivo com CNPJs e Período de Entrega',
                        'papeis': ['fiscente', 'fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'arquivoCNPJs': {
                                'nome': 'Arquivo com lista de CNPJs (até 500)',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 100000,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data de início',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data de fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porListaCNPJsPeriodoEntrega': {
                        'nome': 'Por Lista de CNPJs e Período de Entrega',
                        'papeis': ['fiscente', 'fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'cnpj1': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpj2': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpj3': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpj4': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpj5': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpj6': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpj7': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpj8': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpj9': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpj10': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data de início',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data de fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porArquivoPeriodoEscrituracao': {
                        'nome': 'Por Arquivo com CNPJs e Período da Escrituração',
                        'papeis': ['fiscente', 'fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'arquivoCNPJs': {
                                'nome': 'Arquivo com lista de CNPJs (até 500)',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 100000,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data de início',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data de fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porListaCNPJsPeriodoEscrituracao': {
                        'nome': 'Por Lista de CNPJs e Período da Escrituração',
                        'papeis': ['fiscente', 'fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'cnpj1': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpj2': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpj3': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpj4': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpj5': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpj6': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpj7': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpj8': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpj9': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpj10': {
                                'nome': 'CNPJ 1 a CNPJ 10 (cnpj1 obrigatório, demais opcionais)',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data de início',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data de fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
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
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data de início',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data de fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
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
                        'campos': {
                            'cnpjEstabelecimento': {
                                'nome': 'CNPJ do Estabelecimento',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'opcaoTodosEstabelecimentos': {
                                'nome': 'Buscar Arquivos de Todos os Estabelecimentos',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'ie': {
                                'nome': 'Inscrição Estadual',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Inicio',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCNPJPeriodoTransmissao': {
                        'nome': 'Por CNPJ e Período de Transmissão/Recepção',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'listagem',
                        'campos': {
                            'cnpj': {
                                'nome': 'CNPJ',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'opcaoTodosEstabelecimentos': {
                                'nome': 'Buscar Arquivos de Todos os Estabelecimentos',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Inicio',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCPFPeriodoTransmissao': {
                        'nome': 'Por CPF (Produtor Rural) e Período de Transmissão/Recepção',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'listagem',
                        'campos': {
                            'cpf': {
                                'nome': 'CPF (Produtor Rural)',
                                'tipo': 'cpf',
                                'obrigatorio': True,
                                'default': '00000000000',
                                'tamanhomax': 11,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Inicio',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCNPJPeriodoEFD': {
                        'nome': 'Por CNPJ e Período da Escrituração',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'listagem',
                        'campos': {
                            'cnpj': {
                                'nome': 'CNPJ',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'opcaoTodosEstabelecimentos': {
                                'nome': 'Buscar Arquivos de Todos os Estabelecimentos',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Inicio',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCPFPeriodoEFD': {
                        'nome': 'Por CPF (Produtor Rural) e Período da Escrituração',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'listagem',
                        'campos': {
                            'cpf': {
                                'nome': 'CPF (Produtor Rural)',
                                'tipo': 'cpf',
                                'obrigatorio': True,
                                'default': '00000000000',
                                'tamanhomax': 11,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Inicio',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCNPJPeriodoTransmissaoB2B': {
                        'nome': 'Pedido Por CNPJ e Período de Transmissão B2B',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'cnpj': {
                                'nome': 'CNPJ',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'opcaoTodosEstabelecimentos': {
                                'nome': 'Buscar Arquivos de Todos os Estabelecimentos',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Início',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCPFPeriodoTransmissaoB2B': {
                        'nome': 'Pedido Por CPF (Produtor Rural) e Período de Transmissão/Recepção B2B',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'cpf': {
                                'nome': 'CPF (Produtor Rural)',
                                'tipo': 'cpf',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 11,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Início',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCNPJPeriodoEFDB2B': {
                        'nome': 'Pedido Por CNPJ e Período da Escrituração B2B',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'cnpj': {
                                'nome': 'CNPJ',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'opcaoTodosEstabelecimentos': {
                                'nome': 'Buscar Arquivos de Todos os Estabelecimentos',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Inicio',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCPFPeriodoEFDB2B': {
                        'nome': 'Pedido Por CPF (Produtor Rural) e Período da Escrituração B2B',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'cpf': {
                                'nome': 'CPF (Produtor Rural)',
                                'tipo': 'cpf',
                                'obrigatorio': True,
                                'default': '00000000000',
                                'tamanhomax': 11,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Inicio',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCNPJIEPeriodoTransmissao': {
                        'nome': 'Por CNPJ IE e Período de Transmissão/Recepção',
                        'papeis': ['fiscente'],
                        'finalidade': 'listagem',
                        'campos': {
                            'cnpj': {
                                'nome': 'CNPJ',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'ie': {
                                'nome': 'Inscrição Estadual',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Inicio',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCPFIEPeriodoTransmissao': {
                        'nome': 'Por CPF IE e Período de Transmissão/Recepção',
                        'papeis': ['fiscente'],
                        'finalidade': 'listagem',
                        'campos': {
                            'cpf': {
                                'nome': 'CPF (Produtor Rural)',
                                'tipo': 'cpf',
                                'obrigatorio': True,
                                'default': '00000000000',
                                'tamanhomax': 11,
                                'listas_validas': None,
                            },
                            'ie': {
                                'nome': 'Inscrição Estadual',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Inicio',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCNPJIEPeriodoEFD': {
                        'nome': 'Por CNPJ IE e Período da Escrituracao',
                        'papeis': ['fiscente'],
                        'finalidade': 'listagem',
                        'campos': {
                            'cnpj': {
                                'nome': 'CNPJ',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'ie': {
                                'nome': 'Inscrição Estadual',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Inicio',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCPFIEPeriodoEFD': {
                        'nome': 'Por CPF IE e Período da Escrituracao',
                        'papeis': ['fiscente'],
                        'finalidade': 'listagem',
                        'campos': {
                            'cpf': {
                                'nome': 'CPF (Produtor Rural)',
                                'tipo': 'cpf',
                                'obrigatorio': True,
                                'default': '00000000000',
                                'tamanhomax': 11,
                                'listas_validas': None,
                            },
                            'ie': {
                                'nome': 'Inscrição Estadual',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Inicio',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                },
            },
            '1602-OutUF': {
                'nome': 'Escrituração Fiscal Digital - Outra UF',
                'pesquisas': {
                    'porCNPJIEPeriodoEFD': {
                        'nome': 'Por CNPJ IE e Período da Escrituracao',
                        'papeis': ['fiscente'],
                        'finalidade': 'listagem',
                        'campos': {
                            'cnpj': {
                                'nome': 'CNPJ',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'ie': {
                                'nome': 'Inscrição Estadual',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Inicio',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCPFIEPeriodoEFD': {
                        'nome': 'Por CPF IE e Período da Escrituracao',
                        'papeis': ['fiscente'],
                        'finalidade': 'listagem',
                        'campos': {
                            'cpf': {
                                'nome': 'CPF (Produtor Rural)',
                                'tipo': 'cpf',
                                'obrigatorio': True,
                                'default': '00000000000',
                                'tamanhomax': 11,
                                'listas_validas': None,
                            },
                            'ie': {
                                'nome': 'Inscrição Estadual',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Inicio',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                },
            },
            '1602-OIE': {
                'nome': 'Operações Interestaduais de EFD',
                'pesquisas': {
                    'porCNPJIEPeriodoTransmissao': {
                        'nome': 'Por CNPJ IE e Período de Transmissão/Recepção',
                        'papeis': ['fiscente'],
                        'finalidade': 'listagem',
                        'campos': {
                            'cnpj': {
                                'nome': 'CNPJ',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'ie': {
                                'nome': 'Inscrição Estadual',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Inicio',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCPFIEPeriodoTransmissao': {
                        'nome': 'Por CPF IE e Período de Transmissão/Recepção',
                        'papeis': ['fiscente'],
                        'finalidade': 'listagem',
                        'campos': {
                            'cpf': {
                                'nome': 'CPF (Produtor Rural)',
                                'tipo': 'cpf',
                                'obrigatorio': True,
                                'default': '00000000000',
                                'tamanhomax': 11,
                                'listas_validas': None,
                            },
                            'ie': {
                                'nome': 'Inscrição Estadual',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Inicio',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCNPJIEPeriodoEFD': {
                        'nome': 'Por CNPJ IE e Período da Escrituracao',
                        'papeis': ['fiscente'],
                        'finalidade': 'listagem',
                        'campos': {
                            'cnpj': {
                                'nome': 'CNPJ',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'ie': {
                                'nome': 'Inscrição Estadual',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Inicio',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCPFIEPeriodoEFD': {
                        'nome': 'Por CPF IE e Período da Escrituracao',
                        'papeis': ['fiscente'],
                        'finalidade': 'listagem',
                        'campos': {
                            'cpf': {
                                'nome': 'CPF (Produtor Rural)',
                                'tipo': 'cpf',
                                'obrigatorio': True,
                                'default': '00000000000',
                                'tamanhomax': 11,
                                'listas_validas': None,
                            },
                            'ie': {
                                'nome': 'Inscrição Estadual',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'dataInicio': {
                                'nome': 'Data Inicio',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data Fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
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
                        'campos': {
                            'chaveAcesso': {
                                'nome': 'Chave de Acesso da NF-e',
                                'tipo': 'texto',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 44,
                                'listas_validas': None,
                            },
                            'retornarNFe': {
                                'nome': 'Flags booleanos de quais eventos/documentos retornar (ver defaults na doc)',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarCancelamento': {
                                'nome': 'Flags booleanos de quais eventos/documentos retornar (ver defaults na doc)',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarCartaDeCorrecao': {
                                'nome': 'Flags booleanos de quais eventos/documentos retornar (ver defaults na doc)',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarManifestacaoDestinatario': {
                                'nome': 'Flags booleanos de quais eventos/documentos retornar (ver defaults na doc)',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarRegistroPassagem': {
                                'nome': 'Flags booleanos de quais eventos/documentos retornar (ver defaults na doc)',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarCTeParaNFe': {
                                'nome': 'Flags booleanos de quais eventos/documentos retornar (ver defaults na doc)',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarSUFRAMA': {
                                'nome': 'Flags booleanos de quais eventos/documentos retornar (ver defaults na doc)',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarMDFE': {
                                'nome': 'Flags booleanos de quais eventos/documentos retornar (ver defaults na doc)',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarAverbacao': {
                                'nome': 'Flags booleanos de quais eventos/documentos retornar (ver defaults na doc)',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarIrregularidadeFiscal': {
                                'nome': 'Flags booleanos de quais eventos/documentos retornar (ver defaults na doc)',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarComprovanteEntrega': {
                                'nome': 'Flags booleanos de quais eventos/documentos retornar (ver defaults na doc)',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarEPEC': {
                                'nome': 'Flags booleanos de quais eventos/documentos retornar (ver defaults na doc)',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarEvProrrogacao': {
                                'nome': 'Flags booleanos de quais eventos/documentos retornar (ver defaults na doc)',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarNFeReferenciada': {
                                'nome': 'Flags booleanos de quais eventos/documentos retornar (ver defaults na doc)',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarAtorInteressado': {
                                'nome': 'Flags booleanos de quais eventos/documentos retornar (ver defaults na doc)',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarConciliacaoFinanceira': {
                                'nome': 'Flags booleanos de quais eventos/documentos retornar (ver defaults na doc)',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarIbsCbs': {
                                'nome': 'Flags booleanos de quais eventos/documentos retornar (ver defaults na doc)',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porArquivoChvAcesso': {
                        'nome': 'Por Arquivo com Chaves de Acesso',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'arquivoChvAcesso': {
                                'nome': 'Arquivo TXT com lista de Chaves de Acesso (máx 600.000; até 60Kb)',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porArquivoListaNFe': {
                        'nome': 'Por Arquivo com lista UF/CNPJ/Série/Número',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'arquivoListaNFe': {
                                'nome': 'Arquivo com lista de UF/CNPJ/Série/Número da NFe',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCNPJPeriodo': {
                        'nome': 'Por CNPJ e Periodo',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'cnpjEmitente': {
                                'nome': 'CNPJ do Emitente / Destinatário',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpjDestinatario': {
                                'nome': 'CNPJ do Emitente / Destinatário',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'cnpjBaseEmitente': {
                                'nome': 'CNPJ Base do Emitente / Destinatário',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 8,
                                'listas_validas': None,
                            },
                            'cnpjBaseDestinatario': {
                                'nome': 'CNPJ Base do Emitente / Destinatário',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 8,
                                'listas_validas': None,
                            },
                            'cpfEmitente': {
                                'nome': 'CPF do Emitente / Destinatário',
                                'tipo': 'cpf',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 11,
                                'listas_validas': None,
                            },
                            'cpfDestinatario': {
                                'nome': 'CPF do Emitente / Destinatário',
                                'tipo': 'cpf',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 11,
                                'listas_validas': None,
                            },
                            'dataInicioAutorizacao': {
                                'nome': 'Datas de Autorização e de Emissão',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFimAutorizacao': {
                                'nome': 'Datas de Autorização e de Emissão',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataInicioEmissao': {
                                'nome': 'Datas de Autorização e de Emissão',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFimEmissao': {
                                'nome': 'Datas de Autorização e de Emissão',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCNPJPeriodoRetornandoLista': {
                        'nome': 'Por CNPJ e Periodo retornando lista de Chaves',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'cnpjEmitente': {
                                'nome': 'Mesmos campos de identificação/período de porCNPJPeriodo (sem flags de retorno)',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpjBaseEmitente': {
                                'nome': 'Mesmos campos de identificação/período de porCNPJPeriodo (sem flags de retorno)',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cpfEmitente': {
                                'nome': 'Mesmos campos de identificação/período de porCNPJPeriodo (sem flags de retorno)',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpjDestinatario': {
                                'nome': 'Mesmos campos de identificação/período de porCNPJPeriodo (sem flags de retorno)',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpjBaseDestinatario': {
                                'nome': 'Mesmos campos de identificação/período de porCNPJPeriodo (sem flags de retorno)',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cpfDestinatario': {
                                'nome': 'Mesmos campos de identificação/período de porCNPJPeriodo (sem flags de retorno)',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataInicioAutorizacao': {
                                'nome': 'Mesmos campos de identificação/período de porCNPJPeriodo (sem flags de retorno)',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFimAutorizacao': {
                                'nome': 'Mesmos campos de identificação/período de porCNPJPeriodo (sem flags de retorno)',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataInicioEmissao': {
                                'nome': 'Mesmos campos de identificação/período de porCNPJPeriodo (sem flags de retorno)',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFimEmissao': {
                                'nome': 'Mesmos campos de identificação/período de porCNPJPeriodo (sem flags de retorno)',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porCNPJDiaCorrente': {
                        'nome': 'Por CNPJ retornando DF-e do dia corrente',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'cnpjEmitente': {
                                'nome': 'Identificação emitente/destinatário',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpjBaseEmitente': {
                                'nome': 'Identificação emitente/destinatário',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cpfEmitente': {
                                'nome': 'Identificação emitente/destinatário',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpjDestinatario': {
                                'nome': 'Identificação emitente/destinatário',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpjBaseDestinatario': {
                                'nome': 'Identificação emitente/destinatário',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cpfDestinatario': {
                                'nome': 'Identificação emitente/destinatário',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'utilizarDataEmissao': {
                                'nome': 'Indica se usa data de emissão/autorização',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'utilizarDataAutorizacao': {
                                'nome': 'Indica se usa data de emissão/autorização',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
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
                        'campos': {
                            'cnpj': {
                                'nome': 'CNPJ',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': '00000000000000',
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'buscarTodosEstabelecimentos': {
                                'nome': 'Arquivos de Todos os Estabelecimentos',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'buscarUltimoArquivoTransPeriodo': {
                                'nome': 'Apenas Últimos Arquivos Transmitidos',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataInicioPeriodo': {
                                'nome': 'Data de Início',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFimPeriodo': {
                                'nome': 'Data de Fim',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
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
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data de início',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data de fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
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
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data de início',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data de fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'periodoEntregaIncorporada': {
                        'nome': 'Período de Entrega da Incorporada',
                        'papeis': ['contr', 'proc', 'repr'],
                        'finalidade': 'listagem_e_pedido',
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data início/fim',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data início/fim',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj': {
                                'nome': 'CNPJ Incorporada',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'exercicio': {
                        'nome': 'Período da Escrituração',
                        'papeis': ['contr', 'proc', 'repr'],
                        'finalidade': 'listagem_e_pedido',
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data de início',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data de fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'exercicioIncorporada': {
                        'nome': 'Período de Escrituração da Incorporada',
                        'papeis': ['contr', 'proc', 'repr'],
                        'finalidade': 'listagem_e_pedido',
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data início/fim',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data início/fim',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj': {
                                'nome': 'CNPJ Incorporada',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'cnpjPeriodoEntrega': {
                        'nome': 'CNPJ e Período de Entrega',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'listagem_e_pedido',
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data início/fim de entrega',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data início/fim de entrega',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj': {
                                'nome': 'CNPJ do contribuinte',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'scp': {
                                'nome': 'Código SCP',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'cnpjExercicio': {
                        'nome': 'CNPJ e Período da Escrituração',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'listagem_e_pedido',
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data início/fim da escrituração',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data início/fim da escrituração',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj': {
                                'nome': 'CNPJ do contribuinte',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'scp': {
                                'nome': 'Código SCP',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'listaCNPJPeriodoEntrega': {
                        'nome': 'Lista de CNPJ e Período de Entrega',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'pedido',
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data início/fim de entrega',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data início/fim de entrega',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'arquivoCNPJs': {
                                'nome': 'Arquivo com lista de CNPJs (até 30)',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 100000,
                                'listas_validas': None,
                            },
                        },
                    },
                    'listaCNPJExercicio': {
                        'nome': 'Lista de CNPJ e Período da Escrituração',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'pedido',
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data início/fim',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data início/fim',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'arquivoCNPJs': {
                                'nome': 'Arquivo com lista de CNPJs (até 30)',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 100000,
                                'listas_validas': None,
                            },
                        },
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
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data início/fim de entrega',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data início/fim de entrega',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'arquivoCNPJs': {
                                'nome': 'Arquivo com lista de CNPJs (até 500 b2b/30 fiscal)',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 100000,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'CNPJ10PeriodoEntrega': {
                        'nome': 'CNPJ e Período de Entrega',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'pedido',
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data início/fim de entrega',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data início/fim de entrega',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj1': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj2': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj3': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj4': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj5': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj6': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj7': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj8': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj9': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj10': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'listaCNPJExercicio': {
                        'nome': 'Lista de CNPJ e Período da Escrituração',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'pedido',
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data início/fim da escrituração',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data início/fim da escrituração',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'arquivoCNPJs': {
                                'nome': 'Arquivo com lista de CNPJs (até 500 b2b/30 fiscal)',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 100000,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'CNPJ10Exercicio': {
                        'nome': 'CNPJ e Período da Escrituração',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'pedido',
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data início/fim',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data início/fim',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj1': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj2': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj3': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj4': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj5': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj6': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj7': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj8': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj9': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj10': {
                                'nome': 'CNPJ 1 (obrigatório) a CNPJ 10',
                                'tipo': 'cnpj',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'Completa': {
                        'nome': 'Completa',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'pedido',
                        'campos': {
                            'cnpj': {
                                'nome': 'CNPJ do contribuinte',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataInicioEntrega': {
                                'nome': 'Datas opcionais de entrega/escrituração',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFimEntrega': {
                                'nome': 'Datas opcionais de entrega/escrituração',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataInicioEscrituracao': {
                                'nome': 'Datas opcionais de entrega/escrituração',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFimEscrituracao': {
                                'nome': 'Datas opcionais de entrega/escrituração',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'tipoEscrituracao': {
                                'nome': 'Tipo de Escrituração',
                                'tipo': 'lista',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': 'T=Todas|O=Original|R=Retificadora',
                            },
                            'regimeTributacao': {
                                'nome': 'Regime de Tributação',
                                'tipo': 'lista',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': 'T=Todos|C=Cumulativo|NC=Não cumulativo|M=Misto',
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'DataLucroReal': {
                        'nome': 'Lucro Real/Dia de Entrega',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data da entrega',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'DataRegimeTributario': {
                        'nome': 'Regime Tributário/Dia de Entrega',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data da entrega',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'regimeTributacao': {
                                'nome': 'Regime de Tributação',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': 'C=Cumulativo|NC=Não cumulativo|M=Misto',
                            },
                        },
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
                        'campos': {
                            'arq': {
                                'nome': 'AC e TpNI e NI (CPF ou CNPJ)',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'pesqunit': {
                        'nome': 'Ano-Calendario e Tipo NI e NI',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'ac': {
                                'nome': 'Ano-Calendario',
                                'tipo': 'numero',
                                'obrigatorio': True,
                                'default': '0000',
                                'tamanhomax': 4,
                                'listas_validas': None,
                            },
                            'ni': {
                                'nome': 'Numero de identificacao (CPF ou CNPJ)',
                                'tipo': 'numero',
                                'obrigatorio': True,
                                'default': '00000000000000',
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'tp-ni': {
                                'nome': 'Tipo do NI',
                                'tipo': 'numero',
                                'obrigatorio': True,
                                'default': '0',
                                'tamanhomax': 1,
                                'listas_validas': '1=CPF|2=CNPJ',
                            },
                        },
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
                        'campos': {
                            'listaNIANOARRECADACAO': {
                                'nome': 'listaNIANOARRECADACAO',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
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
                        'campos': {
                            'cnpj': {
                                'nome': 'CNPJ',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': '00000000000000',
                                'tamanhomax': 14,
                                'listas_validas': 'máscara ##.###.###/####-##U',
                            },
                            'anocalendario': {
                                'nome': 'Ano Calendário',
                                'tipo': 'numero',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 4,
                                'listas_validas': None,
                            },
                        },
                    },
                    'arquivocnpjanocalendario': {
                        'nome': 'Arquivo com CNPJ e Ano Calendário',
                        'papeis': ['B2B'],
                        'finalidade': 'pedido',
                        'campos': {
                            'arquivo': {
                                'nome': 'Arquivo CNPJ/AC',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
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
                        'campos': {
                            'ano': {
                                'nome': 'Ano Calendário',
                                'tipo': 'numero',
                                'obrigatorio': True,
                                'default': '2008',
                                'tamanhomax': 4,
                                'listas_validas': None,
                            },
                            'ni': {
                                'nome': 'Número de identificação',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': '00000000000000',
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                        },
                    },
                    'P2': {
                        'nome': 'Arquivo com Ano Calendário e NI',
                        'papeis': ['B2B'],
                        'finalidade': 'pedido',
                        'campos': {
                            'anoni': {
                                'nome': 'Arquivo Ano Calendário e NI',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                },
            },
        },
    },
    16: {
        'nome': 'Simples Nacional',
        'tipos': {
            '1': {
                'nome': 'PGDAS_D|PGDAS|PGMEI|DASNSIMEI|PGDASD_DAS|DEFIS|DAS_COBRANCA|DASN_2008..2012|PGDASD2018|PGDASDDAS2018|DASCOBRANCA2018|PGDASD2018MALHA',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'Data do arquivo',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': "campo id numérico '1', não 'data'",
                            },
                        },
                    },
                },
            },
            '2': {
                'nome': 'PGDAS_D|PGDAS|PGMEI|DASNSIMEI|PGDASD_DAS|DEFIS|DAS_COBRANCA|DASN_2008..2012|PGDASD2018|PGDASDDAS2018|DASCOBRANCA2018|PGDASD2018MALHA',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'Data do arquivo',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': "campo id numérico '1', não 'data'",
                            },
                        },
                    },
                },
            },
            '3': {
                'nome': 'PGDAS_D|PGDAS|PGMEI|DASNSIMEI|PGDASD_DAS|DEFIS|DAS_COBRANCA|DASN_2008..2012|PGDASD2018|PGDASDDAS2018|DASCOBRANCA2018|PGDASD2018MALHA',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'Data do arquivo',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': "campo id numérico '1', não 'data'",
                            },
                        },
                    },
                },
            },
            '4': {
                'nome': 'PGDAS_D|PGDAS|PGMEI|DASNSIMEI|PGDASD_DAS|DEFIS|DAS_COBRANCA|DASN_2008..2012|PGDASD2018|PGDASDDAS2018|DASCOBRANCA2018|PGDASD2018MALHA',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'Data do arquivo',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': "campo id numérico '1', não 'data'",
                            },
                        },
                    },
                },
            },
            '5': {
                'nome': 'PGDAS_D|PGDAS|PGMEI|DASNSIMEI|PGDASD_DAS|DEFIS|DAS_COBRANCA|DASN_2008..2012|PGDASD2018|PGDASDDAS2018|DASCOBRANCA2018|PGDASD2018MALHA',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'Data do arquivo',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': "campo id numérico '1', não 'data'",
                            },
                        },
                    },
                },
            },
            '6': {
                'nome': 'PGDAS_D|PGDAS|PGMEI|DASNSIMEI|PGDASD_DAS|DEFIS|DAS_COBRANCA|DASN_2008..2012|PGDASD2018|PGDASDDAS2018|DASCOBRANCA2018|PGDASD2018MALHA',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'Data do arquivo',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': "campo id numérico '1', não 'data'",
                            },
                        },
                    },
                },
            },
            '7': {
                'nome': 'PGDAS_D|PGDAS|PGMEI|DASNSIMEI|PGDASD_DAS|DEFIS|DAS_COBRANCA|DASN_2008..2012|PGDASD2018|PGDASDDAS2018|DASCOBRANCA2018|PGDASD2018MALHA',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'Data do arquivo',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': "campo id numérico '1', não 'data'",
                            },
                        },
                    },
                },
            },
            '8': {
                'nome': 'PGDAS_D|PGDAS|PGMEI|DASNSIMEI|PGDASD_DAS|DEFIS|DAS_COBRANCA|DASN_2008..2012|PGDASD2018|PGDASDDAS2018|DASCOBRANCA2018|PGDASD2018MALHA',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'Data do arquivo',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': "campo id numérico '1', não 'data'",
                            },
                        },
                    },
                },
            },
            '9': {
                'nome': 'PGDAS_D|PGDAS|PGMEI|DASNSIMEI|PGDASD_DAS|DEFIS|DAS_COBRANCA|DASN_2008..2012|PGDASD2018|PGDASDDAS2018|DASCOBRANCA2018|PGDASD2018MALHA',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'Data do arquivo',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': "campo id numérico '1', não 'data'",
                            },
                        },
                    },
                },
            },
            '10': {
                'nome': 'PGDAS_D|PGDAS|PGMEI|DASNSIMEI|PGDASD_DAS|DEFIS|DAS_COBRANCA|DASN_2008..2012|PGDASD2018|PGDASDDAS2018|DASCOBRANCA2018|PGDASD2018MALHA',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'Data do arquivo',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': "campo id numérico '1', não 'data'",
                            },
                        },
                    },
                },
            },
            '11': {
                'nome': 'PGDAS_D|PGDAS|PGMEI|DASNSIMEI|PGDASD_DAS|DEFIS|DAS_COBRANCA|DASN_2008..2012|PGDASD2018|PGDASDDAS2018|DASCOBRANCA2018|PGDASD2018MALHA',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'Data do arquivo',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': "campo id numérico '1', não 'data'",
                            },
                        },
                    },
                },
            },
            '12': {
                'nome': 'PGDAS_D|PGDAS|PGMEI|DASNSIMEI|PGDASD_DAS|DEFIS|DAS_COBRANCA|DASN_2008..2012|PGDASD2018|PGDASDDAS2018|DASCOBRANCA2018|PGDASD2018MALHA',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'Data do arquivo',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': "campo id numérico '1', não 'data'",
                            },
                        },
                    },
                },
            },
            '18': {
                'nome': 'PGDAS_D|PGDAS|PGMEI|DASNSIMEI|PGDASD_DAS|DEFIS|DAS_COBRANCA|DASN_2008..2012|PGDASD2018|PGDASDDAS2018|DASCOBRANCA2018|PGDASD2018MALHA',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'Data do arquivo',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': "campo id numérico '1', não 'data'",
                            },
                        },
                    },
                },
            },
            '19': {
                'nome': 'PGDAS_D|PGDAS|PGMEI|DASNSIMEI|PGDASD_DAS|DEFIS|DAS_COBRANCA|DASN_2008..2012|PGDASD2018|PGDASDDAS2018|DASCOBRANCA2018|PGDASD2018MALHA',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'Data do arquivo',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': "campo id numérico '1', não 'data'",
                            },
                        },
                    },
                },
            },
            '20': {
                'nome': 'PGDAS_D|PGDAS|PGMEI|DASNSIMEI|PGDASD_DAS|DEFIS|DAS_COBRANCA|DASN_2008..2012|PGDASD2018|PGDASDDAS2018|DASCOBRANCA2018|PGDASD2018MALHA',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'Data do arquivo',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': "campo id numérico '1', não 'data'",
                            },
                        },
                    },
                },
            },
            '21': {
                'nome': 'PGDAS_D|PGDAS|PGMEI|DASNSIMEI|PGDASD_DAS|DEFIS|DAS_COBRANCA|DASN_2008..2012|PGDASD2018|PGDASDDAS2018|DASCOBRANCA2018|PGDASD2018MALHA',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Data',
                        'papeis': ['fiscente', 'fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'Data do arquivo',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': "campo id numérico '1', não 'data'",
                            },
                        },
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
                        'campos': {
                            '4': {
                                'nome': 'Data Inicial',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '5': {
                                'nome': 'Data Final',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                },
            },
            '14': {
                'nome': 'PARCSN',
                'pesquisas': {
                    '3': {
                        'nome': 'Por Período',
                        'papeis': ['(vazio)'],
                        'finalidade': 'pedido',
                        'campos': {
                            '4': {
                                'nome': 'Data Inicial',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '5': {
                                'nome': 'Data Final',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                },
            },
            '15': {
                'nome': 'CONTAGIL',
                'pesquisas': {
                    '4': {
                        'nome': 'Lista Cnpj e Ano',
                        'papeis': ['(vazio)'],
                        'finalidade': 'pedido',
                        'campos': {
                            '6..105': {
                                'nome': 'CnpjAno001 a CnpjAno100 (campo 6=obrigatório; 7-105=opcionais)',
                                'tipo': 'texto',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 19,
                                'listas_validas': 'máscara ##############|####  (14 dig CNPJ + 4 dig ano)',
                            },
                        },
                    },
                },
            },
            '16': {
                'nome': 'PARCSNESP',
                'pesquisas': {
                    '3': {
                        'nome': 'Por Período',
                        'papeis': ['(vazio)'],
                        'finalidade': 'pedido',
                        'campos': {
                            '4': {
                                'nome': 'Data Inicial',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '5': {
                                'nome': 'Data Final',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
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
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data de início',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data de fim',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
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
                        'campos': {
                            'chaveAcesso': {
                                'nome': 'Chave de Acesso do CT-e',
                                'tipo': 'texto',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 44,
                                'listas_validas': None,
                            },
                            'retornarCTe': {
                                'nome': 'Flags booleanos de retorno',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarCancelamento': {
                                'nome': 'Flags booleanos de retorno',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarCartaDeCorrecao': {
                                'nome': 'Flags booleanos de retorno',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarEPEC': {
                                'nome': 'Flags booleanos de retorno',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarRegistroMultiModal': {
                                'nome': 'Flags booleanos de retorno',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarCTeSubstituido': {
                                'nome': 'Flags booleanos de retorno',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarCTeAnulado': {
                                'nome': 'Flags booleanos de retorno',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarRegistroDePassagem': {
                                'nome': 'Flags booleanos de retorno',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarMDFE': {
                                'nome': 'Flags booleanos de retorno',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarRedespacho': {
                                'nome': 'Flags booleanos de retorno',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarGtv': {
                                'nome': 'Flags booleanos de retorno',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarDesacordo': {
                                'nome': 'Flags booleanos de retorno',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarMarcacaoCTeOS': {
                                'nome': 'Flags booleanos de retorno',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarComprovanteEntrega': {
                                'nome': 'Flags booleanos de retorno',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarInsucessoEntrega': {
                                'nome': 'Flags booleanos de retorno',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarVinculacaoPagamento': {
                                'nome': 'Flags booleanos de retorno',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'retornarNFe': {
                                'nome': 'Flags booleanos de retorno',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'varia',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porArquivoChvAcesso': {
                        'nome': 'Por Arquivo com Chaves de Acesso',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'arquivoChvAcesso': {
                                'nome': 'Arquivo TXT com Chaves de Acesso (máx 600.000; até 60Kb)',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porInscricaoEmitenteEPeriodo': {
                        'nome': 'Por CNPJ/CPF Emitente e Período',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'cnpjEmitente': {
                                'nome': 'CNPJ/CNPJ base/CPF do Emitente',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpjBaseEmitente': {
                                'nome': 'CNPJ/CNPJ base/CPF do Emitente',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cpfEmitente': {
                                'nome': 'CNPJ/CNPJ base/CPF do Emitente',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataInicioAutorizacao': {
                                'nome': 'Datas de Autorização/Emissão',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFimAutorizacao': {
                                'nome': 'Datas de Autorização/Emissão',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataInicioEmissao': {
                                'nome': 'Datas de Autorização/Emissão',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFimEmissao': {
                                'nome': 'Datas de Autorização/Emissão',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porInscricaoRemetenteDestinatarioEPeriodo': {
                        'nome': 'Por CNPJ/CPF Remetente/Destinatário e Período',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'cnpjRemetente': {
                                'nome': 'Identificação remetente/destinatário',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpjBaseRemetente': {
                                'nome': 'Identificação remetente/destinatário',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cpfRemetente': {
                                'nome': 'Identificação remetente/destinatário',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpjDestinatario': {
                                'nome': 'Identificação remetente/destinatário',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpjBaseDestinatario': {
                                'nome': 'Identificação remetente/destinatário',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cpfDestinatario': {
                                'nome': 'Identificação remetente/destinatário',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porInscricaoEmitenteDiaCorrente': {
                        'nome': 'Por CNPJ/CPF Emitente DF-e dia corrente',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'cnpjEmitente': {
                                'nome': 'Identificação emitente',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpjBaseEmitente': {
                                'nome': 'Identificação emitente',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cpfEmitente': {
                                'nome': 'Identificação emitente',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'utilizarDataAutorizacao': {
                                'nome': 'Indica se usa data de autorização/emissão',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'utilizarDataEmissao': {
                                'nome': 'Indica se usa data de autorização/emissão',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'porInscricaoRemetenteDestinatarioDiaCorrente': {
                        'nome': 'Por CNPJ/CPF Remetente/Destinatário DF-e dia corrente',
                        'papeis': ['fiscrec', 'b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'cnpjRemetente': {
                                'nome': 'Identificação remetente/destinatário',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpjBaseRemetente': {
                                'nome': 'Identificação remetente/destinatário',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cpfRemetente': {
                                'nome': 'Identificação remetente/destinatário',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpjDestinatario': {
                                'nome': 'Identificação remetente/destinatário',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpjBaseDestinatario': {
                                'nome': 'Identificação remetente/destinatário',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cpfDestinatario': {
                                'nome': 'Identificação remetente/destinatário',
                                'tipo': 'vários',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
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
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data início/fim de entrega',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data início/fim de entrega',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'exercicio': {
                        'nome': 'Período da Escrituração',
                        'papeis': ['contr', 'proc', 'repr'],
                        'finalidade': 'listagem_e_pedido',
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data início/fim',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data início/fim',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'cnpjPeriodoEntrega': {
                        'nome': 'CNPJ e Período de Entrega',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'listagem_e_pedido',
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data início/fim de entrega',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data início/fim de entrega',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj': {
                                'nome': 'CNPJ do contribuinte',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'scp': {
                                'nome': 'Código SCP',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'cnpjExercicio': {
                        'nome': 'CNPJ e Período da Escrituração',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'listagem_e_pedido',
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data início/fim',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data início/fim',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'cnpj': {
                                'nome': 'CNPJ do contribuinte',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'scp': {
                                'nome': 'Código SCP',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'listaCNPJPeriodoEntrega': {
                        'nome': 'Lista de CNPJ e Período de Entrega',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'pedido',
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data início/fim de entrega',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data início/fim de entrega',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'arquivoCNPJs': {
                                'nome': 'Arquivo com lista de CNPJs (até 30)',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 100000,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'listaCNPJExercicio': {
                        'nome': 'Lista de CNPJ e Período da Escrituração',
                        'papeis': ['fiscrec', 'b2b', 'fiscente'],
                        'finalidade': 'pedido',
                        'campos': {
                            'dataInicio': {
                                'nome': 'Data início/fim',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'dataFim': {
                                'nome': 'Data início/fim',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'arquivoCNPJs': {
                                'nome': 'Arquivo com lista de CNPJs (até 30)',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 100000,
                                'listas_validas': None,
                            },
                            'somenteAtivas': {
                                'nome': 'Último arquivo transmitido',
                                'tipo': 'booleano',
                                'obrigatorio': True,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
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
                        'campos': {
                            'ac': {
                                'nome': 'Ano-Calendário',
                                'tipo': 'numero',
                                'obrigatorio': True,
                                'default': '0000',
                                'tamanhomax': 4,
                                'listas_validas': None,
                            },
                            'ni': {
                                'nome': 'Número de identificação (CNPJ)',
                                'tipo': 'numero',
                                'obrigatorio': True,
                                'default': '00000000000000',
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                        },
                    },
                    'pesqlista': {
                        'nome': 'Arquivo com Ano-Calendário e NI',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'arq': {
                                'nome': 'AC e NI(CNPJ)',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
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
                        'campos': {
                            'ac': {
                                'nome': 'Ano-Calendário',
                                'tipo': 'numero',
                                'obrigatorio': True,
                                'default': '0000',
                                'tamanhomax': 4,
                                'listas_validas': None,
                            },
                            'ni': {
                                'nome': 'Número de identificação (CNPJ)',
                                'tipo': 'numero',
                                'obrigatorio': True,
                                'default': '00000000000000',
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                        },
                    },
                    'pesqlista': {
                        'nome': 'Arquivo com Ano-Calendário e NI',
                        'papeis': ['b2b'],
                        'finalidade': 'pedido',
                        'campos': {
                            'arq': {
                                'nome': 'AC e NI(CNPJ)',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
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
                        'campos': {
                            '2': {
                                'nome': 'Número de Recibo',
                                'tipo': 'texto',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 51,
                                'listas_validas': None,
                            },
                            '13': {
                                'nome': 'Baixar arquivo com Assinatura Digital',
                                'tipo': 'booleano',
                                'obrigatorio': False,
                                'default': 'F',
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                },
            },
            '1': {
                'nome': 'Evento de Abertura|Cadastro Empresa Declarante|Cadastro Intermediário|Cadastro Patrocinado|Exclusao|Exclusão e-Financeira|Fechamento',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Número de Recibo',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '2': {
                                'nome': 'Número de Recibo',
                                'tipo': 'texto',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 51,
                                'listas_validas': None,
                            },
                        },
                    },
                    '3': {
                        'nome': 'Por CNPJ Declarante e Identificador do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'CNPJ do Declarante',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '14': {
                                'nome': 'ID EVENTO e-Financeira',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 20,
                                'listas_validas': None,
                            },
                            '10': {
                                'nome': 'Situacao dos Arquivos',
                                'tipo': 'lista',
                                'obrigatorio': False,
                                'default': '1',
                                'tamanhomax': None,
                                'listas_validas': '0=Todas|1=Ativo|2=Retificado|3=Excluído',
                            },
                        },
                    },
                    '8': {
                        'nome': 'Por CNPJ Declarante e Tipo do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'CNPJ do Declarante',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '18': {
                                'nome': 'Data de Início/Fim do Período',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 9,
                                'listas_validas': 'máscara ##/####',
                            },
                            '19': {
                                'nome': 'Data de Início/Fim do Período',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 9,
                                'listas_validas': 'máscara ##/####',
                            },
                            '8': {
                                'nome': 'Data de Início/Fim de Entrega do Evento',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '9': {
                                'nome': 'Data de Início/Fim de Entrega do Evento',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                },
            },
            '2': {
                'nome': 'Evento de Abertura|Cadastro Empresa Declarante|Cadastro Intermediário|Cadastro Patrocinado|Exclusao|Exclusão e-Financeira|Fechamento',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Número de Recibo',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '2': {
                                'nome': 'Número de Recibo',
                                'tipo': 'texto',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 51,
                                'listas_validas': None,
                            },
                        },
                    },
                    '3': {
                        'nome': 'Por CNPJ Declarante e Identificador do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'CNPJ do Declarante',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '14': {
                                'nome': 'ID EVENTO e-Financeira',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 20,
                                'listas_validas': None,
                            },
                            '10': {
                                'nome': 'Situacao dos Arquivos',
                                'tipo': 'lista',
                                'obrigatorio': False,
                                'default': '1',
                                'tamanhomax': None,
                                'listas_validas': '0=Todas|1=Ativo|2=Retificado|3=Excluído',
                            },
                        },
                    },
                    '8': {
                        'nome': 'Por CNPJ Declarante e Tipo do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'CNPJ do Declarante',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '18': {
                                'nome': 'Data de Início/Fim do Período',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 9,
                                'listas_validas': 'máscara ##/####',
                            },
                            '19': {
                                'nome': 'Data de Início/Fim do Período',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 9,
                                'listas_validas': 'máscara ##/####',
                            },
                            '8': {
                                'nome': 'Data de Início/Fim de Entrega do Evento',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '9': {
                                'nome': 'Data de Início/Fim de Entrega do Evento',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                },
            },
            '3': {
                'nome': 'Evento de Abertura|Cadastro Empresa Declarante|Cadastro Intermediário|Cadastro Patrocinado|Exclusao|Exclusão e-Financeira|Fechamento',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Número de Recibo',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '2': {
                                'nome': 'Número de Recibo',
                                'tipo': 'texto',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 51,
                                'listas_validas': None,
                            },
                        },
                    },
                    '3': {
                        'nome': 'Por CNPJ Declarante e Identificador do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'CNPJ do Declarante',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '14': {
                                'nome': 'ID EVENTO e-Financeira',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 20,
                                'listas_validas': None,
                            },
                            '10': {
                                'nome': 'Situacao dos Arquivos',
                                'tipo': 'lista',
                                'obrigatorio': False,
                                'default': '1',
                                'tamanhomax': None,
                                'listas_validas': '0=Todas|1=Ativo|2=Retificado|3=Excluído',
                            },
                        },
                    },
                },
            },
            '4': {
                'nome': 'Evento de Abertura|Cadastro Empresa Declarante|Cadastro Intermediário|Cadastro Patrocinado|Exclusao|Exclusão e-Financeira|Fechamento',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Número de Recibo',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '2': {
                                'nome': 'Número de Recibo',
                                'tipo': 'texto',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 51,
                                'listas_validas': None,
                            },
                        },
                    },
                    '3': {
                        'nome': 'Por CNPJ Declarante e Identificador do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'CNPJ do Declarante',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '14': {
                                'nome': 'ID EVENTO e-Financeira',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 20,
                                'listas_validas': None,
                            },
                            '10': {
                                'nome': 'Situacao dos Arquivos',
                                'tipo': 'lista',
                                'obrigatorio': False,
                                'default': '1',
                                'tamanhomax': None,
                                'listas_validas': '0=Todas|1=Ativo|2=Retificado|3=Excluído',
                            },
                        },
                    },
                },
            },
            '5': {
                'nome': 'Evento de Abertura|Cadastro Empresa Declarante|Cadastro Intermediário|Cadastro Patrocinado|Exclusao|Exclusão e-Financeira|Fechamento',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Número de Recibo',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '2': {
                                'nome': 'Número de Recibo',
                                'tipo': 'texto',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 51,
                                'listas_validas': None,
                            },
                        },
                    },
                    '3': {
                        'nome': 'Por CNPJ Declarante e Identificador do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'CNPJ do Declarante',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '14': {
                                'nome': 'ID EVENTO e-Financeira',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 20,
                                'listas_validas': None,
                            },
                            '10': {
                                'nome': 'Situacao dos Arquivos',
                                'tipo': 'lista',
                                'obrigatorio': False,
                                'default': '1',
                                'tamanhomax': None,
                                'listas_validas': '0=Todas|1=Ativo|2=Retificado|3=Excluído',
                            },
                        },
                    },
                },
            },
            '6': {
                'nome': 'Evento de Abertura|Cadastro Empresa Declarante|Cadastro Intermediário|Cadastro Patrocinado|Exclusao|Exclusão e-Financeira|Fechamento',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Número de Recibo',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '2': {
                                'nome': 'Número de Recibo',
                                'tipo': 'texto',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 51,
                                'listas_validas': None,
                            },
                        },
                    },
                    '3': {
                        'nome': 'Por CNPJ Declarante e Identificador do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'CNPJ do Declarante',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '14': {
                                'nome': 'ID EVENTO e-Financeira',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 20,
                                'listas_validas': None,
                            },
                            '10': {
                                'nome': 'Situacao dos Arquivos',
                                'tipo': 'lista',
                                'obrigatorio': False,
                                'default': '1',
                                'tamanhomax': None,
                                'listas_validas': '0=Todas|1=Ativo|2=Retificado|3=Excluído',
                            },
                        },
                    },
                },
            },
            '7': {
                'nome': 'Evento de Abertura|Cadastro Empresa Declarante|Cadastro Intermediário|Cadastro Patrocinado|Exclusao|Exclusão e-Financeira|Fechamento',
                'pesquisas': {
                    '1': {
                        'nome': 'Por Número de Recibo',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '2': {
                                'nome': 'Número de Recibo',
                                'tipo': 'texto',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 51,
                                'listas_validas': None,
                            },
                        },
                    },
                    '3': {
                        'nome': 'Por CNPJ Declarante e Identificador do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'CNPJ do Declarante',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '14': {
                                'nome': 'ID EVENTO e-Financeira',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 20,
                                'listas_validas': None,
                            },
                            '10': {
                                'nome': 'Situacao dos Arquivos',
                                'tipo': 'lista',
                                'obrigatorio': False,
                                'default': '1',
                                'tamanhomax': None,
                                'listas_validas': '0=Todas|1=Ativo|2=Retificado|3=Excluído',
                            },
                        },
                    },
                    '8': {
                        'nome': 'Por CNPJ Declarante e Tipo do Evento',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'CNPJ do Declarante',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '18': {
                                'nome': 'Data de Início/Fim do Período',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 9,
                                'listas_validas': 'máscara ##/####',
                            },
                            '19': {
                                'nome': 'Data de Início/Fim do Período',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 9,
                                'listas_validas': 'máscara ##/####',
                            },
                            '8': {
                                'nome': 'Data de Início/Fim de Entrega do Evento',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '9': {
                                'nome': 'Data de Início/Fim de Entrega do Evento',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                },
            },
            '8': {
                'nome': 'Movimentação Operação Financeira|Movimentação Previdência Privada',
                'pesquisas': {
                    '2': {
                        'nome': 'Por NI do Declarado e Período das informações',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '4': {
                                'nome': 'Tipo de NI',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': '2=CNPJ|1=CPF|3=NIF PF|4=NIF PJ|5=Passaporte|99=Sem NI',
                            },
                            '5': {
                                'nome': 'Número de Identificação',
                                'tipo': 'numero',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 25,
                                'listas_validas': None,
                            },
                            '18': {
                                'nome': 'Data de Início/Fim do Período',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 9,
                                'listas_validas': 'máscara ##/####',
                            },
                            '19': {
                                'nome': 'Data de Início/Fim do Período',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 9,
                                'listas_validas': 'máscara ##/####',
                            },
                        },
                    },
                    '6': {
                        'nome': 'Por NI do Declarado e Período de Entrega',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '4': {
                                'nome': 'Tipo de NI',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '1=CPF|2=CNPJ|3=NIF PF|4=NIF PJ|5=Passaporte|99=Sem NI',
                            },
                            '5': {
                                'nome': 'Número de Identificação',
                                'tipo': 'numero',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 25,
                                'listas_validas': None,
                            },
                            '8': {
                                'nome': 'Data de Início/Fim de Entrega do Evento',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '9': {
                                'nome': 'Data de Início/Fim de Entrega do Evento',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    '13': {
                        'nome': 'Por CNPJ do Declarante e Lista de Recibos',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'CNPJ do Declarante',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '31': {
                                'nome': 'Arquivo texto com lista de recibos (máx 1000)',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                },
            },
            '9': {
                'nome': 'Movimentação Operação Financeira|Movimentação Previdência Privada',
                'pesquisas': {
                    '2': {
                        'nome': 'Por NI do Declarado e Período das informações',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '4': {
                                'nome': 'Tipo de NI',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': '2=CNPJ|1=CPF|3=NIF PF|4=NIF PJ|5=Passaporte|99=Sem NI',
                            },
                            '5': {
                                'nome': 'Número de Identificação',
                                'tipo': 'numero',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 25,
                                'listas_validas': None,
                            },
                            '18': {
                                'nome': 'Data de Início/Fim do Período',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 9,
                                'listas_validas': 'máscara ##/####',
                            },
                            '19': {
                                'nome': 'Data de Início/Fim do Período',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 9,
                                'listas_validas': 'máscara ##/####',
                            },
                        },
                    },
                    '6': {
                        'nome': 'Por NI do Declarado e Período de Entrega',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '4': {
                                'nome': 'Tipo de NI',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '1=CPF|2=CNPJ|3=NIF PF|4=NIF PJ|5=Passaporte|99=Sem NI',
                            },
                            '5': {
                                'nome': 'Número de Identificação',
                                'tipo': 'numero',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 25,
                                'listas_validas': None,
                            },
                            '8': {
                                'nome': 'Data de Início/Fim de Entrega do Evento',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '9': {
                                'nome': 'Data de Início/Fim de Entrega do Evento',
                                'tipo': 'data',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    '13': {
                        'nome': 'Por CNPJ do Declarante e Lista de Recibos',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'CNPJ do Declarante',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '31': {
                                'nome': 'Arquivo texto com lista de recibos (máx 1000)',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                },
            },
            '11': {
                'nome': 'Movimentação Operação Financeira Anual',
                'pesquisas': {
                    '13': {
                        'nome': 'Por CNPJ do Declarante e Lista de Recibos',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'CNPJ do Declarante',
                                'tipo': 'cnpj',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '31': {
                                'nome': 'Arquivo texto com lista de recibos (máx 1000)',
                                'tipo': 'arquivo',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
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
                        'campos': {
                            'numrec1': {
                                'nome': 'Número do recibo 1',
                                'tipo': 'numero',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'numrec2': {
                                'nome': 'Número do recibo 2 a 10 (opcionais)',
                                'tipo': 'numero',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'numrec3': {
                                'nome': 'Número do recibo 2 a 10 (opcionais)',
                                'tipo': 'numero',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'numrec4': {
                                'nome': 'Número do recibo 2 a 10 (opcionais)',
                                'tipo': 'numero',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'numrec5': {
                                'nome': 'Número do recibo 2 a 10 (opcionais)',
                                'tipo': 'numero',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'numrec6': {
                                'nome': 'Número do recibo 2 a 10 (opcionais)',
                                'tipo': 'numero',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'numrec7': {
                                'nome': 'Número do recibo 2 a 10 (opcionais)',
                                'tipo': 'numero',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'numrec8': {
                                'nome': 'Número do recibo 2 a 10 (opcionais)',
                                'tipo': 'numero',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'numrec9': {
                                'nome': 'Número do recibo 2 a 10 (opcionais)',
                                'tipo': 'numero',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'numrec10': {
                                'nome': 'Número do recibo 2 a 10 (opcionais)',
                                'tipo': 'numero',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'EVT_TRAB_EMP_PERREC': {
                        'nome': 'Eventos trabalhistas por empregador e período de envio',
                        'papeis': ['fiscrec', 'fiscente'],
                        'finalidade': 'listagem_e_pedido',
                        'campos': {
                            'cpf': {
                                'nome': 'CPF do Empregador',
                                'tipo': 'cpf',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'iniPer': {
                                'nome': 'Início do período de envio',
                                'tipo': 'datahora',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'fimPer': {
                                'nome': 'Término do período de envio',
                                'tipo': 'datahora',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'EVT_CAD_TRAB_PER_EMP_PERREC': {
                        'nome': 'Eventos Cadastrais/tabela/trab/periódicos por empregador e período de envio',
                        'papeis': ['fiscrec', 'fiscente'],
                        'finalidade': 'listagem_e_pedido',
                        'campos': {
                            'cpf': {
                                'nome': 'CPF do Empregador',
                                'tipo': 'cpf',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'iniPer': {
                                'nome': 'Início do período de envio',
                                'tipo': 'datahora',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'fimPer': {
                                'nome': 'Término do período de envio',
                                'tipo': 'datahora',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
                    },
                    'EVT_CAD_TRAB_PER_EMP_PERAPUR': {
                        'nome': 'Eventos Cadastrais/tabela/trab/periódicos por empregador e período de apuração',
                        'papeis': ['fiscrec', 'fiscente'],
                        'finalidade': 'listagem_e_pedido',
                        'campos': {
                            'cpf': {
                                'nome': 'CPF do Empregador',
                                'tipo': 'cpf',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'iniPer': {
                                'nome': 'Início do período de apuração',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            'fimPer': {
                                'nome': 'Término do período de apuração',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                        },
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
                        'campos': {
                            '4': {
                                'nome': 'Tipo NI do Contribuinte',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '1=CNPJ|2=CPF',
                            },
                            '5': {
                                'nome': 'NI do Contribuinte (CPF 11 dig / CNPJ 14 dig)',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            '14': {
                                'nome': 'Arquivo texto com lista de NIs (mesmo tipo)',
                                'tipo': 'arquivo',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '1': {
                                'nome': 'Tipo de Evento',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '1000=R-1000 Info contribuinte|1050=R-1050 Entidades Ligadas|1070=R-1070 Processos Adm/Judiciais',
                            },
                            '12': {
                                'nome': 'Baixar arquivo com Assinatura Digital',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': 'NÃO',
                                'tamanhomax': None,
                                'listas_validas': 'NÃO|SIM',
                            },
                        },
                    },
                    '1': {
                        'nome': 'Baixar Eventos de Tabelas',
                        'papeis': ['contr', 'proc', 'repr'],
                        'finalidade': 'pedido',
                        'campos': {
                            '1': {
                                'nome': 'Tipo de Evento',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '1000|1050|1070 (mesma lista acima)',
                            },
                            '12': {
                                'nome': 'Baixar arquivo com Assinatura Digital',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': 'NÃO',
                                'tamanhomax': None,
                                'listas_validas': 'NÃO|SIM',
                            },
                        },
                    },
                },
            },
            '2000': {
                'nome': 'Eventos da família 2000',
                'pesquisas': {
                    '5': {
                        'nome': 'Por Contribuinte e Período de Apuração',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '4': {
                                'nome': 'Tipo NI do Contribuinte',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '1=CNPJ|2=CPF',
                            },
                            '5': {
                                'nome': 'NI do Contribuinte',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            '14': {
                                'nome': 'Arquivo texto com lista de NIs',
                                'tipo': 'arquivo',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '6': {
                                'nome': 'Período de Apuração Inicial',
                                'tipo': 'texto',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 7,
                                'listas_validas': 'máscara ##/####',
                            },
                            '7': {
                                'nome': 'Período de Apuração Final',
                                'tipo': 'texto',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 7,
                                'listas_validas': 'máscara ##/####',
                            },
                            '1': {
                                'nome': 'Tipo de Evento',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '2010|2020|2030|2040|2050|2055|2060|2098|2099|3010',
                            },
                            '8': {
                                'nome': 'Tipo NI do Estabelecimento',
                                'tipo': 'lista',
                                'obrigatorio': False,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '3=CAEPF|4=CNO|1=CNPJ|2=CPF',
                            },
                            '9': {
                                'nome': 'NI do Estabelecimento',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            '12': {
                                'nome': 'Baixar arquivo com Assinatura Digital',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': 'NÃO',
                                'tamanhomax': None,
                                'listas_validas': 'NÃO|SIM',
                            },
                            '13': {
                                'nome': 'Apenas o último arquivo válido?',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': 'SIM',
                                'tamanhomax': None,
                                'listas_validas': 'NÃO|SIM',
                            },
                        },
                    },
                    '6': {
                        'nome': 'Por Contribuinte e Data de Recepção',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '4': {
                                'nome': 'Tipo NI do Contribuinte',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '1=CNPJ|2=CPF',
                            },
                            '5': {
                                'nome': 'NI do Contribuinte',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            '14': {
                                'nome': 'Arquivo texto com lista de NIs',
                                'tipo': 'arquivo',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '2': {
                                'nome': 'Data de Recepção Inicial',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '3': {
                                'nome': 'Data de Recepção Final',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '1': {
                                'nome': 'Tipo de Evento',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '2010|2020|2030|2040|2050|2055|2060|2098|2099|3010',
                            },
                            '8': {
                                'nome': 'Tipo NI do Estabelecimento',
                                'tipo': 'lista',
                                'obrigatorio': False,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '3=CAEPF|4=CNO|1=CNPJ|2=CPF',
                            },
                            '9': {
                                'nome': 'NI do Estabelecimento',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            '12': {
                                'nome': 'Baixar arquivo com Assinatura Digital',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': 'NÃO',
                                'tamanhomax': None,
                                'listas_validas': 'NÃO|SIM',
                            },
                            '13': {
                                'nome': 'Apenas o último arquivo válido?',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': 'SIM',
                                'tamanhomax': None,
                                'listas_validas': 'NÃO|SIM',
                            },
                        },
                    },
                },
            },
            '4000': {
                'nome': 'Eventos da família 4000',
                'pesquisas': {
                    '9': {
                        'nome': 'Por Contribuinte e Período de Apuração',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '4': {
                                'nome': 'Tipo NI do Contribuinte',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '1=CNPJ|2=CPF',
                            },
                            '5': {
                                'nome': 'NI do Contribuinte',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            '14': {
                                'nome': 'Arquivo texto com lista de NIs',
                                'tipo': 'arquivo',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '6': {
                                'nome': 'Período de Apuração Inicial',
                                'tipo': 'texto',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 7,
                                'listas_validas': 'máscara ##/####',
                            },
                            '7': {
                                'nome': 'Período de Apuração Final',
                                'tipo': 'texto',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': 7,
                                'listas_validas': 'máscara ##/####',
                            },
                            '1': {
                                'nome': 'Tipo de Evento',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '4010|4020|4040|4080|4099',
                            },
                            '8': {
                                'nome': 'Tipo NI do Estabelecimento',
                                'tipo': 'lista',
                                'obrigatorio': False,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '3=CAEPF|1=CNPJ|2=CPF',
                            },
                            '9': {
                                'nome': 'NI do Estabelecimento',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            '10': {
                                'nome': 'Tipo NI do Beneficiário',
                                'tipo': 'lista',
                                'obrigatorio': False,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '1=CNPJ|2=CPF',
                            },
                            '11': {
                                'nome': 'NI do Beneficiário',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            '12': {
                                'nome': 'Baixar arquivo com Assinatura Digital',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': 'NÃO',
                                'tamanhomax': None,
                                'listas_validas': 'NÃO|SIM',
                            },
                            '13': {
                                'nome': 'Apenas o último arquivo válido?',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': 'SIM',
                                'tamanhomax': None,
                                'listas_validas': 'NÃO|SIM',
                            },
                        },
                    },
                    '10': {
                        'nome': 'Por Contribuinte e Data de Recepção',
                        'papeis': ['fiscrec'],
                        'finalidade': 'pedido',
                        'campos': {
                            '4': {
                                'nome': 'Tipo NI do Contribuinte',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '1=CNPJ|2=CPF',
                            },
                            '5': {
                                'nome': 'NI do Contribuinte',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            '14': {
                                'nome': 'Arquivo texto com lista de NIs',
                                'tipo': 'arquivo',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '2': {
                                'nome': 'Data de Recepção Inicial',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '3': {
                                'nome': 'Data de Recepção Final',
                                'tipo': 'data',
                                'obrigatorio': True,
                                'default': None,
                                'tamanhomax': None,
                                'listas_validas': None,
                            },
                            '1': {
                                'nome': 'Tipo de Evento',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '4010|4020|4040|4080|4099',
                            },
                            '8': {
                                'nome': 'Tipo NI do Estabelecimento',
                                'tipo': 'lista',
                                'obrigatorio': False,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '3=CAEPF|1=CNPJ|2=CPF',
                            },
                            '9': {
                                'nome': 'NI do Estabelecimento',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            '10': {
                                'nome': 'Tipo NI do Beneficiário',
                                'tipo': 'lista',
                                'obrigatorio': False,
                                'default': '0',
                                'tamanhomax': None,
                                'listas_validas': '1=CNPJ|2=CPF',
                            },
                            '11': {
                                'nome': 'NI do Beneficiário',
                                'tipo': 'texto',
                                'obrigatorio': False,
                                'default': None,
                                'tamanhomax': 14,
                                'listas_validas': None,
                            },
                            '12': {
                                'nome': 'Baixar arquivo com Assinatura Digital',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': 'NÃO',
                                'tamanhomax': None,
                                'listas_validas': 'NÃO|SIM',
                            },
                            '13': {
                                'nome': 'Apenas o último arquivo válido?',
                                'tipo': 'lista',
                                'obrigatorio': True,
                                'default': 'SIM',
                                'tamanhomax': None,
                                'listas_validas': 'NÃO|SIM',
                            },
                        },
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


def campos_da_pesquisa(sistema, tipoarquivo=None, tipopesquisa=None):
    """Retorna o dict de campos esperados para a pesquisa resolvida.

    Cada valor: ``{nome, tipo, obrigatorio, default, tamanhomax, listas_validas}``.
    """
    tipoarquivo, tipopesquisa = _resolve_tipo(
        sistema, tipoarquivo=tipoarquivo, tipopesquisa=tipopesquisa
    )
    return SISTEMAS[sistema]["tipos"][tipoarquivo]["pesquisas"][tipopesquisa]["campos"]


def _pares_periodo(campos):
    """Detecta (campo_inicio, campo_fim) na pesquisa, ou (None, None)."""
    if not campos:
        return None, None

    pares_conhecidos = (
        ("dataInicio", "dataFim"),
        ("iniPer", "fimPer"),
        ("dataInicioPeriodo", "dataFimPeriodo"),
        ("dataInicioAutorizacao", "dataFimAutorizacao"),
        ("dataInicioEmissao", "dataFimEmissao"),
        ("dataInicioEntrega", "dataFimEntrega"),
        ("dataInicioEscrituracao", "dataFimEscrituracao"),
        ("2", "3"),  # EFD-Reinf: recepção
        ("6", "7"),  # EFD-Reinf: período de apuração
    )
    for a, b in pares_conhecidos:
        if a in campos and b in campos:
            return a, b

    # Heurística: campos data/datahora com dicas de início/fim no id ou nome
    candidatos = []
    for cid, meta in campos.items():
        tipo = (meta.get("tipo") or "").lower()
        if tipo not in ("data", "datahora"):
            continue
        blob = f"{cid} {(meta.get('nome') or '')}".lower()
        candidatos.append((cid, blob))

    if len(candidatos) == 2:
        a, b = candidatos[0], candidatos[1]
        a_start = any(h in a[1] for h in ("inicio", "início", "inicial", "ini"))
        b_start = any(h in b[1] for h in ("inicio", "início", "inicial", "ini"))
        a_end = any(h in a[1] for h in ("fim", "final", "termino", "término"))
        b_end = any(h in b[1] for h in ("fim", "final", "termino", "término"))
        if a_start and b_end:
            return a[0], b[0]
        if b_start and a_end:
            return b[0], a[0]
        return a[0], b[0]

    if len(candidatos) == 1:
        return candidatos[0][0], None

    return None, None


def _opcoes_lista(listas_validas):
    """Extrai códigos válidos de ``listas_validas`` (ex.: ``1=CNPJ|2=CPF``).

    Retorna ``None`` quando não há enum (campo livre / máscara).
    """
    if not listas_validas:
        return None
    text = str(listas_validas).strip()
    if not text:
        return None
    lower = text.lower()
    if lower.startswith("máscara") or lower.startswith("mascara"):
        return None
    opcoes = set()
    for part in text.split("|"):
        part = part.strip()
        if not part:
            continue
        if "(" in part:
            part = part.split("(", 1)[0].strip()
        key = part.split("=", 1)[0].strip()
        if key:
            opcoes.add(key)
    return opcoes or None


def _valor_lista_ok(valor, listas_validas):
    """True se valor é aceito pela lista (ou se não há lista restritiva)."""
    opcoes = _opcoes_lista(listas_validas)
    if opcoes is None:
        return True
    return str(valor) in opcoes


def _resolver_chave_campo(schema, chave):
    """Aceita id do campo (``4``) ou nome oficial (``Tipo NI do Contribuinte``)."""
    k = str(chave)
    if k in schema:
        return k
    for cid, meta in schema.items():
        if (meta.get("nome") or "") == k:
            return cid
    return k


def _montar_valores_campos(
    sistema,
    tipoarquivo,
    tipopesquisa,
    inicio=None,
    fim=None,
    campos=None,
    validar=True,
):
    """Monta dict nome->valor para a pesquisa, mapeando inicio/fim e defaults.

    Defaults do Derby com placeholder inválido (ex.: ``0`` fora de
    ``listas_validas``) **não** são enviados — o CSV usa ``0`` só como
    “não selecionado” na UI, não como valor SOAP.
    """
    schema = campos_da_pesquisa(sistema, tipoarquivo, tipopesquisa)
    valores = {}
    if campos:
        for k, v in campos.items():
            if v is not None:
                valores[_resolver_chave_campo(schema, k)] = v

    id_ini, id_fim = _pares_periodo(schema)

    if inicio is not None:
        if id_ini:
            valores.setdefault(id_ini, _normalize_date(inicio, end=False))
        elif schema and validar:
            raise ValueError(
                f"A pesquisa {tipopesquisa!r} do sistema {sistema} não possui "
                f"campo de data inicial; passe os campos nomeados via kwargs. "
                f"Campos: {list(schema)}"
            )
        else:
            valores.setdefault("dataInicio", _normalize_date(inicio, end=False))

    if fim is not None:
        if id_fim:
            valores.setdefault(id_fim, _normalize_date(fim, end=True))
        elif id_ini and inicio is not None and id_fim is None:
            # pesquisa com um único campo de data — fim ignorado se igual schema single
            pass
        elif schema and validar:
            raise ValueError(
                f"A pesquisa {tipopesquisa!r} do sistema {sistema} não possui "
                f"campo de data final; passe os campos nomeados via kwargs. "
                f"Campos: {list(schema)}"
            )
        else:
            valores.setdefault("dataFim", _normalize_date(fim, end=True))

    # defaults do schema — só se forem valores válidos na lista
    for cid, meta in schema.items():
        if cid in valores or meta.get("default") is None:
            continue
        default = meta["default"]
        if _valor_lista_ok(default, meta.get("listas_validas")):
            valores[cid] = default

    if validar and schema:
        desconhecidos = [k for k in valores if k not in schema]
        if desconhecidos:
            raise ValueError(
                f"Campos inválidos para sistema={sistema} tipo={tipoarquivo!r} "
                f"pesquisa={tipopesquisa!r}: {desconhecidos}. "
                f"Esperados: {list(schema)}"
            )
        invalidos = [
            f"{cid}={valores[cid]!r} (válidos: {meta.get('listas_validas')})"
            for cid, meta in schema.items()
            if cid in valores
            and not _valor_lista_ok(valores[cid], meta.get("listas_validas"))
        ]
        if invalidos:
            raise ValueError(
                f"Valores fora de listas_validas para sistema={sistema} "
                f"tipo={tipoarquivo!r} pesquisa={tipopesquisa!r}: {invalidos}"
            )
        faltando = [
            cid
            for cid, meta in schema.items()
            if meta.get("obrigatorio")
            and (cid not in valores or valores[cid] is None or str(valores[cid]) == "")
        ]
        if faltando:
            raise ValueError(
                f"Campos obrigatórios ausentes para sistema={sistema} "
                f"tipo={tipoarquivo!r} pesquisa={tipopesquisa!r}: {faltando}. "
                f"Use campos_da_pesquisa({sistema}, {tipoarquivo!r}, {tipopesquisa!r}) "
                f"para ver o schema."
            )

    return valores


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
        inicio=None,
        fim=None,
        perfil="contr",
        nirepresentado=None,
        tiponirepresentado=None,
        tipoarquivo=None,
        tipopesquisa=None,
        campos=None,
    ):
        tipoarquivo, tipopesquisa = _resolve_tipo(
            sistema, tipoarquivo=tipoarquivo, tipopesquisa=tipopesquisa
        )
        valores = _montar_valores_campos(
            sistema,
            tipoarquivo,
            tipopesquisa,
            inicio=inicio,
            fim=fim,
            campos=campos,
            validar=True,
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
        ]
        for nome, valor in valores.items():
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
        inicio=None,
        fim=None,
    ):
        has_arquivos = bool(arquivos_ids)
        has_pesquisa = bool(pesquisa_campos) or inicio is not None or fim is not None
        if has_arquivos and has_pesquisa and pesquisa_campos:
            raise ValueError(
                "Informe apenas um de: arquivos ou pesquisa_campos "
                "(mutuamente exclusivos conforme a documentação)"
            )
        if has_arquivos and (inicio is not None or fim is not None) and not pesquisa_campos:
            # permitir arquivos + ignorar inicio/fim? melhor erro claro
            pass
        if has_arquivos and pesquisa_campos:
            raise ValueError(
                "Informe apenas um de: arquivos ou pesquisa_campos "
                "(mutuamente exclusivos conforme a documentação)"
            )
        if not has_arquivos and not (pesquisa_campos or inicio is not None or fim is not None):
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

        if not has_arquivos:
            valores = _montar_valores_campos(
                sistema,
                tipoarquivo,
                tipopesquisa,
                inicio=inicio,
                fim=fim,
                campos=pesquisa_campos,
                validar=True,
            )
            parts.append("<pesquisa>")
            for nome, valor in valores.items():
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
        inicio=None,
        fim=None,
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
            inicio: Data/período inicial — mapeado automaticamente para o campo
                correto da pesquisa (ex.: ``dataInicio``, ``iniPer``, ``2``).
            fim: Data/período final — mapeado para ``dataFim``, ``fimPer``, ``3``, etc.
            perfil: "contr" (contribuinte, padrão) ou "proc" (procurador).
            nirepresentado: NI do representado (obrigatório se perfil=proc).
            tiponirepresentado: "cpf" ou "cnpj" (com nirepresentado).
            tipoarquivo: Código do tipo (default: primeiro do sistema).
            tipopesquisa: Código da pesquisa (default: primeira do tipo).
            **campos: Campos da pesquisa pelo nome oficial (ver ``campos_da_pesquisa``).
                Ex.: ``cpf="00000000000"``, ``cnpj="..."``.

        Returns:
            dict com retorno, saida, mensagem, arquivos (lista de IDs) e pedido_id.
            {} em falha de conexão/HTTP.
        """
        entrada = self._build_entrada_pesquisa(
            sistema,
            inicio=inicio,
            fim=fim,
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
        inicio=None,
        fim=None,
    ):
        """Chama SolicitarArquivos.

        Três modos (doc oficial):
            - ``arquivos``: lista de IDs (retorno de pesquisar).
            - ``pesquisa_campos`` / ``inicio``+``fim``: critérios diretos.
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
            inicio / fim: mapeados aos campos de período da pesquisa (modo pesquisa).

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
            inicio=inicio,
            fim=fim,
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
