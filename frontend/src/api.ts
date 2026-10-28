export interface DiagnosticOptions {
  emotions: string[];
  circles: string[];
  drivers_by_emotion: Record<string, string[]>;
}

export interface ResolveHeartPayload {
  belief_system: string;
  user_emotion: string;
  user_circle: string;
  user_driver: string;
}

export interface ScriptureResponse {
  crisis_override: false;
  source: string;
  scripture_text: string;
  word_of_hope: string;
  prayer_reflection: string;
}

export interface CrisisResource {
  name: string;
  contact: string;
}

export interface CrisisResponse {
  crisis_override: true;
  message: string;
  resources: CrisisResource[];
}

export type ResolveHeartResponse = ScriptureResponse | CrisisResponse;

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "");

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function formatDetail(body: unknown): string {
  if (typeof body !== "object" || body === null || !("detail" in body)) return "";
  const detail = (body as { detail: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((entry) => {
        if (typeof entry !== "object" || entry === null) return String(entry);
        const { loc, msg } = entry as { loc?: unknown; msg?: unknown };
        const location = Array.isArray(loc) ? loc.filter((part) => part !== "body").join(".") : "";
        const message = typeof msg === "string" ? msg : "";
        return location ? `${location}: ${message}` : message;
      })
      .filter((text) => text.length > 0)
      .join("; ");
  }
  return "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(
      0,
      `We couldn't reach the server at ${API_BASE_URL}. Check that the backend is running, then try again.`,
    );
  }

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    throw new ApiError(response.status, formatDetail(body) || `The server returned HTTP ${response.status}.`);
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(response.status, "The server returned an unexpected response.");
  }
}

export function fetchDiagnosticOptions(signal?: AbortSignal): Promise<DiagnosticOptions> {
  return request<DiagnosticOptions>("/api/v1/diagnostic-options", { signal });
}

export async function fetchBeliefSystems(signal?: AbortSignal): Promise<string[]> {
  const body = await request<{ belief_systems: string[] }>("/api/v1/belief-systems", { signal });
  return body.belief_systems;
}

export function resolveHeart(payload: ResolveHeartPayload, signal?: AbortSignal): Promise<ResolveHeartResponse> {
  return request<ResolveHeartResponse>("/api/v1/resolve-heart", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
}
