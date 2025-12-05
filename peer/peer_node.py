"""#### Nodo Peer - CON RELAY AUTOMÁTICO"""
import queue
import socket
import threading
import json
import time
import random
from common.protocol import (
    create_message, parse_message,
    MSG_REGISTER, MSG_REGISTER_ACK, MSG_HEARTBEAT, MSG_UNREGISTER, MSG_CHAT,
    MSG_SYNC_PEERS_REQUEST, MSG_SYNC_PEERS_RESPONSE, MSG_PEER_LIST_UPDATE,
    MSG_RELAY_REQUEST, MSG_RELAY_MESSAGE, MSG_CONNECTION_TEST, MSG_CONNECTION_REPLY
)

HEARTBEAT_INTERVAL = 10
GOSSIP_INTERVAL = 5
CONNECTION_TEST_TIMEOUT = 3  # Segundos para probar conexión directa

class PeerNode:
    def __init__(self, username: str, listening_port: int, 
                 discovery_server_ip: str = '127.0.0.1', 
                 discovery_server_port: int = 9999,
                 public_ip: str = None):
        self.username = username
        self.listening_port = listening_port
        
        if public_ip:
            self.public_ip = public_ip
        else:
            self.public_ip = self._get_local_ip()
        
        self.peer_id = f"{username}@{self.public_ip}:{listening_port}"
        self.discovery_server_ip = discovery_server_ip
        self.discovery_server_port = discovery_server_port

        self.peer_list = {}
        self.peer_list_lock = threading.Lock()
        
        # ⭐ NUEVO: Caché de conectividad
        # { peer_id: "direct" | "relay" | "unknown" }
        self.connectivity_cache = {}
        self.connectivity_lock = threading.Lock()

        self.discovery_server_status = "DOWN"
        self.discovery_socket = None
        self.server_socket = None

        self.running = True
        self.incoming_messages = queue.Queue()
        
        print(f"[Peer] Inicializando: {self.peer_id}")
        print(f"[Peer] IP detectada: {self.public_ip}")

    def _get_local_ip(self) -> str:
        """Detecta la IP local del peer."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            print("[Peer] ⚠️ No se pudo detectar IP. Usando 127.0.0.1")
            return "127.0.0.1"

    def start(self):
        """Inicia todos los servicios del peer."""
        print(f"[Peer {self.peer_id}] Iniciando...")

        listener_thread = threading.Thread(target=self.start_p2p_listener, daemon=True)
        listener_thread.start()

        discovery_thread = threading.Thread(target=self.connect_to_discovery, daemon=True)
        discovery_thread.start()

        gossip_thread = threading.Thread(target=self.start_gossip_protocol, daemon=True)
        gossip_thread.start()

        print(f"[Peer {self.peer_id}] Hilos iniciados. Escuchando en {self.public_ip}:{self.listening_port}")
    
    def stop(self):
        """Detiene el peer."""
        print(f"\n[Peer {self.peer_id}] Deteniendo...")
        self.running = False

        if self.discovery_socket and self.discovery_server_status == "UP":
            try:
                msg = create_message(MSG_UNREGISTER, sender_id=self.peer_id)
                self.discovery_socket.sendall(msg)
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                self.discovery_socket.close()

        if self.server_socket:
            self.server_socket.close()

        print(f"[Peer {self.peer_id}] Desconectado.")

    # --- Servidor P2P ---

    def start_p2p_listener(self):
        """Escucha conexiones de otros peers."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind(('0.0.0.0', self.listening_port))
            self.server_socket.listen(5)
            print(f"[P2P Server] Escuchando en 0.0.0.0:{self.listening_port}")

            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    print(f"[P2P Server] Conexión de {addr}")
                    p2p_handler_thread = threading.Thread(
                        target=self.handle_p2p_connection, 
                        args=(conn, addr), 
                        daemon=True
                    )
                    p2p_handler_thread.start()
                except OSError:
                    if self.running:
                        print(f"[P2P Server] Error al aceptar conexión")
                    break

        except OSError as e:
            print(f"[P2P Server] ❌ Error en puerto {self.listening_port}: {e}")
            self.running = False
        finally:
            if self.server_socket:
                self.server_socket.close()

    def handle_p2p_connection(self, conn: socket.socket, addr: tuple):
        """Maneja mensajes entrantes de peers."""
        try:
            buffer = b""
            while self.running:
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

                    if msg['type'] == MSG_CHAT:
                        print(f"✉️ [Chat] Mensaje de {msg['sender_id']}: {msg['content']}")
                        msg_info = {
                            "sender": msg['sender_id'],
                            "content": msg['content']
                        }
                        self.incoming_messages.put(msg_info)
                        
                    elif msg['type'] == MSG_CONNECTION_TEST:
                        # ⭐ NUEVO: Responder test de conectividad
                        print(f"[Connectivity] Test de {msg['sender_id']}")
                        reply = create_message(
                            MSG_CONNECTION_REPLY,
                            sender_id=self.peer_id,
                            to=msg['sender_id']
                        )
                        try:
                            conn.sendall(reply)
                        except:
                            pass
                        
                    elif msg['type'] == MSG_SYNC_PEERS_REQUEST:
                        self.handle_sync_request(conn, msg)

                    elif msg['type'] == MSG_SYNC_PEERS_RESPONSE:
                        self.handle_sync_response(msg)

        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            print(f"[P2P] Error con {addr}: {e}")
        finally:
            conn.close()

    # --- Cliente de Descubrimiento ---

    def connect_to_discovery(self):
        """Conecta al servidor de descubrimiento."""
        while self.running:
            try:
                print(f"[Discovery] Conectando a {self.discovery_server_ip}:{self.discovery_server_port}...")
                self.discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.discovery_socket.settimeout(10)
                self.discovery_socket.connect((self.discovery_server_ip, self.discovery_server_port))
                print(f"[Discovery] ✅ Conectado!")

                reg_msg = create_message(
                    MSG_REGISTER,
                    sender_id=self.peer_id,
                    content={
                        "port": self.listening_port, 
                        "username": self.username,
                        "ip": self.public_ip
                    }
                )
                self.discovery_socket.sendall(reg_msg)

                response_data = self.discovery_socket.recv(4096)
                if not response_data:
                    raise ConnectionError("Servidor no envió ACK")

                ack_msg = parse_message(response_data.split(b'\n')[0])

                if ack_msg and ack_msg['type'] == MSG_REGISTER_ACK:
                    self.peer_id = ack_msg['content']['peer_id']
                    server_peer_list = ack_msg['content']['peer_list']
                    print(f"[Discovery] ✅ Registrado: {self.peer_id}")
                    print(f"[Discovery] Peers conocidos: {len(server_peer_list)}")
                    self.merge_peer_lists(server_peer_list)
                    self.discovery_server_status = "UP"

                    self.start_discovery_heartbeat()

                else:
                    print(f"[Discovery] ❌ Error de registro")
                    self.discovery_socket.close()

            except (ConnectionRefusedError, ConnectionResetError, TimeoutError, ConnectionError) as e:
                print(f"[Discovery] ❌ Servidor inalcanzable: {e}")
                self.discovery_server_status = "DOWN"
                if self.discovery_socket:
                    self.discovery_socket.close()
                self.discovery_socket = None

            time.sleep(15)

    def start_discovery_heartbeat(self):
        """Mantiene conexión con el servidor."""
        buffer = b""
        
        while self.running and self.discovery_server_status == "UP":
            try:
                if not self.discovery_socket:
                    raise ConnectionError("Socket no existe")

                msg = create_message(MSG_HEARTBEAT, sender_id=self.peer_id)
                self.discovery_socket.sendall(msg)
                
                self.discovery_socket.settimeout(HEARTBEAT_INTERVAL)
                
                try:
                    data = self.discovery_socket.recv(4096)
                    
                    if not data:
                        raise ConnectionError("Servidor cerró conexión")
                    
                    buffer += data
                    
                    while b'\n' in buffer:
                        message_data, buffer = buffer.split(b'\n', 1)
                        if not message_data:
                            continue

                        update_msg = parse_message(message_data)
                        
                        if update_msg:
                            if update_msg['type'] == MSG_PEER_LIST_UPDATE:
                                print("[Discovery] 📥 Actualización de peers")
                                content = update_msg.get('content', {})
                                
                                if 'new_peer' in content:
                                    self.merge_peer_lists(content['new_peer'])
                                
                                if 'removed_peer' in content:
                                    self.remove_dead_peer(content['removed_peer'])
                            
                            elif update_msg['type'] == MSG_RELAY_MESSAGE:
                                # ⭐ NUEVO: Mensaje relayed desde el servidor
                                print(f"✉️ [Relay] Mensaje relayed recibido")
                                relay_content = update_msg.get('content', {})
                                msg_info = {
                                    "sender": relay_content.get('original_sender'),
                                    "content": relay_content.get('message')
                                }
                                self.incoming_messages.put(msg_info)

                except socket.timeout:
                    continue

            except (BrokenPipeError, ConnectionResetError, ConnectionError, OSError) as e:
                print(f"[Heartbeat] ❌ Conexión perdida: {e}")
                self.discovery_server_status = "DOWN"
                if self.discovery_socket:
                    self.discovery_socket.close()
                self.discovery_socket = None
                break

    # --- ⭐ NUEVAS FUNCIONES: Test de Conectividad ---

    def test_peer_connectivity(self, peer_id: str, peer_info: dict) -> str:
        """
        Prueba si podemos conectarnos directamente a un peer.
        Retorna: "direct", "relay", o "failed"
        """
        # Verificar caché primero
        with self.connectivity_lock:
            if peer_id in self.connectivity_cache:
                cached = self.connectivity_cache[peer_id]
                # Cache válido por 5 minutos
                return cached
        
        print(f"[Connectivity] Probando conexión directa con {peer_info.get('username')}...")
        
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(CONNECTION_TEST_TIMEOUT)
            s.connect((peer_info['ip'], peer_info['port']))
            
            # Enviar test
            test_msg = create_message(
                MSG_CONNECTION_TEST,
                sender_id=self.peer_id,
                to=peer_id
            )
            s.sendall(test_msg)
            
            # Esperar respuesta
            data = s.recv(1024)
            s.close()
            
            if data:
                reply = parse_message(data.split(b'\n')[0])
                if reply and reply['type'] == MSG_CONNECTION_REPLY:
                    print(f"[Connectivity] ✅ Conexión directa OK con {peer_info.get('username')}")
                    with self.connectivity_lock:
                        self.connectivity_cache[peer_id] = "direct"
                    return "direct"
            
            # No hay respuesta válida
            print(f"[Connectivity] ⚠️ Respuesta inválida de {peer_info.get('username')}")
            with self.connectivity_lock:
                self.connectivity_cache[peer_id] = "relay"
            return "relay"
            
        except (ConnectionRefusedError, TimeoutError, OSError) as e:
            print(f"[Connectivity] ❌ No se puede alcanzar directamente a {peer_info.get('username')}: {e}")
            with self.connectivity_lock:
                self.connectivity_cache[peer_id] = "relay"
            return "relay"

    # --- Envío de Mensajes (Mejorado) ---

    def send_chat_message(self, target_peer_id: str, message_content: str):
        """Envía mensaje (directo o via relay)."""
        peer_info = None
        with self.peer_list_lock:
            peer_info = self.peer_list.get(target_peer_id)

        if not peer_info:
            print(f"[Chat] ❌ Peer {target_peer_id} desconocido")
            return

        # ⭐ PROBAR CONECTIVIDAD
        connectivity = self.test_peer_connectivity(target_peer_id, peer_info)
        
        if connectivity == "direct":
            # Envío directo P2P
            self._send_direct_message(target_peer_id, peer_info, message_content)
        else:
            # Envío via relay
            self._send_relay_message(target_peer_id, message_content)

    def _send_direct_message(self, target_peer_id: str, peer_info: dict, message_content: str):
        """Envía mensaje directo P2P."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5.0)
            s.connect((peer_info['ip'], peer_info['port']))

            msg = create_message(
                MSG_CHAT,
                sender_id=self.peer_id,
                to=target_peer_id,
                content=message_content
            )
            s.sendall(msg)
            s.close()
            print(f"[Chat] ✅ Mensaje directo enviado a {peer_info.get('username')}")

        except Exception as e:
            print(f"[Chat] ❌ Error directo, intentando relay: {e}")
            # Fallback a relay
            with self.connectivity_lock:
                self.connectivity_cache[target_peer_id] = "relay"
            self._send_relay_message(target_peer_id, message_content)

    def _send_relay_message(self, target_peer_id: str, message_content: str):
        """Envía mensaje via servidor relay."""
        if self.discovery_server_status != "UP":
            print(f"[Chat] ❌ No se puede enviar: servidor caído y peer inalcanzable")
            return
        
        print(f"[Chat] 📡 Enviando via relay a {target_peer_id}")
        
        try:
            relay_msg = create_message(
                MSG_RELAY_REQUEST,
                sender_id=self.peer_id,
                to=target_peer_id,
                content={
                    "target_peer_id": target_peer_id,
                    "message": message_content
                }
            )
            self.discovery_socket.sendall(relay_msg)
            print(f"[Chat] ✅ Mensaje relay enviado")
            
        except Exception as e:
            print(f"[Chat] ❌ Error al enviar relay: {e}")

    def broadcast_chat_message(self, message_content: str):
        """Envía mensaje a todos los peers."""
        print(f"[Chat] 📤 Broadcasting: {message_content}")
        with self.peer_list_lock:
            all_peers_ids = list(self.peer_list.keys())

        for peer_id in all_peers_ids:
            if peer_id == self.peer_id:
                continue

            threading.Thread(
                target=self.send_chat_message,
                args=(peer_id, message_content),
                daemon=True
            ).start()

    # --- Gossip Protocol ---

    def start_gossip_protocol(self):
        """Sincronización P2P."""
        print("[Gossip] Protocolo iniciado")
        while self.running:
            time.sleep(GOSSIP_INTERVAL)
            
            if not self.running:
                break
            
            result = self.get_random_peer()
            if result:
                target_peer_id, target_peer_info = result
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(5.0)
                    s.connect((target_peer_info['ip'], target_peer_info['port']))
                    
                    msg = create_message(MSG_SYNC_PEERS_REQUEST, sender_id=self.peer_id)
                    s.sendall(msg)
                    s.close()

                except (ConnectionRefusedError, TimeoutError):
                    self.remove_dead_peer(target_peer_id)
                except Exception:
                    pass

    def get_random_peer(self) -> tuple[str, dict] | None:
        """Obtiene peer aleatorio."""
        with self.peer_list_lock:
            other_peers = [
                (pid, p) for pid, p in self.peer_list.items()
                if pid != self.peer_id
            ]
            if not other_peers:
                return None
            return random.choice(other_peers)

    def handle_sync_request(self, conn: socket.socket, msg: dict):
        """Responde sincronización."""
        with self.peer_list_lock:
            list_to_send = self.peer_list.copy()

        response_msg = create_message(
            MSG_SYNC_PEERS_RESPONSE,
            sender_id=self.peer_id,
            to=msg['sender_id'],
            content={"peer_list": list_to_send}
        )
        try:
            conn.sendall(response_msg)
        except:
            pass

    def handle_sync_response(self, msg: dict):
        """Procesa respuesta de sync."""
        new_list = msg['content']['peer_list']
        self.merge_peer_lists(new_list)

    def merge_peer_lists(self, new_list: dict):
        """Fusiona listas de peers."""
        with self.peer_list_lock:
            count_before = len(self.peer_list)
            self.peer_list.update(new_list)
            count_after = len(self.peer_list)

            if count_after > count_before:
                print(f"[Peer List] ✅ Actualizada. Total: {count_after} peers")

    def remove_dead_peer(self, peer_id: str):
        """Elimina peer caído."""
        with self.peer_list_lock:
            if peer_id in self.peer_list:
                print(f"[P2P] ❌ Eliminando: {peer_id}")
                del self.peer_list[peer_id]
        
        # Limpiar caché de conectividad
        with self.connectivity_lock:
            if peer_id in self.connectivity_cache:
                del self.connectivity_cache[peer_id]

    def run_gossip_cycle(self):
        """Ciclo manual de gossip."""
        result = self.get_random_peer()
        if not result:
            return

        target_peer_id, target_peer_info = result

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5.0)
            s.connect((target_peer_info['ip'], target_peer_info['port']))

            msg = create_message(MSG_SYNC_PEERS_REQUEST, sender_id=self.peer_id)
            s.sendall(msg)

            buffer = b""
            data = s.recv(4096)
            s.close()
            
            if data:
                buffer += data
                if b'\n' in buffer:
                    response_data, _ = buffer.split(b'\n', 1)
                    response_msg = parse_message(response_data)
                    if response_msg and response_msg['type'] == MSG_SYNC_PEERS_RESPONSE:
                        self.handle_sync_response(response_msg)

        except:
            self.remove_dead_peer(target_peer_id)
