"""
Registers a /metrics endpoint on the ComfyUI server exposing Prometheus gauges for
queue depth and VRAM usage.
"""

from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from prometheus_client.core import GaugeMetricFamily, REGISTRY
from prometheus_client.registry import Collector

from server import PromptServer
import comfy.model_management as model_management


def _gpu_backend_type():
    if model_management.is_nvidia():
        return "nvidia"
    if model_management.is_amd():
        return "amd"
    if model_management.is_intel_xpu():
        return "intel_xpu"
    if model_management.is_ascend_npu():
        return "ascend_npu"
    if model_management.is_mlu():
        return "mlu"
    return "other"


def _gpu_info():
    # GPU topology doesn't change at runtime, so resolve labels once at import time.
    # get_gpu_device_options() only adds "gpu:N" entries when there's more than one
    # device, so enumerate get_all_torch_devices() directly to also cover single-GPU hosts.
    # Label by the actual device string (e.g. "cuda:0") rather than list position, since
    # position isn't guaranteed to match the device's real index (see /system_stats, which
    # reorders devices to put the primary one first while still keying off d.index).
    backend_type = _gpu_backend_type()
    info = []
    for device in model_management.get_all_torch_devices():
        info.append((str(device), model_management.get_torch_device_name(device), backend_type))
    return info


GPU_INFO = _gpu_info()


class ComfyUICollector(Collector):
    """Gathers gauge values on demand, at scrape time, rather than tracking running state."""

    def collect(self):
        queue_info = PromptServer.instance.get_queue_info()
        yield GaugeMetricFamily(
            "comfyui_queue_remaining",
            "Number of prompts remaining in the ComfyUI queue",
            value=queue_info["exec_info"]["queue_remaining"],
        )

        gpu_info = GaugeMetricFamily(
            "comfyui_gpu_info",
            "Static info about each visible GPU, always set to 1",
            labels=["gpu", "device", "type"],
        )
        for gpu, device_name, backend_type in GPU_INFO:
            gpu_info.add_metric([gpu, device_name, backend_type], 1)
        yield gpu_info

        vram_state = GaugeMetricFamily(
            "comfyui_vram_state",
            "ComfyUI's selected VRAM management state, always set to 1",
            labels=["state"],
        )
        vram_state.add_metric([model_management.vram_state.name], 1)
        yield vram_state

        vram_total = GaugeMetricFamily(
            "comfyui_vram_total", "Total VRAM reported by the device, in bytes", labels=["gpu"]
        )
        torch_vram_total = GaugeMetricFamily(
            "comfyui_torch_vram_total",
            "Total VRAM allocated to the torch memory pool, in bytes",
            labels=["gpu"],
        )
        vram_free = GaugeMetricFamily(
            "comfyui_vram_free", "Free VRAM reported by the device, in bytes", labels=["gpu"]
        )
        torch_vram_free = GaugeMetricFamily(
            "comfyui_torch_vram_free",
            "Free VRAM available within the torch memory pool, in bytes",
            labels=["gpu"],
        )

        for device in model_management.get_all_torch_devices():
            gpu = str(device)
            total, torch_total = model_management.get_total_memory(device, torch_total_too=True)
            free, torch_free = model_management.get_free_memory(device, torch_free_too=True)
            vram_total.add_metric([gpu], total)
            torch_vram_total.add_metric([gpu], torch_total)
            vram_free.add_metric([gpu], free)
            torch_vram_free.add_metric([gpu], torch_free)

        yield vram_total
        yield torch_vram_total
        yield vram_free
        yield torch_vram_free

        loaded_models = model_management.current_loaded_models
        loaded_models_count = GaugeMetricFamily(
            "comfyui_loaded_models",
            "Number of models currently loaded, by whether they are actively in use",
            labels=["currently_used"],
        )
        currently_used_count = sum(1 for m in loaded_models if m.currently_used)
        loaded_models_count.add_metric(["true"], currently_used_count)
        loaded_models_count.add_metric(["false"], len(loaded_models) - currently_used_count)
        yield loaded_models_count

        model_memory_bytes = GaugeMetricFamily(
            "comfyui_model_memory_bytes",
            "Memory used by loaded models, in bytes, summed for models sharing a class/device/state",
            labels=["model", "device", "state"],
        )
        # Multiple instances (e.g. a base model and a LoRA-patched clone) can share the
        # same (model, device, state) label set, so sum them instead of emitting duplicates.
        memory_by_key = {}
        for m in loaded_models:
            model = m.model
            if model is None:
                continue
            model_name = model.model.__class__.__name__
            device = str(m.device)
            memory_by_key[(model_name, device, "loaded")] = (
                memory_by_key.get((model_name, device, "loaded"), 0) + m.model_loaded_memory()
            )
            memory_by_key[(model_name, device, "offloaded")] = (
                memory_by_key.get((model_name, device, "offloaded"), 0) + m.model_offloaded_memory()
            )
        for (model_name, device, state), value in memory_by_key.items():
            model_memory_bytes.add_metric([model_name, device, state], value)
        yield model_memory_bytes


REGISTRY.register(ComfyUICollector())


@PromptServer.instance.routes.get("/metrics")
async def metrics(request):
    # aiohttp's content_type kwarg rejects a charset param, but CONTENT_TYPE_LATEST
    # includes one (e.g. "text/plain; version=0.0.4; charset=utf-8"), so set the header directly.
    response = web.Response(body=generate_latest(REGISTRY))
    response.headers["Content-Type"] = CONTENT_TYPE_LATEST
    return response
