import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, ApiError } from "../../app/api/client";
import type { Role } from "../../app/api/types";
import { useSession } from "../../app/session/session-context";

interface UserRecord {
  id: string;
  email: string;
  display_name: string;
  role: Role;
  is_disabled: boolean;
}

interface ActivitySnapshot {
  display_name?: string;
}

interface UserActivity {
  id: string;
  action_code: string;
  entity_id: string;
  actor_display_name: string;
  before: ActivitySnapshot | null;
  after: ActivitySnapshot | null;
  created_at: string;
}

type DialogState = { kind: "edit" | "password" | "delete"; user: UserRecord } | null;

function field(values: FormData, name: string): string {
  const value = values.get(name);
  return typeof value === "string" ? value : "";
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.detail : fallback;
}

function activityText(item: UserActivity): string {
  const target = item.after?.display_name ?? item.before?.display_name ?? "a user";
  const verbs: Record<string, string> = {
    USER_CREATED: "created",
    USER_UPDATED: "updated",
    USER_DEACTIVATED: "deactivated",
    USER_REACTIVATED: "reactivated",
    USER_PASSWORD_RESET: "reset the password for",
    USER_DELETED: "deleted",
    PASSWORD_CHANGED: "changed the password for",
  };
  return `${item.actor_display_name} ${verbs[item.action_code] ?? "changed"} ${target}`;
}

function UserDialog({
  state,
  onClose,
  onUpdate,
  onDelete,
  pending,
  error,
  currentUserId,
}: {
  state: DialogState;
  onClose: () => void;
  onUpdate: (id: string, payload: Record<string, unknown>) => void;
  onDelete: (id: string) => void;
  pending: boolean;
  error: unknown;
  currentUserId: string | null;
}) {
  const selected = state?.user;
  const title = state?.kind === "edit" ? `Edit ${selected?.display_name ?? "user"}`
    : state?.kind === "password" ? `Reset password for ${selected?.display_name ?? "user"}`
      : `Delete ${selected?.display_name ?? "user"}?`;
  return (
    <Dialog.Root open={state !== null} onOpenChange={(open) => { if (!open) onClose(); }}>
      <Dialog.Portal>
        <div aria-hidden="true" className="dialog-scrim" />
        <Dialog.Content className="user-dialog">
          <header>
            <div><p className="eyebrow">Account access</p><Dialog.Title>{title}</Dialog.Title></div>
            <Dialog.Close aria-label="Close user action">×</Dialog.Close>
          </header>
          {selected && state?.kind === "edit" ? <form onSubmit={(event) => {
            event.preventDefault();
            const values = new FormData(event.currentTarget);
            const payload: Record<string, unknown> = { display_name: field(values, "display_name").trim() };
            if (selected.id !== currentUserId) payload.role = field(values, "role") as Role;
            onUpdate(selected.id, payload);
          }}>
            <Dialog.Description>Change the name or workspace role. Access changes sign the user out.</Dialog.Description>
            <div className="user-dialog-fields">
              <label>Display name<input defaultValue={selected.display_name} name="display_name" required /></label>
              <label>Role<select defaultValue={selected.role} disabled={selected.id === currentUserId} name="role"><option value="ADMIN">Admin</option><option value="EDITOR">Editor</option><option value="VIEWER">Viewer</option></select></label>
            </div>
            {selected.id === currentUserId ? <p className="form-note">Your own Admin role is locked here.</p> : null}
            {error ? <p className="form-error" role="alert">{errorMessage(error, "User could not be updated.")}</p> : null}
            <footer><Dialog.Close type="button">Cancel</Dialog.Close><button className="primary-button" disabled={pending} type="submit">{pending ? "Saving…" : "Save user"}</button></footer>
          </form> : null}
          {selected && state?.kind === "password" ? <form onSubmit={(event) => {
            event.preventDefault();
            const values = new FormData(event.currentTarget);
            onUpdate(selected.id, { password: field(values, "password") });
          }}>
            <Dialog.Description>Set a new password and sign this user out everywhere.</Dialog.Description>
            <div className="user-dialog-fields"><label>New password<input autoComplete="new-password" minLength={15} name="password" required type="password" /></label></div>
            {error ? <p className="form-error" role="alert">{errorMessage(error, "Password could not be changed.")}</p> : null}
            <footer><Dialog.Close type="button">Cancel</Dialog.Close><button className="primary-button" disabled={pending} type="submit">{pending ? "Setting…" : "Set password"}</button></footer>
          </form> : null}
          {selected && state?.kind === "delete" ? <div className="delete-user-copy">
            <Dialog.Description>This permanently removes the account. Existing workspace records remain, and this action stays in the access ledger.</Dialog.Description>
            <p><strong>{selected.email}</strong></p>
            {error ? <p className="form-error" role="alert">{errorMessage(error, "User could not be deleted.")}</p> : null}
            <footer><Dialog.Close type="button">Cancel</Dialog.Close><button className="danger-button" disabled={pending} onClick={() => onDelete(selected.id)}>{pending ? "Deleting…" : "Delete permanently"}</button></footer>
          </div> : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function UsersPanel() {
  const session = useSession();
  const queryClient = useQueryClient();
  const { data = [], isLoading, isError } = useQuery({ queryKey: ["users"], queryFn: () => api.get<UserRecord[]>("/users") });
  const { data: activity = [] } = useQuery({ queryKey: ["user-activity"], queryFn: () => api.get<UserActivity[]>("/users/activity") });
  const [adding, setAdding] = useState(false);
  const [dialog, setDialog] = useState<DialogState>(null);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["users"] });
    void queryClient.invalidateQueries({ queryKey: ["user-activity"] });
  };
  const create = useMutation({
    mutationFn: (payload: { email: string; display_name: string; password: string; role: Role }) => api.post<UserRecord>("/users", payload),
    onSuccess: () => { setAdding(false); refresh(); },
  });
  const update = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) => api.patch<UserRecord>(`/users/${id}`, payload),
    onSuccess: () => { setDialog(null); refresh(); },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/users/${id}`),
    onSuccess: () => { setDialog(null); refresh(); },
  });
  return <>
    <section className="settings-section users-panel">
      <div><p className="eyebrow">Team mode</p><h2>Users and roles</h2><p>Admins configure access. Editors change the workspace. Viewers read it.</p></div>
      <div className="users-workspace">
        {isLoading ? <p>Loading users…</p> : isError ? <p className="form-error" role="alert">Users could not be loaded.</p> : <ul className="user-list">{data.map((user) => {
          const isSelf = user.id === session.user?.id;
          return <li key={user.id}>
            <div className="user-identity"><strong>{user.display_name}</strong><small>{user.email}</small></div>
            <div className="user-badges"><b>{user.role}</b><span className={user.is_disabled ? "is-disabled" : "is-active"}>{user.is_disabled ? "Deactivated" : "Active"}</span></div>
            <div className="user-actions">
              <button aria-label={`Edit ${user.display_name}`} onClick={() => setDialog({ kind: "edit", user })}>Edit</button>
              <button aria-label={`${user.is_disabled ? "Reactivate" : "Deactivate"} ${user.display_name}`} disabled={isSelf} onClick={() => update.mutate({ id: user.id, payload: { is_disabled: !user.is_disabled } })}>{user.is_disabled ? "Reactivate" : "Deactivate"}</button>
              <button aria-label={`Reset password for ${user.display_name}`} disabled={isSelf} onClick={() => setDialog({ kind: "password", user })}>Reset password</button>
              <button aria-label={`Delete ${user.display_name}`} disabled={isSelf} onClick={() => setDialog({ kind: "delete", user })}>Delete</button>
            </div>
          </li>;
        })}</ul>}
        {update.isError && dialog === null ? <p className="form-error" role="alert">{errorMessage(update.error, "Access could not be changed.")}</p> : null}
        {adding ? <form className="user-form" onSubmit={(event) => {
          event.preventDefault();
          const values = new FormData(event.currentTarget);
          create.mutate({ email: field(values, "email"), display_name: field(values, "display_name"), password: field(values, "password"), role: field(values, "role") as Role });
        }}><label>Display name<input name="display_name" required /></label><label>Email<input autoComplete="username" name="email" required type="email" /></label><label>Initial password<input autoComplete="new-password" minLength={15} name="password" required type="password" /></label><label>Role<select name="role"><option value="EDITOR">Editor</option><option value="VIEWER">Viewer</option><option value="ADMIN">Admin</option></select></label>{create.isError ? <p className="form-error" role="alert">{errorMessage(create.error, "User could not be created.")}</p> : null}<footer><button type="button" onClick={() => setAdding(false)}>Cancel</button><button className="primary-button" disabled={create.isPending} type="submit">{create.isPending ? "Creating…" : "Create user"}</button></footer></form> : <button className="add-user-button" onClick={() => setAdding(true)}>Add user</button>}
        <div className="access-activity"><h3>Recent access changes</h3>{activity.length ? <ol>{activity.slice(0, 8).map((item) => <li key={item.id}><span>{activityText(item)}</span><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time></li>)}</ol> : <p>No account changes yet.</p>}</div>
      </div>
    </section>
    <UserDialog state={dialog} onClose={() => setDialog(null)} onUpdate={(id, payload) => update.mutate({ id, payload })} onDelete={(id) => remove.mutate(id)} pending={update.isPending || remove.isPending} error={update.error ?? remove.error} currentUserId={session.user?.id ?? null} />
  </>;
}

export function PasswordPanel() {
  const session = useSession();
  const password = useMutation({
    mutationFn: (payload: { current_password: string; new_password: string }) => api.post<void>("/auth/change-password", payload),
    onSuccess: () => {
      api.setCsrfToken(null);
      session.setUser(null);
      session.setStatus("unauthenticated");
    },
  });

  if (!session.user?.id) return null;
  return <section className="settings-section password-panel">
    <div><p className="eyebrow">My account</p><h2>Change my password</h2><p>Enter the current password first. A successful change signs this account out everywhere.</p></div>
    <form className="user-form" onSubmit={(event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const values = new FormData(form);
      password.mutate({ current_password: field(values, "current_password"), new_password: field(values, "new_password") }, { onSettled: () => form.reset() });
    }}><label>Current password<input autoComplete="current-password" name="current_password" required type="password" /></label><label>Your new password<input autoComplete="new-password" minLength={15} name="new_password" required type="password" /></label>{password.isError ? <p className="form-error" role="alert">{errorMessage(password.error, "Password could not be changed.")}</p> : null}<footer><button className="primary-button" disabled={password.isPending} type="submit">{password.isPending ? "Changing…" : "Change my password"}</button></footer></form>
  </section>;
}
