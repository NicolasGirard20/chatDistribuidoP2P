"""#### Lanzador del Peer"""

import sys
import random
import os  # <-- Asegúrate de que este import esté (para el sys.path)

# --- INICIO DE CORRECCIÓN DE IMPORTS (la mencioné antes) ---
# Asegúrate de que la raíz del proyecto esté en el path
# para que 'from peer.peer_node' y 'from common.protocol' funcionen.
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
# --- FIN DE CORRECCIÓN DE IMPORTS ---

from peer.peer_node import PeerNode

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Usar argumentos de línea de comandos si se proveen
        # Uso: python run_peer.py <username> <puerto_de_escucha> [<discovery_ip> <discovery_port>]
        username = sys.argv[1]
        try:
            port = int(sys.argv[2])
        except (IndexError, ValueError):
            print("Uso: python run_peer.py <username> <puerto_de_escucha> [<discovery_ip> <discovery_port>]")
            sys.exit(1)

        # Opcional: IP y puerto del servidor de descubrimiento :)
        try:
            discovery_ip = sys.argv[3]
        except IndexError:
            discovery_ip = '127.0.0.1'

        try:
            discovery_port = int(sys.argv[4])
        except (IndexError, ValueError):
            discovery_port = 9999
    else:
        # Generar un peer aleatorio para pruebas fáciles
        username = f"User_{random.randint(100, 999)}"
        port = random.randint(10000, 11000)
        print(f"Iniciando peer con datos aleatorios: {username} en puerto {port}")
        print("Puedes especificar: python run_peer.py <username> <puerto_de_escucha>")
        
        # --- 🐛 ERROR #2 CORREGIDO ---
        # Estas variables también deben definirse en el 'else'
        discovery_ip = '127.0.0.1'
        discovery_port = 9999
        
    # --- 🐛 ERROR #1 CORREGIDO ---
    # La creación del peer y el inicio deben estar AFUERA del 'else'
    # para que se ejecuten en CUALQUIERA de los dos casos (con o sin args).
    peer = PeerNode(username=username, listening_port=port, discovery_server_ip=discovery_ip, discovery_server_port=discovery_port)
    peer.start()