#!/usr/bin/env python3
"""
BitTorrent CLI - Direct import version
Bypasses problematic __init__.py files
"""

import sys
import os
from pathlib import Path

# Setup path for proper imports
client_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(client_dir))

# Now we can import from client package
import cmd
import asyncio
import time
from typing import Optional, Dict
from tabulate import tabulate

from src.client.core.client_manager import ClientManager
from src.client.config.config_mng import ConfigManager
from src.client.connection.network import NetworkManager


class BitTorrentCLI(cmd.Cmd):
    intro = """
╔════════════════════════════════════════════════════════════╗
║         BitTorrent Client - Interactive CLI               ║
╚════════════════════════════════════════════════════════════╝

Type 'help' or '?' to list commands.
Type 'help <command>' for detailed help on a specific command.
    """
    prompt = "bt> "

    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        
        # Crear NetworkManager
        listen_port = self.config.get_listen_port()
        peer_id = f"CLI-{os.getpid()}"
        self.network = NetworkManager(listen_port, peer_id)
        
        # Crear ClientManager
        self.client = ClientManager(self.config, self.network)
        self.client.start()
        print("✓ Client initialized")

    def do_add(self, arg):
        """Add a torrent file
        
        Usage: add <torrent_file_path>
        
        Example:
            add /path/to/file.p2p
        """
        if not arg:
            print("Error: Please specify a torrent file path")
            return
        
        torrent_path = Path(arg).expanduser()
        if not torrent_path.exists():
            print(f"Error: File not found: {torrent_path}")
            return
        
        try:
            # Leer archivo .p2p (pickle)
            import pickle
            with open(torrent_path, 'rb') as f:
                torrent_data = pickle.load(f)
            
            # Extraer datos
            file_name = torrent_data['file_name']
            file_size = torrent_data['file_size']
            file_hash = torrent_data['file_hash']
            chunk_size = torrent_data['chunk_size']
            total_chunks = torrent_data['total_chunks']
            
            print(f"Agregando torrent:")
            print(f"  Archivo: {file_name}")
            print(f"  Tamaño: {self._format_size(file_size)}")
            print(f"  Hash: {file_hash[:16]}...")
            print(f"  Chunks: {total_chunks}")
            
            # Agregar al cliente
            info_hash = self.client.add_torrent(
                torrent_hash=file_hash,
                file_name=file_name,
                file_size=file_size,
                chunk_size=chunk_size,
                total_chunks=total_chunks,
            )
            
            print(f"✓ Torrent agregado y anunciado al tracker: {info_hash[:8]}")
            
        except Exception as e:
            print(f"✗ Error adding torrent: {e}")
            import traceback
            traceback.print_exc()


    def do_list(self, arg):
        """List all torrents
        
        Usage: list
        """
        torrents = self.client.list_torrents()
        
        if not torrents:
            print("No active torrents")
            return
        
        table_data = []
        for info_hash, handle in torrents.items():
            status = self.client.get_status(info_hash)
            
            # Calculate progress
            if status.total_size > 0:
                progress = (status.downloaded / status.total_size) * 100
            else:
                progress = 0.0
            
            # Format speeds
            dl_speed = self._format_speed(status.download_rate)
            ul_speed = self._format_speed(status.upload_rate)
            
            # Format sizes
            downloaded = self._format_size(status.downloaded)
            total = self._format_size(status.total_size)
            
            table_data.append([
                info_hash[:8],
                handle.file_name,  # Corregido: era handle.name
                status.state,
                f"{progress:.1f}%",
                f"{downloaded}/{total}",
                dl_speed,
                ul_speed,
                status.num_peers
            ])
        
        headers = ["Hash", "Name", "State", "Progress", "Downloaded", "DL Speed", "UL Speed", "Peers"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))

    def do_info(self, arg):
        """Show detailed information about a torrent
        
        Usage: info <info_hash>
        
        Example:
            info abc123
        """
        if not arg:
            print("Error: Please specify an info_hash")
            return
        
        # Find matching torrent (allow partial hash)
        torrents = self.client.list_torrents()
        matches = [h for h in torrents.keys() if h.startswith(arg)]
        
        if not matches:
            print(f"Error: No torrent found with hash starting with '{arg}'")
            return
        
        if len(matches) > 1:
            print(f"Error: Multiple torrents match '{arg}':")
            for h in matches:
                print(f"  {h}")
            return
        
        info_hash = matches[0]
        handle = torrents[info_hash]
        status = self.client.get_status(info_hash)
        
        print(f"\n{'='*60}")
        print(f"Torrent Information")
        print(f"{'='*60}")
        print(f"Name:          {handle.file_name}")
        print(f"Info Hash:     {info_hash}")
        print(f"State:         {status.state}")
        print(f"Total Size:    {self._format_size(status.total_size)}")
        print(f"Downloaded:    {self._format_size(status.downloaded)}")
        print(f"Progress:      {(status.downloaded/status.total_size*100) if status.total_size > 0 else 0:.2f}%")
        print(f"DL Speed:      {self._format_speed(status.download_rate)}")
        print(f"UL Speed:      {self._format_speed(status.upload_rate)}")
        print(f"Peers:         {status.num_peers}")
        print(f"Save Path:     {handle.file_path}")
        print(f"{'='*60}\n")

    def do_pause(self, arg):
        """Pause a torrent
        
        Usage: pause <info_hash>
        """
        if not arg:
            print("Error: Please specify an info_hash")
            return
        
        torrents = self.client.list_torrents()
        matches = [h for h in torrents.keys() if h.startswith(arg)]
        
        if not matches:
            print(f"Error: No torrent found with hash starting with '{arg}'")
            return
        
        info_hash = matches[0]
        self.client.pause_torrent(info_hash)
        print(f"✓ Torrent paused: {info_hash[:8]}")

    def do_resume(self, arg):
        """Resume a paused torrent
        
        Usage: resume <info_hash>
        """
        if not arg:
            print("Error: Please specify an info_hash")
            return
        
        torrents = self.client.list_torrents()
        matches = [h for h in torrents.keys() if h.startswith(arg)]
        
        if not matches:
            print(f"Error: No torrent found with hash starting with '{arg}'")
            return
        
        info_hash = matches[0]
        self.client.resume_torrent(info_hash)
        print(f"✓ Torrent resumed: {info_hash[:8]}")

    def do_remove(self, arg):
        """Remove a torrent
        
        Usage: remove <info_hash> [--delete-files]
        
        Options:
            --delete-files    Also delete downloaded files
        """
        if not arg:
            print("Error: Please specify an info_hash")
            return
        
        parts = arg.split()
        hash_arg = parts[0]
        delete_files = "--delete-files" in parts
        
        torrents = self.client.list_torrents()
        matches = [h for h in torrents.keys() if h.startswith(hash_arg)]
        
        if not matches:
            print(f"Error: No torrent found with hash starting with '{hash_arg}'")
            return
        
        info_hash = matches[0]
        self.client.remove_torrent(info_hash, delete_files=delete_files)
        
        if delete_files:
            print(f"✓ Torrent and files removed: {info_hash[:8]}")
        else:
            print(f"✓ Torrent removed (files kept): {info_hash[:8]}")

    def do_watch(self, arg):
        """Watch torrents in real-time
        
        Usage: watch [interval_seconds]
        
        Default interval: 2 seconds
        Press Ctrl+C to stop watching
        """
        interval = 2
        if arg:
            try:
                interval = int(arg)
            except ValueError:
                print(f"Error: Invalid interval '{arg}'")
                return
        
        print(f"Watching torrents (refresh every {interval}s, Ctrl+C to stop)...\n")
        
        try:
            while True:
                # Clear screen
                os.system('clear' if os.name != 'nt' else 'cls')
                
                print(f"BitTorrent Client - Live View (refresh: {interval}s)\n")
                
                torrents = self.client.list_torrents()
                if not torrents:
                    print("No active torrents")
                else:
                    self.do_list("")
                
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\nStopped watching")

    def do_config(self, arg):
        """Show or modify configuration
        
        Usage: 
            config                  Show all configuration
            config <key>            Show specific value
            config <key> <value>    Set configuration value
        
        Keys:
            download_path     Download directory
            torrent_path      Torrent metadata directory
            tracker_url       Tracker URL
            listen_port       Listen port for incoming connections
        """
        parts = arg.split(maxsplit=1)
        
        if not parts:
            # Show all config
            print("\n" + "="*60)
            print("Configuration")
            print("="*60)
            print(f"Download Path:  {self.config.get_download_path()}")
            print(f"Torrent Path:   {self.config.get_torrent_path()}")
            print(f"Tracker URL:    {self.config.get('GENERAL', 'tracker_url')}")
            print(f"Listen Port:    {self.config.get_listen_port()}")
            print(f"Max DL Rate:    {self.config.get_max_download_rate()} KB/s (0 = unlimited)")
            print(f"Max UL Rate:    {self.config.get_max_upload_rate()} KB/s (0 = unlimited)")
            print(f"Max Connections: {self.config.get_max_connections()}")
            print("="*60 + "\n")
        elif len(parts) == 1:
            # Show specific key
            key = parts[0]
            value = self._get_config_value(key)
            if value is not None:
                print(f"{key}: {value}")
        else:
            # Set value
            key, value = parts
            self._set_config_value(key, value)
            print(f"✓ {key} = {value}")

    def do_debug(self, arg):
        """Show debug information
        
        Usage: debug
        """
        print("\n" + "="*60)
        print("Debug Information")
        print("="*60)
        print(f"Client running: {self.client._running}")
        print(f"Event loop alive: {self.client._loop is not None}")
        print(f"Active torrents: {len(self.client._torrents)}")
        print(f"PeerService running: {self.client.peer_service is not None}")
        print("="*60 + "\n")

    def do_exit(self, arg):
        """Exit the CLI
        
        Usage: exit
        """
        print("Shutting down client...")
        self.client.stop()
        print("Goodbye!")
        return True

    def do_quit(self, arg):
        """Exit the CLI (alias for 'exit')"""
        return self.do_exit(arg)

    def do_EOF(self, arg):
        """Handle Ctrl+D"""
        print()
        return self.do_exit(arg)

    # Helper methods
    
    def _format_size(self, bytes_value: int) -> str:
        """Format bytes to human-readable size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} PB"

    def _format_speed(self, bytes_per_sec: float) -> str:
        """Format speed to human-readable format"""
        if bytes_per_sec == 0:
            return "0 B/s"
        return f"{self._format_size(int(bytes_per_sec))}/s"

    def _get_config_value(self, key: str) -> Optional[str]:
        """Get config value by key"""
        key_map = {
            'download_path': lambda: self.config.get_download_path(),
            'torrent_path': lambda: self.config.get_torrent_path(),
            'tracker_url': lambda: self.config.get('GENERAL', 'tracker_url'),
            'listen_port': lambda: str(self.config.get_listen_port()),
        }
        
        getter = key_map.get(key)
        if getter:
            return getter()
        else:
            print(f"Error: Unknown config key '{key}'")
            return None

    def _set_config_value(self, key: str, value: str):
        """Set config value by key"""
        if key == 'download_path':
            self.config.set('GENERAL', 'download_path', value)
        elif key == 'torrent_path':
            self.config.set('GENERAL', 'torrent_path', value)
        elif key == 'tracker_url':
            self.config.set('GENERAL', 'tracker_url', value)
        elif key == 'listen_port':
            self.config.set('GENERAL', 'listen_port', value)
        else:
            print(f"Error: Unknown config key '{key}'")
            return
        
        self.config.save()


def main():
    """Main entry point"""
    try:
        cli = BitTorrentCLI()
        cli.cmdloop()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
