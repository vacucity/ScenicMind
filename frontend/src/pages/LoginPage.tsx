import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";

export function LoginPage() {
  const navigate = useNavigate();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    navigate("/dashboard");
  }

  return (
    <main className="auth-page">
      <section className="auth-scenic" aria-label="智景品牌展示">
        <div className="auth-scenic-shade" />
        <div className="auth-scenic-brand">
          <img src="/brand/logo.png" alt="" />
          <div>
            <strong>智景 ScenicMind</strong>
          </div>
        </div>
        <div className="auth-scenic-copy">
          <span>SCENIC INTELLIGENCE</span>
          <h1>山水之间<br />数据自明</h1>
          <p>面向景区运营的预测与决策支持平台</p>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-panel-inner">
          <img className="auth-wordmark" src="/brand/logo.png" alt="智景 ScenicMind" />
          <div className="auth-tabs" aria-label="账号操作">
            <span className="active">登录</span>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            <header>
              <span>WELCOME BACK</span>
              <h2>欢迎回来</h2>
            </header>
            <label><span>用户名</span><input name="username" placeholder="运营管理员" autoComplete="username" required /></label>
            <label><span>密码</span><input name="password" type="password" placeholder="至少 8 位" autoComplete="current-password" required /></label>
            <button type="submit">登录</button>
          </form>
          <p className="auth-prototype-note">账号由 ScenicMind 后端安全验证，会话有效期为 7 天。</p>
        </div>
      </section>
    </main>
  );
}
