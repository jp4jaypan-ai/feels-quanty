"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type SignalSide = "BUY" | "SELL";

type Signal = {
  id: number;
  code: string;
  name: string;
  side: SignalSide;
  price: string;
  change: string;
  time: string;
  strategy: string;
  rationale: string;
  level: "确认" | "观察";
};

type Strategy = {
  id: string;
  index: string;
  title: string;
  subtitle: string;
  description: string;
  accent: string;
  rule: string;
  fit: string;
};

const strategyCatalog: Strategy[] = [
  {
    id: "trend",
    index: "01",
    title: "趋势跟随",
    subtitle: "Trend / Momentum",
    description: "捕捉方向延续，不在第一次冲高或下跌时抢跑。",
    accent: "violet",
    rule: "突破区间 + 方向持续 + 成交量确认",
    fit: "适合单边盘与放量行情",
  },
  {
    id: "reversion",
    index: "02",
    title: "均值回归",
    subtitle: "Mean Reversion",
    description: "观察价格相对盘中均价的偏离，在回归迹象出现时提醒。",
    accent: "mint",
    rule: "偏离均价 + 极值确认 + 回归触发",
    fit: "适合震荡盘与高流动性标的",
  },
  {
    id: "breakout",
    index: "03",
    title: "波动突破",
    subtitle: "Volatility Breakout",
    description: "等待波动从收缩转向扩张，用突破而不是猜顶猜底。",
    accent: "amber",
    rule: "波动收缩 + 区间突破 + 波动放大",
    fit: "适合开盘与事件驱动阶段",
  },
  {
    id: "relative",
    index: "04",
    title: "相对强弱",
    subtitle: "Relative Strength",
    description: "将个股走势放进指数或板块背景中，过滤市场共振噪音。",
    accent: "blue",
    rule: "个股强弱 + 基准方向 + 超额动量",
    fit: "适合多标的监控与轮动观察",
  },
];

const initialCodes = [
  { code: "301583.SZ", name: "托伦斯", price: "166.31", change: "+1.86%" },
  { code: "000300.SH", name: "沪深300", price: "3,842.16", change: "+0.42%" },
  { code: "399006.SZ", name: "创业板指", price: "2,184.07", change: "-0.18%" },
];

const initialSignals: Signal[] = [
  {
    id: 1,
    code: "301583.SZ",
    name: "托伦斯",
    side: "SELL",
    price: "172.68",
    change: "+5.76%",
    time: "11:02:14",
    strategy: "均值回归",
    rationale: "冲高后回到短线极值带内，等待回归确认",
    level: "确认",
  },
  {
    id: 2,
    code: "301583.SZ",
    name: "托伦斯",
    side: "BUY",
    price: "164.02",
    change: "+0.49%",
    time: "14:16:08",
    strategy: "均值回归",
    rationale: "低位反弹并重新站回短线触发线",
    level: "确认",
  },
  {
    id: 3,
    code: "399006.SZ",
    name: "创业板指",
    side: "SELL",
    price: "2,191.42",
    change: "+0.16%",
    time: "10:38:52",
    strategy: "趋势跟随",
    rationale: "上冲失败，短周期方向出现反转观察",
    level: "观察",
  },
  {
    id: 4,
    code: "000300.SH",
    name: "沪深300",
    side: "BUY",
    price: "3,837.90",
    change: "+0.31%",
    time: "09:47:31",
    strategy: "波动突破",
    rationale: "开盘波动收缩后向上突破早盘区间",
    level: "观察",
  },
];

const pricePath = [
  158.8, 163.1, 168.7, 166.4, 164.2, 165.7, 164.9, 166.1, 167.6, 169.2,
  168.4, 170.7, 172.6, 173.4, 171.9, 172.8, 171.2, 172.3, 170.9, 171.8,
  169.5, 168.8, 169.6, 168.9, 168.3, 167.4, 167.8, 166.6, 165.3, 165.7,
  164.8, 164.1, 163.8, 164.4, 164.0, 164.8, 165.3, 164.9, 166.1, 166.4,
  166.2, 166.7, 166.1, 166.5, 166.3,
];

const vwapPath = pricePath.map((_, index) => 166.8 + Math.sin(index / 8) * 0.55);

function PriceChart({ selectedStrategy }: { selectedStrategy: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const draw = () => {
      const bounds = canvas.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      const width = Math.max(bounds.width, 320);
      const height = Math.max(bounds.height, 260);
      canvas.width = width * ratio;
      canvas.height = height * ratio;
      const context = canvas.getContext("2d");
      if (!context) return;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, width, height);

      const padding = { top: 26, right: 18, bottom: 30, left: 18 };
      const chartWidth = width - padding.left - padding.right;
      const chartHeight = height - padding.top - padding.bottom;
      const min = Math.min(...pricePath) - 1.4;
      const max = Math.max(...pricePath) + 1.4;
      const x = (index: number) => padding.left + (index / (pricePath.length - 1)) * chartWidth;
      const y = (value: number) => padding.top + ((max - value) / (max - min)) * chartHeight;

      context.strokeStyle = "rgba(126, 137, 161, 0.14)";
      context.lineWidth = 1;
      for (let row = 0; row < 5; row += 1) {
        const lineY = padding.top + (row / 4) * chartHeight;
        context.beginPath();
        context.moveTo(padding.left, lineY);
        context.lineTo(width - padding.right, lineY);
        context.stroke();
      }
      for (let column = 0; column < 8; column += 1) {
        const lineX = padding.left + (column / 7) * chartWidth;
        context.beginPath();
        context.moveTo(lineX, padding.top);
        context.lineTo(lineX, height - padding.bottom);
        context.stroke();
      }

      const area = context.createLinearGradient(0, padding.top, 0, height - padding.bottom);
      area.addColorStop(0, "rgba(123, 109, 255, 0.18)");
      area.addColorStop(1, "rgba(123, 109, 255, 0)");
      context.beginPath();
      pricePath.forEach((value, index) => {
        if (index === 0) context.moveTo(x(index), y(value));
        else context.lineTo(x(index), y(value));
      });
      context.lineTo(x(pricePath.length - 1), height - padding.bottom);
      context.lineTo(x(0), height - padding.bottom);
      context.closePath();
      context.fillStyle = area;
      context.fill();

      const drawLine = (values: number[], color: string, lineWidth: number, dash: number[] = []) => {
        context.beginPath();
        context.setLineDash(dash);
        values.forEach((value, index) => {
          if (index === 0) context.moveTo(x(index), y(value));
          else context.lineTo(x(index), y(value));
        });
        context.strokeStyle = color;
        context.lineWidth = lineWidth;
        context.stroke();
        context.setLineDash([]);
      };

      drawLine(vwapPath, "rgba(240, 179, 83, 0.9)", 1.5, [5, 5]);
      drawLine(pricePath, "#9d91ff", 2.6);

      const markers = [
        { index: 14, label: "SELL", color: "#fb7185", value: pricePath[14] },
        { index: 33, label: "BUY", color: "#56d9b5", value: pricePath[33] },
      ];
      markers.forEach((marker) => {
        const markerX = x(marker.index);
        const markerY = y(marker.value);
        context.beginPath();
        context.arc(markerX, markerY, 5, 0, Math.PI * 2);
        context.fillStyle = marker.color;
        context.fill();
        context.beginPath();
        context.arc(markerX, markerY, 9, 0, Math.PI * 2);
        context.strokeStyle = `${marker.color}66`;
        context.lineWidth = 1;
        context.stroke();
        context.font = "700 10px Arial";
        context.fillStyle = marker.color;
        context.fillText(marker.label, markerX - 14, markerY + (marker.label === "BUY" ? 25 : -16));
      });

      context.font = "600 10px Arial";
      context.fillStyle = "rgba(179, 187, 207, 0.72)";
      ["09:30", "10:30", "11:30", "13:00", "14:00", "15:00"].forEach((label, index, labels) => {
        const labelX = padding.left + (index / (labels.length - 1)) * chartWidth;
        context.fillText(label, labelX - (index === labels.length - 1 ? 30 : 12), height - 8);
      });

      context.fillStyle = "rgba(240, 179, 83, 0.86)";
      context.fillText("均价 166.82", width - 88, padding.top - 8);
      context.fillStyle = "rgba(157, 145, 255, 0.88)";
      context.fillText(selectedStrategy === "reversion" ? "回归带" : "价格", padding.left, padding.top - 8);
    };

    draw();
    window.addEventListener("resize", draw);
    return () => window.removeEventListener("resize", draw);
  }, [selectedStrategy]);

  return (
    <div className="chart-canvas-wrap">
      <canvas ref={canvasRef} aria-label="301583.SZ 盘中价格与均价示意图" />
    </div>
  );
}

function AppMark() {
  return <span className="app-mark">Q</span>;
}

export default function Home() {
  const [selectedStrategy, setSelectedStrategy] = useState("reversion");
  const [selectedCode, setSelectedCode] = useState(initialCodes[0].code);
  const [codes, setCodes] = useState(initialCodes);
  const [draftCode, setDraftCode] = useState("");
  const [monitoring, setMonitoring] = useState(false);
  const [windConnected, setWindConnected] = useState(false);
  const [timeframe, setTimeframe] = useState("1m");
  const [soundOn, setSoundOn] = useState(true);
  const [activeNav, setActiveNav] = useState("monitor");
  const [notice, setNotice] = useState<string | null>(null);
  const [clock, setClock] = useState("14:27:18");

  const activeStrategy = strategyCatalog.find((strategy) => strategy.id === selectedStrategy) ?? strategyCatalog[1];
  const activeSymbol = codes.find((item) => item.code === selectedCode) ?? codes[0];

  const visibleSignals = useMemo(
    () => initialSignals.filter((signal) => signal.code === selectedCode || selectedCode === "301583.SZ"),
    [selectedCode],
  );

  useEffect(() => {
    if (!monitoring) return;
    const interval = window.setInterval(() => {
      setClock(new Date().toLocaleTimeString("zh-CN", { hour12: false }));
    }, 1000);
    return () => window.clearInterval(interval);
  }, [monitoring]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 3000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const addCode = () => {
    const normalized = draftCode.trim().toUpperCase();
    if (!normalized) return;
    if (codes.some((item) => item.code === normalized)) {
      setSelectedCode(normalized);
      setNotice("这个标的已经在关注列表中");
      setDraftCode("");
      return;
    }
    setCodes((current) => [...current, { code: normalized, name: "自定义标的", price: "--", change: "--" }]);
    setSelectedCode(normalized);
    setDraftCode("");
    setNotice(`${normalized} 已加入今日监控`);
  };

  const toggleMonitoring = () => {
    setMonitoring((current) => !current);
    setNotice(monitoring ? "监控已暂停，信号不会继续刷新" : "监控已启动，等待实时行情触发信号");
  };

  return (
    <main className="quant-app">
      <aside className="sidebar">
        <div className="brand-lockup">
          <AppMark />
          <div>
            <p className="brand-name">QUANT DESK</p>
            <span className="brand-caption">盘中信号工作台</span>
          </div>
        </div>

        <div className="sidebar-section-label">WORKSPACE</div>
        <nav className="primary-nav" aria-label="工作区导航">
          {[
            ["monitor", "监控台", "◉"],
            ["strategies", "策略库", "⌁"],
            ["signals", "信号日志", "↗"],
            ["settings", "参数设置", "⊙"],
          ].map(([id, label, icon]) => (
            <button
              className={`nav-item ${activeNav === id ? "active" : ""}`}
              key={id}
              onClick={() => {
                setActiveNav(id);
                if (id === "strategies") setNotice("策略库已预制四类可解释策略");
                if (id === "signals") setNotice("信号日志保留每次触发的时间与依据");
                if (id === "settings") setNotice("参数面板将在接入 WindPy 后开放");
              }}
            >
              <span className="nav-icon">{icon}</span>
              {label}
              {id === "signals" && <span className="nav-badge">4</span>}
            </button>
          ))}
        </nav>

        <div className="sidebar-section-label watch-label">TODAY&apos;S WATCH</div>
        <div className="watch-mini-list">
          {codes.slice(0, 4).map((item) => (
            <button
              className={`watch-mini-row ${selectedCode === item.code ? "selected" : ""}`}
              key={item.code}
              onClick={() => setSelectedCode(item.code)}
            >
              <span className="watch-dot" />
              <span>
                <strong>{item.code.split(".")[0]}</strong>
                <small>{item.name}</small>
              </span>
              <em>{item.change}</em>
            </button>
          ))}
        </div>

        <div className="sidebar-bottom">
          <div className="connection-row">
            <span className={`status-dot ${windConnected ? "connected" : "demo"}`} />
            <span>{windConnected ? "WindPy 接入占位" : "演示行情模式"}</span>
          </div>
          <button className="connect-link" onClick={() => { setWindConnected(true); setNotice("已切换为 WindPy 接入预览状态"); }}>
            {windConnected ? "等待本机行情服务" : "连接 WindPy →"}
          </button>
        </div>
      </aside>

      <section className="main-area">
        <header className="topbar">
          <div>
            <p className="eyebrow">INTRADAY SIGNAL DESK / 01</p>
            <h1>今天的盘中信号</h1>
          </div>
          <div className="topbar-actions">
            <span className={`market-pill ${monitoring ? "live" : ""}`}>
              <span className="live-dot" />
              {monitoring ? "监控运行中" : "监控已暂停"}
            </span>
            <span className="date-label">2026.08.11 · {clock}</span>
            <button className="round-button" aria-label="通知设置" onClick={() => setNotice("通知设置：Windows Toast + 声音提醒")}>♢</button>
            <div className="user-avatar">S</div>
          </div>
        </header>

        <div className="page-body">
          <section className="intro-row">
            <div>
              <p className="section-kicker">SIGNAL FIRST, EXECUTION LATER</p>
              <h2>先把箭头做对，再谈自动化。</h2>
              <p className="intro-copy">固定规则负责触发，人工负责确认。每一个提醒都带着触发依据，不把事后图形伪装成实时预测。</p>
            </div>
            <button className={`primary-button ${monitoring ? "stop" : ""}`} onClick={toggleMonitoring}>
              <span className="button-pulse" />
              {monitoring ? "暂停盘中监控" : "启动盘中监控"}
            </button>
          </section>

          <section className="metrics-row" aria-label="监控摘要">
            <div className="metric-card">
              <span className="metric-label">今日关注</span>
              <strong>{codes.length}<small> 个标的</small></strong>
              <span className="metric-note up">+2 较昨日</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">已触发信号</span>
              <strong>04<small> 次</small></strong>
              <span className="metric-note">2 买入 · 2 卖出</span>
            </div>
            <div className="metric-card focus-card">
              <span className="metric-label">当前策略</span>
              <strong>{activeStrategy.title}</strong>
              <span className="metric-note">{activeStrategy.fit}</span>
            </div>
          </section>

          <section className="content-grid">
            <div className="workspace-column">
              <section className="panel watch-panel">
                <div className="panel-heading">
                  <div>
                    <span className="panel-index">A /</span>
                    <h3>今日关注列表</h3>
                  </div>
                  <span className="muted-label">开盘前更新</span>
                </div>
                <div className="watch-input-row">
                  <div className="code-input-wrap">
                    <span className="input-prefix">⌕</span>
                    <input
                      value={draftCode}
                      onChange={(event) => setDraftCode(event.target.value)}
                      onKeyDown={(event) => { if (event.key === "Enter") addCode(); }}
                      placeholder="输入 WindCode，例如 600519.SH"
                      aria-label="添加 WindCode"
                    />
                  </div>
                  <button className="ghost-button" onClick={addCode}>+ 添加标的</button>
                </div>
                <div className="code-chip-row">
                  {codes.map((item) => (
                    <button
                      className={`code-chip ${selectedCode === item.code ? "active" : ""}`}
                      key={item.code}
                      onClick={() => setSelectedCode(item.code)}
                    >
                      <span className="chip-status" />
                      {item.code}
                      <span className="chip-name">{item.name}</span>
                    </button>
                  ))}
                </div>
              </section>

              <section className="panel strategy-panel">
                <div className="panel-heading strategy-heading">
                  <div>
                    <span className="panel-index">B /</span>
                    <h3>预制策略库</h3>
                  </div>
                  <span className="muted-label">选择一个作为今日主策略</span>
                </div>
                <div className="strategy-grid">
                  {strategyCatalog.map((strategy) => (
                    <button
                      className={`strategy-card ${strategy.accent} ${selectedStrategy === strategy.id ? "selected" : ""}`}
                      key={strategy.id}
                      onClick={() => { setSelectedStrategy(strategy.id); setNotice(`${strategy.title} 已设为今日主策略`); }}
                    >
                      <span className="strategy-topline">
                        <span className="strategy-index">{strategy.index}</span>
                        <span className="strategy-check">{selectedStrategy === strategy.id ? "✓" : "＋"}</span>
                      </span>
                      <strong>{strategy.title}</strong>
                      <small>{strategy.subtitle}</small>
                      <p>{strategy.description}</p>
                      <span className="strategy-rule">{strategy.rule}</span>
                    </button>
                  ))}
                </div>
              </section>

              <section className="panel chart-panel">
                <div className="chart-heading">
                  <div className="instrument-title">
                    <span className="instrument-tag">{activeSymbol?.code.split(".")[0] ?? "--"}</span>
                    <div>
                      <h3>{activeSymbol?.name ?? "自定义标的"}</h3>
                      <span>{activeSymbol?.code ?? "--"} · 示例行情</span>
                    </div>
                  </div>
                  <div className="chart-price">
                    <strong>{activeSymbol?.price ?? "--"}</strong>
                    <span className="positive">{activeSymbol?.change ?? "--"}</span>
                  </div>
                  <div className="timeframe-switcher" role="group" aria-label="K线周期">
                    {["1m", "5m", "15m"].map((item) => (
                      <button className={timeframe === item ? "active" : ""} key={item} onClick={() => setTimeframe(item)}>{item}</button>
                    ))}
                  </div>
                </div>
                <div className="chart-legend">
                  <span><i className="legend-line price-line" />价格</span>
                  <span><i className="legend-line mean-line" />盘中均价</span>
                  <span className="chart-badge">{timeframe} · 非重绘预览</span>
                </div>
                <PriceChart selectedStrategy={selectedStrategy} />
              </section>

              <section className="lower-grid">
                <div className="panel rule-panel">
                  <div className="panel-heading compact">
                    <div>
                      <span className="panel-index">C /</span>
                      <h3>当前规则骨架</h3>
                    </div>
                    <span className="rule-state">可解释</span>
                  </div>
                  <div className="rule-list">
                    <div><span>01</span><p><b>观察窗口</b><small>盘中实时更新 {timeframe} 数据</small></p><em>ON</em></div>
                    <div><span>02</span><p><b>触发逻辑</b><small>{activeStrategy.rule}</small></p><em>ON</em></div>
                    <div><span>03</span><p><b>提醒方式</b><small>信号变化时提醒，不重复刷屏</small></p><em>ON</em></div>
                  </div>
                </div>
                <div className="panel note-panel">
                  <span className="note-quote">“</span>
                  <p>主流量化不是一套神奇指标，而是把趋势、回归、波动和相对价值拆成可回放的假设。</p>
                  <div className="note-footer"><span>策略研究底稿</span><span>·</span><span>v0.1</span></div>
                </div>
              </section>
            </div>

            <aside className="signals-column">
              <section className="panel signals-panel">
                <div className="signals-heading">
                  <div>
                    <span className="panel-index">LIVE /</span>
                    <h3>信号流</h3>
                  </div>
                  <button className={`sound-toggle ${soundOn ? "on" : ""}`} onClick={() => setSoundOn((current) => !current)} aria-label="切换声音提醒">{soundOn ? "声" : "静"}</button>
                </div>
                <div className="signal-summary">
                  <span className="summary-orb" />
                  <div><strong>{monitoring ? "等待下一次触发" : "监控尚未启动"}</strong><small>{monitoring ? "WindPy 行情通道待接入" : "启动后将在这里显示提醒"}</small></div>
                </div>
                <div className="signal-feed">
                  {visibleSignals.map((signal) => (
                    <button className="signal-item" key={signal.id} onClick={() => setNotice(`${signal.code} · ${signal.rationale}`)}>
                      <div className={`signal-marker ${signal.side.toLowerCase()}`}><span>{signal.side === "BUY" ? "↗" : "↘"}</span></div>
                      <div className="signal-main">
                        <div className="signal-title-row"><strong>{signal.side === "BUY" ? "买入提醒" : "卖出提醒"}</strong><span>{signal.time}</span></div>
                        <div className="signal-code-row"><span>{signal.name} · {signal.code}</span><em className={signal.change.startsWith("-") ? "negative" : "positive"}>{signal.change}</em></div>
                        <p>{signal.rationale}</p>
                        <div className="signal-meta"><span>{signal.strategy}</span><span className={signal.level === "确认" ? "confirmed" : "watching"}>{signal.level}</span><b>¥ {signal.price}</b></div>
                      </div>
                    </button>
                  ))}
                </div>
                <button className="view-all-button" onClick={() => { setActiveNav("signals"); setNotice("已打开全部信号日志"); }}>查看全部信号 <span>→</span></button>
              </section>

              <section className="panel method-panel">
                <div className="panel-heading compact">
                  <div>
                    <span className="panel-index">METHOD /</span>
                    <h3>策略提示</h3>
                  </div>
                </div>
                <p>今天不预测最高点和最低点，只在信号完成确认后提醒。箭头允许有延迟，但不允许使用未来数据。</p>
                <div className="method-tags"><span>不自动下单</span><span>不读取持仓</span><span>可回放</span></div>
              </section>
            </aside>
          </section>
        </div>
      </section>

      {notice && <div className="toast" role="status"><span className="toast-mark">✓</span>{notice}</div>}
    </main>
  );
}

