import streamlit as st
import sys
import os
import random
import time
import queue

# Añadir el path para que encuentre los módulos (common, peer)
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from peer.peer_node import PeerNode

# --- Configuración de la Página ---
st.set_page_config(page_title="Chat P2P", layout="wide")

# Inicializar el estado de la sesión
if 'peer' not in st.session_state:
    st.session_state.peer = None
    st.session_state.messages = []
    st.session_state.logged_in = False
    st.session_state.server_ip = "127.0.0.1" # Default para pruebas locales

# --- 1. Pantalla de Conexión (Login) ---
if not st.session_state.logged_in:
    st.title("Conectarse al Chat P2P")
    
    # Obtener IP del servidor (para pruebas en red local)
    # Reemplaza con la IP de tu servidor si no es localhost
    st.session_state.server_ip = st.text_input("IP del Servidor de Descubrimiento", st.session_state.server_ip)
    
    # Formulario de conexión
    with st.form("login_form"):
        username = st.text_input("Tu Nombre de Usuario", f"User_{random.randint(100, 999)}")
        port = st.number_input("Tu Puerto de Escucha", min_value=1024, max_value=49151, value=random.randint(10000, 11000))
        submitted = st.form_submit_button("Conectar")

        if submitted:
            if not username or not port or not st.session_state.server_ip:
                st.error("Por favor, completa todos los campos.")
            else:
                with st.spinner("Iniciando y conectando al servidor..."):
                    try:
                        # Crear e iniciar el peer
                        peer = PeerNode(
                            username=username,
                            listening_port=port,
                            discovery_server_ip=st.session_state.server_ip,
                            discovery_server_port=9999
                        )
                        peer.start() # Inicia los hilos (ahora no bloquea)
                        
                        # Guardar en el estado de la sesión
                        st.session_state.peer = peer
                        st.session_state.messages = []
                        st.session_state.logged_in = True
                        st.success(f"¡Conectado como {peer.peer_id}!")
                        time.sleep(1)
                        st.rerun() # Recargar la página para ir al chat
                    
                    except Exception as e:
                        st.error(f"Error al iniciar el peer: {e}")
                        st.error("Asegúrate de que 'run_server.py' esté corriendo.")

# --- 2. Interfaz de Chat (Logueado) ---
else:
    peer: PeerNode = st.session_state.peer
    
    st.title(f"Chat P2P - Conectado como: `{peer.username}`")

    # --- Columna de Peers ---
    with st.sidebar:
        st.header("Peers Conectados")
        if st.button("Actualizar Lista"):
           # SOLUCIÓN 2: Forzar un ciclo de Gossip
            with st.spinner("Sincronizando con la red..."):
                peer.run_gossip_cycle()
            st.rerun() # Recargar la UI
        
        with peer.peer_list_lock:
            if not peer.peer_list:
                st.write("Nadie conectado (aún).")
            else:
                # Mostrar peers (excluyéndose a sí mismo)
                for peer_id, info in peer.peer_list.items():
                    if peer_id != peer.peer_id:
                        st.success(f"**{info['username']}** (`{info['ip']}:{info['port']}`)")

    # --- Columna de Chat ---
    chat_container = st.container()

    # Revisar si hay mensajes nuevos en la cola P2P
    try:
        new_msg = peer.incoming_messages.get_nowait()
        
        # SOLUCIÓN 3: Buscar el username en la peer_list
        sender_id = new_msg['sender']
        sender_username = "Desconocido" # Default
        with peer.peer_list_lock:
            if sender_id in peer.peer_list:
                # Buscar el nombre en la lista
                sender_username = peer.peer_list[sender_id].get('username', sender_id)
            elif sender_id == peer.peer_id:
                # Por si acaso, aunque no debería pasar en broadcast
                sender_username = peer.username 

        st.session_state.messages.append({
            "role": "assistant", 
            "content": f"**{sender_username}**: {new_msg['content']}"
        })
        # Al agregar un mensaje, Streamlit se refresca solo, 
        # pero un rerun puede ser necesario si hay mucha actividad.
        # st.rerun() 
        
    except queue.Empty:
        pass # No hay mensajes nuevos

    # Mostrar historial de mensajes
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # Input de chat (en la parte inferior)
    if prompt := st.chat_input("Escribe tu mensaje... (se enviará a todos)"):
        # SOLUCIÓN 3 (parte de envío):
        # 1. Formatear y añadir el mensaje a nuestra propia UI
        formatted_content = f"**{peer.username} (Tú)**: {prompt}"
        st.session_state.messages.append({"role": "user", "content": formatted_content})

        # 2. Enviar el mensaje a la red P2P (broadcast)
        try:
            peer.broadcast_chat_message(prompt)
        except Exception as e:
            st.error(f"Error al enviar mensaje: {e}")

        # 3. Recargar la UI para mostrar el mensaje enviado
        st.rerun()