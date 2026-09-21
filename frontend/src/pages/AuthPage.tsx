import { FormEvent, useState } from "react";

import { login, register } from "../api/auth";
import type { AuthUser } from "../types/auth";

interface AuthPageProps {
  onAuthenticated: (user: AuthUser) => void;
}

export function AuthPage({ onAuthenticated }: AuthPageProps) {
  const [isRegistering, setIsRegistering] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) return;
    setError("");
    setIsSubmitting(true);
    try {
      const user = isRegistering
        ? await register(email, password, displayName)
        : await login(email, password);
      onAuthenticated(user);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "操作失败，请稍后重试。");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-title">
        <div className="auth-mark">恩</div>
        <p className="answer-label">ENSHI PREFECTURE MUSEUM</p>
        <h1 id="auth-title">{isRegistering ? "创建导览账号" : "登录智能导览"}</h1>
        <p className="auth-intro">登录后，你的对话记录只对自己可见。</p>
        <form onSubmit={handleSubmit}>
          {isRegistering && (
            <label>昵称<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="怎么称呼你" maxLength={100} required /></label>
          )}
          <label>邮箱<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="name@example.com" autoComplete="email" required /></label>
          <label>密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="至少 8 位" minLength={8} maxLength={128} autoComplete={isRegistering ? "new-password" : "current-password"} required /></label>
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className="auth-submit" type="submit" disabled={isSubmitting}>{isSubmitting ? "处理中…" : isRegistering ? "注册并进入" : "登录"}</button>
        </form>
        <button className="auth-switch" type="button" onClick={() => { setIsRegistering((value) => !value); setError(""); }}>
          {isRegistering ? "已有账号？返回登录" : "还没有账号？立即注册"}
        </button>
        <a className="auth-admin-link" href="/admin">进入管理端</a>
      </section>
    </main>
  );
}
