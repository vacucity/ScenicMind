import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import {
  getModuleOneOutput,
  getModuleTwoOutput,
  getModuleTwoSpots,
  type ModuleOneData,
  type ModuleTwoReport,
} from "../api/modules";
import { Icon, type IconName } from "./Icon";
import { DashboardContext } from "./DashboardContext";

const navItems: Array<{ label: string; icon: IconName; to: string }> = [
  { label: "数据看板", icon: "dashboard", to: "/dashboard" },
  { label: "客流预测", icon: "forecast", to: "/dashboard/forecast" },
  { label: "Agent 报告", icon: "agent", to: "/dashboard/agent" },
  { label: "运营准备", icon: "prepare", to: "/dashboard/prepare" },
];

export function DashboardLayout() {
  const navigate = useNavigate();
  const [spots, setSpots] = useState<string[]>(["九寨沟"]);
  const [selectedSpot, setSelectedSpot] = useState("九寨沟");
  const [one, setOne] = useState<ModuleOneData | null>(null);
  const [report, setReport] = useState<ModuleTwoReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getModuleTwoSpots().then(list => {
      if (!active) return;
      if (list.length) {
        setSpots(list);
        if (!list.includes(selectedSpot)) {
          setSelectedSpot(list[0]);
        }
      }
    }).catch(() => undefined);
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    Promise.all([
      getModuleOneOutput(selectedSpot),
      getModuleTwoOutput(selectedSpot),
    ])
      .then(([oneOutput, reportOutput]) => {
        if (!active) return;
        setOne(oneOutput.data);
        setReport(reportOutput.data);
      })
      .catch((requestError: unknown) => {
        if (active) {
          setError(requestError instanceof Error ? requestError.message : "数据加载失败");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedSpot]);

  return (
    <main className="dashboard-page">
      <aside className="sidebar">
        <div>
          <a className="brand-mark" href="/dashboard" aria-label="智景 ScenicMind 首页">
            <span className="brand-glyph" aria-hidden="true"><i /><i /><i /></span>
            <span><b>智景</b><small>SCENICMIND</small></span>
          </a>

          <nav className="sidebar-nav" aria-label="主导航">
            {navItems.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/dashboard"}
                className={({ isActive }) => (isActive ? "active" : "")}
              >
                <Icon name={item.icon} />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="sidebar-foot">
          <span className="park-status"><i />数据正常</span>
          <strong>{selectedSpot} · 全园</strong>
          <small>数据更新于 14:00</small>
        </div>
      </aside>

      <section className="dashboard-main">
        <div className="dashboard-header">
          <div className="header-tools">
            <label className="park-selector" aria-label="选择景点">
              <select
                value={selectedSpot}
                onChange={event => setSelectedSpot(event.target.value)}
                style={{ border: 0, background: "transparent", color: "inherit", fontSize: 13, cursor: "pointer", outline: "none", width: "100%" }}
              >
                {spots.map(spot => (
                  <option key={spot} value={spot}>{spot}</option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {loading || !one || !report ? (
          <div className="card" style={{ padding: 48, textAlign: "center" }}>
            {error
              ? <><h2 style={{ margin: 0 }}>数据加载失败</h2><p style={{ color: "var(--muted)", margin: "8px 0 0" }}>{error}（请确认后端已启动于 127.0.0.1:8001）</p></>
              : <><h2 style={{ margin: 0 }}>正在加载经营驾驶舱…</h2><p style={{ color: "var(--muted)", margin: "8px 0 0" }}>正在请求客流预测与经营报告</p></>}
          </div>
        ) : (
          <DashboardContext.Provider value={{ one, report, spots, selectedSpot, setSelectedSpot }}>
            <Outlet />
          </DashboardContext.Provider>
        )}
      </section>
    </main>
  );
}

export function BackToDashboard() {
  const navigate = useNavigate();
  return (
    <button className="back-link" type="button" onClick={() => navigate("/dashboard")}>
      <Icon name="back" size={14} /> 返回总览
    </button>
  );
}