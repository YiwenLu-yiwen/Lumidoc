# Development guide

`main` is the only maintained branch. Use a fork for proposed changes. The [English README](../README.md) and
[中文 README](../README.zh-CN.md) cover features, setup, and deployment limitations.

## Start the local stack

From the repository root:

```sh
./start_services.sh
```

Docker Compose runs the backend, databases, object storage, and local models.
The frontend is available at `http://localhost:3000`; browser API requests go
through the gateway at `http://localhost:8888`. Internal services are reachable
through their Compose service names, not host ports.

After backend changes, rebuild the affected service, for example:

```sh
docker compose up -d --build --wait chat_service
```

For changes spanning services, use `./start_services.sh --build`.

## Frontend development

Keep the backend running and stop the container serving the frontend before
starting Vite on the same port:

```sh
# Disable the local recovery controller while intentionally stopping the frontend.
docker compose stop container_control frontend
cd frontend
npm ci
npm run dev
```

Frontend development additionally requires Node.js and npm. The container build
uses Node.js 20. Configuration is in `frontend/vite.config.ts`; never expose
server credentials through `VITE_*` variables.

To return to the container frontend, stop Vite and run `./start_services.sh` from
the repository root.

## Where to make changes

| Area | Location |
| --- | --- |
| Pages, components, localization | `frontend/src/` |
| Frontend API clients | `frontend/src/api/` |
| Auth and project access | `src/modules/auth/`, `src/modules/project/` |
| File storage and processing | `src/modules/file/`, `src/modules/fileproc/` |
| Conversations and streaming | `src/modules/chat/` |
| Retrieval and knowledge graphs | `src/modules/lightraglocal/`, `src/modules/graph/` |
| Model service and adapters | `src/modules/llm/`, `src/shared/llm/` |
| Gateway and shared clients | `src/modules/gateway/`, `src/shared/clients/` |
| Runtime configuration | `docker-compose.yml`, `.env.example` |

## Validate changes

Run frontend checks from `frontend/`:

```sh
npm run lint
npm run test -- --run
npm run build
```

The integration smoke test requires a running stack and creates test accounts,
projects, and documents. Use a separate test deployment:

```sh
npm run test:e2e:smoke
```

Backend regression tests are in `tests/`. Run `python -m pytest tests/` in a Python
environment with the relevant service and test dependencies installed. PDF OCR
tests also require the file-processing runtime dependencies. Runtime images do
not all include test tools.

Before committing, check `git diff --check` and `git diff --staged`. Never stage
`.env`, credentials, private documents, logs, databases, or model weights.

## Documentation scope

Keep documentation focused on setup, development, APIs, and operating the project.
Internal audits, personal notes, one-off investigation reports, and unpublished
plans belong outside the tracked repository. Preserve third-party attribution
and license files.

Module-level README files describe individual services; use the current Compose
configuration and source routes when older examples differ from the implementation.
