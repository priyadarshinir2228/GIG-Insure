import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Callable, List

class EventBus:
    """Async Event Bus simulating Apache Kafka Topics and Transactional Outbox Pattern."""

    TOPICS = [
        "order.placed",
        "salary.transfer",
        "insurance.registered",
        "claim.raised",
        "disruption.detected",
        "policy.endorsed"
    ]

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {topic: [] for topic in self.TOPICS}
        self._event_log: List[Dict[str, Any]] = []

    def subscribe(self, topic: str, handler: Callable):
        if topic in self._subscribers:
            self._subscribers[topic].append(handler)

    async def publish(self, topic: str, payload: Dict[str, Any]):
        """Publishes an event to specified Kafka-style topic and dispatches to subscribers."""
        event = {
            "topic": topic,
            "timestamp": datetime.now().isoformat(),
            "payload": payload
        }
        self._event_log.append(event)
        
        # Async dispatch to subscribers
        if topic in self._subscribers:
            for handler in self._subscribers[topic]:
                if asyncio.iscoroutinefunction(handler):
                    await handler(payload)
                else:
                    handler(payload)
        return event

    def get_event_log(self) -> List[Dict[str, Any]]:
        return self._event_log

event_bus = EventBus()
