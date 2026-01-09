from __future__ import annotations
from dataclasses import dataclass
from typing import Dict

from bit_lib.errors.errors import ServiceError
from bit_lib.models import Request, Response, decode_request
from bit_lib.proto.protocol import MProtocol

from ._client import ClientService
from ._host import HostService

import ipaddress
import asyncio
import socket
import time

__all__ = ["PingSweepDiscovery", "DockerDNSDiscovery"]


@dataclass
class TTLCache:
    ips: list[str]
    timestamp: float
    alive: bool = False


class DiscoveryService(HostService, ClientService):
    def __init__(self, host: str, port: int, ttl: int = 30):
        self.ttl = ttl
        self._cache: Dict[str, TTLCache] = {}
        super().__init__(host, port)

    def _is_cache_valid(self, host: str) -> bool:
        if host not in self._cache:
            return False

        cached = self._cache[host]
        elapsed = time.time() - cached.timestamp
        return elapsed < self.ttl

    def update_cache(self, key: str, alive: bool = False, ips: list[str] = []):
        self._cache[key] = TTLCache(
            ips=ips,
            timestamp=time.time(),
            alive=alive,
        )

    def clear_cache(self, host: str | None = None):
        if host is None:
            self._cache.clear()
        else:
            self._cache.pop(host, None)

    async def _handle_response(self, protocol: MProtocol, response: Response):
        await super()._handle_response(protocol, response)

    async def _handle_error(self, protocol: MProtocol, error):
        await super()._handle_error(protocol, error)

    async def _handle_request(self, protocol: MProtocol, request: Request):
        raise NotImplementedError("Subclass must implement _handle_request")

    async def _on_connect(self, protocol):
        await super()._on_connect(protocol)

    async def _on_disconnect(self, protocol, exc):
        await super()._on_disconnect(protocol, exc)

    async def _handle_binary(self, protocol: MProtocol, meta, data):
        pass  # No binary handling needed for ping-sweep


class PingSweepDiscovery(DiscoveryService):
    async def ping(
        self,
        host: str,
        port: int,
        use_cache: bool = True,
        timeout: float = 3.0,
    ) -> bool:
        key = f"{host}:{port}"

        if use_cache and self._is_cache_valid(key):
            return self._cache[key].alive

        try:
            # Build a minimal valid request; remote may return an error response,
            # but that's sufficient to confirm liveness.
            request = Request(
                controller="Discovery",
                command="ping",
                func="ping",
                args=None,
            )
            response = await self.request(
                host,
                port,
                request,
                timeout=timeout,
            )
            alive = isinstance(response, Response)
        except (asyncio.TimeoutError, ConnectionError, OSError):
            alive = False

        self.update_cache(key=key, alive=alive)
        return alive

    async def ping_range(
        self,
        subnet: str,
        port: int,
        use_cache: bool = True,
        timeout: float = 2.0,
        max_workers: int = 10,
    ) -> list[tuple[str, int]]:
        alive_peers = []
        semaphore = asyncio.Semaphore(max_workers)

        async def _ping_with_sem(ip: str):
            async with semaphore:
                is_alive = await self.ping(ip, port, use_cache, timeout)
                return (ip, port) if is_alive else None

        network = ipaddress.ip_network(subnet, strict=False)
        tasks = [_ping_with_sem(host) for host in network.hosts()]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        alive_peers = [r for r in results if r is not None]

        return alive_peers

    async def _handle_request(self, protocol, request: Request):
        ips = [k for k, v in self._cache.items() if v.alive]
        response = request.build_response({"ips": ips, "service": self.host})
        return await self.send_message(protocol, response)


class DockerDNSDiscovery(DiscoveryService):
    async def resolve_service(
        self, service_name: str, use_cache: bool = True
    ) -> list[str]:
        if not service_name:
            raise ValueError("Service name must be provided")

        if use_cache and self._is_cache_valid(service_name):
            return self._cache[service_name].ips

        addrinfo = await self.loop.getaddrinfo(
            host=f"tasks.{service_name}",
            port=None,
            family=socket.AF_INET,
        )
        ips = list(set(sockaddr[0] for _, _, _, _, sockaddr in addrinfo))

        self.update_cache(key=service_name, ips=ips)
        return ips

    async def _handle_request(self, protocol: MProtocol, request: Request):
        _, data = decode_request(request)
        service_name = data.get("service") if data else None

        try:
            ips = await self.resolve_service(service_name, use_cache=True)
            response = request.build_response({"ips": ips, "service": service_name})
        except Exception as e:
            details = {"error_type": type(e).__name__}
            err = ServiceError(details=details)
            response = request.build_error(err.to_dict())

        await self.send_message(protocol, response)
