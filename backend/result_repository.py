"""In-memory repositories for storing execution results with eviction support."""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class ResultRecord:
    """Envelope describing execution results for tests and utilities."""

    id: str
    type: str
    status: str
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "payload": self.payload,
        }


class ResultRepository:
    """Thread-safe repository with FIFO eviction when a limit is reached."""

    def __init__(self, limit: int):
        self._limit = limit
        self._items: "OrderedDict[str, ResultRecord]" = OrderedDict()
        self._lock = threading.Lock()

    def _evict_if_needed(self) -> None:
        while len(self._items) > self._limit:
            self._items.popitem(last=False)

    def list(self) -> List[ResultRecord]:
        with self._lock:
            return list(reversed(list(self._items.values())))

    def get(self, record_id: str) -> Optional[ResultRecord]:
        with self._lock:
            return self._items.get(record_id)

    def create(
        self,
        *,
        record_id: str,
        type: str,
        status: str,
        payload: Optional[Dict[str, Any]] = None,
        started_at: Optional[float] = None,
        finished_at: Optional[float] = None,
        created_at: Optional[float] = None,
        updated_at: Optional[float] = None,
    ) -> ResultRecord:
        payload = payload or {}
        created = created_at or time.time()
        record = ResultRecord(
            id=record_id,
            type=type,
            status=status,
            created_at=created,
            updated_at=updated_at or created,
            started_at=started_at,
            finished_at=finished_at,
            payload=payload,
        )
        with self._lock:
            if record_id in self._items:
                self._items.pop(record_id)
            self._items[record_id] = record
            self._evict_if_needed()
        return record

    def update(
        self,
        record_id: str,
        *,
        status: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        started_at: Optional[float] = None,
        finished_at: Optional[float] = None,
        updated_at: Optional[float] = None,
    ) -> ResultRecord:
        with self._lock:
            record = self._items.get(record_id)
            if not record:
                raise KeyError(record_id)
            if status is not None:
                record.status = status
            if payload is not None:
                record.payload = payload
            if started_at is not None:
                record.started_at = started_at
            if finished_at is not None:
                record.finished_at = finished_at
            record.updated_at = updated_at or time.time()
            self._items.move_to_end(record_id)
            self._evict_if_needed()
            return record

    def upsert(self, record: ResultRecord) -> ResultRecord:
        with self._lock:
            self._items[record.id] = record
            self._evict_if_needed()
            return record

    def values(self) -> Iterable[ResultRecord]:
        with self._lock:
            return tuple(self._items.values())


__all__ = [
    "ResultRecord",
    "ResultRepository",
]
