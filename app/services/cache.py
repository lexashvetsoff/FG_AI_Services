import time
from typing import Optional, Dict


class TTLCache:
    def __init__(self, ttl: int = 7200):
        self._store: Dict[str, dict] = {}
        self._ttl = ttl
    
    def get(self, key: str) -> Optional[dict]:
        item = self._store.get(key)
        if item and (time.time() - item['ts']) < self._ttl:
            return item['data']
        return None
    
    def set(self, key: str, data: dict) -> None:
        self._store[key] = {'data': data, 'ts': time.time()}
    
    def clear(self) -> None:
        self._store.clear()
