import { useEffect, useState } from "react";

import { getCurrentUser } from "./api/auth";
import { clearAuthSession, getAuthToken, getSavedAuthUser } from "./auth/session";
import { ChatPage } from "./pages/ChatPage";
import { AdminPage } from "./pages/AdminPage";
import { AuthPage } from "./pages/AuthPage";
import type { AuthUser } from "./types/auth";

export function App() {
  const [user, setUser] = useState<AuthUser | null>(getSavedAuthUser);
  const [checkingAuth, setCheckingAuth] = useState(() => Boolean(getAuthToken()));

  useEffect(() => {
    if (!getAuthToken()) {
      setCheckingAuth(false);
      return;
    }
    void getCurrentUser()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setCheckingAuth(false));
  }, []);

  if (window.location.pathname.startsWith("/admin")) return <AdminPage />;
  if (checkingAuth) return <main className="auth-page"><section className="auth-card auth-loading"><div className="loading-orbit" aria-hidden="true" /><p>正在验证登录状态…</p></section></main>;
  if (!user) return <AuthPage onAuthenticated={setUser} />;
  return <ChatPage user={user} onLogout={() => { clearAuthSession(); setUser(null); }} />;
}
