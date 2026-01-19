"""
Git Version Manager - Interfaces Package
Abstract base classes and protocols for extensibility.
"""
from .publisher_interface import IPublisher, PublisherRegistry
from .parser_interface import IVersionParser, ParserRegistry

__all__ = [
    'IPublisher', 'PublisherRegistry',
    'IVersionParser', 'ParserRegistry'
]
