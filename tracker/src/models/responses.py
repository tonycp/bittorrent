from bit_lib.models.responses import SuccessResponse
from pydantic import Field


class ElectionResponse(SuccessResponse):
    """Respuesta especial para Bully election - indica propagación necesaria"""

    candidate_id: str = Field(description="ID del mejor candidato según Bully")
    query_count: int = Field(description="Query count del candidato")
    should_propagate: bool = Field(
        description="True si ClusterService debe propagar a otros trackers"
    )
