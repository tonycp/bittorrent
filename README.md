# bittorrent

## Test environment wizard (sin docker-compose)

El entorno de pruebas puede levantarse con un asistente interactivo:

```bash
python tests/env_wizard.py up
```

También puedes pasar parámetros y completar el resto en el wizard:

```bash
python tests/env_wizard.py up --trackers 4 --clients 2 --network torrent_net
```

El script crea red, imágenes y contenedores usando comandos `docker` directos.
