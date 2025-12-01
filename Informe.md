# Informe de SD

## Introducción

El objetivo de este proyecto es diseñar e implementar un sistema de compartición de archivos inspirado en BitTorrent, empleando un modelo P2P sobre una infraestructura distribuida basada en Docker swarm. El sistema permite descargar archivos a partir de un archivo torrent que contiene la información necesaria para recuperar el contenido desde múltiples clientes de la red.  

La motivación principal es superar las limitaciones de enfoques centralizados como FTP, en los que la disponibilidad del contenido depende de un único servidor. En el sistema propuesto, el almacenamiento se delega en los propios clientes y la coordinación en un conjunto de trackers distribuidos, buscando tolerancia a fallos, replicación de metadatos y descarga desde múltiples fuentes de forma escalable.  

---

## Arquitectura: diseño del sistema

### Organización del sistema distribuido

El sistema se organiza en dos tipos de nodos: clientes y trackers. Los clientes son responsables de almacenar y servir los archivos compartidos, así como de descargar contenido a partir de archivos torrent. Los trackers gestionan la información de qué clientes disponen de qué archivos y responden a las consultas de los clientes para que puedan descubrir posibles peers desde los que descargar.  

La arquitectura persigue explícitamente evitar un punto único de fallo en la capa de control. Para ello se despliega un conjunto de trackers lógicamente equivalentes que comparten y replican metadatos sobre torrents y peers. Cualquier cliente puede contactar con cualquiera de estos trackers y obtener una vista suficientemente actualizada del sistema, siempre que al menos un subconjunto de trackers permanezca disponible.  

### Roles del sistema

Los clientes con interfaz gráfica actúan simultáneamente como consumidores y proveedores de contenido. Cada cliente mantiene en su almacenamiento local los archivos que está dispuesto a compartir, es decir, aquellos que ha anunciado previamente a los trackers. Además, ejecuta servicios de descarga y subida de chunks hacia y desde otros peers, así como un pequeño servidor de escucha para atender peticiones entrantes de otros nodos.  

Los trackers son servicios sin interfaz gráfica cuya responsabilidad principal es mantener la correspondencia entre identificadores de torrents (hashes) y conjuntos de peers activos. Cada tracker registra altas y bajas de clientes para cada torrent, responde a consultas de descubrimiento de peers, coordina la replicación de sus tablas de estado con otros trackers y ejecuta mecanismos de limpieza de peers inactivos para mantener información razonablemente precisa.  

### Distribución en redes Docker

Tanto clientes como trackers se despliegan como contenedores en una o varias redes de Docker dentro de un swarm. La resolución de direcciones entre servicios se apoya en el DNS interno de Docker y en una caché de IPs mantenida por los propios componentes. En una misma subred se contempla el uso de mecanismos de descubrimiento por broadcast o multicast para localizar trackers disponibles y reducir la configuración manual. Esta organización permite ejecutar el sistema sobre, al menos, dos máquinas físicas y varias redes virtualizadas, cumpliendo los requisitos de la asignatura.  

---

## Procesos, hilos y asincronía

En cada tracker se levantan varios servicios lógicos dentro del mismo proceso principal. Por un lado, un servidor de escucha basado en sockets que recibe peticiones de clientes y de otros trackers, despachando cada solicitud de forma asíncrona mediante un event loop. Por otro, un servicio encargado de la replicación y consistencia de los datos de metadatos entre trackers, y un servicio de sincronización de acciones periódicas como limpieza de peers inactivos o intercambio de estados.  

En cada cliente se ejecuta al menos un proceso que integra la interfaz gráfica y la lógica de red. Este proceso mantiene: una GUI para gestionar torrents y su progreso, uno o varios servicios de descarga (uno por archivo o torrent en la lista de descargas) y un servidor de escucha que expone los archivos anunciados para que otros peers puedan descargarlos. La separación funcional dentro del proceso facilita diferenciar claramente el plano de control (GUI, coordinación con trackers) del plano de datos (transferencia de chunks entre peers).  

En cuanto a concurrencia interna, los hilos se emplean principalmente para gestionar las descargas de archivos en paralelo, de forma que un cliente pueda descargar distintos torrents o varios chunks simultáneamente sin bloquear la interfaz. La gestión de peticiones de red (especialmente en los trackers) se apoya en un modelo asíncrono basado en asyncio o un event loop similar, lo que permite atender muchas conexiones concurrentes con un único proceso y un conjunto controlado de hilos. No se utilizan procesos adicionales mediante multiprocessing; todo ocurre en el proceso principal de cada nodo, lo que simplifica el despliegue en contenedores.  

---

## Comunicación

La comunicación entre nodos se implementa mediante sockets TCP y, cuando es necesario, UDP, sobre un protocolo propio diseñado para el proyecto. Encima de estos sockets se define un RPC ligero con estructuras de mensajes bien tipadas, que permite a clientes y trackers invocar operaciones remotas (registro de peer, consulta de peers de un torrent, actualización de estado, etc.) sin depender de marcos externos no cubiertos en la asignatura.  

A alto nivel se distinguen dos grandes clases de mensajes: mensajes de request y mensajes de datos. Los mensajes de request incluyen campos como `endpoint`, `handler`, `data` y `command`, lo que permite dirigir la petición al manejador adecuado en cada nodo. Los mensajes asociados a metadatos de archivos (por ejemplo, para consultar el estado de un torrent concreto) incluyen campos como `hash` e `index`. Ambos tipos de mensaje comparten un conjunto de metacampos, entre ellos `msg_id`, `timestamp` y `version`, que se usan posteriormente para sincronización y resolución de conflictos.  

En cuanto a puertos, se reserva un rango por encima del 5555 para los servicios de tracker y otro por encima del 5550 para los servicios de cliente. Para la comunicación distribuida entre trackers (replicación y coordinación) se emplea un subconjunto específico del rango a partir del 5560, lo que facilita configurar reglas de red y cortafuegos en Docker. Existe comunicación servidor-servidor entre trackers para la replicación de tablas y la coordinación de decisiones, además de la comunicación cliente-servidor típica entre clientes y trackers y la comunicación peer-to-peer directa entre clientes para la transferencia de chunks.  

---

## Coordinación y toma de decisiones distribuidas

La coordinación en el plano de datos se basa en decisiones locales informadas por métricas de desempeño. Para seleccionar de qué peer descargar un chunk concreto, el cliente realiza una prueba de velocidad y estabilidad sobre los peers disponibles durante un intervalo fijo y elige el nodo que muestra mejor comportamiento. Además, la interfaz permite que el usuario pueda forzar la prioridad de determinados peers en caso de ser necesario.  

Cuando varios peers solicitan chunks a un mismo cliente, la política de subida es, en primera instancia, por orden de llegada: las peticiones se atienden secuencialmente o en pequeños lotes controlados para evitar saturar el ancho de banda de subida. Esta estrategia sencilla, combinada con límites configurables de ancho de banda por cliente, permite un reparto razonable de recursos sin necesidad de algoritmos de planificación excesivamente complejos.  

En el plano de control, se emplean mecanismos de sincronización locales y distribuidos. A nivel de cada nodo se utilizan locks para proteger estructuras compartidas como la tabla de torrents y peers o el mapa de chunks descargados, evitando condiciones de carrera entre hilos de descarga, subida y servicios de mantenimiento. Entre componentes internos se prevé el uso de colas de mensajes para desacoplar el hilo que recibe peticiones del que las procesa, evitando que ambos accedan simultáneamente a los mismos datos.  

Para la coordinación entre trackers se plantea el uso de relojes lógicos: cada actualización relevante (alta o baja de peer, modificación de metadatos) incrementa un contador lógico asociado y se etiqueta con esa versión. Cuando dos trackers intercambian información y encuentran actualizaciones conflictivas sobre una misma entrada, se aplica una política de “último escritor gana” basada en la comparación de estos relojes. Además, se contempla un esquema de “elección por participación” donde, ante la necesidad de realizar tareas globales como un rebalanceo de réplicas, los trackers activos intercambian identificadores y adoptan como coordinador temporal al que tenga mayor prioridad (por ejemplo, un ID numérico más alto).  

---

## Nombrado y localización

El sistema identifica los torrents y recursos mediante un hash calculado sobre el contenido o sobre el archivo torrent correspondiente. Este hash actúa como identificador único del recurso en toda la red, siendo la clave principal que manejan los trackers para asociar torrents con listas de peers. Los peers, por su parte, se identifican por una combinación de dirección IP y nombre lógico, lo que permite al usuario reconocer nodos conocidos y al sistema resolverlos a direcciones concretas.  

La localización de otros nodos se apoya en el servicio de DNS interno de Docker y, dentro de una misma subred, en mecanismos de broadcast o multicast para descubrir trackers disponibles sin preconfiguración manual exhaustiva. Los clientes consultan al DNS de Docker para resolver nombres de trackers, y en entornos de swarm se puede mantener un listado dinámico de trackers accesibles mediante una ip-cache compartida.  

Para mantener actualizada la información de localización, los trackers ejecutan procesos periódicos que limpian de sus tablas los peers que no han enviado mensajes o heartbeats en un intervalo de tiempo configurable. De este modo se reduce el número de referencias obsoletas y se mejora la calidad de las respuestas que se devuelven a los clientes cuando solicitan peers para un torrent determinado.  

---

## Consistencia y replicación

Los archivos se fragmentan en chunks de tamaño fijo, lo que permite que diferentes partes de un mismo archivo se descarguen en paralelo desde distintos peers. Cada cliente mantiene en memoria la información de qué chunks ha completado y cuál es el estado actual de cada torrent, persistiendo este estado en disco cuando se cierra el programa para no perder el progreso.  

La integridad de los datos se verifica tanto a nivel de chunk como a nivel de archivo completo. Cada chunk descargado se contrasta con un hash esperado, y una vez que se han completado todos los chunks, se calcula y verifica el hash del archivo final. Si un chunk o el archivo completo no coinciden con el hash previsto, se marcan como corruptos y se vuelve a solicitar la pieza a otro peer disponible.  

En cuanto a replicación, los datos de usuario (los propios archivos compartidos) se replican de forma natural entre los clientes que los descargan y deciden seguir sirviéndolos. No se impone una replicación mínima por cliente; si no hay peers que dispongan de un archivo en un momento dado, el cliente deberá esperar a que se conecte algún nodo que lo posea. En cambio, los metadatos gestionados por los trackers (asociaciones torrent–peers) sí se replican explícitamente.  

Se garantiza que la información crítica sobre torrents y peers esté disponible al menos en dos trackers distintos, cumpliendo así un nivel de tolerancia a fallos 2 en la capa de control. La política de replicación tiene en cuenta la participación: los trackers monitorizan cuántas veces se ha pedido información sobre un torrent y utilizan ese dato para decidir dónde y cuántas réplicas mantener. Para equilibrar la carga y evitar que un solo tracker concentre demasiados metadatos, se puede utilizar un esquema de particionado basado en hashing (por ejemplo, asignar el torrent a `hash(torrent) mod N` trackers) y, cuando un torrent se vuelve muy popular, añadir réplicas en trackers menos cargados. Este modelo proporciona una consistencia eventual: las tablas de estado entre trackers convergen con el tiempo mediante intercambios periódicos, aceptando breves periodos de vistas desactualizadas.  

---

## Tolerancia a fallos

El sistema considera varios tipos de fallos típicos en entornos distribuidos. A nivel de cliente, se contempla la caída de un peer a mitad de descarga y los timeouts de conexión. En ambos casos, si un peer deja de responder o se produce un timeout, el cliente descarta el chunk en curso (si estaba en construcción) y repite la solicitud a otro peer disponible para el mismo torrent. Dado que la elección de peer se basa en pruebas periódicas de velocidad y estabilidad, la caída de un nodo se detecta y se evita seguir seleccionándolo en iteraciones posteriores.  

En la capa de trackers, el sistema está diseñado para seguir funcionando correctamente sin pérdida de datos mientras no se superen dos fallos simultáneos, esto es, con tolerancia a fallos de nivel 2. La información de metadatos se mantiene replicada al menos en tres trackers, por lo que el sistema puede soportar la caída de hasta dos de ellos sin perder la capacidad de resolver torrents y localizar peers. Si se caen más de dos trackers, existe riesgo de pérdida parcial de información de metadatos, aunque los datos ya replicados entre clientes seguirán existiendo.  

La incorporación de nuevos nodos también forma parte del modelo de tolerancia a fallos. Cuando un nuevo cliente se une al swarm, debe registrarse en el sistema de trackers disponibles para anunciar los torrents que sirve y poder consultar peers para nuevas descargas. Cuando un nuevo tracker aparece, se anuncia al resto de trackers, solicita un snapshot inicial de las tablas de estado y comienza a participar en el protocolo de replicación. Este comportamiento facilita tanto la recuperación ante fallos como la escalabilidad al añadir capacidad de control progresivamente.  

---

## Seguridad

En la versión actual, la comunicación entre nodos se realiza en texto plano sobre sockets, sin cifrado a nivel de transporte. Esto simplifica la implementación y facilita la depuración, pero deja el sistema expuesto a la inspección del tráfico por parte de terceros con acceso a la red. Como línea de trabajo futuro se propone incorporar TLS sobre TCP para asegurar la confidencialidad e integridad básica de las comunicaciones entre clientes y trackers, así como entre trackers entre sí.  

En cuanto a autenticación y autorización, el diseño contempla la posibilidad de asignar a cada cliente un identificador y una clave compartida, de modo que los mensajes incluyan una firma (por ejemplo, HMAC) que permita a los trackers rechazar peticiones de nodos no autorizados o claramente falsificados. Entre trackers también se podrían intercambiar claves para autenticar mensajes de replicación y evitar la introducción de información maliciosa. Aunque estas funciones no estén completamente implementadas, se describen como extensiones naturales del protocolo actual.  

El sistema ya integra validación de datos de entrada mediante modelos de Pydantic, lo que permite comprobar la forma y tipos de los mensajes antes de despacharlos a los endpoints correspondientes. Esto reduce el riesgo de fallos causados por inputs malformados y facilita aplicar políticas de seguridad adicionales (por ejemplo, filtrado de campos no esperados).  
