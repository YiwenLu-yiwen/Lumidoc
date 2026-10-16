# Publication and deployment review

Review date: 2026-10-16.

This is a bounded repository review, not a guarantee that no sensitive information
or vulnerability exists. Do not treat making a repository public as approval to
expose a running instance to the internet.

## Scope

- Tracked source, documentation, and non-ignored files proposed for commit.
- All 1,027 historical Git blobs reachable before this review, using secret-pattern
  scanning; current local credential values were also compared without printing them.
- Personal contact details, machine paths, fixed server addresses, generated data,
  Docker build contexts, and startup configuration.
- A clean source export with no original `.env`, local data, or ignored OCR models;
  separate Compose project, fresh database/model volumes, and generated credentials.

The scan does not cover remote forks, deleted/unreachable Git objects, external
backups, other machines, or the contents of existing user data volumes. No external
secret-verification requests were made for the history scan.

## Changes made

- Removed personal contact addresses from the error page and license contact
  instructions. Kept the copyright attribution and non-commercial license terms.
- Removed a fixed deployment server address from frontend configuration and CORS
  defaults. Local browser origins remain supported.
- Removed database and Redis URL logging that could disclose credentials.
- Excluded local assistant settings, database snapshots, model weights, and runtime
  data from source/build contexts. Original local data was not deleted.
- Corrected overly broad `lib/` and `models/` ignore rules. They had hidden required
  frontend utilities and Python model definitions from fresh checkouts.
- Made default PDF OCR use the models bundled in its installed dependency when no
  complete explicit override is available; local model files are not copied into images.
- First startup now generates random credentials into an owner-readable `.env`.
  Existing installations are not silently re-keyed.
- Only the frontend and gateway publish host ports, bound to loopback by default.
  Internal databases and services remain on the Compose network.
- Fixed the graph service's Redis address for container networking.
- Applied compatible frontend dependency updates and refreshed the lockfile.

## Remaining publication considerations

**Old history is not scrubbed by an ordinary commit.** Earlier versions still
contain personal contact information, a deployment address, and author/committer
identity. The license also intentionally retains copyright attribution. Choose a
clean publication snapshot or an explicitly planned history rewrite if those
historical details must not be public. This review does not rewrite existing history
or change repository visibility.

No live third-party provider key or complete private key was identified by the
scans. Findings included example/default passwords, test credentials, translations,
and code checking PEM delimiters. Default/example values also matched some existing
local settings: rotate any reused credentials before exposing a deployment. Do not
copy the existing private `.env` into a public artifact.

The frontend dependency audit after compatible updates reports **11 advisories:
4 moderate, 5 high, 2 critical**. Remaining paths include Vitest/tinypool and Tailwind
build tooling; the production Nginx image serves static output and does not run
these Node tools. They still matter for development/build environments. Major tool
migrations were not forced as part of this cleanup. Re-run `npm audit` before a release;
counts and advisories can change. This is not a vulnerability-free release claim.

The supported quick start is local Docker deployment. Public hosting needs TLS,
API/CORS configuration, access controls, and a separate security review. Image tags
and some Python requirements are not fully immutable. Health checks cannot guarantee
model accuracy, arbitrary file compatibility, or crash recovery.

## Verification results

- Clean exported-source deployment: startup completed successfully with a newly
  generated `.env`, independent volumes, and automatic Ollama model provisioning.
- Backend regression suite: 98 passed; local OCR tests: 2 passed; bootstrap failure,
  credential consistency, permissions, and restart preservation test: 1 passed.
- Frontend: 36 unit tests passed; TypeScript/production build passed; lint has no
  errors and 2 existing ref-cleanup warnings.
- End-to-end smoke test passed: registration, login, project creation, upload,
  knowledge-base indexing/query, streamed chat, and cross-user access denial.
- Browser checks passed for language persistence, mobile/desktop homepage layout,
  favicon delivery, and absence of page errors.

The end-to-end test uses invented fixture documents and accounts in the isolated
stack. Real user projects were not used or included in documentation screenshots.

## Reproducing checks

```sh
# Static configuration and shell checks (no .env contents printed)
sh -n start_services.sh stop_services.sh
docker compose config --quiet

# Frontend
cd frontend
npm ci
npm run test -- --run
npm run build
npm audit
```

Backend tests use the backend dependency environment; OCR tests additionally need
the file-processing dependencies. Run deployment checks in a separate checkout and
Compose project so private project data is not used as a test fixture. Do not upload
raw logs or scanner reports: they may contain sensitive values or paths.
