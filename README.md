# Lumidoc

**Turn documents into searchable knowledge and conversations.**

**English** · [简体中文](./README.zh-CN.md)

Lumidoc is a self-hosted document workspace. Upload files, extract readable text
(including scanned PDF pages), organize them by project, and ask questions using
local AI models. The default Docker stack runs Ollama, storage, databases, and
application services on your own machine.

[Quick start](#quick-start) · [Try the example](#try-it-with-two-sample-documents) · [Development](./docs/DEVELOPMENT.md) · [Contributing](./CONTRIBUTING.md) · [Non-commercial license](./LICENSE)

![Lumidoc project workspace showing documents, knowledge-base imports and conversations](./docs/images/workspace.png)

*Actual local deployment, using the fictional Harbor Studio example included in this repository.*

<details>
<summary>Explore the interface: documents, chat and knowledge base</summary>

| Upload and process documents | Ask questions about your documents |
| --- | --- |
| ![Processed sample files in the document library](./docs/images/documents.png) | ![A real model answer grounded in the sample launch brief](./docs/images/chat.png) |

![Two processed documents imported into the project knowledge base](./docs/images/knowledge-base.png)

These are real application captures, not mockups. They contain only a demo account
and fictional sample material. Your answers and processing times depend on the model and hardware.

</details>

## What can I do with it?

| Your task | How Lumidoc helps |
| --- | --- |
| Find an answer buried in several files | Import processed documents into a project's knowledge base, then query it with LightRAG. |
| Read a scanned PDF | Extract its text with local OCR; preview and download the processed Markdown. |
| Keep work for different topics separate | Create projects with their own documents, knowledge bases, and conversations. |
| Ask follow-up questions | Continue a saved conversation; stop generation when needed. Replies can finish while you visit another page. |
| Explore connections between documents | Import documents into the knowledge base and inspect the extracted graph. Results depend on the document content and extraction quality. |
| Write something without using your files | Use chat for drafting and general questions, with or without document references. |

The interface supports English and Simplified Chinese. Conversation deletion is
synchronized between the sidebar and chat view. Document lists persist across
refreshes, and preview/download use the processed content rather than the original
upload.

Conversations inactive for 30 days are archived automatically as whole conversations
and remain accessible from the sidebar. No manual archive action is required.
You can add more processed documents to a knowledge base or delete an indexed
document from its file-status list. Removing it from the knowledge base preserves
the source file, so it can be imported again later.

## Quick start

### Requirements

- Docker Engine or Docker Desktop, with Docker Compose v2 and a POSIX shell
  (Linux/macOS; use WSL2 on Windows).
- Internet access for the first image build, dependencies, and model downloads.
- Enough Docker memory and disk for the full stack. A practical starting point is
  **16 GB RAM and 30 GB free disk**; this is guidance, not a tested minimum.

### Start

```sh
git clone --branch main https://github.com/YiwenLu-yiwen/Lumidoc.git
cd Lumidoc
./start_services.sh
```

On first run, the script creates a private `.env` with random credentials, builds
missing images, starts the services, downloads the configured models, and waits
for service health checks. It preserves an existing `.env` and existing data.
The first run can take several minutes, especially while downloading models.
MinIO is built from a pinned source release.

Open **[http://localhost:3000](http://localhost:3000)**, register an account, and:

1. Create a project.
2. Upload a document and wait for processing to complete.
3. Open the preview or download the processed text.
4. Import the document into the project's knowledge base.
5. Ask a question in chat or the knowledge-base query panel.

Default models: `qwen3:1.7b` for chat and `nomic-embed-text` for embeddings.
No host Python, Node.js, GPU, API key, or separate Ollama installation is required.

### Automatic GPU / CPU selection

`./start_services.sh` prefers a reachable native GPU Ollama, then a working Docker
NVIDIA GPU runtime, and otherwise starts Docker Ollama on CPU. On Apple Silicon,
install and start native Ollama to use Metal; an unavailable native server falls
back to CPU. On other hosts, native GPU use is detected from loaded models; Docker
NVIDIA acceleration requires the NVIDIA Container Toolkit.

Use `--native`, `--gpu`, or `--cpu` to force a mode (explicit choices do not silently
fall back). `--build` can be combined with any mode. Export `NATIVE_OLLAMA_URL` or
set it in `.env` to customize the native endpoint. The model initializer prepares
the configured models in the selected runtime. `./stop_services.sh` remembers the
last successful startup mode and preserves data volumes.

Native mode requires Compose support for `!reset`. Model requests keep models
loaded for 15 minutes (`OLLAMA_KEEP_ALIVE`) for faster subsequent requests.

Chat can use project documents as context and bounds recent history to 6,000 characters.
`CHAT_RETRIEVAL_TIMEOUT` defaults to 8 seconds; `CHAT_MAX_TOKENS` defaults to 512.
Increase these budgets if your documents or requested answers need more time/length.
Knowledge-base queries display a live answer stream and can be stopped.

### Update, inspect, and stop

```sh
./start_services.sh --build             # Rebuild after changing source code
docker compose ps                     # Check service state
docker compose logs --tail=100 fileproc_service
./stop_services.sh                     # Stop while preserving data volumes
```

If Docker is not running, start it first. For a failed first build, check network
access and free disk space, then rerun the startup command. `--wait` checks service
readiness; it does not prove every document or model response will succeed.

## Try it with two sample documents

No private files are needed for your first run. Use the files in
[`examples/getting-started`](./examples/getting-started/README.md):

1. Register your own account, create **Harbor Studio launch**, and open the project.
2. Open **Document Analysis** (the Documents workspace), then upload `launch-brief.txt` and `support-guide.txt` together.
   Wait until both are **Completed**. Refresh the page to see that they remain saved.
3. Select a document to preview or download its processed text.
4. In **Knowledge Graph** (the knowledge-base page), select both files and choose **Import selected files**.
   Wait for **Processed**. Upload and knowledge-base import are separate steps.
5. Open **Chat** and ask: “Who owns the launch, and when is the rehearsal?”
   The source documents say **Maya Chen** and **8 April 2027**.
6. Ask a follow-up in the same conversation. Use **Stop generating** if needed;
   return through the sidebar to continue the saved conversation later.

For a second question, try: “What must be ready before launch?” Compare the reply
with the three checks in the launch brief. The [walkthrough](./examples/getting-started/README.md)
also explains common waiting states and what to try next.

## How it works

```mermaid
flowchart LR
    A[Upload to a project] --> B[File processing]
    B --> C[Text extraction / local PDF OCR]
    C --> D[Preview and download processed text]
    C --> E[Import into knowledge base]
    E --> F[LightRAG index and graph]
    F --> G[Retrieve relevant context]
    G --> H[Local Ollama model]
    Q[Your question and conversation] --> H
    H --> I[Stream and save the answer]
```

Uploading and knowledge-base import are separate steps. Chat retrieves document
context through LightRAG and generates a response through the LLM service.
The knowledge-base query panel uses hybrid retrieval. Model files are downloaded
on first startup; default PDF extraction and inference run locally afterward.
Optional model providers can be configured separately.

## Configuration and deployment scope

The generated `.env` follows [`.env.example`](./.env.example). Edit it for your
installation; never commit it. Existing installations with example/default
passwords should replace them deliberately—changing a database password in `.env`
alone does not migrate an existing database volume.

| Setting | Purpose |
| --- | --- |
| `OLLAMA_CHAT_MODEL` | Local chat and document post-processing model. |
| `OLLAMA_EMBEDDING_MODEL`, `OLLAMA_EMBEDDING_DIM` | Embedding model and dimension; rebuild knowledge indexes if these change. |
| `FILEPROC_CPU_LIMIT`, `FILEPROC_MEMORY_LIMIT` | File-processing limits, defaulting to 2 CPUs and 4 GB. |
| `LIGHTRAG_QUERY_MAX_TOKENS` | Knowledge-query answer budget, default 384. |
| `LIGHTRAG_QUERY_CONTEXT_TOKENS` | Knowledge-query context budget, default 4096. |
| `BIND_HOST` | Published port binding, default `127.0.0.1`. |

**The quick start is for local use.** Public access needs a separate deployment
review, TLS/reverse proxy, browser API address/CORS configuration, and restricted
infrastructure ports. Changing `BIND_HOST` alone is not a production deployment.
The frontend currently defaults to the local API gateway at port 8888.

## Administration

Administrators can open **Administration** from the sidebar to monitor service health,
loaded models, tasks and user access. The page supports English and Chinese and refreshes
every 10 seconds while visible. A failed refresh keeps the last snapshot and shows an
error; the check timestamp tells you how recent it is.

Application services (including the gateway) are monitored by an internal controller.
After two failed checks it attempts recovery, with a 60-second cooldown and at most
three restarts in 15 minutes. While retrying, the admin page shows **Recovering**;
exhausting the budget requires administrator intervention. Manual restart requires
confirmation and clears the recovery block. Two minutes of sustained health resets
the retry budget. Configure this with `AUTO_RESTART_ENABLED`,
`AUTO_RESTART_MAX_ATTEMPTS` and `AUTO_RESTART_WINDOW_SECONDS`.

Accepted uploads, deletions and chat requests are persisted in the `operational_data`
volume. Document processing uses a Redis acknowledgement queue and persistent AOF;
LightRAG imports persist their status and resume after replacement. Interrupted work
is retried up to five times. A crashed model generation starts again, saving one final
reply; it cannot resume GPU memory or the exact interrupted token. Recovery can wait
60–90 seconds for an abandoned worker lease to expire. Keep all data volumes when
recreating containers; deleting volumes removes the recovery records too.

The browser retains unfinished uploads and single-file deletions locally. Reopen the
app and sign in to the same account to resume them. Bytes that have not reached the
server require that browser's saved copy; clearing browser storage removes it.

The admin **Activity** tab shows persisted gateway request metadata, task interruptions
and restart outcomes. Audit records exclude request bodies, query strings and tokens;
private queued work necessarily contains the data needed to complete the operation.
Purely local clicks are not recorded. Back up the operational volume with the other
data volumes and restrict host access; audit and work records currently have no
automatic retention limit.

The controller only controls allowlisted containers in its own Compose project. It is
the only service with the Docker socket mounted and publishes no host port. Docker
socket access is privileged: use a trusted host
([Docker security guidance](https://docs.docker.com/engine/security/)). Databases,
storage and the controller use Docker's restart policy; host processes (including
native Ollama) need host-level supervision. If the controller or Docker daemon is down,
automatic application recovery cannot run until it is restored.

## Current limitations

- OCR produces readable text; it does not preserve every table, formula, or page layout.
- Small local models can be slow or inaccurate. Check important answers against the source.
- Knowledge queries have a 120-second frontend timeout; large documents and CPU-only inference can exceed it.
- Graph completeness depends on indexing and extraction. Uploading alone does not build a knowledge graph.
- Accepted work has bounded crash recovery. Interrupted model generation starts again; it does not resume the exact token. Keep the data volumes and allow worker leases to expire.
- A successful local deployment is not a guarantee for every platform or network. Some base images and dependencies are not fully pinned.

## Repository map

```text
examples/           Fictional documents and a reproducible first-use walkthrough
docs/images/        Real application screenshots using only demo data
frontend/           React + TypeScript interface
src/modules/        Auth, projects, files, processing, chat, RAG, graph, gateway
src/shared/         Shared configuration, storage, service clients, model adapters
libs/LightRAG/      Vendored retrieval implementation
scripts/            Container setup and diagnostics
tests/             Backend regression tests
docker-compose.yml Full local stack
```

[Backend guide](./src/README.md) · [Frontend guide](./frontend/README.md) ·
[Scripts](./scripts/README.md) · [Development guide](./docs/DEVELOPMENT.md)

## Privacy and license

Local credentials, uploads, database files, OCR overrides, and assistant settings
are excluded from commits/build contexts. The default workflow uses local models;
configuring an external provider changes where document content may be sent.
Review logs before sharing them, as they can contain document or request details.

This repository uses a **[non-commercial license](./LICENSE)**. A public repository
does not grant unrestricted commercial use. Copyright notices and Git author
metadata remain part of the repository history.
