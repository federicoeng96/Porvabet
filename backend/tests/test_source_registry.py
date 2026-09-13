"""Tests for the static SOURCE_REGISTRY — a single source of truth that must
stay internally consistent with DATA_SOURCES.md and the `sources` DB table.
Purely a data-shape guard (no branching logic to exercise): catches a
duplicate/typo'd key or an empty note before it silently drifts from the
provider modules it's supposed to describe."""

from app.ingestion.source_registry import SOURCE_REGISTRY
from app.models.enums import DataSourceCategory


def test_every_source_key_is_unique():
    keys = [s.key for s in SOURCE_REGISTRY]
    assert len(keys) == len(set(keys))


def test_every_source_has_a_non_empty_name_and_note():
    for source in SOURCE_REGISTRY:
        assert source.name.strip()
        assert source.notes.strip()


def test_every_source_category_is_a_valid_enum_member():
    for source in SOURCE_REGISTRY:
        assert isinstance(source.category, DataSourceCategory)


def test_registry_is_non_empty():
    assert len(SOURCE_REGISTRY) > 0
