"""
FABOT — prompt_variator.py
Motor de Variedade Criativa.
Problema: LLM recebe sempre o mesmo prompt → gera sempre o mesmo roteiro.
Solução: injetar variações ANTES de mandar para a LLM.
Cada chamada sorteia:
  - Estilo de abertura (1 de 6)
  - Estratégia de bloco por conceito (4 de 8)
  - Frases de reação (4 de 10)
  - Qual personagem/empresa usar primeiro (shuffle)
  - Estilo de analogia (1 de 5)
"""

import random
import time


ABERTURAS = [
    {
        "id": "provocacao",
        "instrucao": """NARRADOR abre com uma PROVOCAÇÃO sobre o tema.
Exemplo: "Você sabia que existe uma diferença ENORME entre saber programar
e saber pensar como programador? Hoje vamos falar de [termos] e você vai
entender por quê."
NÃO cumprimente ninguém na abertura. Vá direto ao ponto.""",
    },
    {
        "id": "historia",
        "instrucao": """NARRADOR abre contando uma MICRO-HISTÓRIA real.
Exemplo: "Em dois mil e dezoito, um estagiário do Itaú deletou uma tabela
inteira do banco de dados por um erro de digitação. Custou três dias de
trabalho de vinte pessoas. Hoje vamos aprender [termos] para que isso
NUNCA aconteça com vocês."
NÃO liste os temas como lista de compras. Conte uma história que conecte.""",
    },
    {
        "id": "pergunta",
        "instrucao": """NARRADOR abre com uma PERGUNTA IMPOSSÍVEL DE IGNORAR.
Exemplo: "Se alguém te pedir pra explicar a diferença entre igual e duplo
igual, você consegue? Se a resposta é 'acho que sim' — esse episódio é pra
você. Hoje: [termos]."
NÃO use "Olá" ou "Bem-vindos". Comece com a pergunta.""",
    },
    {
        "id": "analogia_absurda",
        "instrucao": """NARRADOR abre com uma ANALOGIA IMPREVISTA que conecta
o tema com algo totalmente inesperado do mundo dos negócios.
Exemplo: "Operadores em Python são como decisões estratégicas numa empresa:
se você toma a decisão errada na hora errada, o resultado sai completamente
diferente do esperado. Hoje: [termos]."
NÃO seja previsível. Surpreenda.""",
    },
    {
        "id": "desafio",
        "instrucao": """NARRADOR abre com um DESAFIO para o ouvinte.
Exemplo: "Desafio: no final desse episódio, você vai conseguir olhar pra
qualquer linha de código com um sinal de igual e saber EXATAMENTE o que
está acontecendo. Sem medo, sem dúvida. Hoje: [termos]. Aceita o desafio?"
NÃO seja genérico. O desafio deve ser ESPECÍFICO do tema.""",
    },
    {
        "id": "erro_comum",
        "instrucao": """NARRADOR abre revelando o ERRO MAIS COMUM de iniciantes.
Exemplo: "Noventa por cento dos iniciantes em Python cometem ESSE erro na
primeira semana. E o pior: o programa roda, mas o resultado sai ERRADO.
Hoje vamos falar de [termos] e você vai aprender a nunca cair nessa armadilha."
NÃO diga qual é o erro na abertura — crie suspense.""",
    },
]


ESTRATEGIAS_BLOCO = [
    {
        "id": "problema_primeiro",
        "instrucao": """ESTRATÉGIA: Problema → Dor → Solução → Conceito
Comece mostrando o PROBLEMA: "Imagine que você precisa comparar dois
valores e seu programa faz coisa errada..." Depois mostre a dor de não
saber. Só ENTÃO apresente o conceito como salvador.""",
    },
    {
        "id": "analogia_primeiro",
        "instrucao": """ESTRATÉGIA: Analogia → Conceito → Código → Prática
Comece com uma ANALOGIA do mundo real que explique o conceito ANTES
de nomeá-lo. "Sabe quando você tá no supermercado e compara o preço
por quilo?" — SÓ DEPOIS diga que isso é como operador relacional.""",
    },
    {
        "id": "resultado_primeiro",
        "instrucao": """ESTRATÉGIA: Resultado → Caminho → Fundamento
Comece mostrando o RESULTADO final: "Com três linhas de código, você
calcula o lucro de qualquer produto automaticamente." O ouvinte pensa
"quero isso!". Depois mostre COMO chegar lá. Por último, fundamente.""",
    },
    {
        "id": "erro_primeiro",
        "instrucao": """ESTRATÉGIA: Erro → Consequência → Correção → Conceito
Comece com um ERRO real que iniciantes cometem. Mostre a consequência
terrível. Depois apresente como corrigir e por que funciona. O medo
de errar fixa melhor que a vontade de acertar.""",
    },
    {
        "id": "pergunta_socratica",
        "instrucao": """ESTRATÉGIA: Perguntas → O aluno descobre → Confirmação
O apresentador NÃO explica diretamente. Faz PERGUNTAS que guiam o
ouvinte a descobrir sozinho. "Se eu tenho dez e quero saber se é maior
que cinco, o que faço?" Método socrático puro.""",
    },
    {
        "id": "comparacao",
        "instrucao": """ESTRATÉGIA: Comparação → O que é vs O que NÃO é → Prática
Comece COMPARANDO com algo que o ouvinte já sabe. "Você já sabe somar.
Mas e se eu te perguntar: quanto é dez dividido inteiro por três?
A resposta NÃO é três vírgula três." Esse choque fixa.""",
    },
    {
        "id": "construcao",
        "instrucao": """ESTRATÉGIA: Construir juntos → Passo a passo → Resultado
Em vez de explicar, CONSTRUA algo juntos. "Vamos criar uma calculadora
de troco. Primeiro, precisamos de quê? Do valor pago e do valor do
produto. E como calculo troco?" O ouvinte participa mentalmente.""",
    },
    {
        "id": "historia_real",
        "instrucao": """ESTRATÉGIA: Caso real → Análise → Conceito → Aplicação
Comece com um CASO REAL de empresa. "A Magazine Luiza precisava
calcular a margem de cinquenta mil produtos por dia. O que aconteceu
quando o estagiário usou o operador errado?" Depois destrinche.""",
    },
]


REACOES_HOST = [
    '"Aaah, agora clicou! Faz total sentido!"',
    '"Espera, deixa eu ver se entendi certo..."',
    '"Sério? Nunca tinha pensado por esse lado!"',
    '"Tá, mas e se eu fizer diferente? E se eu..."',
    '"Caramba, isso muda tudo que eu pensava!"',
    '"Hum, então por que todo mundo erra nisso?"',
    '"Para tudo. Repete essa parte que é importante."',
    '"Olha, eu tava pensando errado esse tempo todo..."',
    '"Nossa, se eu tivesse aprendido isso antes..."',
    '"Beleza, agora me dá um exemplo real que eu fixo."',
]


CONFIRMACOES_HOST = [
    '"Isso aí! Agora ficou claro!"',
    '"Boa! Exatamente!"',
    '"Perfeito, é isso mesmo."',
    '"Mandou bem! Era isso que eu queria ouvir."',
    '"Show! Próximo conceito?"',
    '"Certíssimo. Guarda essa."',
    '"Fechou! Não esqueço mais."',
    '"Opa, agora sim. Bora pro próximo?"',
]


ESTILOS_ANALOGIA = [
    "Use analogias de VAREJO E GESTÃO DE ESTOQUE: como a Renner "
    "controla milhares de SKUs no estoque, como o Mercado Livre processa "
    "milhões de pedidos por dia, como um sistema de PDV registra cada "
    "venda no caixa, como a gestão de prateleiras inteligentes otimiza "
    "o espaço disponível. Conecte cada conceito técnico com como esses "
    "processos funcionam no dia a dia de uma loja ou e-commerce.",
    "Use analogias de FINANÇAS E CONTROLADORIA: como um DRE consolida "
    "dados de 50 filiais em um relatório só, como o Nubank detecta fraude "
    "em tempo real olhando padrões de gasto, como uma auditoria rastreia "
    "cada centavo de uma transação, como centros de custo separam despesas "
    "por departamento. Conecte cada conceito com a lógica de um CFO "
    "tomando decisões.",
    "Use analogias de LOGÍSTICA E OPERAÇÕES: como a Ambev roteiriza "
    "500 entregas por dia para bares e restaurantes, como um armazém "
    "automatizado controla entrada e saída de mercadorias, como uma "
    "transportadora calcula o menor custo de frete entre cidades, como a "
    "gestão de frotas otimiza o uso de cada caminhão. Conecte cada "
    "conceito com a complexidade operacional de mover coisas.",
    "Use analogias de MARKETING DIGITAL E CRM: como a Magazine Luiza "
    "segmenta milhões de clientes para enviar ofertas personalizadas, como "
    "uma campanha de e-mail mede conversão olhando quem abriu e quem "
    "clicou, como um CRM registra cada interação do cliente do primeiro "
    "contato até a venda, como dashboards mostram métricas de marketing em "
    "tempo real. Conecte cada conceito com a tomada de decisão baseada "
    "em dados.",
    "Use analogias de RECURSOS HUMANOS: como uma empresa processa a folha "
    "de pagamento de 2000 funcionários sem errar, como um sistema de ponto "
    "eletrônico rastreia horas trabalhadas de cada colaborador, como o "
    "cálculo de benefícios (VR, VT, plano de saúde) varia por employee, "
    "como métricas de RH medem turnover e satisfaction. Conecte cada "
    "conceito com a gestão de pessoas e cultura organizacional.",
]


def gerar_variacoes(
    personagens: list,
    empresas: list,
    episode_number: int = 1,
) -> dict:
    """
    Gera um conjunto de variações para injetar no prompt.
    Cada chamada produz combinação DIFERENTE.

    Usa timestamp em milissegundos como seed parcial para que episódios
    da mesma série tenham variedade mas determinística. Milissegundos
    garantem que mesmo duas chamadas no mesmo segundo tenham seeds
    diferentes (impossível gerar no mesmo ms manualmente).
    """
    seed = int(time.time_ns() // 1_000_000) + episode_number
    rng = random.Random(seed)

    abertura = rng.choice(ABERTURAS)

    estrategias = rng.sample(ESTRATEGIAS_BLOCO, min(4, len(ESTRATEGIAS_BLOCO)))

    personagens_rotacionados = list(personagens) if personagens else []
    rng.shuffle(personagens_rotacionados)

    empresas_rotacionadas = list(empresas) if empresas else []
    rng.shuffle(empresas_rotacionadas)

    reacoes = rng.sample(REACOES_HOST, min(4, len(REACOES_HOST)))
    confirmacoes = rng.sample(CONFIRMACOES_HOST, min(3, len(CONFIRMACOES_HOST)))

    estilo_analogia = rng.choice(ESTILOS_ANALOGIA)

    return {
        "abertura": abertura,
        "estrategias": estrategias,
        "personagens_rotacionados": personagens_rotacionados,
        "empresas_rotacionadas": empresas_rotacionadas,
        "reacoes": reacoes,
        "confirmacoes": confirmacoes,
        "estilo_analogia": estilo_analogia,
    }


def validar_script_anti_repeticao(script_json: dict) -> tuple[bool, list[str]]:
    """
    Valida que o roteiro não contém frases repetitivas ou banidas.
    Retorna (passou, lista_de_problemas).
    """
    import logging

    logger = logging.getLogger(__name__)

    problemas = []

    texto_completo = " ".join(
        s.get("text", "") or "" for s in script_json.get("segments", [])
    ).lower()

    frases_banidas = [
        ("isso escala", "Frase clichê detectada: 'isso escala'"),
        (
            "não escala de jeito nenhum",
            "Frase clichê detectada: 'não escala de jeito nenhum'",
        ),
        ("olá ", "Saudação 'Olá' no início — não é variacional"),
        ("um abraço para", "Frase repetitiva detectada: 'um abraço para'"),
        ("excelente,", "Frase repetitiva: 'Excelente,'"),
        (
            "imagine uma empresa como a [empresa]",
            "Template detectável: empresa entre colchetes",
        ),
    ]

    for frase, msg in frases_banidas:
        if frase in texto_completo:
            problemas.append(msg)

    if script_json.get("segments"):
        hosts = [
            s.get("speaker", "").upper()
            for s in script_json["segments"]
            if s.get("speaker", "").upper() not in ("NARRADOR",)
        ]
        if hosts:
            total = len(hosts)
            unicos = len(set(hosts))
            if total > 0 and unicos / total < 0.3:
                problemas.append(
                    f"Repetição excessiva de apresentador: {unicos}/{total} únicos"
                )

    passou = len(problemas) == 0

    if problemas:
        logger.warning(f"Validação anti-repetição falhou: {problemas}")

    return passou, problemas
