# Server Integration (FastAPI + Nuxt)

This guide describes the recommended architecture when a Nuxt app sends notebook payloads to a Python backend.

## Recommended Architecture

1. Nuxt API route receives notebook payload from client.
2. Nuxt forwards notebook JSON/JSONB payload to your FastAPI service.
3. FastAPI calls `nb2wb.convert(notebook_payload, ...)`.
4. FastAPI returns generated HTML.
5. Nuxt stores/serves rendered HTML.

## FastAPI Example

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any

import nb2wb

app = FastAPI()


class RenderRequest(BaseModel):
    notebook: dict[str, Any]
    target: str = "substack"
    execute: bool = False
    config: dict[str, Any] | None = None


@app.post("/render")
def render(req: RenderRequest) -> dict[str, str]:
    try:
        html = nb2wb.convert(
            req.notebook,
            target=req.target,
            execute=req.execute,
            config=req.config,
            working_dir="/srv/nb2wb/jobs",  # only needed when execute=True
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"html": html}
```

## Nuxt Request Shape

Your Nuxt backend/client can send:

```json
{
  "notebook": { "nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": [] },
  "target": "substack",
  "execute": false,
  "config": {
    "safety": {
      "max_cells": 1500
    }
  }
}
```

This maps directly to `nb2wb.convert()` inputs.

## Operational Guidance

- Keep `execute=false` for untrusted user content whenever possible.
- Run execute-enabled jobs in isolated worker pools.
- Apply API-level body size and timeout limits.
- Set explicit safety limits in `config["safety"]`.
- Log conversion failures with request/job identifiers.

## Suggested Job Isolation

For execute-enabled workloads, run conversion in:

- worker process with strict timeout
- containerized runtime
- constrained filesystem/network policy

Return only final HTML to your app layer.

## Error Handling Strategy

Classify conversion failures by type:

- validation errors (`400`): invalid notebook/config payload
- policy/safety errors (`422`/`400`): exceeded safety limits
- transient system errors (`500`): renderer/runtime failures

For user-facing UX, store structured error details and show actionable guidance.
