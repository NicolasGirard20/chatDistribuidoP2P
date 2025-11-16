"""Definición del Protocolo - CON SOPORTE DE RELAY

Este módulo define los tipos de mensaje y utilidades para crear/parsear
mensajes JSON terminados en newline usados por el sistema P2P.
"""

import json

# --- Tipos de Mensajes Básicos ---
MSG_REGISTER = "REGISTER"
MSG_REGISTER_ACK = "REGISTER_ACK"
MSG_UNREGISTER = "UNREGISTER"
MSG_GET_PEERS = "GET_PEERS"
MSG_PEER_LIST_UPDATE = "PEER_LIST_UPDATE"
MSG_HEARTBEAT = "HEARTBEAT"
MSG_ACK = "ACK"

# --- Mensajes P2P ---
MSG_CHAT = "CHAT"

# --- Mensajes de Gossip ---
MSG_SYNC_PEERS_REQUEST = "SYNC_PEERS_REQUEST"
MSG_SYNC_PEERS_RESPONSE = "SYNC_PEERS_RESPONSE"

# --- ⭐ NUEVOS: Mensajes de RELAY ---
MSG_RELAY_REQUEST = "RELAY_REQUEST"   # Peer → Server: "Reenvía esto al peer X"
MSG_RELAY_MESSAGE = "RELAY_MESSAGE"   # Server → Peer: "Mensaje relayed de Y"
MSG_CONNECTION_TEST = "CONNECTION_TEST"  # Peer → Peer: "¿Me puedes alcanzar?"
MSG_CONNECTION_REPLY = "CONNECTION_REPLY"  # Peer → Peer: "Sí, te puedo alcanzar"

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
