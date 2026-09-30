import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClient, RevisionConflict } from "./client";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ApiClient", () => {
  it("omits CSRF work for safe requests", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: { status: "ok" }, meta: {} }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await new ApiClient().get("/health/live");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const options = fetchMock.mock.calls[0]?.[1];
    expect(new Headers(options?.headers).has("X-CSRF-Token")).toBe(false);
  });

  it("fetches and caches a CSRF token for unsafe requests", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: { csrf_token: "test-csrf" }, meta: {} }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockImplementation(() =>
        Promise.resolve(
          new Response(JSON.stringify({ data: { saved: true }, meta: {} }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        ),
      );
    const client = new ApiClient();

    await client.post("/controls", { name: "Access review" });
    await client.post("/controls", { name: "Change review" });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    const firstMutationHeaders = new Headers(fetchMock.mock.calls[1]?.[1]?.headers);
    const secondMutationHeaders = new Headers(fetchMock.mock.calls[2]?.[1]?.headers);
    expect(firstMutationHeaders.get("X-CSRF-Token")).toBe("test-csrf");
    expect(secondMutationHeaders.get("X-CSRF-Token")).toBe("test-csrf");
  });

  it("preserves the safe revision-conflict contract", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: { csrf_token: "test-csrf" }, meta: {} }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            type: "https://compliance-control-map.local/problems/revision-conflict",
            title: "The requirement changed before your update was saved",
            status: 409,
            detail: "Reload the current values and apply your change again.",
            request_id: "request-1",
            current: { revision: 4 },
          }),
          { status: 409, headers: { "Content-Type": "application/problem+json" } },
        ),
      );

    await expect(new ApiClient().patch("/requirements/cc61/assessment", {})).rejects.toEqual(
      expect.objectContaining<Partial<RevisionConflict>>({
        name: "RevisionConflict",
        currentRevision: 4,
        detail: "Reload the current values and apply your change again.",
      }),
    );
  });

  it("surfaces FastAPI validation messages", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: [{ msg: "Enter a real email address." }] }), {
        status: 422,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(new ApiClient().get("/users")).rejects.toEqual(
      expect.objectContaining({ detail: "Enter a real email address." }),
    );
  });

  it("parses split NDJSON events and sends CSRF with an abort signal", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('{"type":"run_started","run_id":"run-1"}\n{"type":"text_'));
        controller.enqueue(encoder.encode('delta","text":"Draft"}\n'));
        controller.close();
      },
    });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: { csrf_token: "stream-csrf" }, meta: {} }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(stream, {
          status: 200,
          headers: { "Content-Type": "application/x-ndjson" },
        }),
      );
    const abort = new AbortController();
    const events: Array<Record<string, unknown>> = [];

    await new ApiClient().stream(
      "/inference/runs/stream",
      { skill_id: "control-review" },
      (event) => events.push(event),
      abort.signal,
    );

    expect(events).toEqual([
      { type: "run_started", run_id: "run-1" },
      { type: "text_delta", text: "Draft" },
    ]);
    const options = fetchMock.mock.calls[1]?.[1];
    expect(new Headers(options?.headers).get("X-CSRF-Token")).toBe("stream-csrf");
    expect(options?.signal).toBe(abort.signal);
  });
});
