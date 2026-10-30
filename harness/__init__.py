"""Versioned coding harness factory; tools/providers remain independent plugins."""
from .engine import CodingHarness, HarnessConfig
from .state import RunState, CheckpointStore

_VERSIONS = {"v1": CodingHarness}


def register_harness(version, factory):
    if not isinstance(version, str) or not version or version in _VERSIONS:
        raise ValueError("invalid or duplicate harness version")
    if not callable(factory):
        raise TypeError("harness factory must be callable")
    _VERSIONS[version] = factory


def create_harness(version="v1", **kwargs):
    try:
        factory = _VERSIONS[version]
    except KeyError:
        raise ValueError("unknown harness version: " + str(version))
    return factory(**kwargs)
