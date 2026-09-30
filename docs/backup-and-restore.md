# Backup and restore

The administrative export is a portable ZIP, not a live database snapshot. New exports use schema version 2. They include a versioned JSON representation of workspace assessments, users as disabled identity records, controls, typed requirement and control text resources, mappings, document/evidence metadata, and stored file bytes. They exclude password hashes and active sessions.

Each stored file has a declared size and SHA-256 digest in `manifest.json`. Restore accepts schema versions 1 and 2, requires the manifest and workspace data versions to match, bounds member count and total expansion, rejects absolute/traversal/duplicate paths, verifies sizes and digests, and writes files under new randomized storage keys. Version 1 requirement notes restore as `NOTE` resources with an empty title, no internal contact, and revision 1. Version 1 archives have no control text resources.

## Local workflow

Create an export while the app is running:

```powershell
.\launch.ps1 -Mode export -Archive data\workspace.zip
```

For a new machine, copy the project and archive, set `CCM_LOAD_DEMO=false` in `.env`, launch once, and restore before making any workspace change:

```powershell
.\launch.ps1
.\launch.ps1 -Mode restore -Archive data\workspace.zip
```

Restore is intentionally fail-closed when the target contains users, controls, documents, evidence, requirement/control text resources, or changed assessments. It does not merge two workspaces. Required framework versions must already be installed.

For a disposable local reset, export first, then run `.\launch.ps1 -Refresh`. The refresh removes only the two verified local Compose volumes and cannot run in server mode.

## Team mode

Log in as an administrator and use Settings → Backup and portability. Store the resulting archive in an access-controlled, encrypted location. The application does not schedule backups, encrypt archives, set retention, or test recovery for you. Also maintain and test infrastructure-level PostgreSQL and storage backups appropriate to your deployment.
