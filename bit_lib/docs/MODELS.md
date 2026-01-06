# Referencia de modelos de `bit_lib`

Este archivo lista los modelos Pydantic principales y las dataclasses usadas por `bit_lib`.

## Modelos principales (Pydantic)

Ubicados en `bit_lib/models/message.py`.

- BaseMessage
  - `type: str` (discriminador)
  - `version: str` (por defecto `PROTOCOL_VERSION`)
  - `msg_id: str` (por defecto id generado tipo uuid)
  - `timestamp: int` (por defecto `time.time_ns`)

- MetaData (BaseMessage)
  - `type`: "metadata"
  - `hash: str` — hash del recurso
  - `index: int` — índice del chunk

- Request (BaseMessage)
  - `type`: "request"
  - `controller: str`
  - `command: str`
  - `func: str`
  - `args: Optional[Data]` — datos estructurados arbitrarios (ver `typing`)

- Response (BaseMessage)
  - `type`: "response"
  - `reply_to: str` — id del mensaje original
  - `data: Optional[Data]` — payload de la respuesta

- ErrorMessage (Response)
  - `type`: "error"

- MessageUnion: `Union[Request, Response, ErrorMessage, MetaData]`

## Modelos auxiliares de respuesta

Ubicados en `bit_lib/models/responses.py`.

- SuccessResponse
  - `status: str` (por defecto "ok")
  - `message: Optional[str]`

- HandshakeSuccess (extiende SuccessResponse)
  - `protocol_version: str`

- KeepaliveSuccess
  - `last_announce: datetime`

- RegisterSuccess
  - `info_hash: str`

## Header y utilidades

Ubicados en `bit_lib/models/header.py`.

- Header (dataclass)
  - `controller: str`
  - `command: str`
  - `func: str`
  - `args: List[str]`

- `decode_request(request: Request) -> (Header, Dict)`
  - mapea una `Request` a `Header` y devuelve el dict `args` original

- `process_header(header: Header)`
  - devuelve `(endpoint, gen_index(command, func, args))` usado como identificación de endpoint

## Modelos de bloques y chunks

- `BlockInfo` (dataclass, `bit_lib/models/blockinfo.py`)
  - `offset: int`
  - `size: int`
  - `data: Optional[bytes]`
  - `received: bool`

## Aliases de tipos y helpers

Consulta `bit_lib/models/typing.py` para los tipos reutilizados en handlers y controladores (`Controller`, `Handler`, `Data`, etc.). Estos alias son referenciados por `args` y `data` en `Request/Response`.

## Dónde actualizar

- Cuando cambies un modelo Pydantic en `bit_lib/models`, actualiza este `MODELS.md` y, si las formas de mensaje cambian, también actualiza `bit_lib/PROTOCOL.md` para mantener la documentación sincronizada.
