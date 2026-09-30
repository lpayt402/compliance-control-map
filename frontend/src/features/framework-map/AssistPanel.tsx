import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";

import { ApiError, api } from "../../app/api/client";
import type {
  ContextPreview,
  InferenceProvider,
  InferenceSkill,
  InferenceStatus,
  InferenceStreamEvent,
  TextResourceKind,
} from "../../app/api/types";

export interface AssistanceResourceDraft {
  kind: TextResourceKind;
  title: string;
  body: string;
}

interface AssistPanelProps {
  canEdit: boolean;
  entityId: string;
  entityType: "requirement" | "control";
  onImplementationDraft: (text: string) => void;
  onResourceDraft: (draft: AssistanceResourceDraft) => void;
}

interface InferenceRunHistory {
  id: string;
  provider_display_name: string;
  model_id: string;
  skill_id: string;
  skill_version: string;
  status: string;
  started_at: string;
  duration_ms: number | null;
  error_code: string | null;
  feedback_rating: string | null;
}

type RunState = "IDLE" | "RUNNING" | "COMPLETED" | "CANCELLED" | "TIMED_OUT" | "FAILED";

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.detail : "The assistance request could not be completed.";
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function proposalBody(proposal: Record<string, unknown>): string {
  const sections: Array<[string, unknown]> = [
    ["Summary", proposal.summary],
    ["Objective", proposal.objective],
    ["Known facts", proposal.known_facts],
    ["Assumptions", proposal.assumptions],
    ["Missing information", proposal.missing_information ?? proposal.missing_details ?? proposal.missing_operating_detail],
    ["Suggested next actions", proposal.suggested_next_actions],
    ["Wording suggestions", proposal.wording_suggestions],
    ["Prerequisites", proposal.prerequisites],
    ["Steps", proposal.steps],
    ["Expected artifacts", proposal.expected_artifacts],
    ["Validation checks", proposal.validation_checks],
    ["Contacts and questions", proposal.contacts_and_questions],
    ["Evidence categories", proposal.evidence_categories],
    ["Limitations", proposal.limitations],
  ];
  return sections.flatMap(([heading, value]) => {
    if (typeof value === "string" && value.trim()) return [`${heading}\n${value.trim()}`];
    const values = stringList(value);
    return values.length ? [`${heading}\n${values.map((item) => `- ${item}`).join("\n")}`] : [];
  }).join("\n\n");
}

function implementationDraft(proposal: Record<string, unknown>): string | null {
  const value = proposal.implementation_notes ?? proposal.implementation_note_draft;
  return typeof value === "string" && value.trim() ? value : null;
}

function proposalTitle(proposal: Record<string, unknown>): string {
  return typeof proposal.title === "string" && proposal.title.trim()
    ? proposal.title
    : "Assistance draft";
}

function terminalLabel(state: RunState): string {
  if (state === "TIMED_OUT") return "Timed out";
  if (state === "CANCELLED") return "Cancelled";
  if (state === "COMPLETED") return "Completed";
  if (state === "FAILED") return "Failed";
  if (state === "RUNNING") return "Running";
  return "Ready to preview";
}

export function AssistPanel({
  canEdit,
  entityId,
  entityType,
  onImplementationDraft,
  onResourceDraft,
}: AssistPanelProps) {
  const queryClient = useQueryClient();
  const controllerRef = useRef<AbortController | null>(null);
  const [skillId, setSkillId] = useState("");
  const [providerId, setProviderId] = useState("");
  const [instruction, setInstruction] = useState("");
  const [includeTextResources, setIncludeTextResources] = useState(true);
  const [includeMappedResources, setIncludeMappedResources] = useState(true);
  const [preview, setPreview] = useState<ContextPreview | null>(null);
  const [externalConfirmed, setExternalConfirmed] = useState(false);
  const [output, setOutput] = useState("");
  const [proposal, setProposal] = useState<Record<string, unknown> | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [structured, setStructured] = useState<boolean | null>(null);
  const [runState, setRunState] = useState<RunState>("IDLE");
  const [runError, setRunError] = useState<string | null>(null);
  const [copyState, setCopyState] = useState("");
  const [feedbackState, setFeedbackState] = useState("");
  const [feedbackComment, setFeedbackComment] = useState("");

  const statusQuery = useQuery({
    queryKey: ["inference", "status"],
    queryFn: () => api.get<InferenceStatus>("/inference/status"),
    enabled: canEdit,
  });
  const providersQuery = useQuery({
    queryKey: ["inference", "providers"],
    queryFn: () => api.get<InferenceProvider[]>("/inference/providers"),
    enabled: canEdit,
  });
  const skillsQuery = useQuery({
    queryKey: ["inference", "skills"],
    queryFn: () => api.get<InferenceSkill[]>("/inference/skills"),
    enabled: canEdit,
  });
  const historyQuery = useQuery({
    queryKey: ["inference", "runs"],
    queryFn: () => api.get<InferenceRunHistory[]>("/inference/runs"),
    enabled: canEdit,
  });
  const providers = (Array.isArray(providersQuery.data) ? providersQuery.data : []).filter((item) => item.enabled);
  const skills = (Array.isArray(skillsQuery.data) ? skillsQuery.data : []).filter((item) => item.record_scopes.includes(entityType));
  const provider = providers.find((item) => item.id === providerId);
  const skill = skills.find((item) => item.id === skillId);
  const isExternal = provider?.data_policy !== undefined && provider.data_policy !== "LOCAL_ONLY";
  const contextPayload = useMemo(() => ({
    skill_id: skillId,
    record_references: [{ kind: entityType, record_id: entityId }],
    instruction,
    include_text_resources: includeTextResources,
    include_mapped_resources: includeMappedResources,
  }), [entityId, entityType, includeMappedResources, includeTextResources, instruction, skillId]);

  const clearPreview = (): void => {
    setPreview(null);
    setExternalConfirmed(false);
    setRunError(null);
  };
  const previewMutation = useMutation({
    mutationFn: () => api.post<ContextPreview>("/inference/context-preview", contextPayload),
    onSuccess: (nextPreview) => {
      setPreview(nextPreview);
      setRunState("IDLE");
      setRunError(null);
    },
  });
  const feedback = useMutation({
    mutationFn: (rating: "USEFUL" | "NOT_USEFUL") => api.post(`/inference/runs/${runId}/feedback`, { rating, comment: feedbackComment.trim() || null }),
    onSuccess: (_data, rating) => {
      setFeedbackState(rating === "USEFUL" ? "Marked useful" : "Marked not useful");
      void queryClient.invalidateQueries({ queryKey: ["inference", "runs"] });
    },
  });

  async function run(): Promise<void> {
    if (!preview || !provider || !skill) return;
    const controller = new AbortController();
    controllerRef.current = controller;
    setOutput("");
    setProposal(null);
    setRunId(null);
    setStructured(null);
    setRunError(null);
    setRunState("RUNNING");
    setFeedbackState("");
    try {
      await api.stream<InferenceStreamEvent>(
        "/inference/runs/stream",
        {
          ...contextPayload,
          provider_profile_id: provider.id,
          agent_id: "compliance-assistant",
          context_digest: preview.digest,
          external_transfer_confirmed: isExternal && externalConfirmed,
        },
        (event) => {
          if (event.type === "run_started" && event.run_id) setRunId(event.run_id);
          if (event.type === "text_delta" && event.text) setOutput((current) => current + event.text);
          if (event.type === "proposal" && event.proposal) setProposal(event.proposal);
          if (event.type === "completed") {
            setStructured(Boolean(event.structured));
            setRunState(event.terminal_state === "CANCELLED" ? "CANCELLED" : "COMPLETED");
          }
          if (event.type === "error") {
            setRunError(event.message ?? "The assistance run failed.");
            setRunState(event.terminal_state === "TIMED_OUT" ? "TIMED_OUT" : event.terminal_state === "CANCELLED" ? "CANCELLED" : "FAILED");
          }
        },
        controller.signal,
      );
    } catch (error) {
      if (controller.signal.aborted || (error instanceof DOMException && error.name === "AbortError")) {
        setRunState("CANCELLED");
        setRunError(null);
      } else {
        setRunState("FAILED");
        setRunError(errorMessage(error));
      }
    } finally {
      controllerRef.current = null;
      if (isExternal) setExternalConfirmed(false);
      void queryClient.invalidateQueries({ queryKey: ["inference", "runs"] });
    }
  }

  async function copyResult(): Promise<void> {
    try {
      await navigator.clipboard.writeText(proposal ? proposalBody(proposal) || output : output);
      setCopyState("Copied");
    } catch {
      setCopyState("Copy failed");
    }
  }

  if (!canEdit) return <p className="viewer-note">Viewer access · model assistance is unavailable.</p>;
  if (statusQuery.isLoading || providersQuery.isLoading || skillsQuery.isLoading) return <p className="resource-state">Loading optional assistance…</p>;
  if (statusQuery.isError || providersQuery.isError || skillsQuery.isError) return <p className="form-error" role="alert">Optional assistance could not be loaded.</p>;
  if (!statusQuery.data?.enabled || !statusQuery.data.ready) return <p className="viewer-note">Model assistance is disabled. All compliance workflows remain available without it.</p>;

  const implementation = proposal ? implementationDraft(proposal) : null;
  const proposalSummary = proposal ? proposalBody(proposal) : "";
  const sources = proposal ? stringList(proposal.source_references) : [];
  const history = (Array.isArray(historyQuery.data) ? historyQuery.data : [])
    .filter((item) => typeof item.status === "string" && typeof item.started_at === "string")
    .slice(0, 5);
  const canRun = Boolean(preview && provider && skill && runState !== "RUNNING" && (!isExternal || externalConfirmed));

  return (
    <section className="assist-panel" aria-label="Optional model assistance">
      <header><p className="eyebrow">Optional · advisory · human-reviewed</p><h3>Assist this {entityType}</h3><p>Generate a bounded draft from the exact context shown below. Nothing is saved or applied automatically.</p></header>
      <div className="assist-controls">
        <label>Skill<select value={skillId} onChange={(event) => { setSkillId(event.target.value); clearPreview(); }}><option value="">Choose a skill</option>{skills.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Provider<select value={providerId} onChange={(event) => { setProviderId(event.target.value); clearPreview(); }}><option value="">Choose a provider</option>{providers.map((item) => <option key={item.id} value={item.id}>{item.display_name} · {item.model_id}</option>)}</select></label>
        <label className="assist-wide">Optional instruction<textarea maxLength={4000} rows={3} value={instruction} onChange={(event) => { setInstruction(event.target.value); clearPreview(); }} /></label>
        <fieldset className="assist-options assist-wide"><legend>Optional context</legend><label><input checked={includeMappedResources} type="checkbox" onChange={(event) => { setIncludeMappedResources(event.target.checked); clearPreview(); }} /> Mapped record metadata</label><label><input checked={includeTextResources} type="checkbox" onChange={(event) => { setIncludeTextResources(event.target.checked); clearPreview(); }} /> Typed resource text</label></fieldset>
        <button disabled={!skill || !provider || previewMutation.isPending} type="button" onClick={() => previewMutation.mutate()}>{previewMutation.isPending ? "Building preview…" : "Preview exact context"}</button>
        {previewMutation.isError ? <p className="form-error assist-wide" role="alert">{errorMessage(previewMutation.error)}</p> : null}
      </div>
      {preview ? (
        <section className="context-preview">
          <header><h4>Exact context preview</h4><span>{preview.text.length.toLocaleString()} characters</span></header>
          <pre>{preview.text}</pre>
          <div className="context-facts"><span>{preview.typed_resource_text_included ? "Typed resource text included" : "Typed resource text excluded"}</span><span>Stored attachment bytes excluded</span>{preview.omissions.map((item) => <span key={item}>{item}</span>)}</div>
          {isExternal && provider ? (
            <aside className="external-transfer" role="note">
              <strong>External transfer confirmation required for this run</strong>
              <dl><div><dt>Provider / model</dt><dd>{provider.display_name} / {provider.model_id}</dd></div><div><dt>Destination</dt><dd>{provider.base_url}</dd></div><div><dt>Record types</dt><dd>{preview.selected_record_types.join(", ")}</dd></div><div><dt>Typed resource text</dt><dd>{preview.typed_resource_text_included ? "Included" : "Excluded"}</dd></div><div><dt>Attachments</dt><dd>Stored attachment bytes excluded</dd></div></dl>
              <label><input checked={externalConfirmed} type="checkbox" onChange={(event) => setExternalConfirmed(event.target.checked)} /> I confirm this context may be sent to the selected external provider for this run.</label>
            </aside>
          ) : null}
          <div className="assist-runbar"><button className="primary-button" disabled={!canRun} type="button" onClick={() => void run()}>Run assistance</button>{runState === "RUNNING" ? <button type="button" onClick={() => { setRunState("CANCELLED"); controllerRef.current?.abort(); }}>Stop assistance</button> : null}</div>
        </section>
      ) : null}
      {runState !== "IDLE" || output ? (
        <section className="assist-result">
          <header><div><p className="eyebrow">Run result</p><h4>{proposal ? proposalTitle(proposal) : "Assistance output"}</h4></div><span aria-live="polite" role="status">{terminalLabel(runState)}</span></header>
          {provider ? <p className="assist-metadata">{provider.display_name} · {provider.model_id}{runId ? ` · Run ${runId}` : ""}</p> : null}
          {runError ? <p className="form-error" role="alert">{runError}</p> : null}
          {proposal ? <div className="proposal-card">{implementation ? <section><strong>Implementation notes</strong><p>{implementation}</p></section> : null}{proposalSummary ? <pre>{proposalSummary}</pre> : null}{sources.length ? <div aria-label="Source references" className="source-chips">{sources.map((source) => <span key={source}>{source}</span>)}</div> : null}</div> : output ? <pre className="advice-output">{output}</pre> : <p>Waiting for provider output…</p>}
          {structured === false && runState === "COMPLETED" ? <p className="unstructured-label">Unstructured advice-only result</p> : null}
          {output || proposal ? <div className="proposal-actions">
            {proposal && implementation ? <button type="button" onClick={() => onImplementationDraft(implementation)}>Use as implementation-note draft</button> : null}
            {proposal && proposalSummary ? <button type="button" onClick={() => onResourceDraft({ kind: "NOTE", title: proposalTitle(proposal), body: proposalSummary })}>Use as new note draft</button> : null}
            {proposal && typeof proposal.objective === "string" ? <button type="button" onClick={() => onResourceDraft({ kind: "PLAYBOOK", title: proposalTitle(proposal), body: proposalSummary })}>Use as playbook draft</button> : null}
            <button type="button" onClick={() => void copyResult()}>Copy result</button><span aria-live="polite">{copyState}</span>
          </div> : null}
          {runId && ["COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED"].includes(runState) ? <div className="assist-feedback"><label>Optional feedback comment<input maxLength={500} value={feedbackComment} onChange={(event) => setFeedbackComment(event.target.value)} /></label><span>Was this useful?</span><button disabled={feedback.isPending} type="button" onClick={() => feedback.mutate("USEFUL")}>Useful</button><button disabled={feedback.isPending} type="button" onClick={() => feedback.mutate("NOT_USEFUL")}>Not useful</button><span aria-live="polite">{feedbackState}</span>{feedback.isError ? <span className="form-error" role="alert">Feedback was not recorded.</span> : null}</div> : null}
        </section>
      ) : null}
      <section className="assist-history">
        <header><h4>Recent assistance runs</h4><span>Workspace-local history</span></header>
        {historyQuery.isError ? <p className="form-error" role="alert">Run history could not be loaded.</p> : history.length ? <ul>{history.map((item) => <li key={item.id}><div><strong>{item.skill_id} <small>v{item.skill_version}</small></strong><span>{item.provider_display_name} · {item.model_id}</span></div><div><b>{item.status}</b><time dateTime={item.started_at}>{new Date(item.started_at).toLocaleString()}</time><small>{item.duration_ms === null ? "Duration unavailable" : `${item.duration_ms} ms`}{item.error_code ? ` · ${item.error_code}` : ""}{item.feedback_rating ? ` · ${item.feedback_rating}` : ""}</small></div></li>)}</ul> : <p className="resource-state">No assistance runs recorded for this view.</p>}
      </section>
    </section>
  );
}
