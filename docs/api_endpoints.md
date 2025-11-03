# API Reference Overview

The backend exposes a unified JSON envelope for every successful response:

```json
{
  "status": "success",
  "data": {"...": "payload"},
  "meta": {"...": "optional metadata"}
}
```

Error responses use the shared structure registered by the middleware:

```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Запрос не прошёл валидацию",
    "details": {"errors": ["..."]}
  }
}
```

The tables below summarise the main endpoints that were introduced or updated.

## Results

| Method & Path        | Description                                  |
|----------------------|----------------------------------------------|
| `GET /results`       | Returns combined history for tests and utilities. Optional query `job_type=tests|utilities` filters the list. |
| `GET /results/{id}`  | Returns a single record by identifier. Optional `job_type` narrows the search. |
| `DELETE /results/{id}` | Removes the record from history. Optional `job_type` targets a specific repository. |

**Response payload** (`data` field):

```json
{
  "items": [
    {
      "id": "23ac94b1f3c9",
      "type": "tests",
      "status": "running",
      "summary": {
        "status": "running",
        "total": 4,
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "duration": 12.4
      },
      "payload": {"...": "job specific data"}
    }
  ],
  "history": [
    {"type": "tests", "limit": 20, "total": 7},
    {"type": "utilities", "limit": 50, "total": 3}
  ]
}
```

`status` supports the lifecycle states **queued**, **running**, **completed**, **failed** and **stopped** so the UI can render meaningful badges.

## Utilities

| Method & Path              | Description |
|----------------------------|-------------|
| `POST /utilities/run`      | Starts a utility by name. Passes a validated `parameters` object. |
| `GET /utilities/jobs`      | Lists history for utility runs. |
| `GET /utilities/{id}`      | Returns a single utility job. |

**Run request examples**:

```json
{"utility": "check_conf", "parameters": {"ip": "10.0.0.1", "password": "pass", "iterations": 3, "delay": 30}}
{"utility": "check_hash", "parameters": {"dir1": "/tmp/a", "dir2": "/tmp/b"}}
{"utility": "fpga_reload", "parameters": {"ip": "10.0.0.1", "slot": 9, "max_attempts": 1000}}
```

The response `data` contains the job record, while `meta.success` mirrors the execution outcome and `meta.error` carries textual diagnostics.

## Tunnels

| Method & Path | Description |
|---------------|-------------|
| `GET /tunnels` | Returns tunnel manager state inside the response envelope. |

`data` contains `alive`, `configured_ports` and the list of `leases` with ownership metadata.

## Tests

The existing test endpoints now follow the envelope convention:

| Method & Path         | Notes |
|-----------------------|-------|
| `GET /tests/types`    | Returns the cached catalog inside `data`. |
| `GET /tests/jobs`     | Lists job history (`data.items`) and history metadata (`data.history`). |
| `GET /tests/status`   | Returns a single job record. |
| `POST /tests/run`     | Queues a job; `meta.job_id` stores the identifier. |
| `POST /tests/stop`    | Stops the job and returns outcome details in `meta`. |

`TestsRunRequest` still accepts `selected_tests`, while responses expose the job summary at the top level for quick glance rendering.

## Error codes

* `VALIDATION_ERROR` – payload failed Pydantic validation (422).
* `HTTP_404` – resource was not found (e.g. missing result or job).
* `HTTP_503` – tunnel ports are busy.
* `HTTP_409` – tunnel configuration conflict.
* `PING_ERROR` – low-level ping execution failed.
* `INTERNAL_ERROR` – unexpected server-side failure.

All errors share the same envelope which simplifies front-end handling and logging.
