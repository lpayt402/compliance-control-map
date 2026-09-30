import { useQuery } from "@tanstack/react-query";

import { api } from "../../app/api/client";
import { useSession } from "../../app/session/session-context";
import { ExportPanel } from "./ExportPanel";
import { ProviderPanel } from "./ProviderPanel";
import { PasswordPanel, UsersPanel } from "./UsersPanel";

interface FrameworkRecord { slug: string; name: string; active_version: { version: string; requirement_count: number } | null; }

export function SettingsPage() {
  const { user } = useSession();
  const isAdmin = !user || user.role === "ADMIN";
  const { data: frameworks = [] } = useQuery({ queryKey: ["frameworks"], queryFn: () => api.get<FrameworkRecord[]>("/frameworks") });
  return (
    <section className="settings-page">
      <header className="operational-heading"><div><p className="eyebrow">Workspace administration</p><h1>Settings</h1></div><p>Manage users, workspace configuration, and portable backups.</p></header>
      <section className="settings-section"><div><p className="eyebrow">Framework sources</p><h2>Installed framework packs</h2><p>Framework wording in this workspace is concise, original implementation guidance—not licensed auditor text.</p></div><ul className="framework-register">{frameworks.map((framework) => <li key={framework.slug}><strong>{framework.name}</strong><span>{framework.active_version ? `${framework.active_version.version} · ${framework.active_version.requirement_count} requirements` : "No active version"}</span></li>)}</ul></section>
      {isAdmin ? <><UsersPanel /><ExportPanel /></> : <section className="settings-section"><div><p className="eyebrow">Administrative tools</p><h2>Team and backup controls</h2><p>Administrators can manage users and backups.</p></div></section>}
      <PasswordPanel />
      {isAdmin ? <ProviderPanel /> : <section className="settings-section"><div><p className="eyebrow">Optional, advisory assistance</p><h2>Model providers</h2><p>Provider configuration is restricted to workspace administrators. Assistance never changes workspace records automatically.</p></div></section>}
    </section>
  );
}
