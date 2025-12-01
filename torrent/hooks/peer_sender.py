from shared.hooks import BaseHook
from shared.hooks.actions import send_command, request_data, send_data


class PeerSender(BaseHook):
    """
    Define todos los mensajes que este cliente puede enviar a otros peers.
    """

    @send_command
    def handshake(self, client_id: str, info_hash: str):
        # Los argumentos de esta función se pasan automáticamente a kwargs
        # y luego al create_hook
        return {}

    @send_command
    def keep_alive(self):
        return {}

    @send_command
    def choke(self):
        return {}

    @send_command
    def unchoke(self):
        return {}

    @send_command
    def interested(self):
        return {}

    @request_data
    def request_piece(self, index: int, begin: int, length: int):
        # Esto generará un Request con args={"index":..., "begin":...}
        return {}

    @send_data
    def piece(self, index: int, begin: int, block: bytes):
        # Nota: Para datos binarios grandes, quizás quieras un manejo especial
        # pero por ahora el protocolo lo manejará como JSON/Bytes híbrido si usas tu dts.
        return {}
