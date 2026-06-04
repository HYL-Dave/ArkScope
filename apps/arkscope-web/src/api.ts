// Thin client for the local ArkScope sidecar.
//
// Connection params come from the Electron preload bridge (window.arkscope) when
// running in the desktop shell, or fall back to a dev default when running the
// Vite dev server in a plain browser.

export interface ApiStatus {
  status: string;
  timestamp: string;
  tools_registered: number;
  tool_categories: Record<string, number>;
  data_sources: Record<string, number>;
}

interface ArkscopeBridge {
  apiBase: string;
  apiToken?: string;
}

declare global {
  interface Window {
    arkscope?: ArkscopeBridge;
  }
}

export const apiBase: string =
  window.arkscope?.apiBase ??
  (import.meta.env.VITE_API_BASE as string | undefined) ??
  "http://127.0.0.1:8420";

const apiToken: string | undefined = window.arkscope?.apiToken;

function authHeaders(): Record<string, string> {
  return apiToken ? { "x-arkscope-token": apiToken } : {};
}

export async function getHealthz(): Promise<boolean> {
  try {
    const r = await fetch(`${apiBase}/healthz`, { headers: authHeaders() });
    return r.ok;
  } catch {
    return false;
  }
}

export async function getStatus(): Promise<ApiStatus> {
  const r = await fetch(`${apiBase}/status`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`/status returned ${r.status}`);
  return (await r.json()) as ApiStatus;
}
