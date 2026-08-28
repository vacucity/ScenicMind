export function DashboardPage() {
  return (
    <main className="dashboard-page">
      <aside className="sidebar">
        <span className="brand">智景 SCENICMIND</span>
        <nav aria-label="主导航">
          <a href="/dashboard" aria-current="page">数据看板</a>
        </nav>
      </aside>

      <section className="dashboard-main">
        <header className="dashboard-header">
          <div>
            <span>OVERVIEW</span>
            <h1>数据看板</h1>
          </div>
          <a href="/login">退出</a>
        </header>

        <section className="empty-panel">
          <h2>看板内容区</h2>
          <p>在这里接入预测数据、图表和文本。</p>
        </section>
      </section>
    </main>
  );
}
