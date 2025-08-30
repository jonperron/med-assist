"""
Event system for observing application events.
Implements the Observer pattern for logging and monitoring.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from enum import Enum
import logging

from app.services.logger import get_logger


class EventType(Enum):
    """Types of events that can be observed."""

    FILE_UPLOADED = "file_uploaded"
    TEXT_EXTRACTED = "text_extracted"
    ENTITIES_EXTRACTED = "entities_extracted"
    ERROR_OCCURRED = "error_occurred"
    BATCH_PROCESSED = "batch_processed"


class Event:
    """Event data structure."""

    def __init__(self, event_type: EventType, data: Dict[str, Any]):
        self.event_type = event_type
        self.data = data


class EventObserver(ABC):
    """Abstract observer for handling events."""

    @abstractmethod
    async def handle_event(self, event: Event) -> None:
        """Handle an observed event."""


class LoggingObserver(EventObserver):
    """Observer that logs events."""

    def __init__(self):
        self.logger = get_logger("event_observer")

    async def handle_event(self, event: Event) -> None:
        """Log the event."""
        self.logger.info("Event: %s, Data: %s", event.event_type.value, event.data)


class EventPublisher:
    """Publisher that notifies observers of events."""

    def __init__(self):
        self._observers: List[EventObserver] = []

    def add_observer(self, observer: EventObserver) -> None:
        """Add an observer to the publisher."""
        self._observers.append(observer)

    def remove_observer(self, observer: EventObserver) -> None:
        """Remove an observer from the publisher."""
        self._observers.remove(observer)

    async def publish_event(self, event: Event) -> None:
        """Publish an event to all observers."""
        for observer in self._observers:
            try:
                await observer.handle_event(event)
            except Exception as exc:  # pylint: disable=W0718
                # Don't let observer errors break the main flow
                logging.error("Observer error: %s", exc)


# Global event publisher instance
event_publisher = EventPublisher()
event_publisher.add_observer(LoggingObserver())
