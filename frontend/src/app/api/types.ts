export interface Envelope<T> {
  data: T;
  meta: Record<string, unknown>;
}

export interface ApiProblem {
  type: string;
  title: string;
  status: number;
  detail: string;
  request_id?: string;
  current?: { revision?: number };
}

export type Role = "ADMIN" | "EDITOR" | "VIEWER";

export interface SessionUser {
  id: string | null;
  email: string | null;
  display_name: string;
  role: Role;
}

export type ReadinessStatus =
  | "NOT_ASSESSED"
  | "GAP"
  | "IN_PROGRESS"
  | "PARTIAL"
  | "READY"
  | "NOT_APPLICABLE";

export interface PersonSummary {
  id: string;
  display_name: string;
  email: string | null;
}

export interface AssessmentSummary {
  id: string;
  status_code: ReadinessStatus;
  applicability: "UNDETERMINED" | "APPLICABLE" | "NOT_APPLICABLE";
  owner: PersonSummary | null;
  assignee: PersonSummary | null;
  due_date: string | null;
  implementation_notes: string;
  tags: string[];
  revision: number;
  updated_at: string;
}

export interface RequirementSummary {
  id: string;
  external_id: string;
  title: string;
  summary: string;
  guidance: string;
  source_reference: string;
  parent_id: string | null;
  framework: { id: string; slug: string; name: string; version: string };
  domain: { id: string; external_id: string; name: string };
  assessment: AssessmentSummary;
  document_count: number;
  evidence_count: number;
  control_count: number;
  last_updated: string;
}

export type TextResourceKind = "NOTE" | "PLAYBOOK" | "CONTACT";

export interface TextResource {
  id: string;
  kind: TextResourceKind;
  title: string;
  body: string;
  author_user_id: string | null;
  author: PersonSummary | null;
  contact_user_id: string | null;
  contact_user: PersonSummary | null;
  revision: number;
  created_at: string;
  edited_at: string | null;
}

export interface ControlRecord {
  id: string;
  code: string;
  name: string;
  description: string;
  status_code: "PLANNED" | "IMPLEMENTING" | "OPERATING" | "NEEDS_ATTENTION" | "RETIRED";
  owner: PersonSummary | null;
  implementation_notes: string;
  tags: string[];
  revision: number;
  created_at: string;
  updated_at: string;
  requirements: Array<{
    id: string;
    coverage: string;
    rationale: string;
    requirement: {
      id: string;
      external_id: string;
      title: string;
      domain: string;
      framework: string;
    };
  }>;
}

export interface ActivityRecord {
  id: string;
  action_code: string;
  actor_user_id: string | null;
  actor_display_name?: string | null;
  change_summary?: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  created_at: string;
}

export interface InferenceStatus {
  enabled: boolean;
  ready: boolean;
  allowed_base_urls: string[];
  limits: {
    max_concurrent_runs: number;
    max_context_chars: number;
    max_output_chars: number;
    max_iterations: number;
    max_tool_calls: number;
    timeout_seconds: number;
  };
}

export interface InferenceCapabilities {
  streaming: boolean;
  tool_calls: boolean;
  structured_output: boolean;
  embeddings: boolean;
  max_context_tokens: number | null;
}

export interface InferenceProvider {
  id: string;
  provider_identifier: string;
  display_name: string;
  base_url: string;
  model_id: string;
  api_mode: "CHAT_COMPLETIONS";
  capabilities: InferenceCapabilities;
  timeout_seconds: number;
  tls_policy: "REQUIRED" | "PRIVATE_CA_ALLOWED" | "PLAINTEXT_LOCAL_ONLY";
  data_policy: "LOCAL_ONLY" | "REDACTED_EXTERNAL" | "EXTERNAL_ALLOWED";
  secret_status: "CONFIGURED" | "MISSING" | "NOT_REQUIRED";
  enabled: boolean;
  is_default: boolean;
  last_tested_at: string | null;
  last_test_status: string | null;
  last_test_latency_ms: number | null;
  revision: number;
  created_at: string;
  updated_at: string;
}

export interface InferenceSkill {
  id: string;
  version: string;
  name: string;
  description: string;
  record_scopes: string[];
  writes_workspace: false;
  requires_confirmation: boolean;
  output_schema: Record<string, unknown>;
}

export interface ContextPreview {
  text: string;
  digest: string;
  source_references: string[];
  omissions: string[];
  selected_record_types: string[];
  typed_resource_text_included: boolean;
  attachment_bytes_included: false;
}

export interface InferenceStreamEvent extends Record<string, unknown> {
  type: "run_started" | "status" | "text_delta" | "usage" | "proposal" | "completed" | "error";
  run_id?: string;
  status?: string;
  text?: string;
  usage?: Record<string, number>;
  proposal?: Record<string, unknown>;
  terminal_state?: "COMPLETED" | "CANCELLED" | "TIMED_OUT" | "FAILED";
  structured?: boolean;
  error_code?: string;
  message?: string;
}
