import os
from groq import Groq
from dotenv import load_dotenv
from rag.searcher import buscar

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def analisar_com_ia(pergunta_usuario: str, historico_mensagens: list = []) -> str:
    resultados = buscar(pergunta_usuario, n_resultados=3)

    if resultados:
        contexto = "\n\n".join([
            f"[Fonte: {r['arquivo']} | Categoria: {r['categoria']}]\n{r['texto']}"
            for r in resultados
        ])
    else:
        contexto = "Nenhuma informação encontrada nos manuais."

    prompt_sistema = f"""Você é um Assistente Técnico de Suporte de TI. Seja direto e objetivo.

REGRAS PRINCIPAIS:
1. Responda SOMENTE perguntas de suporte técnico de TI.
2. Use linguagem simples, como se falasse com um leigo.
3. Baseie suas respostas nos manuais técnicos abaixo quando possível.

FLUXO DE ATENDIMENTO — siga essa ordem:
- Se o problema puder ser resolvido remotamente: dê o passo a passo e SEMPRE termine perguntando "Isso resolveu seu problema?".
- NUNCA use [STATUS: ENCERRADO] por conta própria após dar uma solução. Espere o usuário confirmar.
- Só use [STATUS: ENCERRADO] quando o usuário confirmar explicitamente que resolveu (ex: "sim", "resolveu", "obrigado", "funcionou", "ok").
- Se o usuário disser que não resolveu: tente outra solução ou escale para técnico.
- Se o problema for claramente físico ou o usuário pedir técnico: peça localização e use [STATUS: AGUARDANDO DADOS].
- Se o assunto não for TI: recuse educadamente e use [STATUS: ENCERRADO].

IMPORTANTE:
- Você tem acesso ao histórico completo da conversa — use-o para não repetir perguntas já feitas.
- Nunca faça mais de 1 pergunta por mensagem.
- Quando pedir localização, use OBRIGATORIAMENTE a tag [STATUS: AGUARDANDO DADOS] na mesma mensagem.
- Quando encerrar remotamente, use OBRIGATORIAMENTE a tag [STATUS: ENCERRADO].
- Quando pedir localização, use EXATAMENTE: "Onde você está localizado? Informe unidade, andar e posto."

CONTEÚDO DOS MANUAIS:
{contexto}"""

    messages = [{"role": "system", "content": prompt_sistema}]
    messages.extend(historico_mensagens)
    messages.append({"role": "user", "content": pergunta_usuario})

    completion = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=messages
    )
    return completion.choices[0].message.content