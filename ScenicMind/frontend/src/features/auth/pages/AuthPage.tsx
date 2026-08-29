import { useState, type FormEvent } from "react";
import { navigate } from "../../../app/navigation";
import { AppLink } from "../../../shared/components/AppLink";
import { registerUser, signIn } from "../services/session";

type AuthMode = "login" | "register";

export function AuthPage({ mode }: { mode: AuthMode }) {
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const isRegister = mode === "register";
  const [notice] = useState(() => {
    if (isRegister) return "";
    const value = window.sessionStorage.getItem("scenicmind.auth.notice") ?? "";
    window.sessionStorage.removeItem("scenicmind.auth.notice");
    return value;
  });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    const data = new FormData(event.currentTarget);
    const username = String(data.get("username") ?? "").trim();
    const password = String(data.get("password") ?? "");

    try {
      setSubmitting(true);
      if (isRegister) {
        const email = String(data.get("email") ?? "").trim();
        const confirm = String(data.get("confirm") ?? "");
        if (password.length < 8) throw new Error("密码至少需要 8 位");
        if (password !== confirm) throw new Error("两次输入的密码不一致");
        await registerUser({ username, email, password });
        window.sessionStorage.setItem("scenicmind.auth.notice", "注册成功，请登录");
        navigate("/login", { replace: true });
        return;
      }

      await signIn(username, password);
      navigate("/upload", { replace: true });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "操作失败，请重试");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-scenic" aria-label="智景品牌展示">
        <div className="auth-scenic-shade" />
        <div className="auth-scenic-brand">
          <img src="/brand/logo-circle.png" alt="" />
          <div><strong>智景 ScenicMind</strong></div>
        </div>
        <div className="auth-scenic-copy">
          <span>SCENIC INTELLIGENCE</span>
          <h1>山水之间<br />数据自明</h1>
          <p>面向景区运营的预测与决策支持平台</p>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-panel-inner">
          <img className="auth-wordmark" src="/brand/logo-scenicmind.png" alt="智景 ScenicMind" />
          <div className="auth-tabs" aria-label="账号操作">
            <AppLink to="/login" className={!isRegister ? "active" : ""}>登录</AppLink>
            <AppLink to="/register" className={isRegister ? "active" : ""}>注册</AppLink>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            <header>
              <span>{isRegister ? "CREATE ACCOUNT" : "WELCOME BACK"}</span>
              <h2>{isRegister ? "创建运营账号" : "欢迎回来"}</h2>
            </header>
            <label><span>用户名</span><input name="username" placeholder="运营管理员" autoComplete="username" required /></label>
            {isRegister && <label><span>邮箱</span><input name="email" type="email" placeholder="you@scenicmind.com" autoComplete="email" required /></label>}
            <label><span>密码</span><input name="password" type="password" placeholder="至少 8 位" autoComplete={isRegister ? "new-password" : "current-password"} required /></label>
            {isRegister && <label><span>确认密码</span><input name="confirm" type="password" placeholder="再次输入密码" autoComplete="new-password" required /></label>}
            {(message || notice) && <p className={message ? "form-message error" : "form-message success"} role="status">{message || notice}</p>}
            <button type="submit" disabled={submitting}>{submitting ? "处理中…" : isRegister ? "注册" : "登录"}</button>
          </form>
          <p className="auth-prototype-note">体验账号：test　体验密码：test</p>
        </div>
      </section>
    </main>
  );
}
