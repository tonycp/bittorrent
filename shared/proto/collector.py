from typing import Dict, Optional, Set, List
from shared.const import c_proto as cp
from shared.interface import BlockInfo

import asyncio
import hashlib


class BlockCollector:
    def __init__(self, index: int, hash: str, total: int, size: int = cp.BLOCK_SIZE):
        self.index = index
        self.hash = hash
        self.total = total
        self.size = size

        self.blocks: Dict[int, BlockInfo] = {}
        self.received_blocks: Set[int] = set()
        self.complete_data: Optional[bytes] = None
        self.verified = False

        self._lock = asyncio.Lock()
        self._event = asyncio.Event()

        self._initialize_blocks()

    def _initialize_blocks(self):
        total_blocks = (self.total + self.size - 1) // self.size

        for block_index in range(total_blocks):
            offset = block_index * self.size
            remaining = self.total - offset
            size = min(self.size, remaining)

            info = BlockInfo(offset=offset, size=size, received=False)
            self.blocks[block_index] = info

    def _is_complete(self) -> bool:
        return len(self.received_blocks) == len(self.blocks)

    def _reset_block(self):
        for block in self.blocks.values():
            block.data = None
            block.received = False
        self.received_blocks.clear()
        self.complete_data = None
        self.verified = False
        self._event.clear()

    def get_progress(self) -> float:
        total_blocks = len(self.blocks)
        if total_blocks == 0:
            return 0.0
        return len(self.received_blocks) / total_blocks

    async def add_block(self, block_index: int, block_data: bytes) -> bool:
        if self.complete_data:
            return False

        async with self._lock:
            if block_index not in self.blocks:
                return False

            block = self.blocks[block_index]

            if len(block_data) != block.size:
                return False

            block.data = block_data
            block.received = True
            self.received_blocks.add(block_index)

            if self._is_complete():
                await self._assemble_block()
                if await self._verify_block():
                    self._event.set()
                    return True

            return True

    async def get_missing_blocks(self) -> List[int]:
        async with self._lock:
            return [idx for idx, block in self.blocks.items() if not block.received]

    async def wait_for_completion(self) -> Optional[bytes]:
        await self._event.wait()
        return self.complete_data if self.verified else None

    async def _assemble_block(self):
        chunk_data = bytearray(self.total)

        for _, block in sorted(self.blocks.items()):
            if block.data:
                start = block.offset
                end = start + len(block.data)
                chunk_data[start:end] = block.data

        self.complete_data = bytes(chunk_data)

    async def _verify_block(self) -> bool:
        if not self.complete_data:
            return False

        hash = hashlib.sha1(self.complete_data).hexdigest()
        is_valid = hash == self.hash

        if is_valid:
            self.verified = True
        else:
            self._reset_block()

        return is_valid
