"""Typed exceptions, so callers can catch failures by category instead of by message."""

from __future__ import annotations


class ForensicsError(Exception):
    """Base class for all errors raised by this package."""


class UnsafeTracePathError(ForensicsError, ValueError):
    """A trace id resolved to a path outside the trace root (path-traversal attempt)."""


class TraceNotFoundError(ForensicsError):
    """No trace exists for the requested id."""
