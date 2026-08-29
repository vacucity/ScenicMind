import type { FormEvent } from "react";

export function LoginPage() {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    window.location.href = "/dashboard";
  }

  return (
    <main className="login-page">
      <section className="brand-panel">
        <span className="brand">智景 SCENICMIND</span>
        <h1>智慧景区<br />管理平台</h1>
      </section>

      <section className="login-panel">
        <form className="login-form" onSubmit={handleSubmit}>
          <header>
            <span>登录</span>
            <h2>欢迎回来</h2>
          </header>

          <label>
            账号
            <input name="username" autoComplete="username" required />
          </label>
          <label>
            密码
            <input name="password" type="password" autoComplete="current-password" required />
          </label>

          <button type="submit">进入经营驾驶舱</button>
        </form>
      </section>
    </main>
  );
}
