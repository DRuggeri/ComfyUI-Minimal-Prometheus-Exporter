"""
@title: Prometheus Exporter
@nickname: Prometheus Exporter
@description: Exposes a /metrics endpoint with Prometheus gauges for ComfyUI queue depth and VRAM usage
"""

from . import prometheus_exporter  # noqa: F401  (registers the /metrics route on import)

NODE_CLASS_MAPPINGS = {}
__all__ = ["NODE_CLASS_MAPPINGS"]
