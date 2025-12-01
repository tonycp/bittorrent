from shared.core.client import ClientService
from torrent.hooks import PeerSender


class PeerClient(ClientService):
    def __init__(self):
        super().__init__()
        # Inicializamos el definidor de mensajes
        self.sender = PeerSender()

    async def _on_connect(self, protocol):
        await super()._on_connect(protocol)

        # EJEMPLO DE USO:
        # 1. Llamamos al hook. Esto NO envía nada, solo devuelve el objeto Request.
        msg_handshake = self.sender.handshake(
            client_id="MY_CLIENT_001", info_hash="12345..."
        )

        # 2. Usamos el servicio para enviarlo
        await self.send_message(protocol, msg_handshake)
        print("Handshake enviado!")

    async def start_download(self, index):
        # Es muy limpio leer esto:
        req = self.sender.request_piece(index=index, begin=0, length=16384)
        await self.send_message(self.protocol, req)
