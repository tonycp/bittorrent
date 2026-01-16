from __future__ import annotations
from dataclasses import dataclass
from typing import Dict
import logging

from bit_lib.errors.errors import ServiceError
from bit_lib.models import Request, Response
from bit_lib.proto.protocol import MProtocol

from ._client import ClientService
from ._host import HostService

import ipaddress
import asyncio
import socket
import time

__all__ = ["PingSweepDiscovery", "DockerDNSDiscovery"]

logger = logging.getLogger(__name__)


@dataclass
class TTLCache:
    ips: list[str]
    timestamp: float
    alive: bool = False


class DiscoveryService(HostService, ClientService):
    def __init__(self, host: str, port: int, ttl: int = 30):
        # Use super() for proper MRO handling
        super().__init__(host, port)
        self.ttl = ttl
        self._cache: Dict[str, TTLCache] = {}

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
        logger.debug(
            f"DiscoveryService: received response reply_to={response.reply_to}"
        )
        # Route to ClientService to resolve pending futures
        from ._client import ClientService as _Client

        await _Client._handle_response(self, protocol, response)

    async def _handle_error(self, protocol: MProtocol, error):
        logger.error(
            f"DiscoveryService: received error: {getattr(error, 'data', error)}"
        )
        from ._client import ClientService as _Client

        await _Client._handle_error(self, protocol, error)

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
            cached_result = self._cache[key].alive
            logger.debug(f"PingSweep: cached ping to {host}:{port} = {cached_result}")
            return cached_result

        try:
            # Build a minimal valid request; remote may return an error response,
            # but that's sufficient to confirm liveness.
            request = Request(
                controller="Discovery",
                command="get",
                func="ping",
                args={},
            )
            logger.debug(f"PingSweep: sending ping to {host}:{port}...")
            try:
                response = await self.request(
                    host,
                    port,
                    request,
                    timeout=timeout,
                )
                logger.debug(
                    f"PingSweep: response from {host}:{port}: type={type(response).__name__}, response={response}"
                )
                alive = isinstance(response, Response)
                self.update_cache(key=key, alive=alive)
                if alive:
                    logger.info(f"PingSweep: FOUND ALIVE PEER at {host}:{port}!")
            except TypeError as te:
                logger.error(
                    f"PingSweep: TypeError when pinging {host}:{port}: {te}",
                    exc_info=True,
                )
                raise
        except Exception as e:
            # Any failure means host not alive for our purposes
            logger.debug(f"PingSweep: ping to {host}:{port} failed: {e}")
            alive = False

        return alive

    async def ping_range(
        self,
        subnet: str,
        port: int,
        timeout: float = 2.0,
        max_workers: int = 10,
        use_cache: bool = True,
        return_new_only: bool = False,
    ) -> list[tuple[str, int]]:
        """Escanea subnet buscando hosts activos. Retorna lista de (ip, port) vivos."""

        # If cache is valid, use it
        if use_cache and self._is_cache_valid(subnet):
            cached_ips = self._cache[subnet].ips
            logger.debug(
                f"PingSweep: cached resolve for {subnet}, got {len(cached_ips)} IPs"
            )
            # Convert cached IPs to (ip, port) tuples
            cached_peers = [(ip, port) for ip in cached_ips]
            return [] if return_new_only else cached_peers

        # Get old IPs for comparison if needed
        old_ips = set()
        if return_new_only and subnet in self._cache:
            old_ips = set(self._cache[subnet].ips)

        semaphore = asyncio.Semaphore(max_workers)

        async def _ping_with_sem(ip: str):
            async with semaphore:
                try:
                    ip_str = f"{ip}"
                    # Skip common gateway addresses and self.host
                    if ip_str.endswith(".1") or ip_str == self.host:
                        return None
                    is_alive = await self.ping(
                        ip_str, port, use_cache=True, timeout=timeout
                    )
                    return (ip_str, port) if is_alive else None
                except Exception as e:
                    logger.warning(f"PingSweep: error pinging host={ip}: {e}")
                    return None

        network = ipaddress.ip_network(subnet, strict=False)
        hosts = [f"{host}" for host in network.hosts()]
        logger.debug(f"PingSweep: subnet={subnet}, hosts_to_probe={len(hosts)}")
        logger.debug(
            f"PingSweep: scanning IPs: {hosts[:10]}...{hosts[-5:] if len(hosts) > 10 else ''}"
        )
        results = await asyncio.gather(
            *(_ping_with_sem(h) for h in hosts), return_exceptions=False
        )
        alive_peers = [r for r in results if r is not None]

        # Cache the result: store just IPs, not tuples
        alive_ips = [ip for ip, _ in alive_peers]
        self.update_cache(key=subnet, ips=alive_ips)

        logger.info(f"PingSweep: alive_peers={len(alive_peers)}")

        # Filter to only new peers if requested
        if return_new_only:
            new_peers = [(ip, port) for ip, port in alive_peers if ip not in old_ips]
            logger.debug(
                f"PingSweep: {subnet} found {len(new_peers)} new peers (total: {len(alive_peers)})"
            )
            return new_peers

        return alive_peers

    async def _handle_request(self, protocol, request: Request):
        """Handle discovery ping requests"""
        # For ping requests, respond with liveness confirmation
        if request.func == "ping":
            response = request.build_response(
                {
                    "alive": True,
                    "host": self.host,
                    "port": self.port,
                }
            )
            logger.debug(f"PingSweep: responded to ping from {request}")
        else:
            # Unknown request
            err = ServiceError(details={"error": f"Unknown func: {request.func}"})
            response = request.build_error(err.to_dict())

        await self.send_message(protocol, response)


class DockerDNSDiscovery(DiscoveryService):
    async def resolve_service(
        self, service_name: str, use_cache: bool = True, return_new_only: bool = False
    ) -> list[str]:
        if not service_name:
            raise ValueError("Service name must be provided")

        # If cache is valid, use it
        if use_cache and self._is_cache_valid(service_name):
            cached_ips = self._cache[service_name].ips
            logger.debug(f"DockerDNS: cached resolve for {service_name} = {cached_ips}")
            return [] if return_new_only else cached_ips

        # Get old IPs for comparison if needed
        old_ips = set()
        if return_new_only and service_name in self._cache:
            old_ips = set(self._cache[service_name].ips)

        ips: list[str] = []

        # Try plain service name (works with docker-compose + network aliases)
        try:
            addrinfo = await self.loop.getaddrinfo(
                host=service_name,
                port=None,
                family=socket.AF_INET,
            )
            ips = list(set(sockaddr[0] for _, _, _, _, sockaddr in addrinfo))
        except Exception:
            logger.debug(f"DockerDNS: no DNS entries for service {service_name}")
            ips = []

        self.update_cache(key=service_name, ips=ips)

        # Filter to only new IPs if requested
        if return_new_only:
            new_ips = [ip for ip in ips if ip not in old_ips]
            logger.debug(
                f"DockerDNS: {service_name} found {len(new_ips)} new IPs (total: {len(ips)})"
            )
            return new_ips

        return ips

    async def _handle_request(self, protocol: MProtocol, request: Request):
        """Handle discovery ping requests"""
        # For ping requests, respond with liveness confirmation
        if request.func == "ping":
            response = request.build_response(
                {
                    "alive": True,
                    "host": self.host,
                    "port": self.port,
                }
            )
            logger.debug(f"DockerDNS: responded to ping from {request}")
        else:
            # Unknown request
            err = ServiceError(details={"error": f"Unknown func: {request.func}"})
            response = request.build_error(err.to_dict())

        await self.send_message(protocol, response)
