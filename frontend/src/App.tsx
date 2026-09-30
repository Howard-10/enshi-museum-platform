import { useEffect, useState } from "react";

import { getCurrentUser } from "./api/auth";
import { clearAuthSession, getAuthToken, getSavedAuthUser } from "./auth/session";
import { ChatPage } from "./pages/ChatPage";
import { AdminPage } from "./pages/AdminPage";
import { AuthPage } from "./pages/AuthPage";
import type { AuthUser } from "./types/auth";

const AUTH_REQUIRED = import.meta.env.VITE_AUTH_REQUIRED === "true";
const GUEST_USER: AuthUser = {
  id: "guest",
  email: "无需登录",
  display_name: "访客",
  role: "visitor",
};

export function App() {
  const [user, setUser] = useState<AuthUser | null>(() => getSavedAuthUser() ?? (AUTH_REQUIRED ? null : GUEST_USER));
  const [checkingAuth, setCheckingAuth] = useState(() => AUTH_REQUIRED && Boolean(getAuthToken()));

  useEffect(() => {
    if (!AUTH_REQUIRED) return;
    if (!getAuthToken()) {
      setCheckingAuth(false);
      return;
    }
    void getCurrentUser()
      .then(setUser)
      .catch(() => setUser(AUTH_REQUIRED ? null : GUEST_USER))
      .finally(() => setCheckingAuth(false));
  }, []);

  if (window.location.pathname.startsWith("/admin")) return <AdminPage />;
  if (checkingAuth) return <main className="auth-page"><section className="auth-card auth-loading"><div className="loading-orbit" aria-hidden="true" /><p>正在验证登录状态…</p></section></main>;
  if (!user) return <AuthPage onAuthenticated={setUser} />;
  return <ChatPage user={user} onLogout={() => { clearAuthSession(); setUser(AUTH_REQUIRED ? null : GUEST_USER); }} />;
}
