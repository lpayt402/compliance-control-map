import type { ApiProblem, Envelope } from "./types";

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function validationMessage(item: unknown): string | null {
  if (item === null || typeof item !== "object") return null;
  const message = (item as Record<string, unknown>).msg;
  return typeof message === "string" ? message : null;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly problem: ApiProblem;

  constructor(problem: ApiProblem) {
    super(problem.detail);
    this.name = "ApiError";
    this.status = problem.status;
    this.detail = problem.detail;
    this.problem = problem;
  }
}

export class RevisionConflict extends ApiError {
  readonly currentRevision: number | undefined;

  constructor(problem: ApiProblem) {
    super(problem);
    this.name = "RevisionConflict";
    this.currentRevision = problem.current?.revision;
  }
}

export class ApiClient {
  private csrfToken: string | null = null;
  private csrfRequest: Promise<string> | null = null;

  private path(path: string): string {
    return `/api/v1${path.startsWith("/") ? path : `/${path}`}`;
  }

  private async csrf(): Promise<string> {
    if (this.csrfToken) return this.csrfToken;
    if (!this.csrfRequest) {
      this.csrfRequest = fetch(this.path("/auth/csrf"), {
        credentials: "include",
        headers: { Accept: "application/json" },
      })
        .then(async (response) => {
          if (!response.ok) throw await this.errorFrom(response);
          const payload = (await response.json()) as Envelope<{ csrf_token: string }>;
          this.csrfToken = payload.data.csrf_token;
          return payload.data.csrf_token;
        })
        .finally(() => {
          this.csrfRequest = null;
        });
    }
    return this.csrfRequest;
  }

  setCsrfToken(token: string | null): void {
    this.csrfToken = token;
  }

  private async errorFrom(response: Response): Promise<ApiError> {
    const contentType = response.headers.get("content-type") ?? "";
    let problem: ApiProblem;
    if (contentType.includes("json")) {
      const candidate = (await response.json()) as Partial<ApiProblem>;
      const rawDetail = (candidate as { detail?: unknown }).detail;
      const validationItems: unknown[] = Array.isArray(rawDetail) ? rawDetail as unknown[] : [];
      const validationMessages = validationItems
        .map(validationMessage)
        .filter((message): message is string => message !== null);
      problem = {
        type: typeof candidate.type === "string" ? candidate.type : "about:blank",
        title: typeof candidate.title === "string" ? candidate.title : "Request failed",
        status: response.status,
        detail:
          typeof rawDetail === "string"
            ? rawDetail
            : validationMessages.length
              ? validationMessages.join(" ")
            : "The server could not complete the request.",
        request_id:
          typeof candidate.request_id === "string" ? candidate.request_id : undefined,
        current: candidate.current,
      };
    } else {
      problem = {
        type: "about:blank",
        title: "Request failed",
        status: response.status,
        detail: "The server could not complete the request.",
      };
    }
    if (response.status === 409 && problem.current?.revision !== undefined) {
      return new RevisionConflict(problem);
    }
    return new ApiError(problem);
  }

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const method = (init.method ?? "GET").toUpperCase();
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (UNSAFE_METHODS.has(method)) headers.set("X-CSRF-Token", await this.csrf());
    const response = await fetch(this.path(path), {
      ...init,
      method,
      headers,
      credentials: "include",
    });
    if (!response.ok) throw await this.errorFrom(response);
    if (response.status === 204) return undefined as T;
    const envelope = (await response.json()) as Envelope<T>;
    return envelope.data;
  }

  get<T = unknown>(path: string): Promise<T> {
    return this.request<T>(path);
  }

  private jsonRequest<T>(method: string, path: string, body: unknown): Promise<T> {
    return this.request<T>(path, {
      method,
      body: JSON.stringify(body),
      headers: { "Content-Type": "application/json" },
    });
  }

  post<T = unknown>(path: string, body?: unknown): Promise<T> {
    return this.jsonRequest<T>("POST", path, body ?? {});
  }

  patch<T = unknown>(path: string, body: unknown): Promise<T> {
    return this.jsonRequest<T>("PATCH", path, body);
  }

  delete<T = void>(path: string): Promise<T> {
    return this.request<T>(path, { method: "DELETE" });
  }

  upload<T>(path: string, body: FormData): Promise<T> {
    return this.request<T>(path, { method: "POST", body });
  }

  async stream<T extends Record<string, unknown>>(
    path: string,
    body: unknown,
    onEvent: (event: T) => void,
    signal?: AbortSignal,
  ): Promise<void> {
    const response = await fetch(this.path(path), {
      method: "POST",
      body: JSON.stringify(body),
      credentials: "include",
      signal,
      headers: {
        Accept: "application/x-ndjson",
        "Content-Type": "application/json",
        "X-CSRF-Token": await this.csrf(),
      },
    });
    if (!response.ok) throw await this.errorFrom(response);
    if (!response.body) throw new Error("The assistance stream returned no response body.");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffered = "";
    try {
      while (true) {
        const { done, value } = await reader.read();
        buffered += decoder.decode(value, { stream: !done });
        const lines = buffered.split("\n");
        buffered = lines.pop() ?? "";
        for (const line of lines) {
          if (line.trim()) onEvent(JSON.parse(line) as T);
        }
        if (done) break;
      }
      if (buffered.trim()) onEvent(JSON.parse(buffered) as T);
    } finally {
      reader.releaseLock();
    }
  }

  async download(path: string, method = "GET"): Promise<{ blob: Blob; filename: string }> {
    const headers = new Headers({ Accept: "application/octet-stream" });
    if (UNSAFE_METHODS.has(method)) headers.set("X-CSRF-Token", await this.csrf());
    const response = await fetch(this.path(path), { method, headers, credentials: "include" });
    if (!response.ok) throw await this.errorFrom(response);
    const disposition = response.headers.get("content-disposition") ?? "";
    const match = disposition.match(/filename="?([^";]+)"?/i);
    return { blob: await response.blob(), filename: match?.[1] ?? "download" };
  }
}

export const api = new ApiClient();
