"""#### Servidor de descubrimiento - VERSION RED"""

import socket
import threading
import json
import time
from common.protocol import (
    create_message, parse_message, 
    MSG_REGISTER, MSG_REGISTER_ACK, MSG_HEARTBEAT, 
    MSG_PEER_LIST_UPDATE, MSG_UNREGISTER,
    MSG_RELAY_REQUEST, MSG_RELAY_MESSAGE
)

HOST = '0.0.0.0'  # ⭐ Escuchar en TODAS las interfaces
PORT = 9999
HEARTBEAT_TIMEOUT = 30

class DiscoveryServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        # { peer_id: (ip, port, username, last_heartbeat) }
        self.peers = {}
        self.peers_lock = threading.Lock()
        
        # { peer_id: socket }
        self.client_sockets = {}
        self.client_sockets_lock = threading.Lock()
        
        self.server_socket = None
        print(f"[Server] Inicializando en {self.host}:{self.port}")

    def start(self):
        """Inicia el servidor."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            print(f"[Server] ✅ Escuchando en {self.port}...")
            print(f"[Server] 🌐 Accesible desde la red local")
            
            # Mostrar IPs disponibles
            self._print_available_ips()

            # Monitor de heartbeats
            monitor_thread = threading.Thread(target=self.monitor_peers, daemon=True)
            monitor_thread.start()

            while True:
                conn, addr = self.server_socket.accept()
                print(f"[Server] 🔌 Nueva conexión desde {addr[0]}:{addr[1]}")
                handler_thread = threading.Thread(
                    target=self.handle_client, 
                    args=(conn, addr), 
                    daemon=True
                )
                handler_thread.start()

        except OSError as e:
            print(f"[Server] ❌ Error: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()

    def _print_available_ips(self):
        """Muestra las IPs donde el servidor está disponible."""
        import socket
        hostname = socket.gethostname()
        try:
            local_ip = socket.gethostbyname(hostname)
            print(f"[Server] 📍 IP Local: {local_ip}")
            print(f"[Server] 💡 Los peers deben conectarse a: {local_ip}:{self.port}")
        except:
            print(f"[Server] ⚠️ No se pudo detectar IP local")

    def handle_client(self, conn: socket.socket, addr: tuple):
        """Maneja la conexión de un único peer."""
        peer_id = None
        try:
            buffer = b""
            while True:
                data = conn.recv(1024)
                if not data:
                    break

                buffer += data

                while b'\n' in buffer:
                    message_data, buffer = buffer.split(b'\n', 1)
                    if not message_data:
                        continue

                    msg = parse_message(message_data)
                    if not msg:
                        continue

                    peer_id = msg.get("sender_id")

                    if msg['type'] == MSG_REGISTER:
                        # ⭐ CAMBIO IMPORTANTE: Usar la IP del contenido si está disponible
                        peer_ip = msg['content'].get('ip')
                        if not peer_ip:
                            # Fallback: usar la IP de la conexión
                            peer_ip = addr[0]
                            print(f"[Server] ⚠️ Peer no envió IP, usando IP de conexión: {peer_ip}")
                        
                        peer_id = self.register_peer(conn, (peer_ip, addr[1]), msg['content'])

                    elif msg['type'] == MSG_HEARTBEAT:
                        self.update_heartbeat(peer_id)

                    elif msg['type'] == MSG_UNREGISTER:
                        print(f"[Server] 👋 Peer {peer_id} se desregistró")
                        break

                    else:
                        print(f"[Server] ❓ Mensaje desconocido de {peer_id}: {msg['type']}")

        except (ConnectionResetError, BrokenPipeError):
            print(f"[Server] 🔌 Conexión perdida con {addr} (Peer: {peer_id})")
        except Exception as e:
            print(f"[Server] ❌ Error con {addr}: {e}")
        finally:
            if peer_id:
                self.unregister_peer(peer_id)
            conn.close()

    def register_peer(self, conn: socket.socket, addr: tuple, content: dict) -> str:
        """Registra un nuevo peer."""
        peer_ip = addr[0]  # Ya viene corregida del handle_client
        peer_listen_port = content.get('port')
        peer_username = content.get('username')

        peer_id = f"{peer_username}@{peer_ip}:{peer_listen_port}"

        peer_info = {
            "ip": peer_ip,
            "port": peer_listen_port,
            "username": peer_username,
        }

        print(f"[Server] ✅ Registrando: {peer_id}")

        with self.peers_lock:
            self.peers[peer_id] = (peer_ip, peer_listen_port, peer_username, time.time())

            peers_list_for_client = {
                pid: {"ip": p[0], "port": p[1], "username": p[2]}
                for pid, p in self.peers.items()
            }
            
            with self.client_sockets_lock:
                self.client_sockets[peer_id] = conn

        # Enviar ACK
        ack_msg = create_message(
            MSG_REGISTER_ACK,
            sender_id="server",
            to=peer_id,
            content={"peer_id": peer_id, "peer_list": peers_list_for_client}
        )
        conn.sendall(ack_msg)

        # Notificar a otros peers
        self.broadcast_peer_update(new_peer_id=peer_id, new_peer_info=peer_info)

        return peer_id

    def unregister_peer(self, peer_id: str):
        """Elimina un peer."""
        removed_peer_info = None
        with self.peers_lock:
            if peer_id in self.peers:
                removed_peer_info = self.peers.pop(peer_id)
                print(f"[Server] ❌ Peer eliminado: {peer_id}")
        
        with self.client_sockets_lock:
            if peer_id in self.client_sockets:
                client_conn = self.client_sockets.pop(peer_id)
                try:
                    client_conn.close()
                except Exception as e:
                    print(f"[Server] Error cerrando socket de {peer_id}: {e}")
        
        if removed_peer_info:
            self.broadcast_peer_update(removed_peer_id=peer_id)

    def broadcast_peer_update(self, new_peer_id: str = None, 
                             new_peer_info: dict = None, 
                             removed_peer_id: str = None):
        """Notifica cambios a todos los peers."""
        
        if not new_peer_id and not removed_peer_id:
            return

        print(f"[Broadcast] 📢 Notificando cambios...")

        content = {}
        if new_peer_id:
            content['new_peer'] = {new_peer_id: new_peer_info}
        if removed_peer_id:
            content['removed_peer'] = removed_peer_id

        update_msg = create_message(
            MSG_PEER_LIST_UPDATE,
            sender_id="server",
            content=content
        )

        sockets_to_notify = []
        with self.client_sockets_lock:
            sockets_to_notify = list(self.client_sockets.items())

        peers_failed = []

        for peer_id, conn in sockets_to_notify:
            if peer_id == new_peer_id:
                continue

            try:
                conn.sendall(update_msg)
            except (BrokenPipeError, ConnectionResetError, OSError) as e:
                print(f"[Broadcast] ❌ Error enviando a {peer_id}")
                peers_failed.append(peer_id)
            except Exception as e:
                print(f"[Broadcast] ❌ Error inesperado con {peer_id}: {e}")
                peers_failed.append(peer_id)

        if peers_failed:
            print(f"[Broadcast] 🧹 Limpiando {len(peers_failed)} peers fallidos")
            for peer_id in peers_failed:
                self.unregister_peer(peer_id)

    def update_heartbeat(self, peer_id: str):
        """Actualiza timestamp del heartbeat."""
        with self.peers_lock:
            if peer_id in self.peers:
                p = self.peers[peer_id]
                self.peers[peer_id] = (p[0], p[1], p[2], time.time())
            else:
                print(f"[Server] ⚠️ Heartbeat de peer desconocido: {peer_id}")

    def monitor_peers(self):
        """Monitor de peers inactivos."""
        print("[Monitor] ⏰ Monitor iniciado")
        while True:
            time.sleep(10)

            peers_to_remove = []
            now = time.time()

            with self.peers_lock:
                for peer_id, (ip, port, username, last_heartbeat) in self.peers.items():
                    if now - last_heartbeat > HEARTBEAT_TIMEOUT:
                        print(f"[Monitor] ⏰ Timeout: {peer_id}")
                        peers_to_remove.append(peer_id)

            for peer_id in peers_to_remove:
                self.unregister_peer(peer_id)
