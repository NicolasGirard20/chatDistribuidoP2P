
"""Definición del Protocolo

Este módulo define los tipos de mensaje y utilidades para crear/parsear
mensajes JSON terminados en newline usados por el sistema P2P.
"""

import json

# --- Tipos de Mensajes ---
MSG_REGISTER = "REGISTER"        # Peer -> Servidor: Registrarse
MSG_REGISTER_ACK = "REGISTER_ACK"  # Servidor -> Peer: OK, aquí está tu ID y la lista
MSG_UNREGISTER = "UNREGISTER"      # Peer -> Servidor: Me voy
MSG_GET_PEERS = "GET_PEERS"        # (Opcional) Peer -> Servidor: Dame la lista
MSG_PEER_LIST_UPDATE = "PEER_LIST_UPDATE" # Servidor -> Peer: Alguien se unió/fue

MSG_CHAT = "CHAT"                # Peer -> Peer: Mensaje de chat
MSG_HEARTBEAT = "HEARTBEAT"      # Peer -> Servidor: Sigo vivo
MSG_ACK = "ACK"                  # (Opcional) Peer -> Peer: Recibí tu mensaje

# --- Mensajes para Tolerancia a Fallos (Gossip) ---
# Cuando un peer detecta que el servidor está caído:
MSG_SYNC_PEERS_REQUEST = "SYNC_PEERS_REQUEST" # Peer A -> Peer B: ¿A quién conoces?
MSG_SYNC_PEERS_RESPONSE = "SYNC_PEERS_RESPONSE" # Peer B -> Peer A: A esta gente

# --- Funciones de Utilidad ---

def create_message(msg_type: str, sender_id: str = "system", content: any = None, to: str = "ALL") -> bytes:
    """
    Crea un mensaje JSON estandarizado y lo codifica a bytes.
    """
    message = {
        "type": msg_type,
        "sender_id": sender_id,
        "to": to,
        "content": content,
    }
    # Añadimos un terminador de nueva línea para delimitar mensajes en el stream
    return (json.dumps(message) + '\n').encode('utf-8')

def parse_message(data: bytes) -> dict | None:
    """
    Intenta parsear un mensaje JSON desde bytes.
    """
    try:
        return json.loads(data.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        print(f"[Protocol] Error al decodificar: {data}")
        return None
