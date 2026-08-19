/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_GATEWAY_URL?: string;
  readonly VITE_PROJECT_SERVICE_URL?: string;
  readonly VITE_CHAT_SERVICE_URL?: string;
  readonly VITE_RAG_SERVICE_URL?: string;
  readonly VITE_FILE_SERVICE_URL?: string;
  readonly VITE_QUESTION_SERVICE_URL?: string;
  readonly VITE_GRAPH_SERVICE_URL?: string;
  readonly VITE_AUTH_SERVICE_URL?: string;
  readonly VITE_MONITORING_SERVICE_URL?: string;
  readonly VITE_FRONTEND_URL?: string;
  readonly VITE_API_PREFIX?: string;
  readonly VITE_DEBUG_MODE?: string;
  readonly VITE_LOG_LEVEL?: string;
  readonly VITE_DEPLOYMENT_MODE?: string;
  readonly VITE_USE_MOCK_API?: string;
  readonly VITE_API_DEFAULT_TIMEOUT?: string;
  readonly VITE_BACKEND_HEALTH_CHECK_INTERVAL?: string;
  readonly [key: string]: string | undefined;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

interface Window {
  __authInitialized?: boolean;
  __fetchingPermissions?: boolean;
}
