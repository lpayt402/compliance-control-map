import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../../app/api/client";
import { createQueryClient } from "../../app/query-client";
import { ProviderPanel } from "./ProviderPanel";

afterEach(() => vi.restoreAllMocks());

describe("ProviderPanel", () => {
  it("creates only a secret reference and surfaces a sanitized provider test", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "get").mockImplementation((path) => Promise.resolve((
      path === "/inference/status"
        ? {
            enabled: true,
            ready: true,
            allowed_base_urls: ["http://host.docker.internal:11434/v1"],
            limits: {
              max_concurrent_runs: 2,
              max_context_chars: 60000,
              max_output_chars: 12000,
              max_iterations: 4,
              max_tool_calls: 8,
              timeout_seconds: 90,
            },
          }
        : []
    ) as never));
    const created = {
      id: "provider-1",
      provider_identifier: "local-ollama",
      display_name: "Local Ollama",
      base_url: "http://host.docker.internal:11434/v1",
      model_id: "qwen3:8b",
      api_mode: "CHAT_COMPLETIONS",
      capabilities: {
        streaming: true,
        tool_calls: false,
        structured_output: false,
        embeddings: false,
        max_context_tokens: null,
      },
      timeout_seconds: 60,
      tls_policy: "PLAINTEXT_LOCAL_ONLY",
      data_policy: "LOCAL_ONLY",
      secret_status: "NOT_REQUIRED",
      enabled: false,
      is_default: false,
      last_tested_at: null,
      last_test_status: null,
      last_test_latency_ms: null,
      revision: 1,
      created_at: "2026-08-24T00:00:00Z",
      updated_at: "2026-08-24T00:00:00Z",
    };
    const post = vi.spyOn(api, "post")
      .mockResolvedValueOnce(created)
      .mockResolvedValueOnce({
        reachable: true,
        model_accepted: true,
        latency_ms: 12,
        error_code: null,
        message: "Provider and configured model responded successfully.",
      });
    render(
      <QueryClientProvider client={createQueryClient()}>
        <ProviderPanel />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Enabled and ready")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Add provider" }));
    await user.type(screen.getByLabelText("Profile ID"), "local-ollama");
    await user.type(screen.getByLabelText("Display name"), "Local Ollama");
    await user.type(
      screen.getByLabelText("Base URL"),
      "http://host.docker.internal:11434/v1",
    );
    await user.type(screen.getByLabelText("Model ID"), "qwen3:8b");
    await user.selectOptions(screen.getByLabelText("TLS policy"), "PLAINTEXT_LOCAL_ONLY");
    await user.click(screen.getByRole("button", { name: "Save provider" }));

    expect(post).toHaveBeenNthCalledWith(1, "/inference/providers", expect.objectContaining({
      provider_identifier: "local-ollama",
      secret_ref: null,
    }));
    expect(post.mock.calls[0]?.[1]).not.toHaveProperty("api_key");

    expect(await screen.findByText("Not required")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Test Local Ollama" }));
    await waitFor(() => expect(post).toHaveBeenNthCalledWith(
      2,
      "/inference/providers/provider-1/test",
      {},
    ));
    expect(await screen.findByText("Connected · 12 ms")).toBeVisible();
  });
});
