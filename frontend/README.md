# Lumidoc frontend

React, TypeScript, and Vite power the project workspace, document preview,
knowledge-base management, and streaming chat interface.

See the [development guide](../docs/DEVELOPMENT.md) for starting the backend and
switching between the container frontend and Vite.

From this directory:

```sh
npm ci
npm run dev              # Development server
npm run lint             # ESLint checks
npm run test -- --run    # Unit tests
npm run build            # TypeScript check and production bundle
```

`src/api/` contains API clients; `src/features/` contains feature screens;
`src/components/` contains shared UI; `src/context/` contains application providers.
The default API gateway is `http://localhost:8888`.

`npm run test:e2e:smoke` exercises a running backend and creates fixture data.
Run it only against a separate test deployment.
