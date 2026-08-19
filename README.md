# Lumidoc

Language: **English** | [简体中文](./README.zh-CN.md)

Lumidoc is a modular intelligent document platform built around RAG, graph knowledge, and multi-service processing. It supports file ingestion, semantic retrieval, document-grounded chat, QA workflows, and service-level observability.

## Features

- Multi-service architecture for file, chat, graph, auth, RAG, and monitoring modules
- Support for local storage and S3/MinIO object storage
- PostgreSQL (`pgvector`) + Redis + Neo4j integration
- Docker-only runtime, including the local chat and embedding models
- Extensible module layout under `src/modules`

## Repository Structure

```text
.
├── src/                    # Core backend modules and shared libraries
├── frontend/               # Frontend application
├── scripts/                # Setup, diagnostics, and maintenance scripts
├── docs/                   # Architecture and analysis documents
├── docker-compose.yml      # Containerized deployment
├── start_services.sh       # Portable one-command Docker startup
└── stop_services.sh        # Portable one-command Docker shutdown
```

## Quick Start

### 1. Prerequisites

- Docker with Docker Compose support

### 2. Configure Environment

```bash
cp .env.example .env
```

Update `.env` values as needed. The default model runtime is the CPU-compatible
Ollama container; no host model server or hardware-specific runtime is required.

### 3. Start Services

```bash
./start_services.sh
```

The script validates the Compose configuration, builds every application module,
starts the complete stack, provisions the configured models, and waits for health
checks. The same script is used on every Docker-supported host.

### 4. Stop Services

```bash
./stop_services.sh
```

This removes containers and the Compose network while preserving database, object
storage, and model volumes.

## Module Docs

- Backend modules overview: [src/README.md](./src/README.md)
- Script usage guide: [scripts/README.md](./scripts/README.md)
- Frontend guide: [frontend/README.md](./frontend/README.md)

## Notes

- Keep secrets in `.env` and do not commit private credentials.
- Do not start individual modules on the host; the supported runtime is Docker Compose.
