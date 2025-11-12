
"""#### Lanzador del Servidor"""

import os
import sys

# ensure project root is on sys.path so discovery_server package can be imported reliably
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from discovery_server.discovery_server import DiscoveryServer

# Configuración
HOST = '0.0.0.0'
PORT = 9999

if __name__ == "__main__":
    print("Iniciando Servidor de Descubrimiento...")
    server = DiscoveryServer(HOST, PORT)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[Server] Cerrando servidor.")