import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Navigate } from "react-router";

import { api } from "../../app/api/client";
import type { SessionUser } from "../../app/api/types";
import { useSession } from "../../app/session/session-context";

interface LoginResponse { user: SessionUser; csrf_token: string; }

export function LoginPage() {
  const { status, setStatus, setUser } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const mutation = useMutation({
    mutationFn: () => api.post<LoginResponse>("/auth/login", { email: email.trim(), password }),
    onSuccess: (response) => {
      api.setCsrfToken(response.csrf_token);
      setPassword("");
      setUser(response.user);
      setStatus("authenticated");
    },
    onError: () => setPassword(""),
  });

  if (status === "authenticated") return <Navigate replace to="/dashboard" />;
  return (
    <main className="login-page">
      <section className="login-manual">
        <div className="login-mark" aria-hidden="true">C·C</div>
        <p className="eyebrow">Team workspace</p>
        <h1>Sign in to the control map</h1>
        <p>One quiet place for requirements, controls, documents, and proof.</p>
        <form onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
          <label>Email<input autoComplete="username" required type="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
          <label>Password<input autoComplete="current-password" required type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          {mutation.isError ? <p className="form-error" role="alert">Sign-in failed. Check the email and password, then try again.</p> : null}
          <button className="primary-button" disabled={mutation.isPending} type="submit">{mutation.isPending ? "Signing in…" : "Sign in"}</button>
        </form>
        <small>Local mode can run without this screen. Team mode uses secure server-side sessions.</small>
      </section>
    </main>
  );
}
