# ComfyUI Prometheus Exporter

Exposes a `/metrics` endpoint on the ComfyUI server so [Prometheus](https://prometheus.io/) can scrape queue depth, VRAM usage, and loaded-model stats directly from the native ComfyUI API — no separate process or port required.

## Installation

### ComfyUI Manager (recommended)

1. Open **ComfyUI Manager** inside ComfyUI.
2. Search for **"Prometheus Exporter"** and click **Install**.
3. Restart ComfyUI.

### Comfy Registry (comfy-cli)

```bash
comfy node registry-install comfyui-prometheus-exporter
```

### Manual Download

1. Open a terminal inside your `custom_nodes` folder in your ComfyUI installation.
2. Clone this repository:

```bash
git clone https://github.com/druggeri/ComfyUI-Prometheus-Exporter.git
```

3. Install its dependencies:

```bash
pip install -r ComfyUI-Prometheus-Exporter/requirements.txt
```

4. Restart ComfyUI.

## Usage

Once installed, metrics are available at:

```
http://<comfyui-host>:<port>/metrics
```

Point a Prometheus scrape config at that endpoint:

```yaml
scrape_configs:
  - job_name: comfyui
    static_configs:
      - targets: ["<comfyui-host>:<port>"]
```

## Metrics

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `comfyui_queue_remaining` | Gauge | — | Number of prompts remaining in the ComfyUI queue |
| `comfyui_gpu_info` | Gauge | `gpu`, `device`, `type` | Static info about each visible GPU, always `1` |
| `comfyui_vram_state` | Gauge | `state` | ComfyUI's selected VRAM management state, always `1` |
| `comfyui_vram_total` | Gauge | `gpu` | Total VRAM reported by the device, in bytes |
| `comfyui_torch_vram_total` | Gauge | `gpu` | Total VRAM allocated to the torch memory pool, in bytes |
| `comfyui_vram_free` | Gauge | `gpu` | Free VRAM reported by the device, in bytes |
| `comfyui_torch_vram_free` | Gauge | `gpu` | Free VRAM available within the torch memory pool, in bytes |
| `comfyui_loaded_models` | Gauge | `currently_used` | Number of models currently loaded |
| `comfyui_model_memory_bytes` | Gauge | `model`, `device`, `state` | Memory used by loaded models, in bytes (`state` is `loaded` or `offloaded`) |

Standard `python_*` and `process_*` metrics from `prometheus_client` are included as well.
