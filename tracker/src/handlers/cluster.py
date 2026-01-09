"""Handler para operaciones de cluster y coordinación entre trackers."""

from bit_lib.handlers.crud import get, update
from bit_lib.handlers.hander import BaseHandler
from bit_lib.tools.controller import controller
from bit_lib.context import VectorClock
from bit_lib.models import DataResponse

from src.models import (
    ClusterState,
    ElectionResponse,
)
from src.models.cluster import TrackerState

from . import dtos


@controller("Cluster")
class ClusterHandler(BaseHandler):
    def __init__(self, cluster_state: ClusterState):
        super().__init__()
        self.state = cluster_state

    @update(dtos.JOIN_DATASET)
    async def join(self, remote: TrackerState):
        """Recibe anuncio de un tracker que se une al cluster (Bully convergence)"""

        # Obtener tracker local desde ClusterState (extrae solo campos comunes)
        local_tracker = TrackerState.model_validate(self.state, from_attributes=True)

        # Bully: elegir el máximo entre local y remoto
        # Criterio: max(query_count DESC, tracker_id DESC)
        candidates = [local_tracker, remote]
        winner = max(candidates, key=lambda t: (t.query_count, t.tracker_id))

        new_coordinator = winner.tracker_id

        # Actualizar estado: ambos trackers saben quién ganó
        self.state.is_coordinator = new_coordinator == self.state.tracker_id
        self.state.coordinator_id = new_coordinator

        # Marcar coordinador en ambos
        local_tracker.is_coordinator = local_tracker.tracker_id == new_coordinator
        remote.is_coordinator = remote.tracker_id == new_coordinator

        # Guardar remote en caché (no guardar local, es ruido)
        await self.state.cache.set(remote.tracker_id, remote)

        # Merge de vector clocks (actualizar causalidad)
        await self.state.vector_clock.merge(remote.vector_clock)

        return DataResponse(
            data={
                "local_state": local_tracker,
                "new_coordinator": new_coordinator,  # Ambos ahora saben el mismo líder
            }
        )

    @update(dtos.CLUSTER_HEARTBEAT_DATASET)
    async def heartbeat(
        self,
        tracker_id: str,
        query_count: int,
        vector_clock: VectorClock,
    ):
        """Recibe heartbeat de un tracker para actualizar liveness"""
        # Obtener tracker de caché
        tracker = await self.state.cache.get(tracker_id)

        if tracker:
            # Actualizar vector clock y query_count
            tracker.vector_clock = vector_clock
            tracker.query_count = query_count

            # Actualizar en caché (refresca timestamp automáticamente)
            await self.state.cache.set(tracker_id, tracker)
        else:
            # Si no existe, crearlo (nuevo tracker descubierto vía heartbeat)
            new_tracker = TrackerState(
                tracker_id=tracker_id,
                host="unknown",  # Se actualizará en próximo JOIN
                port=0,
                vector_clock=vector_clock,
                is_coordinator=False,
            )
            new_tracker.query_count = query_count
            await self.state.cache.set(tracker_id, new_tracker)

        # Merge vector clocks
        await self.state.vector_clock.merge(vector_clock)

        return DataResponse(
            data={
                "status": "ack",
                "tracker_id": self.state.tracker_id,
                "is_coordinator": self.state.is_coordinator,
                "coordinator_id": self.state.coordinator_id,
            }
        )

    @get(dtos.VIEW_DATASET)
    async def view(self):
        """Retorna vista del cluster con trackers activos"""
        # Obtener todos los trackers no expirados de la caché
        active_trackers = []

        for _, tracker_state in self.state.cache.items():
            active_trackers.append(tracker_state)

        return DataResponse(
            data={
                "trackers": active_trackers,
                "coordinator_id": self.state.coordinator_id,
                "total": len(active_trackers),
            }
        )

    @update(dtos.NORMALIZE_DATASET)
    async def normalize(self, delta: int):
        """Recibe comando de normalización del líder y aplica delta a query_count local"""
        # Obtener tracker propio desde ClusterState (extrae solo campos comunes)
        local_tracker = TrackerState.model_validate(self.state, from_attributes=True)

        # Aplicar normalización con clamp a 0
        current_count = local_tracker.query_count
        new_count = max(0, current_count - delta)

        # Aquí se debería persistir en BD vía TrackerRepository
        # Por ahora solo actualizamos en memoria
        # TODO: Integrar con TrackerRepository para persistir query_count

        return DataResponse(
            data={
                "status": "normalized",
                "tracker_id": self.state.tracker_id,
                "old_count": current_count,
                "new_count": new_count,
                "delta": delta,
            }
        )

    @get(dtos.ELECTION_DATASET)
    async def election(self, candidate_id: str, query_count: int):
        """
        Responde a solicitud de elección (Algoritmo Bully).
        Si tengo mayor (query_count, tracker_id), respondo con ElectionResponse.
        ClusterService detecta ElectionResponse y propaga automáticamente.
        """
        local_tracker = TrackerState.model_validate(self.state, from_attributes=True)
        local_count = local_tracker.query_count

        # Bully: Si tengo más que el candidato, soy mejor candidato
        if local_count > query_count or (
            local_count == query_count and self.state.tracker_id > candidate_id
        ):
            # Yo soy mejor candidato
            return ElectionResponse(
                candidate_id=self.state.tracker_id,
                query_count=local_count,
                should_propagate=True,
            )
        else:
            # Candidato es mejor, lo acepto
            return ElectionResponse(
                candidate_id=candidate_id,
                query_count=query_count,
                should_propagate=False,
            )
