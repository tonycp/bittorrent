#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
STATE_FILE = ROOT_DIR / "tests" / "env_wizard_state.json"


class WizardError(RuntimeError):
    pass


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"history": []}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"history": []}
    if not isinstance(data, dict):
        return {"history": []}
    history = data.get("history", [])
    if not isinstance(history, list):
        history = []

    normalized: list[dict] = []
    seen_hashes: set[str] = set()
    for entry in history:
        if not isinstance(entry, dict):
            continue
        args = entry.get("args", [])
        if not isinstance(args, list) or not args:
            continue
        entry_hash = entry.get("hash")
        if not isinstance(entry_hash, str) or not entry_hash:
            payload = json.dumps(args, ensure_ascii=False, separators=(",", ":"))
            entry_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        timestamp = entry.get("timestamp", datetime.now(timezone.utc).isoformat())
        if entry_hash in seen_hashes:
            continue
        seen_hashes.add(entry_hash)
        normalized.append({"hash": entry_hash, "timestamp": timestamp, "args": args})

    return {"history": normalized}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def command_hash(args_list: list[str]) -> str:
    payload = json.dumps(args_list, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def save_history(args_list: list[str]) -> tuple[bool, str]:
    state = load_state()
    history = state.setdefault("history", [])
    current_hash = command_hash(args_list)
    now = datetime.now(timezone.utc).isoformat()

    for index, entry in enumerate(history):
        if entry.get("hash") == current_hash:
            history[index] = {
                "hash": current_hash,
                "timestamp": now,
                "args": args_list,
            }
            save_state(state)
            return False, current_hash

    history.append(
        {
            "hash": current_hash,
            "timestamp": now,
            "args": args_list,
        }
    )
    max_items = 50
    if len(history) > max_items:
        del history[:-max_items]
    save_state(state)
    return True, current_hash


def ask_and_save_history(args_list: list[str], mode: str = "prompt") -> None:
    selected_mode = mode if mode in {"prompt", "save", "skip"} else "prompt"
    if selected_mode == "skip":
        return

    if selected_mode == "prompt" and not ask_bool("¿Guardar este comando en historial?", False):
        print("Comando no guardado.")
        return

    is_new, cmd_hash = save_history(args_list)
    if is_new:
        print(f"Comando guardado (hash={cmd_hash[:10]}).")
    else:
        print(f"Comando ya existía (hash={cmd_hash[:10]}). Se actualizó como reciente.")
    print("Usa 'python tests/env_wizard.py recent' para verlo.")


def args_to_shell(args_list: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in args_list)


def run(cmd: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    printable = " ".join(shlex.quote(part) for part in cmd)
    print(f"\n$ {printable}")
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=capture,
    )


def ask_text(label: str, default: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value or default


def ask_int(label: str, default: int, min_value: int = 0) -> int:
    while True:
        raw = input(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("Valor inválido. Debe ser un entero.")
            continue
        if value < min_value:
            print(f"Valor inválido. Debe ser >= {min_value}.")
            continue
        return value


def ask_bool(label: str, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{label} [{suffix}]: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes", "s", "si"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Respuesta inválida. Usa y/n.")


def docker_available() -> bool:
    return shutil.which("docker") is not None


def display_is_reachable(display: str) -> bool:
    checker = shutil.which("xdpyinfo")
    if checker is None:
        return True
    result = subprocess.run(
        [checker, "-display", display],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def enable_xhost_access() -> bool:
    xhost_cmd = shutil.which("xhost")
    if xhost_cmd is None:
        print("Aviso: 'xhost' no está instalado; no se puede autorizar Docker automáticamente.")
        return False
    result = subprocess.run(
        [xhost_cmd, "+local:docker"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        print("Acceso X11 habilitado para contenedores Docker (xhost +local:docker).")
        return True
    print("No se pudo habilitar xhost automáticamente.")
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    return False


def default_display_value() -> str:
    env_display = os.getenv("DISPLAY", "").strip()
    if env_display:
        return env_display
    if sys.platform.startswith("linux"):
        return ":0"
    return "host.docker.internal:0"


def container_exists(name: str) -> bool:
    result = run(["docker", "ps", "-a", "--format", "{{.Names}}"], capture=True)
    return name in result.stdout.splitlines()


def remove_container_if_exists(name: str) -> None:
    if container_exists(name):
        run(["docker", "rm", "-f", name])


def ensure_network(name: str, subnet: str) -> None:
    current = run(["docker", "network", "ls", "--format", "{{.Name}}"], capture=True)
    existing = set(current.stdout.splitlines())
    if name in existing:
        print(f"Red '{name}' ya existe. Se reutiliza.")
        return
    run(["docker", "network", "create", "--subnet", subnet, name])


def list_container_names() -> list[str]:
    result = run(["docker", "ps", "-a", "--format", "{{.Names}}"], capture=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def list_docker_volumes() -> list[str]:
    result = run(["docker", "volume", "ls", "--format", "{{.Name}}"], capture=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def remove_network_if_exists(name: str) -> None:
    current = run(["docker", "network", "ls", "--format", "{{.Name}}"], capture=True)
    existing = set(current.stdout.splitlines())
    if name in existing:
        run(["docker", "network", "rm", name], check=False)


def build_images(build_client: bool) -> None:
    print("\n== Build de imágenes ==")
    run(["docker", "build", "-t", "bit_lib_base:latest", str(ROOT_DIR / "bit_lib")])
    run(["docker", "build", "-t", "bt_tracker:latest", str(ROOT_DIR / "tracker")])
    if build_client:
        run(["docker", "build", "-t", "bt_client:latest", str(ROOT_DIR / "client")])


def start_trackers(
    tracker_count: int,
    network_name: str,
    subnet: str,
    rpc_start_port: int,
) -> list[tuple[str, int, int]]:
    print("\n== Levantando trackers ==")
    started: list[tuple[str, int, int]] = []
    min_cluster_size = max(1, min(3, tracker_count))

    for index in range(1, tracker_count + 1):
        name = f"tracker-{index}"
        host_rpc = rpc_start_port + ((index - 1) * 2)
        host_cluster = host_rpc + 1

        remove_container_if_exists(name)

        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "--hostname",
            name,
            "--network",
            network_name,
            "--network-alias",
            "tracker",
            "-p",
            f"{host_rpc}:5555",
            "-p",
            f"{host_cluster}:5556",
            "-v",
            f"{ROOT_DIR / 'tracker' / 'src'}:/app/src",
            "-v",
            f"{ROOT_DIR / 'bit_lib'}:/bit_lib",
            "-v",
            f"tracker{index}-data:/app/data",
            "-e",
            f"SERVICES__TRACKER_ID={name}",
            "-e",
            "SERVICES__TRACKER__HOST=0.0.0.0",
            "-e",
            "SERVICES__TRACKER__PORT=5555",
            "-e",
            "SERVICES__CLUSTER__HOST=0.0.0.0",
            "-e",
            "SERVICES__CLUSTER__PORT=5556",
            "-e",
            "SERVICES__CLUSTER__SERVICE_NAME=tracker",
            "-e",
            f"SERVICES__CLUSTER__DISCOVERY_PING_SUBNET={subnet}",
            "-e",
            f"SERVICES__CLUSTER__MIN_CLUSTER_SIZE={min_cluster_size}",
            "bt_tracker:latest",
        ]

        run(cmd)
        started.append((name, host_rpc, host_cluster))

    return started


def start_clients(
    client_count: int,
    tracker_count: int,
    network_name: str,
    with_gui: bool,
    display: str,
    peer_start_port: int,
    debug_start_port: int,
) -> list[tuple[str, int, int]]:
    print("\n== Levantando clients ==")
    started: list[tuple[str, int, int]] = []
    tracker_urls = ",".join(f"tracker-{i}:5555" for i in range(1, tracker_count + 1))
    torrents_dir = ROOT_DIR / "client" / "torrents"
    torrents_dir.mkdir(parents=True, exist_ok=True)
    xauthority = os.getenv("XAUTHORITY", str(Path.home() / ".Xauthority"))
    xauthority_path = Path(xauthority)

    for index in range(1, client_count + 1):
        name = f"client-{index}"
        peer_port = peer_start_port + (index - 1)
        debug_port = debug_start_port + (index - 1)

        remove_container_if_exists(name)

        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "--hostname",
            name,
            "--network",
            network_name,
        ]

        if with_gui:
            if sys.platform.startswith("linux") and "host.docker.internal" in display:
                cmd.extend(["--add-host", "host.docker.internal:host-gateway"])
            cmd.extend([
                "-e",
                f"DISPLAY={display}",
                "-v",
                "/tmp/.X11-unix:/tmp/.X11-unix:rw",
            ])
            if xauthority_path.exists():
                cmd.extend([
                    "-e",
                    "XAUTHORITY=/root/.Xauthority",
                    "-v",
                    f"{xauthority_path}:/root/.Xauthority:ro",
                ])
            elif sys.platform.startswith("linux"):
                print(
                    "Aviso: no se encontró XAUTHORITY; si falla GUI ejecuta 'xhost +local:docker' en el host."
                )

        cmd.extend([
            "-v",
            f"{ROOT_DIR / 'client' / 'src'}:/app/src",
            "-v",
            f"{ROOT_DIR / 'bit_lib'}:/bit_lib",
            "-v",
            f"{torrents_dir}:/app/torrents",
            "-e",
            f"LISTEN_PORT={peer_port}",
            "-e",
            f"PEER_ID={name}",
            "-e",
            "DOWNLOAD_PATH=/app/downloads",
            "-e",
            "TORRENT_PATH=/app/torrents",
            "-e",
            "TRACKER_HOST=tracker-1",
            "-e",
            "TRACKER_PORT=5555",
            "-e",
            f"TRACKER_URLS={tracker_urls}",
        ])

        cmd.extend([
            "--tmpfs",
            "/app/downloads",
            "--tmpfs",
            "/app/config",
        ])

        if with_gui:
            cmd.append("bt_client:latest")
        else:
            cmd.extend([
                "--entrypoint",
                "/bin/sh",
                "bt_client:latest",
                "-lc",
                "uv sync --extra libs --no-managed-python && xvfb-run -a uv run client",
            ])

        run(cmd)
        started.append((name, peer_port, debug_port))

    return started


def print_summary(
    network_name: str,
    subnet: str,
    trackers: list[tuple[str, int, int]],
    clients: list[tuple[str, int, int]],
) -> None:
    print("\n=== Resumen ===")
    print(f"Red: {network_name} ({subnet})")
    print(f"Trackers: {len(trackers)}")
    for name, rpc_port, cluster_port in trackers:
        print(f"  - {name}: RPC host {rpc_port}->5555, Cluster host {cluster_port}->5556")

    print(f"Clients: {len(clients)}")
    for name, peer_port, debug_port in clients:
        print(f"  - {name}: P2P host {peer_port}->6881, Debug host {debug_port}->5678")

    print("\nSugerencias:")
    print("  docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'")
    print("  docker logs -f tracker-1")


def command_up(args: argparse.Namespace) -> int:
    if not docker_available():
        raise WizardError("No se encontró 'docker' en PATH.")

    print("\n=== Wizard de entorno de pruebas (Docker sin compose) ===")
    print("Completa los pasos. Enter usa el valor por defecto.\n")

    network_name = args.network or ask_text("Nombre de red", "torrent_net")
    subnet = args.subnet or ask_text("Subnet CIDR", "172.29.0.0/24")
    tracker_count = args.trackers if args.trackers is not None else ask_int("Cantidad de trackers", 2, 1)
    client_count = args.clients if args.clients is not None else ask_int("Cantidad de clients", 0, 0)
    rpc_start_port = args.rpc_start_port if args.rpc_start_port is not None else ask_int("Puerto base RPC host", 5555, 1)
    peer_start_port = args.peer_start_port if args.peer_start_port is not None else ask_int("Puerto base P2P host", 6881, 1)
    debug_start_port = (
        args.debug_start_port if args.debug_start_port is not None else ask_int("Puerto base Debug host", 5678, 1)
    )

    with_gui = args.with_gui
    if client_count == 0:
        with_gui = False
    elif args.with_gui is None:
        with_gui = ask_bool("¿Activar GUI/X11 para clients?", False)

    display = args.display
    if with_gui and not display:
        display = ask_text("Valor de DISPLAY", default_display_value())

    auto_xhost = args.auto_xhost
    if with_gui and sys.platform.startswith("linux") and auto_xhost is None:
        auto_xhost = ask_bool("¿Autorizar Docker en X11 con xhost +local:docker?", True)
    if auto_xhost is None:
        auto_xhost = False

    should_build = args.build
    if args.build is None:
        should_build = ask_bool("¿Construir imágenes antes de levantar?", True)

    print("\n== Plan de ejecución ==")
    print(f"- Red: {network_name} ({subnet})")
    print(f"- Trackers: {tracker_count}")
    print(f"- Clients: {client_count}")
    print(f"- GUI: {'sí' if with_gui else 'no'}")
    print("- Datos clientes efímeros: sí")
    if with_gui:
        print(f"- DISPLAY: {display}")
        print(f"- Auto xhost: {'sí' if auto_xhost else 'no'}")
    print(f"- Build: {'sí' if should_build else 'no'}")

    if not ask_bool("¿Continuar?", True):
        print("Operación cancelada.")
        return 0

    if with_gui and sys.platform.startswith("linux"):
        if auto_xhost:
            enable_xhost_access()
        if not display_is_reachable(display or ""):
            raise WizardError(
                f"No se pudo conectar al servidor X con DISPLAY='{display}'. "
                "Verifica que el servidor X esté activo y autorizado para Docker."
            )

    if should_build:
        build_images(build_client=client_count > 0)

    ensure_network(network_name, subnet)
    trackers = start_trackers(
        tracker_count=tracker_count,
        network_name=network_name,
        subnet=subnet,
        rpc_start_port=rpc_start_port,
    )

    clients = start_clients(
        client_count=client_count,
        tracker_count=tracker_count,
        network_name=network_name,
        with_gui=bool(with_gui),
        display=display or "host.docker.internal:0",
        peer_start_port=peer_start_port,
        debug_start_port=debug_start_port,
    )

    print_summary(network_name, subnet, trackers, clients)

    replay_args = [
        "up",
        "--network",
        network_name,
        "--subnet",
        subnet,
        "--trackers",
        str(tracker_count),
        "--clients",
        str(client_count),
        "--rpc-start-port",
        str(rpc_start_port),
        "--peer-start-port",
        str(peer_start_port),
        "--debug-start-port",
        str(debug_start_port),
        "--build" if should_build else "--no-build",
    ]
    if with_gui:
        replay_args.extend([
            "--with-gui",
            "--display",
            display or default_display_value(),
            "--auto-xhost" if auto_xhost else "--no-auto-xhost",
        ])
    else:
        replay_args.append("--no-with-gui")

    print("\nResumen de repetición:")
    print(f"  {args_to_shell(replay_args)}")
    ask_and_save_history(replay_args, args.history_mode)
    return 0


def command_down(args: argparse.Namespace) -> int:
    if not docker_available():
        raise WizardError("No se encontró 'docker' en PATH.")

    print("\n=== Wizard de limpieza (down) ===")

    network_name = args.network or ask_text("Nombre de red a remover", "torrent_net")
    remove_volumes = bool(args.remove_volumes)

    all_containers = list_container_names()
    targets = [name for name in all_containers if name.startswith("tracker-") or name.startswith("client-")]

    print("\n== Plan de limpieza ==")
    print(f"- Contenedores objetivo: {len(targets)}")
    if targets:
        print("  " + ", ".join(targets))
    print(f"- Red: {network_name}")
    print(f"- Eliminar volúmenes: {'sí' if remove_volumes else 'no'}")
    if not remove_volumes:
        print("- Seguridad: NO se borran volúmenes ni archivos de bind mounts")

    if not ask_bool("¿Continuar?", True):
        print("Operación cancelada.")
        return 0

    for name in targets:
        run(["docker", "rm", "-f", name], check=False)

    remove_network_if_exists(network_name)

    if remove_volumes:
        confirm_purge = input("Escribe DELETE para confirmar borrado de volúmenes: ").strip()
        if confirm_purge != "DELETE":
            print("Confirmación inválida. Se omite borrado de volúmenes.")
            print("\nLimpieza completada.")
            return 0

        volumes = list_docker_volumes()
        volume_targets = [
            name
            for name in volumes
            if (
                name.startswith("tracker")
                and name.endswith("-data")
                and name[7:-5].isdigit()
            )
            or (
                name.startswith("client")
                and (name.endswith("-downloads") or name.endswith("-config"))
                and name[6 : name.rfind("-")].isdigit()
            )
            or name == "shared-torrents"
        ]
        for volume in volume_targets:
            run(["docker", "volume", "rm", volume], check=False)

    replay_args = [
        "down",
        "--network",
        network_name,
        "--remove-volumes" if remove_volumes else "--no-remove-volumes",
    ]
    ask_and_save_history(replay_args, args.history_mode)

    print("\nLimpieza completada.")
    return 0


def command_recent(args: argparse.Namespace) -> int:
    state = load_state()
    history: list[dict] = state.get("history", [])
    if not history:
        print("No hay comandos recientes guardados.")
        return 0

    limit = max(1, args.limit)
    shown = history[-limit:]

    print("\n=== Comandos recientes ===")
    print(f"Archivo: {STATE_FILE}")
    for idx, entry in enumerate(reversed(shown), start=1):
        entry_args = entry.get("args", [])
        ts = entry.get("timestamp", "sin-fecha")
        entry_hash = str(entry.get("hash", "sin-hash"))
        if not isinstance(entry_args, list):
            continue
        print(f"[{idx}] {ts}  hash={entry_hash[:10]}  {args_to_shell(entry_args)}")

    print("\nRepetir: python tests/env_wizard.py repeat --index 1")
    return 0


def command_repeat(args: argparse.Namespace) -> int:
    state = load_state()
    history: list[dict] = state.get("history", [])
    if not history:
        raise WizardError("No hay historial para repetir.")

    index = args.index
    if index <= 0:
        raise WizardError("El índice debe ser >= 1.")
    if index > len(history):
        raise WizardError(f"Índice fuera de rango. Hay {len(history)} comandos guardados.")

    target = history[-index]
    target_args = target.get("args", [])
    if not isinstance(target_args, list) or not target_args:
        raise WizardError("Entrada de historial inválida.")

    print("\n=== Repetir comando ===")
    print(args_to_shell(target_args))
    if not ask_bool("¿Ejecutar ahora?", True):
        print("Operación cancelada.")
        return 0

    command = [sys.executable, str(Path(__file__).resolve()), *target_args, "--history-mode", "skip"]
    result = subprocess.run(command, check=False)
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Wizard interactivo para levantar entornos de test sin docker-compose.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    up = subparsers.add_parser("up", help="Levanta trackers/clients de forma interactiva")
    up.add_argument("--network", type=str, default=None, help="Nombre de la red docker")
    up.add_argument("--subnet", type=str, default=None, help="Subnet de la red docker (CIDR)")
    up.add_argument("--trackers", type=int, default=None, help="Cantidad de trackers")
    up.add_argument("--clients", type=int, default=None, help="Cantidad de clients")
    up.add_argument("--rpc-start-port", type=int, default=None, help="Puerto base de RPC host para trackers")
    up.add_argument("--peer-start-port", type=int, default=None, help="Puerto base P2P host para clients")
    up.add_argument("--debug-start-port", type=int, default=None, help="Puerto base debug host para clients")
    up.add_argument("--with-gui", action=argparse.BooleanOptionalAction, default=None, help="Activa GUI/X11 en clients")
    up.add_argument("--display", type=str, default=None, help="Valor DISPLAY si --with-gui")
    up.add_argument(
        "--auto-xhost",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Ejecuta xhost +local:docker antes de iniciar clients GUI (Linux)",
    )
    up.add_argument("--build", action=argparse.BooleanOptionalAction, default=None, help="Construir imágenes antes de up")
    up.add_argument("--history-mode", choices=["prompt", "save", "skip"], default="prompt", help=argparse.SUPPRESS)

    down = subparsers.add_parser("down", help="Detiene y limpia el entorno generado")
    down.add_argument("--network", type=str, default=None, help="Nombre de la red docker a remover")
    down.add_argument(
        "--remove-volumes",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Elimina volúmenes de test (tracker*-data, client*-downloads/config, shared-torrents)",
    )
    down.add_argument("--history-mode", choices=["prompt", "save", "skip"], default="prompt", help=argparse.SUPPRESS)

    recent = subparsers.add_parser("recent", help="Lista comandos recientes guardados")
    recent.add_argument("--limit", type=int, default=10, help="Cantidad de comandos a mostrar")

    repeat = subparsers.add_parser("repeat", help="Repite un comando guardado en historial")
    repeat.add_argument("--index", type=int, default=1, help="Índice del historial (1 = más reciente)")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "up":
            return command_up(args)
        if args.command == "down":
            return command_down(args)
        if args.command == "recent":
            return command_recent(args)
        if args.command == "repeat":
            return command_repeat(args)
        parser.print_help()
        return 1
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
        return 130
    except (subprocess.CalledProcessError, WizardError) as exc:
        print(f"\nError: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
