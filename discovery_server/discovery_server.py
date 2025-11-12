"""#### Servidor de descubrimiento"""

import socket
import threading
import json
import time
from common.protocol import create_message, parse_message, MSG_REGISTER, MSG_REGISTER_ACK, MSG_HEARTBEAT, MSG_PEER_LIST_UPDATE, MSG_UNREGISTER

HOST = '0.0.0.0'
PORT = 9999
HEARTBEAT_TIMEOUT = 30  # Segundos para considerar a un peer desconectado

class DiscoveryServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        # Lista de peers: { peer_id: (ip, port, username, last_heartbeat) }
        self.peers = {}
        self.peers_lock = threading.Lock()
        
        # --- AÑADIR ESTO ---
        # Almacena los sockets de conexión de cada peer para poder enviarles updates
        # { peer_id: socket.socket }
        self.client_sockets = {}
        self.client_sockets_lock = threading.Lock()
        # --- FIN DE LO AÑADIDO ---
        
        self.server_socket = None
        print(f"[Server] Iniciando en {self.host}:{self.port}")

    def start(self):
        """Inicia el servidor y el monitor de heartbeats."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            print(f"[Server] Escuchando conexiones en {self.port}...")

            # Iniciar thread para monitorear heartbeats y peers caídos
            monitor_thread = threading.Thread(target=self.monitor_peers, daemon=True)
            monitor_thread.start()

            while True:
                conn, addr = self.server_socket.accept()
                # Cada cliente se maneja en su propio thread
                handler_thread = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True)
                handler_thread.start()

        except OSError as e:
            print(f"[Server] Error: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()

    def handle_client(self, conn: socket.socket, addr: tuple):
        """Maneja la conexión de un único peer."""
        print(f"[Server] Nueva conexión de {addr}")
        peer_id = None
        try:
            # Usamos un buffer para manejar mensajes que llegan juntos
            buffer = b""
            while True:
                data = conn.recv(1024)
                if not data:
                    break # Cliente cerró conexión

                buffer += data

                # Procesar todos los mensajes completos en el buffer
                while b'\n' in buffer:
                    message_data, buffer = buffer.split(b'\n', 1)
                    if not message_data:
                        continue

                    msg = parse_message(message_data)
                    if not msg:
                        continue

                    peer_id = msg.get("sender_id") # El ID que el peer *cree* que tiene

                    if msg['type'] == MSG_REGISTER:
                        # Peer se está registrando
                        peer_id = self.register_peer(conn, addr, msg['content'])

                    elif msg['type'] == MSG_HEARTBEAT:
                        self.update_heartbeat(peer_id)

                    elif msg['type'] == MSG_UNREGISTER:
                        print(f"[Server] Peer {peer_id} se desregistró.")
                        break # Termina el bucle y cierra la conexión

                    else:
                        print(f"[Server] Mensaje desconocido de {peer_id}: {msg['type']}")

        except (ConnectionResetError, BrokenPipeError):
            print(f"[Server] Conexión perdida con {addr} (Peer ID: {peer_id})")
        except Exception as e:
            print(f"[Server] Error manejando a {addr}: {e}")
        finally:
            if peer_id:
                self.unregister_peer(peer_id)
            conn.close()

    def register_peer(self, conn: socket.socket, addr: tuple, content: dict) -> str:
        """Registra un nuevo peer y notifica a los demás."""
        peer_ip = addr[0]
        peer_listen_port = content.get('port')
        peer_username = content.get('username')

        # Generar un ID único (en un caso real, usar UUID)
        peer_id = f"{peer_username}@{peer_ip}:{peer_listen_port}"

        peer_info = {
            "ip": peer_ip,
            "port": peer_listen_port,
            "username": peer_username,
        }

        print(f"[Server] Registrando peer: {peer_id}")

        with self.peers_lock:
            # Guardar información completa, incluyendo timestamp
            self.peers[peer_id] = (peer_ip, peer_listen_port, peer_username, time.time())

            # Crear una lista "limpia" de peers para enviar
            peers_list_for_client = {
                pid: {"ip": p[0], "port": p[1], "username": p[2]}
                for pid, p in self.peers.items()
            }
            # --- AÑADIR ESTO_nic ---
            # Guardar el socket del cliente para enviarle actualizaciones
            with self.client_sockets_lock:
                self.client_sockets[peer_id] = conn
            # --- FIN DE LO AÑADIDO_nic ---

        # Enviar ACK al nuevo peer con su ID y la lista de peers
        ack_msg = create_message(
            MSG_REGISTER_ACK,
            sender_id="server",
            to=peer_id,
            content={"peer_id": peer_id, "peer_list": peers_list_for_client}
        )
        conn.sendall(ack_msg)

        # Notificar a *todos los demás* peers sobre el nuevo integrante
        self.broadcast_peer_update(new_peer_id=peer_id, new_peer_info=peer_info)

        return peer_id

    def unregister_peer(self, peer_id: str):
        """Elimina un peer y notifica a los demás."""
        removed_peer_info = None
        with self.peers_lock:
            if peer_id in self.peers:
                removed_peer_info = self.peers.pop(peer_id)
                print(f"[Server] Peer {peer_id} eliminado.")
        # --- AÑADIR ESTO _Nic ---
        # Cerrar y eliminar el socket guardado para este peer
        with self.client_sockets_lock:
            if peer_id in self.client_sockets:
                client_conn = self.client_sockets.pop(peer_id)
                try:
                    # Cierra la conexión desde el lado del servidor
                    client_conn.close() 
                except Exception as e:
                    print(f"[Server] Error al cerrar socket de {peer_id}: {e}")
        # --- FIN DE LO AÑADIDO_nic ---
        if removed_peer_info:
            # Notificar a los peers restantes
            self.broadcast_peer_update(removed_peer_id=peer_id)

   
    def broadcast_peer_update(self, new_peer_id: str = None, new_peer_info: dict = None, removed_peer_id: str = None):
        """Envía la lista actualizada de peers a todos los peers activos."""
        
        if not new_peer_id and not removed_peer_id:
            return # Nada que hacer

        print(f"[Broadcast] Notificando a todos los peers...")

        # Crear el contenido del mensaje
        content = {}
        if new_peer_id:
            # { 'new_peer': { 'peer_id_nuevo': { 'ip': ..., 'port': ... } } }
            content['new_peer'] = {new_peer_id: new_peer_info}
        if removed_peer_id:
            content['removed_peer'] = removed_peer_id # 'peer_id_eliminado'

        # Crear el mensaje
        # Asumimos que MSG_PEER_LIST_UPDATE está definido en protocol.py
        update_msg = create_message(
            MSG_PEER_LIST_UPDATE,
            sender_id="server",
            content=content
        )

        # Hacemos una copia de la lista de sockets para no bloquear
        # la lista principal mientras enviamos mensajes
        sockets_to_notify = []
        with self.client_sockets_lock:
            sockets_to_notify = list(self.client_sockets.items())

        peers_failed = []

        for peer_id, conn in sockets_to_notify:
            # No enviar la notificación al peer que *acaba* de unirse
            # (ya recibió la lista completa en el ACK)
            if peer_id == new_peer_id:
                continue

            try:
                conn.sendall(update_msg)
            except (BrokenPipeError, ConnectionResetError, OSError) as e:
                print(f"[Broadcast] Error enviando a {peer_id}. Marcando para eliminar.")
                peers_failed.append(peer_id)
            except Exception as e:
                print(f"[Broadcast] Error inesperado con {peer_id}: {e}")
                peers_failed.append(peer_id)

        # Limpiar peers que fallaron (probablemente se desconectaron)
        if peers_failed:
            print(f"[Broadcast] Limpiando {len(peers_failed)} peers fallidos.")
            for peer_id in peers_failed:
                # Esta función se encarga de todo
                self.unregister_peer(peer_id)
    def update_heartbeat(self, peer_id: str):
        """Actualiza el timestamp del último heartbeat de un peer."""
        with self.peers_lock:
            if peer_id in self.peers:
                p = self.peers[peer_id]
                self.peers[peer_id] = (p[0], p[1], p[2], time.time())
                # print(f"[Server] Heartbeat de {peer_id}")
            else:
                print(f"[Server] Heartbeat de peer desconocido {peer_id}. Ignorando.")

    def monitor_peers(self):
        """Thread que corre periódicamente para limpiar peers inactivos."""
        print("[Monitor] Monitor de peers iniciado.")
        while True:
            time.sleep(10) # Revisar cada 10 segundos

            peers_to_remove = []
            now = time.time()

            with self.peers_lock:
                for peer_id, (ip, port, username, last_heartbeat) in self.peers.items():
                    if now - last_heartbeat > HEARTBEAT_TIMEOUT:
                        print(f"[Monitor] Peer {peer_id} ha superado el timeout. Eliminando.")
                        peers_to_remove.append(peer_id)

            # Eliminar fuera del lock de iteración
            for peer_id in peers_to_remove:
                self.unregister_peer(peer_id)
