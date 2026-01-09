"""DTOs para operaciones del registro de trackers distribuidos"""

from bit_lib.models.typing import DataSet

# Registrar/actualizar tracker en la red
REGISTER_TRACKER_DATASET: DataSet = {
    "tracker_id": (str, ...),
    "host": (str, ...),
    "port": (int, ...),
    "status": (str, "online"),
    "vector_clock": (dict, ...),
}

# Obtener tracker por tracker_id
GET_TRACKER_DATASET: DataSet = {
    "tracker_id": (str, ...),
}

# Obtener trackers activos
GET_ACTIVE_TRACKERS_DATASET: DataSet = {
    "ttl_minutes": (int, 30),
}

# Actualizar last_seen de un tracker
UPDATE_LAST_SEEN_DATASET: DataSet = {
    "tracker_id": (str, ...),
}

# Marcar tracker como inactivo
MARK_INACTIVE_DATASET: DataSet = {
    "tracker_id": (str, ...),
}

# Eliminar trackers muertos
REMOVE_DEAD_TRACKERS_DATASET: DataSet = {
    "ttl_minutes": (int, 60),
}

# Obtener todos los trackers
GET_ALL_TRACKERS_DATASET: DataSet = {}
