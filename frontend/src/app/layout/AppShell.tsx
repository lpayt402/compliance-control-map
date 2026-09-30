import { useState, type ReactNode } from "react";

import { api } from "../api/client";
import { useOptionalSession } from "../session/session-context";
import { CommandPalette } from "./CommandPalette";
import { PrimaryNav } from "./PrimaryNav";

export function AppShell({ children }: { children: ReactNode }) {
  const session = useOptionalSession();
  const [signingOut, setSigningOut] = useState(false);
  const openCommands = () => {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }));
  };
  return (
    <div className="app-shell">
      <a className="skip-link" href="#workspace">Skip to workspace</a>
      <aside className="rail">
        <div className="brand-lockup" aria-label="Compliance Control Map">
          <span className="brand-mark" aria-hidden="true">C·C</span>
          <div><strong>Control map</strong><span>Field manual</span></div>
        </div>
        <PrimaryNav />
        <div className="rail-note">
          <span className="connection-dot" aria-hidden="true" />
          <div><strong>Local workspace</strong><span>Evidence stays here.</span></div>
        </div>
      </aside>
      <div className="workbench">
        <header className="topbar">
          <p><span>Workspace</span>Compliance readiness</p>
          <div className="topbar-actions">
            {session?.user?.id ? <div className="session-account"><span>{session.user.display_name}</span><button disabled={signingOut} onClick={() => {
              setSigningOut(true);
              api.post<void>("/auth/logout").then(() => {
                api.setCsrfToken(null);
                session.setUser(null);
                session.setStatus("unauthenticated");
              }).catch(() => setSigningOut(false));
            }}>{signingOut ? "Signing out…" : "Sign out"}</button></div> : null}
            <button className="command-trigger" onClick={openCommands}>Search <kbd>Ctrl K</kbd></button>
          </div>
        </header>
        <main id="workspace" tabIndex={-1}>{children}</main>
      </div>
      <CommandPalette />
    </div>
  );
}
