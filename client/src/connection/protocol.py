import json
import time
import uuid

class Protocol:
    VERSION = "1.0"
    
    COMMANDS = {
        'CONNECT': 'connect',
        'DISCONNECT': 'disconnect',
        'REQUEST_FILE': 'request_file',
        'REQUEST_CHUNK': 'request_chunk',
        'SEND_CHUNK': 'send_chunk',
        'FILE_INFO': 'file_info',
        'PEER_LIST': 'peer_list',
        'ANNOUNCE': 'announce',
        'HANDSHAKE': 'handshake',
        'KEEPALIVE': 'keepalive'
    }
    
    @staticmethod
    def create_message(command, func=None, args=None, msg_id=None):
        if msg_id is None:
            msg_id = f"msg_{uuid.uuid4().hex[:8]}"
        
        message = {
            "version": Protocol.VERSION,
            "command": command,
            "func": func or "",
            "args": args or {},
            "id": msg_id,
            "timestamp": int(time.time())
        }
        return message
    
    @staticmethod
    def encode_message(message):
        json_str = json.dumps(message)
        json_bytes = json_str.encode('utf-8')
        length = len(json_bytes)
        length_bytes = length.to_bytes(4, byteorder='big')
        return length_bytes + json_bytes
    
    @staticmethod
    def decode_message(data):
        try:
            return json.loads(data.decode('utf-8'))
        except:
            return None
    
    @staticmethod
    def create_handshake(peer_id, client_name="CustomP2P"):
        return Protocol.create_message(
            Protocol.COMMANDS['HANDSHAKE'],
            func="init",
            args={
                "peer_id": peer_id,
                "client_name": client_name,
                "protocol_version": Protocol.VERSION
            }
        )
    
    @staticmethod
    def create_file_info_request(file_hash):
        return Protocol.create_message(
            Protocol.COMMANDS['FILE_INFO'],
            func="request",
            args={"file_hash": file_hash}
        )
    
    @staticmethod
    def create_file_info_response(file_hash, file_name, file_size, total_chunks):
        return Protocol.create_message(
            Protocol.COMMANDS['FILE_INFO'],
            func="response",
            args={
                "file_hash": file_hash,
                "file_name": file_name,
                "file_size": file_size,
                "total_chunks": total_chunks
            }
        )
    
    @staticmethod
    def create_chunk_request(file_hash, chunk_id):
        return Protocol.create_message(
            Protocol.COMMANDS['REQUEST_CHUNK'],
            func="request",
            args={
                "file_hash": file_hash,
                "chunk_id": chunk_id
            }
        )
    
    @staticmethod
    def create_chunk_response(file_hash, chunk_id, chunk_data):
        return Protocol.create_message(
            Protocol.COMMANDS['SEND_CHUNK'],
            func="response",
            args={
                "file_hash": file_hash,
                "chunk_id": chunk_id,
                "chunk_data": chunk_data
            }
        )
    
    @staticmethod
    def create_announce(peer_id, files_available):
        return Protocol.create_message(
            Protocol.COMMANDS['ANNOUNCE'],
            func="init",
            args={
                "peer_id": peer_id,
                "files": files_available
            }
        )
    
    @staticmethod
    def create_keepalive():
        return Protocol.create_message(
            Protocol.COMMANDS['KEEPALIVE'],
            func="ping"
        )
