#!/usr/bin/env python3
"""
Script para crear archivos .p2p (torrent)
"""
import sys
import os
import hashlib
from pathlib import Path
import pickle


CHUNK_SIZE = 512 * 1024  # 512 KB


def calculate_file_hash(file_path: str) -> str:
    """Calcula SHA256 del archivo completo"""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            sha256.update(chunk)
    return sha256.hexdigest()


def calculate_chunk_hash(chunk_data: bytes) -> str:
    """Calcula SHA256 de un chunk"""
    return hashlib.sha256(chunk_data).hexdigest()


def create_torrent(file_path: str, tracker_url: str = "http://localhost:5555"):
    """Crea archivo .p2p para un archivo"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
    
    file_path = Path(file_path).resolve()
    file_size = os.path.getsize(file_path)
    file_hash = calculate_file_hash(str(file_path))
    file_name = file_path.name
    total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    
    print(f"Creando torrent para: {file_name}")
    print(f"Tamaño: {file_size:,} bytes ({file_size / (1024*1024):.2f} MB)")
    print(f"Hash: {file_hash}")
    print(f"Chunks: {total_chunks}")
    
    # Calcular hashes de chunks
    chunks_info = []
    with open(file_path, "rb") as f:
        for i in range(total_chunks):
            chunk_data = f.read(CHUNK_SIZE)
            chunk_hash = calculate_chunk_hash(chunk_data)
            chunks_info.append({
                "chunk_id": i,
                "chunk_size": len(chunk_data),
                "chunk_hash": chunk_hash,
            })
            if (i + 1) % 10 == 0 or i == total_chunks - 1:
                print(f"  Procesado chunk {i+1}/{total_chunks}")
    
    # Crear estructura de torrent
    torrent_data = {
        "file_name": file_name,
        "file_size": file_size,
        "file_hash": file_hash,
        "chunk_size": CHUNK_SIZE,
        "total_chunks": total_chunks,
        "tracker_address": tracker_url,
        "chunks_info": chunks_info,
    }
    
    # Guardar archivo .p2p
    torrent_file = file_path.with_suffix('.p2p')
    with open(torrent_file, 'wb') as f:
        pickle.dump(torrent_data, f)
    
    print(f"\n✓ Torrent creado: {torrent_file}")
    return str(torrent_file)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python create_torrent.py <archivo> [tracker_url]")
        print("Ejemplo: python create_torrent.py /tmp/test.bin http://localhost:5555")
        sys.exit(1)
    
    file_path = sys.argv[1]
    tracker_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:5555"
    
    try:
        torrent_file = create_torrent(file_path, tracker_url)
        print(f"\nAhora puedes agregar este torrent al cliente:")
        print(f"  add {torrent_file}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
