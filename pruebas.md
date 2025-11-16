# 🧪 Guía de Pruebas - Sistema de Chat P2P Distribuido

## 📋 Índice de Pruebas

1. [Pruebas Básicas de Funcionalidad](#1-pruebas-básicas-de-funcionalidad)
2. [Pruebas de Comunicación P2P](#2-pruebas-de-comunicación-p2p)
3. [Pruebas de Tolerancia a Fallos](#3-pruebas-de-tolerancia-a-fallos)
4. [Pruebas del Protocolo Gossip](#4-pruebas-del-protocolo-gossip)


---

## 1. Pruebas Básicas de Funcionalidad

### 🧪 Prueba 1.1: Inicio del Servidor

**Objetivo**: Verificar que el servidor de descubrimiento inicia correctamente.

**Pasos**:
1. Ejecutar `python run_server.py`
2. Observar la salida en consola

**Resultado Esperado**:
```
Iniciando Servidor de Descubrimiento...
[Server] Iniciando en 0.0.0.0:9999
[Server] Escuchando conexiones en 9999...
[Monitor] Monitor de peers iniciado.
```

**Criterios de Éxito**:
- ✅ No hay errores en consola
- ✅ El servidor escucha en el puerto 9999
- ✅ El monitor de peers se inicia

**Posibles Fallos**:
- ❌ Puerto 9999 ya está en uso → Cambiar puerto en configuración
- ❌ Error de permisos → Ejecutar con permisos adecuados

---

### 🧪 Prueba 1.2: Conexión de un Solo Peer

**Objetivo**: Verificar que un peer puede conectarse al servidor exitosamente.

**Pasos**:
1. Iniciar el servidor
2. Ejecutar `streamlit run web_chat.py`
3. Ingresar nombre de usuario "Alice"
4. Click en "Conectar"

**Resultado Esperado**:
- UI muestra "✅ ¡Conectado como Alice!"
- Indicador cambia a "🟢 Servidor Online"
- Contador muestra "👥 0 peers" (solo Alice)
- Logs del servidor muestran: `[Server] Registrando peer: Alice@...`

**Criterios de Éxito**:
- ✅ Conexión exitosa
- ✅ ID de peer asignado correctamente
- ✅ Heartbeats se envían cada 10 segundos
- ✅ No hay errores en consola

---

### 🧪 Prueba 1.3: Conexión de Múltiples Peers

**Objetivo**: Verificar que múltiples peers pueden conectarse simultáneamente.

**Pasos**:
1. Iniciar el servidor
2. Abrir 3 ventanas del navegador (navegación privada recomendada)
3. Conectar como "Alice", "Bob" y "Charlie"

**Resultado Esperado**:
- Cada peer se conecta exitosamente
- Alice ve: "👥 2 peers" (Bob y Charlie)
- Bob ve: "👥 2 peers" (Alice y Charlie)
- Charlie ve: "👥 2 peers" (Alice y Bob)
- Sidebar muestra todos los otros peers con IP:Puerto

**Criterios de Éxito**:
- ✅ Todos los peers reciben la lista completa
- ✅ Cada peer tiene un ID único
- ✅ La lista se actualiza automáticamente cuando alguien se une

---

### 🧪 Prueba 1.4: Desconexión Limpia

**Objetivo**: Verificar que un peer puede desconectarse correctamente.

**Pasos**:
1. Tener 3 peers conectados (Alice, Bob, Charlie)
2. Bob presiona el botón "🚪" (Desconectar)
3. Observar qué pasa en Alice y Charlie

**Resultado Esperado**:
- Bob se desconecta y vuelve a la pantalla de login
- Alice y Charlie actualizan su contador a "👥 1 peer"
- Bob desaparece de la sidebar de ambos
- Logs del servidor: `[Server] Peer Bob@... eliminado.`

**Criterios de Éxito**:
- ✅ MSG_UNREGISTER enviado correctamente
- ✅ Servidor notifica a todos los peers
- ✅ Listas de peers se actualizan automáticamente
- ✅ No quedan conexiones zombies

---

## 2. Pruebas de Comunicación P2P

### 🧪 Prueba 2.1: Envío de Mensaje Simple

**Objetivo**: Verificar que un peer puede enviar mensajes a otros.

**Pasos**:
1. Conectar Alice y Bob
2. Alice escribe "Hola Bob!" y presiona Enter
3. Observar ambas pantallas

**Resultado Esperado**:
- En Alice: "**Alice (Tú)**: Hola Bob!"
- En Bob: "**Alice**: Hola Bob!" (después de 1-2 segundos)
- El mensaje aparece en la UI de Bob automáticamente

**Criterios de Éxito**:
- ✅ Mensaje enviado vía conexión P2P directa
- ✅ Mensaje aparece en el destinatario
- ✅ No pasa por el servidor de descubrimiento
- ✅ Formato correcto del mensaje

---

### 🧪 Prueba 2.2: Broadcast a Múltiples Peers

**Objetivo**: Verificar que los mensajes llegan a todos los peers.

**Pasos**:
1. Conectar Alice, Bob, Charlie y Dave
2. Alice escribe "Hola a todos!"
3. Verificar que aparece en todos

**Resultado Esperado**:
- El mensaje aparece en Bob, Charlie y Dave
- Cada uno lo ve como "**Alice**: Hola a todos!"
- Alice ve su propio mensaje como "**Alice (Tú)**: Hola a todos!"

**Criterios de Éxito**:
- ✅ Mensaje llega a todos los peers (3/3)
- ✅ Tiempo de propagación < 2 segundos
- ✅ No hay duplicados
- ✅ Orden correcto de mensajes

---

### 🧪 Prueba 2.3: Conversación Bidireccional

**Objetivo**: Verificar el flujo de conversación natural.

**Pasos**:
1. Conectar Alice y Bob
2. Secuencia de mensajes:
   - Alice: "Hola Bob!"
   - Bob: "Hola Alice, ¿cómo estás?"
   - Alice: "Muy bien, gracias"
   - Bob: "¡Genial!"

**Resultado Esperado**:
- Ambos peers ven toda la conversación en orden
- Los mensajes se intercalan correctamente
- No hay pérdida de mensajes
- Los timestamps (si los hay) son correctos

**Criterios de Éxito**:
- ✅ 4/4 mensajes entregados
- ✅ Orden cronológico correcto
- ✅ Identificación correcta de remitente
- ✅ No hay race conditions

---

### 🧪 Prueba 2.4: Mensajes Especiales

**Objetivo**: Verificar que mensajes con caracteres especiales se manejan correctamente.

**Pasos**:
1. Conectar Alice y Bob
2. Enviar mensajes con:
   - Emojis: "Hola 👋 😊 🎉"
   - Acentos: "Mónica, José, François"
   - Símbolos: "Precio: $100 • 50% descuento"
   - Multilínea: Presionar Enter múltiples veces
   - JSON-like: `{"test": "value"}`

**Resultado Esperado**:
- Todos los caracteres se muestran correctamente
- No hay corrupción de datos
- La codificación UTF-8 funciona bien

**Criterios de Éxito**:
- ✅ Emojis se muestran correctamente
- ✅ Acentos preservados
- ✅ Símbolos especiales no rompen el protocolo
- ✅ No hay errores de encoding

---

## 3. Pruebas de Tolerancia a Fallos

### 🧪 Prueba 3.1: Caída del Servidor Durante Operación

**Objetivo**: Verificar que el sistema continúa funcionando sin servidor.

**Pasos**:
1. Conectar Alice, Bob y Charlie (servidor UP)
2. Enviar algunos mensajes (verificar que funciona)
3. Detener el servidor (Ctrl+C en `run_server.py`)
4. Esperar 5-10 segundos
5. Intentar enviar más mensajes

**Resultado Esperado**:
- Indicador cambia de "🟢 Servidor Online" a "🟡 Modo P2P"
- Los peers **aún pueden enviarse mensajes** entre sí
- La comunicación P2P directa sigue funcionando
- Logs: `[Heartbeat] Error en conexión con servidor: ... Servidor caído.`

**Criterios de Éxito**:
- ✅ Detección de caída del servidor (< 15 segundos)
- ✅ Mensajes P2P siguen funcionando
- ✅ No hay crash de peers
- ✅ UI refleja el cambio de estado

---

### 🧪 Prueba 3.2: Reconexión Automática al Servidor

**Objetivo**: Verificar que los peers se reconectan cuando el servidor vuelve.

**Pasos**:
1. Detener el servidor (con peers conectados)
2. Esperar 30 segundos en "Modo P2P"
3. Reiniciar el servidor: `python run_server.py`
4. Esperar 15-20 segundos
5. Observar los peers

**Resultado Esperado**:
- Peers detectan el servidor nuevamente
- Indicador cambia a "🟢 Servidor Online"
- Peers se re-registran automáticamente
- Logs: `[Discovery] Conectado a 127.0.0.1:9999`

**Criterios de Éxito**:
- ✅ Reconexión automática en < 20 segundos
- ✅ Listas de peers se sincronizan
- ✅ Comunicación sigue funcionando
- ✅ No se pierden mensajes durante la transición

---

### 🧪 Prueba 3.3: Peer Cae Abruptamente

**Objetivo**: Verificar la detección y limpieza de peers caídos.

**Pasos**:
1. Conectar Alice, Bob y Charlie
2. Cerrar la ventana de Bob **sin usar el botón de desconectar** (simula crash)
3. Esperar 30-40 segundos
4. Observar Alice y Charlie

**Resultado Esperado**:

**Con Servidor UP**:
- Después de ~30 segundos (HEARTBEAT_TIMEOUT)
- Servidor detecta que Bob no envía heartbeats
- Servidor notifica a Alice y Charlie
- Bob desaparece de sus listas

**Con Servidor DOWN**:
- En el próximo ciclo de gossip (5-10 segundos)
- Alice o Charlie intentan sincronizar con Bob
- Falla la conexión → Bob es marcado como caído
- Bob es eliminado localmente

**Criterios de Éxito**:
- ✅ Detección de peer caído
- ✅ Notificación a otros peers
- ✅ Limpieza de listas
- ✅ No afecta comunicación entre Alice y Charlie

---

### 🧪 Prueba 3.4: Red Lenta / Timeout

**Objetivo**: Verificar comportamiento con latencia de red.

**Pasos**:
1. Conectar Alice y Bob
2. **Simular latencia** (requiere herramientas como `tc` en Linux):
   ```bash
   sudo tc qdisc add dev lo root netem delay 2000ms
   ```
3. Intentar enviar mensajes
4. Observar comportamiento

**Resultado Esperado**:
- Mensajes pueden tardar más en llegar (2+ segundos)
- Sistema no marca peers como caídos prematuramente
- Timeouts configurados (5s) manejan la latencia
- Eventualmente los mensajes llegan

**Criterios de Éxito**:
- ✅ Sistema tolera latencia razonable (< 5s)
- ✅ No hay falsos positivos de "peer caído"
- ✅ Mensajes eventualmente se entregan
- ✅ No hay crashes por timeouts

---

## 4. Pruebas del Protocolo Gossip

### 🧪 Prueba 4.1: Sincronización Básica

**Objetivo**: Verificar que el gossip propaga información correctamente.

**Pasos**:
1. Detener el servidor
2. Conectar Alice y Bob (modo P2P)
3. Alice envía un mensaje a Bob
4. Presionar "🔄 Actualizar" en ambos peers
5. Verificar las listas

**Resultado Esperado**:
- Ambos peers mantienen sus listas sincronizadas
- El botón "Actualizar" fuerza un ciclo de gossip
- Logs: `[Gossip] Sincronizando con Bob...`
- Las listas son consistentes

**Criterios de Éxito**:
- ✅ Sincronización manual funciona
- ✅ Listas se mantienen actualizadas
- ✅ No hay errores de comunicación
- ✅ Protocolo MSG_SYNC funciona

---

### 🧪 Prueba 4.2: Gossip Automático

**Objetivo**: Verificar la sincronización automática cada 5 segundos.

**Pasos**:
1. Detener el servidor
2. Conectar Alice, Bob y Charlie
3. Esperar sin hacer nada por 15-20 segundos
4. Observar logs en consola del peer

**Resultado Esperado**:
- Cada 5 segundos (GOSSIP_INTERVAL)
- Logs muestran: `[Gossip] Ejecutando ciclo de sincronización P2P programado.`
- Cada peer selecciona un peer aleatorio y sincroniza
- No hay errores

**Criterios de Éxito**:
- ✅ Gossip automático activo
- ✅ Intervalo de 5s respetado
- ✅ Selección aleatoria de peers
- ✅ Sincronización exitosa

---

### 🧪 Prueba 4.3: Propagación de Información

**Objetivo**: Verificar que la información se propaga entre peers sin servidor.

**Pasos**:
1. Detener el servidor
2. Conectar Alice, Bob y Charlie (todos se conocen)
3. **Nuevo peer Dave se conecta directamente a Alice** (simulación manual):
   - En modo P2P, Dave solo conoce a Alice inicialmente
4. Esperar ciclos de gossip (15-30 segundos)
5. Verificar que Bob y Charlie eventualmente conocen a Dave

**Resultado Esperado**:
```
t=0s:  Dave conoce: [Dave, Alice]
       Alice conoce: [Alice, Bob, Charlie, Dave]
       Bob conoce: [Alice, Bob, Charlie]
       Charlie conoce: [Alice, Bob, Charlie]

t=5s:  Alice hace gossip con Bob
       Bob aprende sobre Dave

t=10s: Bob hace gossip con Charlie
       Charlie aprende sobre Dave

t=15s: Todos conocen a Dave ✅
```

**Criterios de Éxito**:
- ✅ Información se propaga gradualmente
- ✅ Convergencia eventual alcanzada
- ✅ Todos los peers tienen la misma lista
- ✅ No hay loops infinitos

---

### 🧪 Prueba 4.4: Detección Distribuida de Fallo

**Objetivo**: Verificar que peers caídos son detectados sin servidor.

**Pasos**:
1. Detener el servidor
2. Conectar Alice, Bob, Charlie y Dave
3. Cerrar la ventana de Dave (crash)
4. Esperar 10-15 segundos
5. Observar las listas de Alice, Bob y Charlie

**Resultado Esperado**:
- El primer peer que intenta sincronizar con Dave detecta el fallo
- Dave es marcado como caído y eliminado localmente
- En el siguiente ciclo de gossip, esta información se propaga
- Eventualmente todos eliminan a Dave de sus listas

**Criterios de Éxito**:
- ✅ Detección de fallo en < 10 segundos
- ✅ Propagación de información de fallo
- ✅ Convergencia: todos eliminan a Dave
- ✅ Sistema estabiliza sin el peer caído

---
