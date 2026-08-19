# Runtime scripts

Lumidoc is operated through Docker Compose. Host-level dependency installers,
database reset utilities, hardware-specific setup, and one-off recovery scripts
have been removed.

- `docker_healthcheck.py` is copied into backend images and performs HTTP health
  checks without requiring `curl`.
- `setup_pgvector.sql` is mounted into PostgreSQL's initialization directory and
  enables the `vector` extension for a new database volume.

Use the repository-level commands for normal operation:

```bash
./start_services.sh
./stop_services.sh
```

Persistent data is managed by Docker volumes. Back up a volume before performing
manual database or object-storage maintenance.
