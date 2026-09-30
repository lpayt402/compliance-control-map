import { useEffect, useMemo, useState, type ReactNode } from "react";

import { api, ApiError } from "../api/client";
import type { SessionUser } from "../api/types";
import { SessionContext } from "./session-context";

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [status, setStatus] = useState<"loading" | "authenticated" | "unauthenticated">("loading");

  useEffect(() => {
    let active = true;
    api.get<SessionUser>("/auth/me").then((current) => {
      if (!active) return;
      setUser(current);
      setStatus("authenticated");
    }).catch((error: unknown) => {
      if (!active) return;
      if (error instanceof ApiError && error.status === 401) setStatus("unauthenticated");
      else setStatus("unauthenticated");
    });
    return () => { active = false; };
  }, []);

  const value = useMemo(() => ({ user, status, setUser, setStatus }), [status, user]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
