# Referencia del protocolo de `bit_lib`

Este documento describe el protocolo de comunicación implementado en `bit_lib/proto` y las formas principales de mensajes utilizadas en el proyecto. Coloca este archivo dentro de `bit_lib/` para que servicios y clientes consulten el contrato canónico.

## Envoltorio de mensajes (formato en la red)

- Todos los mensajes en la red usan el siguiente formato envolvente:
  - 1 byte: `msg_type` (0 = mensaje JSON, 1 = mensaje binario)
  - `SIZE_HEAD` bytes: tamaño de la carga útil (entero en big-endian). En este proyecto `SIZE_HEAD = 4`.
  - `payload` bytes: contenido real del mensaje (longitud = tamaño)

- Constantes (desde `bit_lib/bit_lib/const/c_proto.py`):
  - `ENCODING = "utf-8"`
  - `BYTEORDER = "big"`
  - `SIZE_HEAD = 4`
  - `MSG_TYPE_JSON = 0`
  - `MSG_TYPE_BINARY = 1`
  - `BLOCK_SIZE = 16384`
  - `PROTOCOL_VERSION = "2.0"`

- Nota: `MessageProtocol` en `proto/protocol.py` espera que el primer byte sea el tipo de mensaje y luego lee el tamaño usando los siguientes `SIZE_HEAD` bytes. El sobre usado es: `msg_type (1) | size (SIZE_HEAD) | payload`.

## Mensajes JSON

- Los mensajes JSON se producen mediante `DataSerialize.encode_message()` que llama a `message.model_dump_json()` (pydantic) y codifica la cadena con `UTF-8`.
- Al recibir, las cargas JSON se parsean mediante `MessageUnion.model_validate_json()` a modelos Pydantic tipados.

### Campos comunes (BaseMessage)

- `type: str` (discriminador)
- `version: str` (versión del protocolo)
- `msg_id: str` (id único, generado por defecto)
- `timestamp: int` (ns desde epoch)

### Tipos de mensaje

- `request` (Request)
  - `controller: str` — nombre lógico del controlador
  - `command: str` — nombre de la operación
  - `func: str` — identificador de función/manejador
  - `args: Optional[Data]` — argumentos (estructurados, p.ej. dict/list)

- `response` (Response)
  - `reply_to: str` — `msg_id` de la petición original
  - `data: Optional[Data]` — payload de la respuesta

- `error` (ErrorMessage, sub-clase de Response)
  - mismos campos que Response; típicamente `status`/`message` aparecen en `data` o en objetos estructurados

- `metadata` (MetaData)
  - `hash: str` — identificador del recurso / hash
  - `index: int` — índice del chunk

### Ejemplo de petición JSON

```json
{
  "type": "request",
  "controller": "Bit",
  "command": "announce",
  "func": "register_peer",
  "args": {
    "info_hash": "abc123",
    "peer_id": "peer1",
    "port": 6881,
    "left": 0
  }
}
```

### Ejemplo de respuesta JSON

```json
{
  "type": "response",
  "reply_to": "msg_...",
  "data": {
    "status": "ok",
    "peers": [ { "peer_id": "peer1", "ip": "1.2.3.4", "port": 6881 } ]
  }
}
```

## Mensajes binarios

- Los mensajes binarios usan `MSG_TYPE_BINARY` y llevan un encabezado metadata en JSON seguido del payload binario.
- El formato binario producido por `DataSerialize.encode_data(metadata, binary_data)` es:
  - `metadata_head` (SIZE_HEAD bytes) + `metadata_json_bytes` + `binary_data`
  - donde `metadata_json_bytes` es la misma codificación JSON usada por `encode_message`.
- Al recibir, `DataSerialize.decode_data()` lee la cabeza del metadata, decodifica el JSON a `MetaData` y devuelve `(metadata, binary_bytes)`.

### Caso de uso

- Transferencia de datos de chunk: enviar un `MetaData` que describa `hash` e `index`, seguido de los bytes crudos del chunk.

## Helpers de serialización

- `DataSerialize.add_head(data: bytes) -> bytes` — prefija un byte-string con un entero `SIZE_HEAD` en big-endian.
- `DataSerialize.split_head(msg: bytes) -> (size, rest)` — separa la cabeza y devuelve el entero tamaño y los bytes restantes.
- `DataSerialize.encode_message(message)` / `decode_message(bytes)` — codifica/decodifica modelos Pydantic a/desde JSON en bytes.
- `DataSerialize.encode_data(metadata, binary_data)` / `decode_data(bytes)` — codifica/decodifica metadata + payload binario.

## Biblioteca de tiempo de ejecución del protocolo

- `MessageProtocol` (subclase de `asyncio.Protocol`) en `proto/protocol.py` implementa un lector en streaming:
  - `data_received` acumula bytes en un buffer y procesa mensajes completos con framing.
  - `send_message(message: BaseMessage)` empaqueta un mensaje JSON y escribe `msg_type | head | payload`.
  - `send_binary(metadata, data_bin)` empaqueta la transferencia binaria como se describió arriba.
  - Callbacks:
    - `message_callbac` — llamado con el mensaje Pydantic parseado (`MessageUnion`) para mensajes JSON.
    - `data_chunk_callback` — llamado con `(MessageProtocol, MetaData, bytes)` para mensajes binarios.
    - `connection_callback` / `disconnect_callback` — callbacks opcionales del ciclo de vida.

## Notas y compatibilidad

- Todos los mensajes JSON deben validar contra los modelos Pydantic en `bit_lib.models`.
- Mantener `PROTOCOL_VERSION` sincronizada entre componentes; los mensajes incluyen `version` para ayudar compatibilidad.
- Este documento es el complemento canónico del código — si se cambian modelos en `bit_lib/models`, actualiza `bit_lib/MODELS.md` y este archivo.

Referencias:

- `bit_lib/bit_lib/proto/message.py` (DataSerialize)
- `bit_lib/bit_lib/proto/protocol.py` (MessageProtocol)
- `bit_lib/bit_lib/models/message.py` (tipos de mensaje)
