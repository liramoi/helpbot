import sqlite3
from datetime import datetime
import os

DB_PATH = "database/servicedesk.db"

def inicializar_db():
    if not os.path.exists("database"):
        os.makedirs("database")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chamados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            protocolo TEXT UNIQUE,
            historico TEXT,
            status TEXT,
            dados_usuario TEXT,
            data_criacao TEXT
        )
    """)
    conn.commit()
    conn.close()

def atualizar_chamado(protocolo, texto_usuario, resposta_ia, status, dados=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    agora = datetime.now().strftime("%H:%M:%S")
    nova_interacao = f"[{agora}] Usuário: {texto_usuario}\n[{agora}] IA: {resposta_ia}\n"

    # Busca se já existe
    cursor.execute("SELECT historico FROM chamados WHERE protocolo = ?", (protocolo,))
    row = cursor.fetchone()

    if row:
        novo_historico = row[0] + "\n" + nova_interacao
        cursor.execute("UPDATE chamados SET historico = ?, status = ?, dados_usuario = ? WHERE protocolo = ?", 
                       (novo_historico, status, dados, protocolo))
    else:
        data_inicio = datetime.now().strftime("%d/%m/%Y %H:%M")
        cursor.execute("INSERT INTO chamados (protocolo, historico, status, data_criacao) VALUES (?, ?, ?, ?)",
                       (protocolo, nova_interacao, status, data_inicio))
    
    conn.commit()
    conn.close()