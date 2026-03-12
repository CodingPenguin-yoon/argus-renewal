from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable, Optional

from ...config.env import Settings
from .provider_descriptors import DisclosureProviderDescriptor, NewsProviderDescriptor


@dataclass(frozen=True)
class RawIngestionFactoryExtension:
    disclosure_provider_descriptors: tuple[DisclosureProviderDescriptor, ...] = ()
    news_provider_descriptors: tuple[NewsProviderDescriptor, ...] = ()


DescriptorFactoryCallable = Callable[[Settings], Any]


def parse_descriptor_factory_paths(value: Optional[str]) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def load_raw_ingestion_factory_extensions(settings: Settings) -> RawIngestionFactoryExtension:
    merged = RawIngestionFactoryExtension()
    for path in parse_descriptor_factory_paths(settings.raw_ingestion_descriptor_factory_paths):
        factory = load_descriptor_factory(path)
        payload = factory(settings)
        extension = coerce_raw_ingestion_factory_extension(payload)
        merged = RawIngestionFactoryExtension(
            disclosure_provider_descriptors=(
                *merged.disclosure_provider_descriptors,
                *extension.disclosure_provider_descriptors,
            ),
            news_provider_descriptors=(
                *merged.news_provider_descriptors,
                *extension.news_provider_descriptors,
            ),
        )
    return merged


def load_descriptor_factory(path: str) -> DescriptorFactoryCallable:
    normalized = path.strip()
    if ":" in normalized:
        module_name, attribute_name = normalized.split(":", 1)
    else:
        module_name, _, attribute_name = normalized.rpartition(".")

    if not module_name or not attribute_name:
        raise ValueError(f"Invalid descriptor factory path: {path}")

    module = import_module(module_name)
    factory = getattr(module, attribute_name, None)
    if factory is None or not callable(factory):
        raise ValueError(f"Descriptor factory is not callable: {path}")
    return factory


def coerce_raw_ingestion_factory_extension(payload: RawIngestionFactoryExtension | dict[str, Any] | None) -> RawIngestionFactoryExtension:
    if payload is None:
        return RawIngestionFactoryExtension()
    if isinstance(payload, RawIngestionFactoryExtension):
        return payload
    if not isinstance(payload, dict):
        raise ValueError("Raw ingestion descriptor factory must return dict or RawIngestionFactoryExtension")

    disclosure_descriptors = payload.get("disclosure_provider_descriptors") or payload.get("disclosures") or ()
    news_descriptors = payload.get("news_provider_descriptors") or payload.get("news") or ()
    return RawIngestionFactoryExtension(
        disclosure_provider_descriptors=tuple(disclosure_descriptors),
        news_provider_descriptors=tuple(news_descriptors),
    )
