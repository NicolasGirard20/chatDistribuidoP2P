
"""#### Nodo Peer (Cliente/Servidor)"""
import queue
import socket
import threading
import json
import time
import random
from common.protocol import (
    create_message, parse_message,
    MSG_REGISTER, MSG_REGISTER_ACK, MSG_HEARTBEAT, MSG_UNREGISTER, MSG_CHAT,
    MSG_SYNC_PEERS_REQUEST, MSG_SYNC_PEERS_RESPONSE, MSG_PEER_LIST_UPDATE
)

HEARTBEAT_INTERVAL = 10 # Enviar heartbeat cada 10 seg
GOSSIP_INTERVAL = 5 # Sincronizar con peers cada 5 seg (si el servidor cae)

class PeerNode:
    def __init__(self, username: str, listening_port: int, discovery_server_ip: str = '127.0.0.1', discovery_server_port: int = 9999):
        self.username = username
        self.listening_port = listening_port # Puerto donde este peer escucha
        self.peer_id = f"{username}@{socket.gethostbyname(socket.gethostname())}:{listening_port}"

        # Dirección del servidor de descubrimiento (configurable)
        self.discovery_server_ip = discovery_server_ip
        self.discovery_server_port = discovery_server_port

        # Lista de peers conocidos: { peer_id: {"ip": str, "port": int, "username": str} }
        self.peer_list = {}
        self.peer_list_lock = threading.Lock()

        self.discovery_server_status = "DOWN" # Empezamos asumiendo que está caído
        self.discovery_socket = None
        self.server_socket = None # Socket para escuchar a otros peers

        self.running = True
        self.incoming_messages = queue.Queue()
    def start(self):
        """Inicia todos los servicios del peer."""
        print(f"[Peer {self.peer_id}] Iniciando...")

        # 1. Iniciar el servidor P2P (para escuchar a otros peers)
        listener_thread = threading.Thread(target=self.start_p2p_listener, daemon=True)
        listener_thread.start()

        # 2. Conectar al servidor de descubrimiento
        discovery_thread = threading.Thread(target=self.connect_to_discovery, daemon=True)
        discovery_thread.start()

        # 3. Iniciar el protocolo de Gossip (si el servidor falla)
        # Esto implementa tu idea de "descargar conexiones"
        gossip_thread = threading.Thread(target=self.start_gossip_protocol, daemon=True)
        gossip_thread.start()
        """
        # 4. (Demo) Iniciar un bucle para enviar mensajes
        # En una app real, esto sería reemplazado por la UI (cli_interface.py)
        demo_sender_thread = threading.Thread(target=self.demo_message_sender, daemon=True)
        demo_sender_thread.start()

        print(f"[Peer {self.peer_id}] Listo. Escuchando en el puerto {self.listening_port}")
        # Mantener el thread principal vivo
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
        """
        print(f"[Peer {self.peer_id}] Hilos iniciados. Escuchando en el puerto {self.listening_port}")
    
    def stop(self):
        """Detiene el peer y notifica al servidor."""
        print(f"\n[Peer {self.peer_id}] Deteniendo...")
        self.running = False

        # Notificar al servidor de descubrimiento
        if self.discovery_socket and self.discovery_server_status == "UP":
            try:
                msg = create_message(MSG_UNREGISTER, sender_id=self.peer_id)
                self.discovery_socket.sendall(msg)
            except (BrokenPipeError, ConnectionResetError):
                pass # El servidor ya podría estar caído
            finally:
                self.discovery_socket.close()

        # Cerrar el socket de escucha P2P
        if self.server_socket:
            self.server_socket.close()

        print(f"[Peer {self.peer_id}] Desconectado.")

    # --- 1. Lógica del Servidor P2P ---

    def start_p2p_listener(self):
        """Inicia el socket que escucha conexiones de *otros peers*."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind(('0.0.0.0', self.listening_port))
            self.server_socket.listen(5)

            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    # Manejar cada conexión de peer en un thread separado
                    p2p_handler_thread = threading.Thread(target=self.handle_p2p_connection, args=(conn, addr), daemon=True)
                    p2p_handler_thread.start()
                except OSError:
                    if self.running:
                        print(f"[P2P Server] Error al aceptar conexión (Socket cerrado?)")
                    break # Salir del bucle si el socket se cerró

        except OSError as e:
            print(f"[P2P Server] Error al bindiar puerto {self.listening_port}: {e}")
            self.running = False
        finally:
            if self.server_socket:
                self.server_socket.close()

    def handle_p2p_connection(self, conn: socket.socket, addr: tuple):
        """Maneja un mensaje entrante de otro peer."""
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
                        #print(f"\n[Mensaje de {msg['sender_id']}]: {msg['content']}\n> ", end="")
                        msg_info = {
                        "sender": msg['sender_id'],
                        "content": msg['content']
                        }
                        self.incoming_messages.put(msg_info)
                    elif msg['type'] == MSG_SYNC_PEERS_REQUEST:
                        # Un peer nos pide nuestra lista (Gossip)
                        self.handle_sync_request(conn, msg)

                    elif msg['type'] == MSG_SYNC_PEERS_RESPONSE:
                        # Un peer nos responde con su lista (Gossip)
                        self.handle_sync_response(msg)

                    else:
                        print(f"[P2P] Mensaje P2P desconocido de {addr}: {msg['type']}")

        except (ConnectionResetError, BrokenPipeError):
            # print(f"[P2P] Conexión P2P perdida con {addr}")
            pass
        except Exception as e:
            print(f"[P2P] Error en conexión P2P con {addr}: {e}")
        finally:
            conn.close()

    # --- 2. Lógica del Cliente de Descubrimiento ---

    def connect_to_discovery(self):
        """Intenta conectarse y registrarse en el servidor de descubrimiento."""
        while self.running:
            try:
                self.discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.discovery_socket.connect((self.discovery_server_ip, self.discovery_server_port))
                print(f"[Discovery] Conectado a {self.discovery_server_ip}:{self.discovery_server_port}")

                # 1. Enviar registro
                reg_msg = create_message(
                    MSG_REGISTER,
                    sender_id=self.peer_id, # Enviamos el ID que *creemos* tener
                    content={"port": self.listening_port, "username": self.username}
                )
                self.discovery_socket.sendall(reg_msg)

                # 2. Esperar ACK y lista de peers
                response_data = self.discovery_socket.recv(4096) # Esperar una lista grande
                if not response_data:
                    raise ConnectionError("Servidor no envió ACK")

                # Asumimos que el ACK viene en un solo paquete por simplicidad
                ack_msg = parse_message(response_data.split(b'\n')[0])

                if ack_msg and ack_msg['type'] == MSG_REGISTER_ACK:
                    self.peer_id = ack_msg['content']['peer_id'] # Actualizar con el ID oficial
                    server_peer_list = ack_msg['content']['peer_list']
                    print(f"[Discovery] Registrado! ID Oficial: {self.peer_id}")
                    self.merge_peer_lists(server_peer_list)
                    self.discovery_server_status = "UP"

                    # 3. Iniciar bucle de Heartbeat
                    self.start_discovery_heartbeat()

                else:
                    print(f"[Discovery] Error de registro. Respuesta: {ack_msg}")
                    self.discovery_socket.close()

            except (ConnectionRefusedError, ConnectionResetError, ConnectionAbortedError, TimeoutError, ConnectionError) as e:
                print(f"[Discovery] Servidor caído o inalcanzable. ({e})")
                self.discovery_server_status = "DOWN"
                if self.discovery_socket:
                    self.discovery_socket.close()
                self.discovery_socket = None

            # Reintentar conexión cada 15 segundos
            time.sleep(15)

    def start_discovery_heartbeat(self):
        """
        Mantiene la conexión con el servidor, enviando heartbeats
        y escuchando actualizaciones de la lista de peers.
        """
        buffer = b""
        
        while self.running and self.discovery_server_status == "UP":
            try:
                if not self.discovery_socket:
                    raise ConnectionError("Socket de descubrimiento no existe")

                # 1. ENVIAR HEARTBEAT
                msg = create_message(MSG_HEARTBEAT, sender_id=self.peer_id)
                self.discovery_socket.sendall(msg)
                
                # 2. ESCUCHAR UPDATES (con timeout)
                # Ponemos el socket en modo "escucha" con un timeout 
                # igual al intervalo del heartbeat.
                self.discovery_socket.settimeout(HEARTBEAT_INTERVAL)
                
                try:
                    # El socket se bloqueará aquí hasta que reciba datos
                    # O hasta que pasen 10 seg (HEARTBEAT_INTERVAL)
                    data = self.discovery_socket.recv(4096)
                    
                    if not data:
                        # Servidor cerró la conexión
                        raise ConnectionError("Servidor cerró la conexión")
                    
                    buffer += data
                    
                    # Procesar todos los mensajes en el buffer
                    while b'\n' in buffer:
                        message_data, buffer = buffer.split(b'\n', 1)
                        if not message_data:
                            continue

                        update_msg = parse_message(message_data)
                        
                        if update_msg and update_msg['type'] == MSG_PEER_LIST_UPDATE:
                            print("[Discovery] ¡Actualización de peers recibida del servidor!")
                            content = update_msg.get('content', {})
                            
                            # Añadir nuevo peer
                            if 'new_peer' in content:
                                # content['new_peer'] es un dict: { peer_id: info }
                                self.merge_peer_lists(content['new_peer'])
                            
                            # Eliminar peer caído
                            if 'removed_peer' in content:
                                # content['removed_peer'] es un str: 'peer_id'
                                self.remove_dead_peer(content['removed_peer'])
                        
                        else:
                            # Puede ser un ACK duplicado o algo inesperado
                            print(f"[Discovery] Recibido mensaje no esperado del servidor: {update_msg.get('type')}")

                except socket.timeout:
                    # --- ESTO ES NORMAL ---
                    # Significa que no hubo updates en los últimos 10 seg.
                    # Simplemente continuamos al siguiente ciclo del while
                    # para enviar el próximo heartbeat.
                    continue 

            except (BrokenPipeError, ConnectionResetError, ConnectionError, OSError) as e:
                print(f"[Heartbeat] Error en conexión con servidor: {e}. Servidor caído.")
                self.discovery_server_status = "DOWN"
                if self.discovery_socket:
                    self.discovery_socket.close()
                self.discovery_socket = None
                # Romper este bucle. El bucle exterior en 
                # connect_to_discovery() se encargará de reconectar.
                break
            except Exception as e:
                print(f"[Heartbeat] Error inesperado: {e}")
                self.discovery_server_status = "DOWN"
                if self.discovery_socket:
                    self.discovery_socket.close()
                self.discovery_socket = None
                break

    # --- 3. Lógica de Tolerancia a Fallos (Gossip) ---

    def start_gossip_protocol(self):
        """
        Esta es la implementación de tu idea.
        Si el servidor de descubrimiento está caído, le preguntamos
        a otros peers por sus listas de conexiones.
        """
        print("[Gossip] Protocolo de Gossip iniciado. Esperando estado del servidor...")
        while self.running:
            # Esperar ANTES de ejecutar, para no hacerlo apenas arranca
            time.sleep(GOSSIP_INTERVAL) 
            
            if not self.running:
                break
            
            # Ya no comprobamos si el servidor está caído.
            # Siempre sincronizamos, para propagar cambios.
            print("[Gossip] Ejecutando ciclo de sincronización P2P programado.")

            result = self.get_random_peer() 
            if result: 
                target_peer_id, target_peer_info = result 
                try:
                    print(f"[Gossip] Sincronizando con {target_peer_info['username']}...") 
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(5.0)
                    s.connect((target_peer_info['ip'], target_peer_info['port'])) 
                    
                    # Pedirle su lista
                    msg = create_message(MSG_SYNC_PEERS_REQUEST, sender_id=self.peer_id)
                    s.sendall(msg)
                    
                    # (El resto de la lógica para recibir la respuesta 
                    # ya está en handle_p2p_connection, así que 
                    # esta conexión s.close() es correcta. 
                    # O puedes implementar la lógica de recepción aquí
                    # como en run_gossip_cycle)
                    
                    # Para ser consistentes, llamemos a la misma lógica
                    # del botón "Actualizar":
                    s.close() # Cerramos la conexión de arriba
                    self.run_gossip_cycle() # Reusamos la lógica completa
                    

                except (ConnectionRefusedError, TimeoutError):
                    print(f"[Gossip] Peer {target_peer_info['username']} no responde. Eliminando.") 
                    self.remove_dead_peer(target_peer_id) 
                except Exception as e:
                    print(f"[Gossip] Error al sincronizar con {target_peer_info.get('username')}: {e}")

    # Código Corregido (Devuelve un tuple)
    def get_random_peer(self) -> tuple[str, dict] | None:
        """Obtiene un (peer_id, peer_info) aleatorio, excluyéndose a sí mismo."""
        with self.peer_list_lock:
            # Filtrar nuestra propia ID
            other_peers = [
                (pid, p) for pid, p in self.peer_list.items()
                if pid != self.peer_id and p.get('port') != self.listening_port
            ]
            if not other_peers:
                return None
            
            # Devuelve (peer_id, peer_info)
            return random.choice(other_peers)

    def handle_sync_request(self, conn: socket.socket, msg: dict):
        """Un peer nos pide nuestra lista; se la enviamos."""
        # print(f"[Gossip] Recibida solicitud SYNC de {msg['sender_id']}")
        with self.peer_list_lock:
            # Creamos una copia para evitar problemas de concurrencia
            list_to_send = self.peer_list.copy()

        response_msg = create_message(
            MSG_SYNC_PEERS_RESPONSE,
            sender_id=self.peer_id,
            to=msg['sender_id'],
            content={"peer_list": list_to_send}
        )
        try:
            conn.sendall(response_msg)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def handle_sync_response(self, msg: dict):
        """Recibimos una lista de peers de otro peer; la fusionamos."""
        sender_id = msg['sender_id']
        new_list = msg['content']['peer_list']
        print(f"[Gossip] Recibida lista de peers de {sender_id}. Fusionando...")
        self.merge_peer_lists(new_list)

    def merge_peer_lists(self, new_list: dict):
        """Fusiona una lista de peers recibida con la nuestra."""
        with self.peer_list_lock:
            # Simplemente actualizamos. Una fusión más inteligente
            # podría usar timestamps para ver qué entrada es más nueva.
            count_before = len(self.peer_list)
            self.peer_list.update(new_list)
            count_after = len(self.peer_list)

            if count_after > count_before:
                print(f"[Peer List] Lista actualizada. Total peers: {count_after}")
                # print(self.peer_list)

    def remove_dead_peer(self, peer_id: str):
        """Elimina un peer de la lista si falla la conexión."""
        with self.peer_list_lock:
            if peer_id in self.peer_list:
                print(f"[P2P] Eliminando peer caído: {peer_id}")
                del self.peer_list[peer_id]

    # --- 4. Lógica de Envío de Mensajes ---

    def send_chat_message(self, target_peer_id: str, message_content: str):
        """Envía un mensaje de chat directo a un peer específico."""
        peer_info = None
        with self.peer_list_lock:
            peer_info = self.peer_list.get(target_peer_id)

        if not peer_info:
            print(f"[Chat] Error: Peer {target_peer_id} desconocido.")
            return

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
            print(f"[Chat] Mensaje enviado a {target_peer_id}")

        except (ConnectionRefusedError, TimeoutError):
            print(f"[Chat] Error: No se pudo conectar con {target_peer_id}. Marcando como caído.")
            self.remove_dead_peer(target_peer_id)
        except Exception as e:
            print(f"[Chat] Error enviando a {target_peer_id}: {e}")

    def broadcast_chat_message(self, message_content: str):
        """Envía un mensaje a todos los peers conocidos."""
        print(f"[Chat] Enviando broadcast: {message_content}")
        with self.peer_list_lock:
            # Copiar la lista para evitar problemas si se modifica durante la iteración
            all_peers_ids = list(self.peer_list.keys())

        for peer_id in all_peers_ids:
            if peer_id == self.peer_id:
                continue # No enviarse a sí mismo

            # Usar threading para no bloquear el broadcast si un peer es lento
            threading.Thread(
                target=self.send_chat_message,
                args=(peer_id, message_content),
                daemon=True
            ).start()

    def demo_message_sender(self):
        """Función de demostración que envía un broadcast cada 20 seg."""
        time.sleep(10) # Esperar a registrarse
        count = 1
        while self.running:
            msg = f"Mensaje de broadcast #{count} desde {self.username}"
            self.broadcast_chat_message(msg)
            count += 1
            time.sleep(20)

    # --- NUEVA FUNCIÓN PARA EL BOTÓN DE ACTUALIZAR ---
    def run_gossip_cycle(self):
        """
        Ejecuta un ciclo de sincronización Gossip con un peer aleatorio.
        Esto es para ser llamado manualmente (ej. desde la UI).
        """
        print("[Gossip] Ejecutando ciclo de Gossip manual.")
        
        result = self.get_random_peer()
        if not result:
            print("[Gossip] No hay otros peers con quien sincronizar.")
            return

        target_peer_id, target_peer_info = result

        try:
            print(f"[Gossip] Sincronizando con {target_peer_info['username']}...")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5.0)
            s.connect((target_peer_info['ip'], target_peer_info['port']))

            # Pedirle su lista
            msg = create_message(MSG_SYNC_PEERS_REQUEST, sender_id=self.peer_id)
            s.sendall(msg)

            # Esperar la respuesta aquí mismo para forzar la actualización de la UI
            buffer = b""
            data = s.recv(4096) # Asumir < 4k
            s.close()
            if not data:
                raise ConnectionError("No data received from peer")
            
            buffer += data

            if b'\n' in buffer:
                response_data, _ = buffer.split(b'\n', 1)
                response_msg = parse_message(response_data)
                if response_msg and response_msg['type'] == MSG_SYNC_PEERS_RESPONSE:
                    self.handle_sync_response(response_msg)
                    print("[Gossip] Sincronización manual completada.")
                    return
            
            print("[Gossip] Respuesta de sincronización inválida.")

        except (ConnectionRefusedError, TimeoutError, ConnectionError):
            print(f"[Gossip] Peer {target_peer_info['username']} no responde. Eliminando.")
            self.remove_dead_peer(target_peer_id)
        except Exception as e:
            print(f"[Gossip] Error al sincronizar con {target_peer_info.get('username')}: {e}")