import uuid
import sqlite3
import os
import re
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from contextlib import asynccontextmanager

from api.claude import analisar_com_ia

DB_PATH = "database/servicedesk.db"

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.path.exists("database"):
        os.makedirs("database")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chamados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            protocolo TEXT UNIQUE,
            historico TEXT,
            historico_ia TEXT,
            status TEXT,
            dados_usuario TEXT,
            data_criacao TEXT,
            ultima_atividade TEXT
        )
    """)
    for coluna in ["historico_ia", "ultima_atividade"]:
        try:
            cursor.execute(f"ALTER TABLE chamados ADD COLUMN {coluna} TEXT")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()
    yield

app = FastAPI(title="HelpBot Service Desk", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Consulta(BaseModel):
    texto: str
    protocolo: Optional[str] = None
    dados_pre_coleta: Optional[str] = None

class EdicaoChamado(BaseModel):
    status: str
    dados_usuario: Optional[str] = None
    observacao: Optional[str] = None

def salvar_ou_atualizar_chamado(protocolo, interacao, status, info_contato, historico_ia_json=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    agora_hora = datetime.now().strftime("%H:%M:%S")
    agora_completo = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    log = f"[{agora_hora}] {interacao}\n"

    cursor.execute("SELECT historico FROM chamados WHERE protocolo = ?", (protocolo,))
    row = cursor.fetchone()

    if row:
        novo_historico = row[0] + log
        cursor.execute(
            "UPDATE chamados SET historico = ?, status = ?, historico_ia = ?, ultima_atividade = ? WHERE protocolo = ?",
            (novo_historico, status, historico_ia_json, agora_completo, protocolo)
        )
    else:
        data_inicio = datetime.now().strftime("%d/%m/%Y %H:%M")
        cursor.execute("""
            INSERT INTO chamados (protocolo, historico, historico_ia, status, dados_usuario, data_criacao, ultima_atividade)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (protocolo, log, historico_ia_json, status, info_contato, data_inicio, agora_completo))

    conn.commit()
    conn.close()

def buscar_chamado(protocolo):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT status, historico, historico_ia FROM chamados WHERE protocolo = ?", (protocolo,))
    row = cursor.fetchone()
    conn.close()
    return row

def reconstruir_historico_ia(historico_ia_json: str) -> list:
    if not historico_ia_json:
        return []
    try:
        return json.loads(historico_ia_json)
    except:
        return []

def serializar_historico_ia(historico: list) -> str:
    return json.dumps(historico, ensure_ascii=False)

PALAVRAS_CONFIRMACAO = [
    "sim", "obrigado", "funcionou", "ok", "consegui",
    "deu certo", "perfeito", "ótimo", "resolvido", "certo",
    "valeu", "muito obrigado", "foi resolvido", "problema resolvido",
    "tudo bem", "entendido"
]

PALAVRAS_NEGACAO = [
    "não", "nao", "nada", "continua", "ainda", "persiste",
    "mesmo assim", "continua igual", "não funcionou", "não resolveu",
    "não deu", "não consegui", "sem sucesso"
]

def usuario_confirmou_resolucao(texto: str) -> bool:
    texto_lower = texto.lower().strip()

    # Se tiver palavra de negação, não é confirmação
    if any(p in texto_lower for p in PALAVRAS_NEGACAO):
        return False

    return any(p in texto_lower for p in PALAVRAS_CONFIRMACAO)

@app.post("/chat")
async def chat_endpoint(consulta: Consulta):
    protocolo = consulta.protocolo if consulta.protocolo else str(uuid.uuid4())[:8].upper()

    row = buscar_chamado(protocolo)
    status_anterior = row[0] if row else None
    historico_anterior = row[1] if row else ""
    historico_ia_json = row[2] if row else None

    historico_mensagens = reconstruir_historico_ia(historico_ia_json)

    # Se o status é ATENDIMENTO INICIAL e o usuário confirmou resolução
    if status_anterior == "ATENDIMENTO INICIAL" and usuario_confirmou_resolucao(consulta.texto):
        mensagem_resposta = (
            "Fico feliz que tenha resolvido! 😊 "
            f"Seu protocolo de atendimento é #{protocolo}. "
            "Se precisar de mais suporte, é só abrir uma nova solicitação."
        )
        status_atual = "ENCERRADO"

        historico_mensagens.append({"role": "user", "content": consulta.texto})
        historico_mensagens.append({"role": "assistant", "content": mensagem_resposta})

        interacao_formatada = f"USUÁRIO: {consulta.texto} | IA: {mensagem_resposta}"
        salvar_ou_atualizar_chamado(
            protocolo, interacao_formatada, status_atual,
            consulta.dados_pre_coleta,
            serializar_historico_ia(historico_mensagens)
        )
        return {
            "resposta": mensagem_resposta,
            "protocolo": protocolo,
            "status": "ENCERRADO"
        }

    historico_mensagens = reconstruir_historico_ia(historico_ia_json)

    # Palavras que indicam que a IA pediu localização
    palavras_pedido_localizacao = [
        "onde você está localizado",
        "onde você está",
        "qual é a sua localização",
        "informe sua localização",
        "me informe onde",
        "unidade, andar e posto",
        "informe unidade",
        "onde você se encontra",
        "visita técnica",
        "onde fica",
        "qual sua localização",
    ]

    ia_pediu_localizacao = status_anterior == "AGUARDANDO DADOS" and any(
        p in historico_anterior.lower() for p in palavras_pedido_localizacao
    )

    # Se a IA já pediu localização, registra e encerra
    if ia_pediu_localizacao:
        localizacao = consulta.texto
        mensagem_resposta = (
            f"Obrigado! Sua localização foi registrada: {localizacao}. "
            f"Um técnico será enviado em breve. Seu protocolo é #{protocolo}. "
            f"Seu atendimento foi encerrado."
        )
        status_atual = "NÃO SOLUCIONADO"

        historico_mensagens.append({"role": "user", "content": consulta.texto})
        historico_mensagens.append({"role": "assistant", "content": mensagem_resposta})

        interacao_formatada = f"USUÁRIO: {consulta.texto} | IA: {mensagem_resposta}"
        salvar_ou_atualizar_chamado(
            protocolo, interacao_formatada, status_atual,
            consulta.dados_pre_coleta,
            serializar_historico_ia(historico_mensagens)
        )
        return {
            "resposta": mensagem_resposta,
            "protocolo": protocolo,
            "status": "NÃO SOLUCIONADO"
        }

    # Chama a IA com histórico completo
    resposta_ia = analisar_com_ia(consulta.texto, historico_mensagens)

    # Detecta status pelas tags
    status_atual = "ATENDIMENTO INICIAL"
    if "[STATUS: ENCERRADO]" in resposta_ia:
        status_atual = "ENCERRADO"
    elif "[STATUS: NÃO SOLUCIONADO]" in resposta_ia:
        status_atual = "NÃO SOLUCIONADO"
    elif "[STATUS: AGUARDANDO DADOS]" in resposta_ia:
        status_atual = "AGUARDANDO DADOS"
    else:
        # Detecta pedido de localização mesmo sem tag
        pedidos_localizacao = [
            "onde você está localizado",
            "informe unidade, andar e posto",
            "onde você se encontra",
            "qual sua localização",
            "informe sua localização",
        ]
        if any(p in resposta_ia.lower() for p in pedidos_localizacao):
            status_atual = "AGUARDANDO DADOS"

    # Limpa tags da resposta
    mensagem_resposta = re.sub(r"\[STATUS:.*?\]", "", resposta_ia).strip()

    if not mensagem_resposta:
        mensagem_resposta = "Atendimento encerrado. Se precisar de suporte, abra uma nova solicitação."
        status_atual = "ENCERRADO"

    # Atualiza histórico IA com a troca atual
    historico_mensagens.append({"role": "user", "content": consulta.texto})
    historico_mensagens.append({"role": "assistant", "content": mensagem_resposta})

    interacao_formatada = f"USUÁRIO: {consulta.texto} | IA: {mensagem_resposta}"
    salvar_ou_atualizar_chamado(
        protocolo, interacao_formatada, status_atual,
        consulta.dados_pre_coleta,
        serializar_historico_ia(historico_mensagens)
    )

    return {
        "resposta": mensagem_resposta,
        "protocolo": protocolo,
        "status": status_atual
    }

@app.get("/chamados")
async def listar_chamados():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chamados ORDER BY id DESC")
    chamados = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return chamados

@app.post("/chamados/{protocolo}/encerrar")
async def encerrar_chamado(protocolo: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    agora = datetime.now().strftime("%H:%M:%S")
    cursor.execute("SELECT historico FROM chamados WHERE protocolo = ?", (protocolo,))
    row = cursor.fetchone()
    if row:
        novo_historico = row[0] + f"[{agora}] TÉCNICO: Chamado encerrado manualmente.\n"
        cursor.execute(
            "UPDATE chamados SET status = ?, historico = ? WHERE protocolo = ?",
            ("ENCERRADO", novo_historico, protocolo)
        )
        conn.commit()
    conn.close()
    return {"ok": True}

@app.put("/chamados/{protocolo}")
async def editar_chamado(protocolo: str, edicao: EdicaoChamado):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    agora = datetime.now().strftime("%H:%M:%S")
    cursor.execute("SELECT historico FROM chamados WHERE protocolo = ?", (protocolo,))
    row = cursor.fetchone()
    if row:
        historico = row[0]
        if edicao.observacao:
            historico += f"[{agora}] TÉCNICO: {edicao.observacao}\n"
        cursor.execute(
            "UPDATE chamados SET status = ?, dados_usuario = ?, historico = ? WHERE protocolo = ?",
            (edicao.status, edicao.dados_usuario, historico, protocolo)
        )
        conn.commit()
    conn.close()
    return {"ok": True}

@app.get("/diagnostico")
async def diagnostico():
    from rag.searcher import buscar
    import chromadb
    from chromadb.utils import embedding_functions
    from pathlib import Path

    CHROMA_DIR = Path("chroma_db")
    try:
        client_diag = chromadb.PersistentClient(path=str(CHROMA_DIR))
        col = client_diag.get_collection(
            name="helpbot",
            embedding_function=embedding_functions.DefaultEmbeddingFunction()
        )
        total_chunks = col.count()
        teste = buscar("como conectar ao wifi", n_resultados=2)
        return {
            "status": "ok",
            "total_chunks_indexados": total_chunks,
            "teste_busca": {
                "pergunta": "como conectar ao wifi",
                "resultados_encontrados": len(teste),
                "preview": [
                    {
                        "arquivo": r["arquivo"],
                        "categoria": r["categoria"],
                        "trecho": r["texto"][:150] + "..."
                    }
                    for r in teste
                ]
            }
        }
    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}
    
@app.post("/chamados/verificar-inatividade")
async def verificar_inatividade():
    """Encerra chamados sem resposta há mais de 10 minutos após solução oferecida."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT protocolo, ultima_atividade, historico 
        FROM chamados 
        WHERE status = 'ATENDIMENTO INICIAL' AND ultima_atividade IS NOT NULL
    """)
    chamados = cursor.fetchall()
    encerrados = 0

    for protocolo, ultima_atividade, historico in chamados:
        try:
            ultima = datetime.strptime(ultima_atividade, "%d/%m/%Y %H:%M:%S")
            minutos_inativo = (datetime.now() - ultima).seconds // 60

            if minutos_inativo >= 10:
                agora = datetime.now().strftime("%H:%M:%S")
                novo_historico = historico + f"[{agora}] SISTEMA: Chamado encerrado automaticamente por inatividade.\n"
                cursor.execute(
                    "UPDATE chamados SET status = ?, historico = ? WHERE protocolo = ?",
                    ("ENCERRADO", novo_historico, protocolo)
                )
                encerrados += 1
        except:
            continue

    conn.commit()
    conn.close()
    return {"encerrados": encerrados}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)