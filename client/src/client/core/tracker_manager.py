import asyncio
import logging
import re
import socket
import time
from typing import Optional, List, Dict, Any

from ..config.utils import get_env_settings
from ..config.config_mng import ConfigManager
from ..connection.tracker_client import TrackerClient

logger = logging.getLogger(__name__)


class TrackerManager:
    """Manager para comunicación con trackers usando bit_lib"""

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.env_settings = get_env_settings()

        # Cliente asíncrono para trackers (bit_lib)
        self.tracker_client: Optional[TrackerClient] = None

        # Cache de trackers conocidos (para tolerancia a fallos)
        self._known_trackers: List[tuple] = []
        self._current_tracker_idx = 0

        # Tracker actual conectado (para GUI)
        self._current_tracker: Optional[tuple] = None
        # Estado por tracker para UI/monitoring
        self._tracker_status: Dict[tuple, Dict[str, Any]] = {}

    @staticmethod
    def _resolve_host_to_ip(host: str) -> str:
        """Resuelve hostname a IP para mostrar en GUI; fallback al host original."""
        try:
            return socket.gethostbyname(host)
        except Exception:
            return host

    def _bootstrap_trackers(self, tracker_host: str, tracker_port: int):
        """Añade trackers del clúster desde el tracker principal (tracker-1..tracker-4)."""
        base_match = re.match(r"^(tracker)(?:-(\d+))?$", tracker_host)
        if not base_match:
            return

        base_name = base_match.group(1)
        for index in range(1, 5):
            host = f"{base_name}-{index}"
            self.add_tracker(host, tracker_port)

    @staticmethod
    def _get_client_ip(target_host: str = None) -> str:
        """Obtiene IP local enrutable del cliente (evita loopback 127.x).

        Si se proporciona target_host, conecta a ese host para determinar
        la interfaz correcta de red.
        """
        connect_host = target_host if target_host else "8.8.8.8"

        # Método principal: socket UDP "connect" para descubrir interfaz activa.
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect((connect_host, 80))
                ip = sock.getsockname()[0]
                if ip and not ip.startswith("127.") and ip != "0.0.0.0":
                    return ip
        except Exception:
            pass

        # Fallback: resolver hostname, pero ignorar loopback.
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            if ip and not ip.startswith("127.") and ip != "0.0.0.0":
                return ip
        except Exception:
            pass

        return "127.0.0.1"

    async def start(self):
        """Inicia el cliente de tracker (async)"""
        current_loop = asyncio.get_running_loop()

        needs_client = self.tracker_client is None
        if not needs_client:
            client_loop = getattr(self.tracker_client, "loop", None)
            needs_client = (
                client_loop is None
                or client_loop.is_closed()
                or client_loop is not current_loop
            )

        if needs_client:
            self.tracker_client = TrackerClient(loop=current_loop)
            await self.tracker_client.start()

            # Inicializar lista de trackers conocidos desde config
            tracker_host, tracker_port = self.config_manager.get_tracker_address()
            self._bootstrap_trackers(tracker_host, tracker_port)
            tracker_tuple = (tracker_host, tracker_port)
            if tracker_tuple not in self._known_trackers:
                self._known_trackers.append(tracker_tuple)

            self._current_tracker = tracker_tuple
            self._tracker_status[tracker_tuple] = {
                "state": "checking",
                "latency_ms": None,
                "last_check": time.time(),
                "last_error": "",
                "display_ip": self._resolve_host_to_ip(tracker_host),
            }

            logger.info(
                f"TrackerManager iniciado (tracker principal: {tracker_host}:{tracker_port})"
            )

    async def stop(self):
        """Detiene el cliente de tracker"""
        if self.tracker_client:
            await self.tracker_client.stop()
            logger.info("TrackerManager detenido")

    def get_current_tracker(self) -> Optional[tuple]:
        """Retorna el tracker actual conectado (host, port)"""
        return self._current_tracker

    def get_tracker_display_ip(self, host: str) -> str:
        """Retorna IP de display para un host de tracker."""
        return self._resolve_host_to_ip(host)

    def get_known_trackers(self) -> List[tuple]:
        """Retorna lista de trackers conocidos"""
        return self._known_trackers.copy()

    def get_tracker_statuses(self) -> List[Dict[str, Any]]:
        """Retorna estado de trackers conocidos para mostrar en GUI."""
        statuses: List[Dict[str, Any]] = []
        for host, port in self._known_trackers:
            tracker_key = (host, port)
            raw = self._tracker_status.get(tracker_key, {})
            statuses.append(
                {
                    "host": host,
                    "display_ip": raw.get("display_ip", self._resolve_host_to_ip(host)),
                    "port": port,
                    "state": raw.get("state", "down"),
                    "latency_ms": raw.get("latency_ms"),
                    "last_check": raw.get("last_check"),
                    "last_error": raw.get("last_error", ""),
                    "is_current": tracker_key == self._current_tracker,
                }
            )
        return statuses

    def is_tracker_session_active(self) -> bool:
        """Indica si el cliente de tracker está iniciado en esta sesión."""
        return bool(
            self.tracker_client and getattr(self.tracker_client, "_running", False)
        )

    def add_tracker(self, host: str, port: int):
        """Añade un tracker a la lista de conocidos"""
        tracker_tuple = (host, port)
        if tracker_tuple not in self._known_trackers:
            self._known_trackers.append(tracker_tuple)
            self._tracker_status[tracker_tuple] = {
                "state": "down",
                "latency_ms": None,
                "last_check": None,
                "last_error": "Sin verificar",
                "display_ip": self._resolve_host_to_ip(host),
            }
            logger.info(f"Tracker añadido: {host}:{port}")

    def prefer_tracker(self, host: str, port: int):
        """Marca un tracker como preferido para próximos requests."""
        tracker_tuple = (host, port)
        self.add_tracker(host, port)

        try:
            idx = self._known_trackers.index(tracker_tuple)
            self._current_tracker_idx = idx
            self._current_tracker = tracker_tuple
            status = self._tracker_status.get(tracker_tuple, {})
            status["state"] = status.get("state", "checking")
            status["last_check"] = time.time()
            self._tracker_status[tracker_tuple] = status
            logger.info(f"Tracker preferido: {host}:{port}")
        except ValueError:
            logger.warning(f"No se pudo marcar tracker preferido: {host}:{port}")

    async def _check_tracker_alive(
        self, host: str, port: int, timeout: float = 2.0
    ) -> Dict[str, Any]:
        """Verifica si un tracker está vivo por conexión TCP simple."""
        started = time.perf_counter()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout,
            )
            writer.close()
            await writer.wait_closed()
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            return {
                "state": "active",
                "latency_ms": elapsed_ms,
                "last_error": "",
            }
        except Exception as e:
            return {
                "state": "down",
                "latency_ms": None,
                "last_error": str(e)[:120],
            }

    async def refresh_tracker_health_async(self, timeout: float = 2.0):
        """Actualiza estado de vida de todos los trackers conocidos."""
        if not self._known_trackers:
            return

        checking_at = time.time()
        for host, port in self._known_trackers:
            tracker = (host, port)
            prev = self._tracker_status.get(tracker, {})
            self._tracker_status[tracker] = {
                "state": "checking",
                "latency_ms": prev.get("latency_ms"),
                "last_check": checking_at,
                "last_error": "",
                "display_ip": prev.get("display_ip", self._resolve_host_to_ip(host)),
            }

        checks = [
            self._check_tracker_alive(host, port, timeout=timeout)
            for host, port in self._known_trackers
        ]
        results = await asyncio.gather(*checks, return_exceptions=True)
        checked_at = time.time()

        for tracker, result in zip(self._known_trackers, results):
            host, port = tracker
            if isinstance(result, Exception):
                self._tracker_status[tracker] = {
                    "state": "down",
                    "latency_ms": None,
                    "last_check": checked_at,
                    "last_error": str(result)[:120],
                    "display_ip": self._resolve_host_to_ip(host),
                }
                continue

            self._tracker_status[tracker] = {
                "state": result.get("state", "down"),
                "latency_ms": result.get("latency_ms"),
                "last_check": checked_at,
                "last_error": result.get("last_error", ""),
                "display_ip": self._resolve_host_to_ip(host),
            }

    # ==================== Métodos Asíncronos (core) ====================

    async def register_torrent_async(
        self,
        torrent_hash: str,
        file_name: str,
        file_size: int,
        total_chunks: int,
        piece_length: int = 16384,
    ) -> bool:
        """Registra torrent en tracker (async) - load balances entre trackers"""
        if not self.tracker_client:
            await self.start()

        # Intentar con trackers conocidos hasta que uno funcione, rotando para load balance
        num_trackers = len(self._known_trackers)
        if num_trackers == 0:
            logger.error("No hay trackers conocidos para registrar")
            return False

        for attempt in range(num_trackers):
            idx = (self._current_tracker_idx + attempt) % num_trackers
            tracker_host, tracker_port = self._known_trackers[idx]

            try:
                success = await self.tracker_client.register_torrent(
                    tracker_host=tracker_host,
                    tracker_port=tracker_port,
                    torrent_hash=torrent_hash,
                    file_name=file_name,
                    file_size=file_size,
                    total_chunks=total_chunks,
                    piece_length=piece_length,
                )

                if success:
                    self._current_tracker = (tracker_host, tracker_port)
                    self._current_tracker_idx = idx
                    self._tracker_status[(tracker_host, tracker_port)] = {
                        "state": "active",
                        "latency_ms": self._tracker_status.get(
                            (tracker_host, tracker_port), {}
                        ).get("latency_ms"),
                        "last_check": time.time(),
                        "last_error": "",
                        "display_ip": self._resolve_host_to_ip(tracker_host),
                    }
                    logger.info(
                        f"Torrent {torrent_hash[:8]} registrado en {tracker_host}:{tracker_port}"
                    )
                    return True
            except Exception as e:
                self._tracker_status[(tracker_host, tracker_port)] = {
                    "state": "down",
                    "latency_ms": None,
                    "last_check": time.time(),
                    "last_error": str(e)[:120],
                    "display_ip": self._resolve_host_to_ip(tracker_host),
                }
                logger.warning(
                    f"Error registrando en tracker {tracker_host}:{tracker_port}: {e}"
                )
                continue

        logger.error("No se pudo registrar el torrent en ningún tracker")
        return False

    async def get_peers_async(self, info_hash: str) -> List[Dict[str, Any]]:
        """Obtiene peers para un torrent (async) - load balances entre trackers"""
        if not self.tracker_client:
            await self.start()

        # Intentar con trackers conocidos, rotando el índice para load balance
        num_trackers = len(self._known_trackers)
        if num_trackers == 0:
            logger.warning("No hay trackers conocidos")
            return []

        for attempt in range(num_trackers):
            idx = (self._current_tracker_idx + attempt) % num_trackers
            tracker_host, tracker_port = self._known_trackers[idx]

            try:
                peers = await self.tracker_client.get_peers(
                    tracker_host=tracker_host,
                    tracker_port=tracker_port,
                    torrent_hash=info_hash,
                )

                if peers:
                    # Actualizar índice actual para próxima llamada
                    self._current_tracker_idx = (idx + 1) % num_trackers
                    self._current_tracker = (tracker_host, tracker_port)
                    self._tracker_status[(tracker_host, tracker_port)] = {
                        "state": "active",
                        "latency_ms": self._tracker_status.get(
                            (tracker_host, tracker_port), {}
                        ).get("latency_ms"),
                        "last_check": time.time(),
                        "last_error": "",
                        "display_ip": self._resolve_host_to_ip(tracker_host),
                    }
                    logger.info(
                        f"Obtenidos {len(peers)} peers de {tracker_host}:{tracker_port}"
                    )
                    return peers
            except Exception as e:
                self._tracker_status[(tracker_host, tracker_port)] = {
                    "state": "down",
                    "latency_ms": None,
                    "last_check": time.time(),
                    "last_error": str(e)[:120],
                    "display_ip": self._resolve_host_to_ip(tracker_host),
                }
                logger.warning(
                    f"Error obteniendo peers de {tracker_host}:{tracker_port}: {e}"
                )
                continue

        logger.warning(f"No se pudieron obtener peers para {info_hash[:8]}")
        return []

    async def announce_async(
        self,
        info_hash: str,
        peer_id: str,
        uploaded: int = 0,
        downloaded: int = 0,
        left: int = 0,
    ):
        """Anuncia peer al tracker (async)"""
        if not self.tracker_client:
            await self.start()

        num_trackers = len(self._known_trackers)
        if num_trackers == 0:
            raise RuntimeError("No hay trackers conocidos para announce")

        for attempt in range(num_trackers):
            idx = (self._current_tracker_idx + attempt) % num_trackers
            tracker_host, tracker_port = self._known_trackers[idx]
            tracker_id = f"{tracker_host}:{tracker_port}"

            try:
                response = await self.tracker_client.announce_peer(
                    tracker_host=tracker_host,
                    tracker_port=tracker_port,
                    tracker_id=tracker_id,
                    peer_id=peer_id,
                    torrent_hash=info_hash,
                    ip=self._get_client_ip(tracker_host),
                    port=self.config_manager.get_listen_port(),
                    uploaded=uploaded,
                    downloaded=downloaded,
                    left=left,
                )

                if response is None:
                    raise RuntimeError("Announce sin respuesta válida")

                self._current_tracker = (tracker_host, tracker_port)
                self._current_tracker_idx = (idx + 1) % num_trackers
                self._tracker_status[(tracker_host, tracker_port)] = {
                    "state": "active",
                    "latency_ms": self._tracker_status.get(
                        (tracker_host, tracker_port), {}
                    ).get("latency_ms"),
                    "last_check": time.time(),
                    "last_error": "",
                    "display_ip": self._resolve_host_to_ip(tracker_host),
                }
                logger.info(
                    f"Announce exitoso para {info_hash[:8]} en {tracker_host}:{tracker_port}"
                )
                return

            except Exception as e:
                self._tracker_status[(tracker_host, tracker_port)] = {
                    "state": "down",
                    "latency_ms": None,
                    "last_check": time.time(),
                    "last_error": str(e)[:120],
                    "display_ip": self._resolve_host_to_ip(tracker_host),
                }
                logger.warning(
                    f"Error en announce con {tracker_host}:{tracker_port}: {e}"
                )

        raise RuntimeError(f"No se pudo anunciar {info_hash[:8]} en ningún tracker")

    async def discover_trackers_async(self) -> List[tuple]:
        """
        Descubre trackers adicionales de la red (para tolerancia a fallos).

        En una implementación completa, esto podría usar:
        - DHT (Distributed Hash Table)
        - Tracker exchanges
        - Configuración estática
        """
        # Por ahora retornar trackers conocidos
        return self._known_trackers.copy()

    # ==================== Wrappers Síncronos (para compatibilidad) ====================

    def register_torrent(self, torrent_data, tracker_address=None) -> bool:
        """Registra torrent (sync wrapper)"""
        return asyncio.run(
            self.register_torrent_async(
                torrent_hash=torrent_data.file_hash,
                file_name=torrent_data.file_name,
                file_size=torrent_data.file_size,
                total_chunks=torrent_data.total_chunks,
            )
        )

    def get_peers(self, info_hash: str, tracker_address=None) -> List[Dict[str, Any]]:
        """Obtiene peers (sync wrapper)"""
        return asyncio.run(self.get_peers_async(info_hash))

    def announce(self, info_hash: str, peer_id: str, tracker_address=None):
        """Anuncia peer (sync wrapper)"""
        asyncio.run(self.announce_async(info_hash, peer_id))
