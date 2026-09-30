# Internal Deployment and User Administration Design

**Date:** 2026-08-23

**Status:** Approved for implementation planning

## Goal

Give a non-developer a clear path from the local demo to an authenticated internal deployment, while exposing the small set of account controls an internal tracker needs: add, edit, deactivate, reactivate, reset a password, change one's own password, and permanently delete.

This remains a lightweight, single-workspace internal tool. It does not become an identity-governance or records-management system.

## Existing foundation

- Local mode uses SQLite, binds to loopback, loads labeled demo records, and requires no login.
- Server mode uses PostgreSQL, enables local password authentication, and bootstraps an initial Admin from environment variables.
- Passwords use Argon2id. Sessions are stored server-side, carried in HTTP-only cookies, protected by CSRF checks, and revoked when access changes.
- The API already supports user creation plus role, display-name, and disabled-state updates. The Settings UI currently exposes only creation and listing.
- The existing activity table can record account changes without adding a new audit schema.

## Decisions

### Account lifecycle

Settings will show each user's display name, email, role, and Active or Deactivated state. Admins can:

- create an account with an initial password;
- change its display name or role;
- set a new password;
- deactivate or reactivate it; and
- permanently delete it after confirmation.

Deactivation is the normal offboarding action. It keeps ownership references and history while immediately blocking new authentication and revoking active sessions.

Permanent deletion is available for test accounts and cleanup. Existing foreign-key behavior will clear deleted-user ownership fields while retaining the associated control, evidence, requirement, note, and activity records. A final `USER_DELETED` activity event stores the deleted user's non-secret identity snapshot so the administrative action remains understandable.

The application will refuse to deactivate, demote, or delete the currently signed-in Admin. It will also refuse an operation that would leave the workspace without an active Admin. The Admin must create or promote another Admin first.

### Password handling

Admins can set another user's new password. This revokes every session belonging to that user. An Admin changes their own password through the self-service action described below. The UI calls an administrator-set password a new or initial password, not a temporary password, because V1 will not add a forced-password-change state.

Signed-in users can change their own password by supplying their current password and a new password. A successful change revokes all sessions, including the current one, and returns the user to login. Passwords and password hashes never appear in API responses, activity snapshots, exports, or logs.

The existing password rules remain: at least 15 characters, at least 64 characters accepted, no composition rules, Unicode normalization, common-password blocking, and Argon2id storage.

### Activity

User administration will use the existing activity model. It will record concise action codes such as:

- `USER_CREATED`
- `USER_UPDATED`
- `USER_DEACTIVATED`
- `USER_REACTIVATED`
- `USER_PASSWORD_RESET`
- `USER_DELETED`
- `PASSWORD_CHANGED`

Events include actor, target user ID, timestamp, and non-secret before/after snapshots. An Admin-only recent-access-changes list in Settings will surface the latest events. The structured backup/export continues to include activity records.

### API shape

The existing `/api/v1/users` resource remains the administrative boundary:

- `GET /users` lists account state for Admins.
- `POST /users` creates an account.
- `PATCH /users/{id}` changes display name, role, disabled state, or password.
- `DELETE /users/{id}` permanently deletes an account after server-side safety checks.
- `GET /users/activity` returns recent account-lifecycle events for Admins.

Self-service password changes live under authentication:

- `POST /auth/change-password` verifies the current password, stores the new hash, revokes sessions, and clears authentication cookies.

All mutations retain the existing Admin authorization, CSRF, origin, validation, generic error, and safe-response conventions.

### Settings experience

The existing Settings page remains the destination. It will gain:

- a compact user table rather than a separate administration product;
- clear Active and Deactivated labels;
- an Add user form;
- per-user Edit, Deactivate/Reactivate, Reset password, and Delete actions;
- a single confirmation dialog for permanent deletion;
- inline explanations when an action is unavailable; and
- a short recent-access-changes ledger.

Actions will use plain verbs, visible progress/error states, keyboard-accessible dialogs, and touch targets consistent with the existing Field Manual interface. Viewer and Editor roles continue to see only the existing explanation that account controls require an Admin.

### Credentials and deployment handoff

The README will contain an explicit credentials section:

- Local mode: no login and no credentials.
- Server mode email: the value of `CCM_BOOTSTRAP_ADMIN_EMAIL` in `.env`.
- Server mode password: the value of `CCM_BOOTSTRAP_ADMIN_PASSWORD` in `.env` for first login.
- There is no committed universal password. `.env` remains untracked and must not be shared or committed.

After a server start, the launcher will print the configured login email and point to `.env` for the password without echoing the password itself.

The README will provide two deployment paths:

1. **Fresh internal deployment:** set PostgreSQL, bootstrap Admin, allowed origin/host, disable server demo loading, start server mode, log in, change the Admin password, back up, and place the app behind TLS.
2. **Promote genuine local work:** export the local workspace, start an empty PostgreSQL workspace with demo loading disabled, then restore the archive as an Admin. Demo records are never silently migrated.

After the first Admin changes the bootstrap password, the bootstrap password may be cleared from `.env`. Server Compose will permit an empty bootstrap value on later restarts because an active Admin already exists; a fresh database without valid bootstrap credentials will continue to fail closed with a clear error.

The launcher's server preflight will detect placeholder values and explain which `.env` entries must be changed before Docker starts.

## Error handling

- Duplicate email returns a conflict without changing the existing account.
- Invalid new passwords return the current password-policy message.
- Incorrect current password returns a generic authentication error.
- Missing target accounts return not found.
- Self-lockout and final-Admin operations return a clear conflict.
- A failed account mutation leaves the user and sessions unchanged.
- Password values are cleared from browser form state after use.

## Testing

Backend tests will cover Admin-only access, account creation, state transitions, session revocation, self-lockout prevention, final-Admin protection, password changes, deletion, activity snapshots, secret exclusion, and SQLite/PostgreSQL behavior.

Frontend tests will cover account states and actions, unavailable self/final-Admin actions, password forms, deletion confirmation, errors, and the activity ledger. Browser tests will exercise the main Admin lifecycle and confirm Editor/Viewer access remains blocked.

Launcher and documentation contract tests will verify placeholder rejection, credential wording, non-disclosure of password values, and both fresh-deployment and local-export promotion paths.

## Research notes

- NIST SP 800-63B-4 became final on 2025-07-31 and remains the current normative baseline for password authentication: <https://csrc.nist.gov/pubs/sp/800/63/B/4/final>.
- OWASP continues to recommend verifying the current password before a self-service change and invalidating sessions after password or permission changes: <https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html> and <https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html>.
- CISA reporting continues to document exploited authentication-bypass paths, supporting the existing decision to keep the administrative surface authenticated and place server mode behind TLS: <https://www.cisa.gov/known-exploited-vulnerabilities-catalog>.
- `argon2-cffi` 25.1.0 remains the current PyPI release and matches the project's existing pin; no authentication-library migration is required: <https://pypi.org/project/argon2-cffi/>.

## Deliberately out of scope

- OIDC, SSO, SCIM, MFA, invitations, recovery email, and directory synchronization
- approval workflows or access-review campaigns
- legal retention, deletion holds, or records-management policy
- forced password rotation or forced first-login password changes
- public internet deployment automation, certificates, DNS, or firewall management
