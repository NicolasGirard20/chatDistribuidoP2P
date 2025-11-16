# 📚 Documentación - Sistema de Chat P2P Distribuido

## 🎯 Descripción General

Este proyecto implementa un **sistema de chat peer-to-peer (P2P) distribuido** con tolerancia a fallos. Los peers pueden comunicarse directamente entre sí sin depender exclusivamente de un servidor central, utilizando un protocolo de gossip para mantener la sincronización de la red.

### Características Principales

- ✅ **Comunicación P2P Directa**: Los peers se comunican directamente sin intermediarios
- ✅ **Servidor de Descubrimiento**: Facilita el descubrimiento inicial de peers
- ✅ **Tolerancia a Fallos**: Continúa funcionando si el servidor cae (modo gossip)
- ✅ **Sincronización Automática**: Los peers comparten información de la red entre sí
- ✅ **Interfaz Web Moderna**: UI construida con Streamlit
- ✅ **Heartbeat Monitoring**: Detección automática de peers caídos

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────┐
│           Servidor de Descubrimiento            │
│         (discovery_server.py)                   │
│                                                 │
│  - Registra peers nuevos                       │
│  - Mantiene lista centralizada                 │
│  - Monitorea heartbeats                        │
│  - Notifica cambios en la red                  │
└─────────────┬───────────────────────────────────┘
              │
              │ Registro inicial + Updates
              │
    ┌─────────┴─────────┬─────────────┬──────────┐
    │                   │             │          │
┌───▼────┐         ┌───▼────┐    ┌───▼────┐  ┌──▼─────┐
│ Peer 1 │◄───────►│ Peer 2 │    │ Peer 3 │  │ Peer N │
└────────┘  Gossip └────────┘    └────────┘  └────────┘
    ▲        P2P         ▲            ▲           ▲
    │                    │            │           │
    └────────────────────┴────────────┴───────────┘
           Comunicación Directa (MSG_CHAT)
```

### Flujo de Comunicación

1. **Inicio**: Peer se conecta al servidor de descubrimiento
2. **Registro**: Servidor asigna ID y envía lista de peers activos
3. **Heartbeat**: Peer envía señales periódicas de vida al servidor
4. **Chat**: Peers se comunican directamente entre sí
5. **Gossip**: Si el servidor cae, los peers se sincronizan entre ellos

---

## 📁 Estructura del Proyecto

```
proyecto/
│
├── common/
│   └── protocol.py              # Definición del protocolo de mensajes
│
├── discovery_server/
│   └── discovery_server.py      # Servidor centralizado de descubrimiento
│
├── peer/
│   └── peer_node.py             # Lógica del nodo peer
│
├── run_server.py                # Lanzador del servidor
└── web_chat.py                  # Interfaz web con Streamlit
```

---

## 🔧 Componentes Detallados

### 1. Protocol (protocol.py)

Define los tipos de mensajes y funciones para crear/parsear mensajes JSON.

#### Tipos de Mensajes

| Mensaje | Dirección | Propósito |
|---------|-----------|-----------|
| `MSG_REGISTER` | Peer → Servidor | Registrarse en la red |
| `MSG_REGISTER_ACK` | Servidor → Peer | Confirmación con ID y lista de peers |
| `MSG_HEARTBEAT` | Peer → Servidor | "Sigo vivo" |
| `MSG_UNREGISTER` | Peer → Servidor | "Me voy" |
| `MSG_PEER_LIST_UPDATE` | Servidor → Peer | Notificación de cambios en la red |
| `MSG_CHAT` | Peer → Peer | Mensaje de chat directo |
| `MSG_SYNC_PEERS_REQUEST` | Peer → Peer | "¿A quién conoces?" (Gossip) |
| `MSG_SYNC_PEERS_RESPONSE` | Peer → Peer | "Conozco a esta gente" (Gossip) |

#### Estructura de Mensaje

```json
{
  "type": "MSG_CHAT",
  "sender_id": "Alice@192.168.1.10:10001",
  "to": "Bob@192.168.1.11:10002",
  "content": "Hola Bob!"
}
```

#### Funciones Principales

```python
create_message(msg_type, sender_id, content, to) -> bytes
parse_message(data: bytes) -> dict | None
```

---

### 2. Discovery Server (discovery_server.py)

Servidor centralizado que facilita el descubrimiento de peers.

#### Responsabilidades

1. **Registro de Peers**: Asigna IDs únicos a nuevos peers
2. **Mantenimiento de Lista**: Guarda información de todos los peers activos
3. **Monitoreo de Heartbeats**: Elimina peers que no responden (timeout: 30s)
4. **Broadcasting de Updates**: Notifica a todos cuando alguien se une/sale

#### Estructura de Datos

```python
# Lista de peers activos
self.peers = {
    "Alice@192.168.1.10:10001": (ip, port, username, last_heartbeat),
    "Bob@192.168.1.11:10002": (ip, port, username, last_heartbeat),
    ...
}

# Sockets de conexión para cada peer
self.client_sockets = {
    "Alice@192.168.1.10:10001": socket_object,
    ...
}
```

#### Configuración

```python
HOST = '0.0.0.0'          # Escuchar en todas las interfaces
PORT = 9999               # Puerto del servidor
HEARTBEAT_TIMEOUT = 30    # Segundos antes de considerar peer muerto
```

#### Métodos Clave

- `register_peer()`: Registra nuevo peer y notifica a la red
- `unregister_peer()`: Elimina peer y notifica su salida
- `broadcast_peer_update()`: Envía actualizaciones a todos
- `monitor_peers()`: Thread que limpia peers inactivos cada 10s

---

### 3. Peer Node (peer_node.py)

Nodo peer que actúa como cliente y servidor simultáneamente.

#### Arquitectura del Peer

```
┌──────────────────────────────────────────────┐
│              PeerNode                        │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │   P2P Listener (start_p2p_listener)    │ │
│  │   - Escucha en listening_port          │ │
│  │   - Recibe MSG_CHAT y MSG_SYNC_*       │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │   Discovery Client                     │ │
│  │   - Conecta al servidor                │ │
│  │   - Envía heartbeats (cada 10s)        │ │
│  │   - Recibe peer_list_updates           │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │   Gossip Protocol                      │ │
│  │   - Sincroniza con peers (cada 5s)     │ │
│  │   - Detecta peers caídos               │ │
│  │   - Propaga información de red         │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │   Message Queue                        │ │
│  │   - Cola de mensajes entrantes         │ │
│  │   - Procesada por la UI                │ │
│  └────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

#### Threads del Peer

1. **P2P Listener**: Acepta conexiones entrantes de otros peers
2. **Discovery Client**: Mantiene conexión con el servidor
3. **Gossip Protocol**: Sincroniza periódicamente con peers aleatorios
4. **Main Thread**: Maneja la UI y envío de mensajes

#### Configuración

```python
HEARTBEAT_INTERVAL = 10  # Enviar heartbeat cada 10s
GOSSIP_INTERVAL = 5      # Sincronizar con peers cada 5s
```

#### Métodos Principales

**Comunicación con Servidor:**
- `connect_to_discovery()`: Conecta y registra con el servidor
- `start_discovery_heartbeat()`: Mantiene conexión viva

**Comunicación P2P:**
- `start_p2p_listener()`: Escucha conexiones de otros peers
- `handle_p2p_connection()`: Procesa mensajes P2P entrantes
- `send_chat_message()`: Envía mensaje a un peer específico
- `broadcast_chat_message()`: Envía mensaje a todos los peers

**Protocolo Gossip:**
- `start_gossip_protocol()`: Sincroniza periódicamente
- `handle_sync_request()`: Responde solicitudes de sincronización
- `handle_sync_response()`: Procesa respuestas de sincronización
- `merge_peer_lists()`: Fusiona listas de peers recibidas

**Gestión de Peers:**
- `get_random_peer()`: Selecciona peer aleatorio para gossip
- `remove_dead_peer()`: Elimina peer que no responde

---

### 4. Web Chat UI (web_chat.py)

Interfaz web construida con Streamlit que proporciona una experiencia de usuario moderna.

#### Pantallas

**1. Pantalla de Login**
```
┌─────────────────────────────────────┐
│  🌐 Conectarse al Chat P2P          │
│                                     │
│  IP Servidor: [127.0.0.1        ]  │
│  Usuario:     [Alice            ]  │
│  Puerto:      🔌 10543 (auto)      │
│                                     │
│         [🚀 Conectar]               │
└─────────────────────────────────────┘
```

**2. Pantalla de Chat**
```
┌─────────────────────────────────────────────────┐
│ 💬 Chat P2P - Alice                             │
│                                                 │
│ 🟢 Servidor Online | 👥 3 peers | 🔄 Auto | 🚪 │
├─────────────────────────────────────────────────┤
│                                                 │
│  💬 Bob: Hola Alice!                            │
│  💬 Charlie: ¿Cómo están todos?                 │
│  💬 Alice (Tú): ¡Todo bien!                     │
│                                                 │
├─────────────────────────────────────────────────┤
│  ✏️ Escribe un mensaje...                      │
└─────────────────────────────────────────────────┘

Sidebar:
┌──────────────────┐
│ 👥 Peers Online  │
│                  │
│ [🔄 Actualizar]  │
│ ──────────────── │
│ **Bob**          │
│ 192.168.1.11:... │
│ ──────────────── │
│ **Charlie**      │
│ 192.168.1.12:... │
└──────────────────┘
```

#### Estado de la Sesión

```python
st.session_state = {
    'peer': PeerNode,              # Instancia del peer
    'messages': [...],             # Historial de mensajes
    'logged_in': bool,             # Estado de login
    'server_ip': str,              # IP del servidor
    'auto_refresh': bool,          # Auto-actualización activada
    'temp_port': int               # Puerto temporal antes de login
}
```

#### Características de la UI

- **Auto-refresh**: Actualiza mensajes cada 1 segundo automáticamente
- **Actualización Manual**: Botón para forzar sincronización gossip
- **Indicador de Estado**: Muestra si el servidor está online o en modo P2P
- **Contador de Peers**: Muestra cantidad de peers conectados
- **Lista Lateral**: Muestra todos los peers activos con su información

---

## 🚀 Cómo Usar el Sistema

### Requisitos Previos

```bash
pip install streamlit
```

### Paso 1: Iniciar el Servidor de Descubrimiento

```bash
python run_server.py
```

Salida esperada:
```
Iniciando Servidor de Descubrimiento...
[Server] Iniciando en 0.0.0.0:9999
[Server] Escuchando conexiones en 9999...
[Monitor] Monitor de peers iniciado.
```

### Paso 2: Iniciar Peers

**Opción A: Interfaz Web (Recomendado)**

```bash
streamlit run web_chat.py
```

**Opción B: Múltiples Instancias**

Abrir varias ventanas del navegador en `http://localhost:8501`

Cada ventana representa un peer diferente.

### Paso 3: Conectarse

1. Ingresa tu nombre de usuario (ej: "Alice")
2. El puerto se asigna automáticamente
3. Click en "🚀 Conectar"

### Paso 4: Chatear

- Escribe mensajes en el campo inferior
- Los mensajes se envían a todos los peers
- La UI se actualiza automáticamente

---

## 🔄 Protocolo de Gossip (Tolerancia a Fallos)

### ¿Qué es Gossip?

El protocolo de gossip permite que los peers mantengan sincronizada la lista de la red **sin depender del servidor**.

### Funcionamiento

```
┌─────────┐                     ┌─────────┐
│ Peer A  │  MSG_SYNC_REQUEST  │ Peer B  │
│         ├────────────────────►│         │
│ Lista:  │                     │ Lista:  │
│ - A     │  MSG_SYNC_RESPONSE │ - A     │
│ - B     │◄────────────────────┤ - B     │
│         │                     │ - C ⭐  │
│         │                     │ - D ⭐  │
└─────────┘                     └─────────┘

Resultado: Peer A ahora conoce a C y D
```

### Ciclo de Gossip

1. **Cada 5 segundos**, el peer:
   - Selecciona un peer aleatorio de su lista
   - Le envía `MSG_SYNC_PEERS_REQUEST`
   - Recibe `MSG_SYNC_PEERS_RESPONSE` con su lista
   - Fusiona ambas listas

2. **Detección de Fallos**:
   - Si un peer no responde → Se marca como caído y se elimina
   - La información se propaga en el siguiente ciclo de gossip

### Ejemplo de Escenario de Fallo

```
Estado Inicial:
Servidor UP → Todos conocen a todos (A, B, C, D)

Servidor CAE ❌

t=0s:  A conoce: [A, B, C, D]
       B conoce: [A, B, C, D]
       C conoce: [A, B, C, D]

t=5s:  Nuevo peer E se conecta
       E solo conoce: [E]

t=10s: A hace gossip con E
       A aprende sobre E
       E aprende sobre A, B, C, D

t=15s: B hace gossip con A
       B aprende sobre E

t=20s: Toda la red conoce a E ✅
```

---

## 🛡️ Manejo de Errores y Tolerancia a Fallos

### Escenarios Cubiertos

| Escenario | Mecanismo | Resultado |
|-----------|-----------|-----------|
| Servidor cae | Protocolo Gossip | Comunicación P2P continúa |
| Peer cae durante chat | Timeout + remove_dead_peer() | Se elimina de la lista |
| Heartbeat no llega | Monitor del servidor | Peer eliminado tras 30s |
| Conexión P2P falla | Exception handling | Se marca peer como caído |
| Mensaje no se entrega | Thread individual | No bloquea otros envíos |

### Timeouts Configurados

```python
# Servidor
HEARTBEAT_TIMEOUT = 30s      # Tiempo antes de eliminar peer

# Peer
HEARTBEAT_INTERVAL = 10s     # Frecuencia de heartbeats
GOSSIP_INTERVAL = 5s         # Frecuencia de sincronización
SOCKET_TIMEOUT = 5s          # Timeout de conexión P2P
```

---

## 📊 Flujos de Datos Completos

### Flujo 1: Registro de Peer Nuevo

```
┌──────┐                ┌─────────┐              ┌──────┐
│Peer A│                │ Server  │              │Peer B│
└──┬───┘                └────┬────┘              └──┬───┘
   │                         │                      │
   │ 1. MSG_REGISTER         │                      │
   ├────────────────────────►│                      │
   │                         │                      │
   │ 2. MSG_REGISTER_ACK     │                      │
   │    + peer_list          │                      │
   │◄────────────────────────┤                      │
   │                         │                      │
   │                         │ 3. MSG_PEER_LIST_    │
   │                         │    UPDATE (new: A)   │
   │                         ├─────────────────────►│
   │                         │                      │
   │ 4. MSG_HEARTBEAT        │                      │
   ├────────────────────────►│                      │
   │         (cada 10s)      │                      │
```

### Flujo 2: Envío de Mensaje de Chat

```
┌──────┐                              ┌──────┐
│Peer A│                              │Peer B│
└──┬───┘                              └──┬───┘
   │                                     │
   │ 1. Usuario escribe mensaje          │
   │    "Hola!"                          │
   │                                     │
   │ 2. broadcast_chat_message()         │
   │                                     │
   │ 3. Conecta a IP:Port de B           │
   ├────────────────────────────────────►│
   │                                     │
   │ 4. Envía MSG_CHAT                   │
   ├────────────────────────────────────►│
   │                                     │
   │                                     │ 5. Añade a queue
   │                                     │ 6. UI muestra mensaje
   │                                     │
```

### Flujo 3: Sincronización Gossip

```
┌──────┐                              ┌──────┐
│Peer A│                              │Peer C│
└──┬───┘                              └──┬───┘
   │                                     │
   │ 1. Timer de gossip (5s)             │
   │                                     │
   │ 2. get_random_peer() → Peer C       │
   │                                     │
   │ 3. MSG_SYNC_PEERS_REQUEST           │
   ├────────────────────────────────────►│
   │                                     │
   │ 4. MSG_SYNC_PEERS_RESPONSE          │
   │    {peer_list: [A, B, C, D]}       │
   │◄────────────────────────────────────┤
   │                                     │
   │ 5. merge_peer_lists()               │
   │    A ahora conoce a D (nuevo)       │
   │                                     │
```

---

## 🔧 Configuración Avanzada

### Ajustar Intervalos de Tiempo

**En `peer_node.py`:**
```python
HEARTBEAT_INTERVAL = 10  # Más bajo = detección rápida, más tráfico
GOSSIP_INTERVAL = 5      # Más bajo = sincronización rápida
```

**En `discovery_server.py`:**
```python
HEARTBEAT_TIMEOUT = 30   # Más alto = más tolerante a lag
```

### Cambiar Puerto del Servidor

**En `run_server.py` y `web_chat.py`:**
```python
PORT = 9999  # Cambiar a otro puerto si 9999 está ocupado
```

### Ejecutar en Red Local

1. Encontrar IP local:
```bash
# Linux/Mac
ifconfig | grep inet

# Windows
ipconfig
```

2. En `web_chat.py`, usar la IP del servidor:
```python
st.session_state.server_ip = "192.168.1.100"  # IP real
```

3. Asegurar que el firewall permita los puertos

---

## 🐛 Troubleshooting

### Problema: "No se pudo conectar al servidor"

**Causa**: Servidor no está corriendo o puerto bloqueado

**Solución**:
1. Verificar que `run_server.py` esté ejecutándose
2. Revisar firewall/antivirus
3. Probar con `telnet localhost 9999`

### Problema: "Peer no responde" en logs

**Causa**: Peer se desconectó abruptamente

**Solución**: Normal, el sistema lo detectará y eliminará automáticamente

### Problema: Mensajes no aparecen

**Causa**: Auto-refresh desactivado

**Solución**: Activar checkbox "🔄 Auto" o presionar botón "Actualizar"

### Problema: No se ven otros peers

**Causa**: Lista no sincronizada

**Solución**: Presionar "🔄 Actualizar" en la sidebar

---

## 📈 Métricas y Monitoreo

### Logs Importantes

**Servidor:**
```
[Server] Registrando peer: Alice@192.168.1.10:10001
[Broadcast] Notificando a todos los peers...
[Monitor] Peer Bob@... ha superado el timeout. Eliminando.
```

**Peer:**
```
[Discovery] Conectado a 127.0.0.1:9999
[Discovery] Registrado! ID Oficial: Alice@192.168.1.10:10001
[Gossip] Sincronizando con Bob...
[Chat] Mensaje enviado a Bob@...
[P2P] Eliminando peer caído: Charlie@...
```

### Indicadores de Salud

- ✅ **Servidor Online**: Heartbeats funcionando
- ✅ **N Peers Conectados**: Lista sincronizada
- ⚠️ **Modo P2P**: Servidor caído, usando gossip
- ❌ **0 Peers**: Problema de red o configuración

---

## 🎓 Conceptos Clave

### Peer-to-Peer (P2P)

Arquitectura donde cada nodo actúa como cliente y servidor simultáneamente, eliminando la dependencia de un servidor central para la comunicación.

### Protocolo Gossip

Método de propagación de información donde los nodos se comunican periódicamente con un subconjunto aleatorio de otros nodos, similar a cómo se propagan rumores.

### Heartbeat

Señal periódica enviada para indicar que un nodo sigue activo. Si no se recibe por cierto tiempo, se asume que el nodo falló.

### Discovery Server

Servidor de arranque que facilita el descubrimiento inicial de peers, pero no es crítico para el funcionamiento continuo del sistema.

### Tolerancia a Fallos

Capacidad del sistema de continuar funcionando correctamente incluso cuando algunos componentes fallan.

---

## 🎯 Mejoras Futuras Posibles

1. **Encriptación**: Implementar SSL/TLS para mensajes
2. **Autenticación**: Sistema de login con contraseñas
3. **Persistencia**: Guardar historial de mensajes en base de datos
4. **Rooms/Canales**: Múltiples salas de chat
5. **Archivos**: Compartir archivos entre peers
6. **DHT**: Tabla hash distribuida para escalabilidad
7. **NAT Traversal**: Soporte para redes detrás de NAT
8. **Compresión**: Comprimir mensajes para reducir bandwidth

---

## 📝 Licencia y Créditos

Este proyecto fue desarrollado como demostración educativa de sistemas distribuidos P2P con tolerancia a fallos.

### Tecnologías Utilizadas

- **Python 3.x**: Lenguaje principal
- **Streamlit**: Framework de UI web
- **Socket Programming**: Comunicación de red
- **Threading**: Concurrencia y paralelismo
- **JSON**: Serialización de mensajes

---

## 📞 Contacto y Soporte

Para preguntas, reportes de bugs o sugerencias sobre este proyecto, puedes:

1. Revisar los logs del sistema
2. Verificar la configuración de red
3. Asegurar que todos los puertos estén disponibles
4. Consultar la sección de Troubleshooting

---

**¡Disfruta tu chat P2P distribuido! 🚀**