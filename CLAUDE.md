# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Building and Running Services

**Start all microservices:**
```bash
./start_services.sh
```

**Stop all microservices:**
```bash
./stop_services.sh
```

**Frontend development:**
```bash
cd frontend
npm run dev                    # Development server
npm run build                  # Production build
npm run lint                   # Lint TypeScript/React code
npm run test                   # Run tests with vitest
npm run clean                  # Clean compiled files
```

**Backend development:**
```bash
# 所有后端服务现在都在微服务架构中
./start_services.sh  # 启动所有微服务
```

**Individual microservice testing:**
```bash
cd src/modules/[service-name]
python -m [service-name].main --port [port]
```

**System diagnostics:**
```bash
python scripts/diagnose_services.py
```

### Testing

**Run Python tests:**
```bash
pytest tests/
pytest tests/test_auth_service.py  # Specific service
pytest tests/integration/          # Integration tests
pytest --cov=src tests/ --cov-report=html  # With coverage
pytest -x                          # Stop on first failure
```

**Frontend tests:**
```bash
cd frontend
npm run test                       # Run vitest tests
npm run clean                      # Clean compiled files before build
```

### Linting and Formatting

**Python:**
```bash
ruff check src/              # Check for style issues
ruff format src/             # Format code
```

**Frontend:**
```bash
cd frontend
npm run lint                 # ESLint + TypeScript checking
npm run clean                # Remove compiled files
npm run clean-build          # Clean + build for development
npm run clean-build:prod     # Clean + production build
```

## Architecture Overview

Lumidoc is a microservices-based intelligent document processing platform with strict service isolation and shared infrastructure components.

### Core Architecture Principles

1. **Microservices Isolation**: Each service (`src/modules/[service]/`) handles a single responsibility
2. **Shared Infrastructure**: Common components in `src/shared/` for configuration, service discovery, and utilities
3. **Service Communication**: All inter-service calls use the unified ServiceClient (`src/shared/service_client.py`)
4. **API Gateway**: All external access routes through the gateway service (port 8888)
5. **Service Discovery**: Redis-based automatic service registration and discovery

### Service Portfolio

**Core Infrastructure Services:**
- **Gateway** (8888): API gateway and load balancer
- **Auth** (8007): JWT authentication and user management
- **Project** (8020): Multi-tenant project management
- **Monitoring** (8008): Health checks and system monitoring

**Data Processing Services:**
- **File** (8004): File upload/download and metadata management
- **FileProc** (8005): Async document processing (PDF, Office, OCR)
- **LightRAG** (8006): RAG service with vector search and knowledge graphs
- **Graph** (8003): Neo4j knowledge graph construction and queries
- **LLM** (8080): Unified LLM interface (Deepseek, OpenAI, Azure, Ollama)

**Business Logic Services:**
- **Chat** (8001): WebSocket chat with context management
- **Question** (8002): Q&A management and knowledge base

**Frontend:**
- **React App** (3000): TypeScript + Vite + TailwindCSS
- **Backend API** (8000): FastAPI main backend service

### Data Stores

- **PostgreSQL**: Relational data + pgvector for embeddings
- **Redis**: Caching, queues, and service registry
- **Neo4j**: Knowledge graph storage
- **MinIO**: Object storage for documents and files (S3-compatible)

### Key Data Flows

1. **Document Processing**: File → FileProc → LightRAG → Graph
2. **Intelligent Q&A**: Question → LightRAG → LLM → Response
3. **Real-time Chat**: WebSocket → Chat → LightRAG + LLM → Stream Response
4. **Project Management**: Project → Auth → File → Other Services

## Development Patterns

### Configuration Management

All services use unified configuration from `src/shared/config/`:
- Environment variables via `.env` files (local development only)
- Service-specific configs in each module's `config/` directory
- Kubernetes ConfigMap support for production
- Use national mirror sources for dependencies (Taobao, Tsinghua)
- All sensitive credentials must be environment-driven, never hardcoded

### Service Communication

**Always use ServiceClient for inter-service calls:**
```python
from src.shared.service_client import ServiceClient

client = ServiceClient()
result = await client.call_service(
    service_name="llm",
    endpoint="/api/v1/llm/generate",
    method="POST",
    data={"prompt": "Hello world"}
)
```

**Service Registration Pattern:**
```python
from src.shared.service_discovery import ServiceRegistry

registry = ServiceRegistry()
await registry.register_service(
    service_name="auth",
    service_url="http://localhost:8007",
    health_check_url="http://localhost:8007/healthz"
)
```

### Error Handling

Use standardized error responses from `src/shared/errors/`:
```python
from src.shared.errors.service_errors import ServiceError
from src.shared.errors.error_handlers import handle_service_error
```

### Database Integration

**PostgreSQL with pgvector:**
```python
from src.shared.database import get_database_connection
from src.shared.config.service_config import DatabaseConfig
```

**Redis operations:**
```python
from src.shared.clients.redis_client import get_redis_client
```

### File Storage Integration

**Use unified storage interface for all file operations:**
```python
from src.shared.storage.storage_factory import get_storage

# For different directory types
upload_storage = await get_storage(directory_type="upload")
content_storage = await get_storage(directory_type="content") 
rag_storage = await get_storage(directory_type="rag")
models_storage = await get_storage(directory_type="models")

# Basic operations
await storage.save_file(file_id="example.txt", content=b"data")
content = await storage.get_file("example.txt")
exists = await storage.file_exists("example.txt")
await storage.delete_file("example.txt")

# For MinIO: Get presigned URLs for direct access
url = storage.get_file_url("example.txt", expire=3600)
```

### LLM Integration

All LLM calls go through the unified LLM service:
```python
# Don't call LLM APIs directly
# Use the LLM service instead
llm_response = await client.call_service(
    service_name="llm",
    endpoint="/api/v1/llm/chat",
    data={"messages": messages, "model": "deepseek-chat"}
)
```

## Important Constraints

### Code Style and Development Standards
- **All documentation and comments must be in Chinese** (as per .cursorrules)
- Follow existing patterns in each service
- Use TypeScript for frontend, Python 3.9+ for backend
- Maintain strict type hints in Python
- Component naming: PascalCase, functions: camelCase, constants: UPPER_CASE
- Interface names use `I` prefix (IUserService), types use `T` prefix (TUserData)
- Use ESLint + Prettier for consistent formatting
- Functions should have single responsibility and not exceed 50 lines
- Enforce Test-Driven Development (TDD) with >80% test coverage

### Architecture Rules
- **Strict microservices isolation**: Each service in `src/modules/{service}/` handles single responsibility
- **Never** bypass the gateway for external API access
- **Never** hardcode service URLs - use service discovery
- **Never** share database connections between services  
- **Never** put business logic in `src/shared/` - only infrastructure components
- All service communication must use unified ServiceClient
- Services must register with Redis-based service discovery
- Each service requires standardized `/healthz` health check endpoint

### Security
- All inter-service calls require JWT authentication
- Sensitive data must be encrypted in transit
- No secrets in code or logs
- User input must be validated and sanitized
- Implement data retention and cleanup policies

### Frontend Specifics
- No file extensions in import statements
- Use `npm run clean` before builds to remove compiled files
- Follow the component patterns in `src/components/`
- API calls through centralized clients in `src/api/`
- Responsive design supporting both mobile and desktop
- Components must support hover, focus, disabled states
- Meet basic accessibility standards (WCAG 2.1)

## Environment Setup

1. **Prerequisites**: Python 3.9+, Node.js 16+, Docker
2. **Conda Environment**: Activate the Lumidoc conda environment: `conda activate Lumidoc` (not base)
3. **Install dependencies**: `pip install -r requirements.txt` and `cd frontend && npm install`
4. **Setup environment**: Copy `.env.example` to `.env` and configure
5. **Auto-initialization**: Run `./start_services.sh` - MinIO containers start automatically
6. **Verify setup**: `python scripts/diagnose_services.py`

### 🔄 First Run Experience

**For new team members or fresh deployments:**
- No manual setup needed
- MinIO initializes with proper bucket configuration using Docker volumes
- All storage paths are created on-demand by S3Storage interface

**Manual MinIO setup (optional):**
```bash
# If you need to setup MinIO separately
./scripts/setup_minio.sh
```

### MinIO Storage Setup

**Quick setup for MinIO:**
```bash
# Initialize and test MinIO
./scripts/setup_minio.sh

# Migrate existing files to MinIO (optional)
python3 scripts/migrate_to_minio.py

# Test MinIO integration
python3 scripts/test_minio_integration.py
```

**MinIO Configuration:**
- Storage type is controlled by `STORAGE_TYPE=s3` in `.env`
- All directory paths (UPLOAD_DIR, CONTENT_DIR, RAG_DIR, MODELS_DIR) are mapped to MinIO bucket prefixes
- MinIO runs in Docker with persistent volumes
- MinIO Console: http://localhost:9001 (minioadmin/minioadmin)
- API Endpoint: http://localhost:9000

## Troubleshooting

**Service startup issues:**
- Check logs in `logs/` directory
- Verify port availability with `lsof -i :[port]`
- Ensure Docker containers are running

**Database connection issues:**
- Verify pgvector extension: `docker exec stp_postgres psql -U stpuser -d stpdb -c "SELECT * FROM pg_extension WHERE extname = 'vector'"`
- Check Redis connectivity: `redis-cli -h localhost -p 6379 ping`

**Frontend issues:**
- Run `npm run clean` to clear compiled files
- Check for duplicate .js/.ts files
- Verify no file extensions in imports

**LLM service issues:**
- Check API keys in environment variables
- Verify model availability through `/api/v1/llm/models` endpoint
- Monitor rate limits and quotas

**NumPy compatibility issues:**
- If experiencing numpy compatibility errors with docling, downgrade numpy: `pip install "numpy<2.0"`
- This resolves pandas/docling library compatibility issues

**MinIO/S3 storage issues:**
- Ensure STORAGE_TYPE=s3 is set in environment variables for services using S3
- Check MinIO container status: `docker ps | grep minio`
- Verify bucket configuration and access credentials
- Check storage logs for connection errors

## Development Workflow

### Git Workflow and Commit Standards
- Use semantic commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
- Each commit should address a single issue
- Provide clear commit messages in Chinese
- All changes must pass automated tests before merging
- No "fix naming" or "test" patch-style commits allowed

### Code Review Standards
- All complex logic must include business context and explanations
- No empty directories, temporary code, or debug statements
- All modifications must be consistent with existing team standards
- Test coverage must be maintained above 80%
- Documentation must be updated for API changes