import streamlit as st
import sys
import os
import random
import time
import queue
import threading

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
    st.session_state.server_ip = "127.0.0.1"
    st.session_state.auto_refresh = True

# --- 1. Pantalla de Conexión (Login) ---
if not st.session_state.logged_in:
    st.title("🌐 Conectarse al Chat P2P")
    
    st.info("💡 **Tip**: Abre múltiples ventanas de navegador para simular varios peers")
    
    st.session_state.server_ip = st.text_input(
        "IP del Servidor de Descubrimiento", 
        st.session_state.server_ip
    )
    
    # Formulario de conexión
    with st.form("login_form"):
        username = st.text_input(
            "Tu Nombre de Usuario",
            placeholder=f"Ejemplo: User_{random.randint(100, 999)}",
            key="username_input"
        )
        
        # El puerto se genera automáticamente (no se muestra al usuario)
        # Generamos un puerto aleatorio cada vez que se carga la página
        if 'temp_port' not in st.session_state:
            st.session_state.temp_port = random.randint(10000, 11000)
        
        port = st.session_state.temp_port
        
        # Mostrar el puerto que se usará (solo informativo)
        st.caption(f"🔌 Puerto asignado automáticamente: **{port}**")
        
        submitted = st.form_submit_button("🚀 Conectar")

        if submitted:
            # Eliminar espacios en blanco al inicio y final
            username = username.strip()
            
            if not username or not st.session_state.server_ip:
                st.error("❌ Por favor, ingresa tu nombre de usuario.")
            else:
                with st.spinner("Iniciando y conectando al servidor..."):
                    try:
                        peer = PeerNode(
                            username=username,
                            listening_port=port,
                            discovery_server_ip=st.session_state.server_ip,
                            discovery_server_port=9999
                        )
                        peer.start()
                        
                        # Esperar registro
                        max_wait = 10
                        wait_time = 0
                        while peer.discovery_server_status != "UP" and wait_time < max_wait:
                            time.sleep(0.5)
                            wait_time += 0.5
                        
                        if peer.discovery_server_status != "UP":
                            st.error("⚠️ No se pudo conectar al servidor. ¿Está corriendo 'run_server.py'?")
                            peer.stop()
                        else:
                            st.session_state.peer = peer
                            st.session_state.messages = []
                            st.session_state.logged_in = True
                            # Limpiar el puerto temporal
                            del st.session_state.temp_port
                            st.success(f"✅ ¡Conectado como {peer.username}!")
                            time.sleep(1)
                            st.rerun()
                    
                    except Exception as e:
                        st.error(f"❌ Error al iniciar el peer: {e}")

# --- 2. Interfaz de Chat (Logueado) ---
else:
    peer: PeerNode = st.session_state.peer
    
    st.title(f"💬 Chat P2P - `{peer.username}`")
    
    # --- Barra Superior ---
    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
    
    with col1:
        if peer.discovery_server_status == "UP":
            st.success("🟢 Servidor Online")
        else:
            st.warning("🟡 Modo P2P")
    
    with col2:
        with peer.peer_list_lock:
            peer_count = len([p for p in peer.peer_list.keys() if p != peer.peer_id])
        st.info(f"👥 {peer_count} peers")
    
    with col3:
        # Toggle auto-refresh
        auto_refresh = st.checkbox("🔄 Auto", value=st.session_state.auto_refresh, key="auto_refresh_toggle")
        st.session_state.auto_refresh = auto_refresh
    
    with col4:
        if st.button("🚪", help="Desconectar"):
            peer.stop()
            st.session_state.logged_in = False
            st.session_state.peer = None
            st.rerun()

    # --- Sidebar: Peers ---
    with st.sidebar:
        st.header("👥 Peers Online")
        
        if st.button("🔄 Actualizar", use_container_width=True):
            peer.run_gossip_cycle()
            time.sleep(0.3)
            st.rerun()
        
        st.divider()
        
        with peer.peer_list_lock:
            peers_to_show = {
                pid: info for pid, info in peer.peer_list.items() 
                if pid != peer.peer_id
            }
            
            if not peers_to_show:
                st.caption("👻 Esperando peers...")
            else:
                for peer_id, info in peers_to_show.items():
                    st.markdown(f"**{info['username']}**")
                    st.caption(f"`{info['ip']}:{info['port']}`")
                    st.divider()

    # --- ⭐ PROCESAR MENSAJES ENTRANTES ---
    new_messages_found = False
    
    # Vaciar TODA la cola
    while True:
        try:
            new_msg = peer.incoming_messages.get_nowait()
            
            sender_id = new_msg['sender']
            sender_username = "Desconocido"
            
            with peer.peer_list_lock:
                if sender_id in peer.peer_list:
                    sender_username = peer.peer_list[sender_id].get('username', sender_id)
                elif sender_id == peer.peer_id:
                    sender_username = peer.username

            st.session_state.messages.append({
                "role": "assistant", 
                "content": f"**{sender_username}**: {new_msg['content']}",
                "sender": sender_username
            })
            
            new_messages_found = True
            
        except queue.Empty:
            break

    # --- MOSTRAR CHAT ---
    chat_container = st.container()
    
    with chat_container:
        if not st.session_state.messages:
            st.info("🔭 No hay mensajes. ¡Escribe algo!")
        else:
            for i, message in enumerate(st.session_state.messages):
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

    # --- INPUT DE MENSAJE ---
    prompt = st.chat_input("✏️ Escribe un mensaje...")
    
    if prompt:
        # Añadir a UI
        st.session_state.messages.append({
            "role": "user", 
            "content": f"**{peer.username} (Tú)**: {prompt}",
            "sender": peer.username
        })

        # Enviar por P2P
        try:
            peer.broadcast_chat_message(prompt)
            # Pequeña pausa para que se envíe
            time.sleep(0.1)
        except Exception as e:
            st.error(f"❌ Error: {e}")

        st.rerun()

    # --- ⭐ AUTO-REFRESH CON st.empty() ---
    if st.session_state.auto_refresh:
        # Placeholder para el refresh
        refresh_placeholder = st.empty()
        
        # Mostrar contador y forzar rerun
        with refresh_placeholder:
            st.caption(f"🔄 Escuchando... ({len(st.session_state.messages)} mensajes)")
        
        # Esperar 1 segundo y recargar
        time.sleep(1)
        st.rerun()
    else:
        st.caption(f"⏸️ Auto-refresh desactivado. Presiona 🔄 para actualizar manualmente.")
        
        # Botón manual de refresh
        if st.button("🔄 Revisar Mensajes Nuevos"):
            st.rerun()