import { createContext, useContext } from "react";

import type { SessionUser } from "../api/types";

export interface SessionContextValue {
  user: SessionUser | null;
  status: "loading" | "authenticated" | "unauthenticated";
  setUser: (user: SessionUser | null) => void;
  setStatus: (status: SessionContextValue["status"]) => void;
}

export const SessionContext = createContext<SessionContextValue | null>(null);

export function useSession(): SessionContextValue {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession must be used inside SessionProvider");
  return session;
}

export function useOptionalSession(): SessionContextValue | null {
  return useContext(SessionContext);
}
