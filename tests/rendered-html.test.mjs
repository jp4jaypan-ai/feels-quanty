import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the concise dual-strategy workspace without fictional signals", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const [html, page] = await Promise.all([
    response.text(),
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(html, /<title>feels-quanty · 盘中信号工作台<\/title>/i);
  assert.match(html, />feels-quanty</);
  assert.match(html, /今日标的/);
  assert.match(html, /添加 WindCode/);
  assert.match(html, /事件/);
  assert.match(html, /设置/);
  assert.match(html, /运行策略/);
  assert.match(html, /分时波段/);
  assert.match(html, /多尺度动能/);
  assert.match(html, /自动定级 · MACD-V/);
  assert.match(html, /双策略/);
  assert.match(html, /模式/);
  assert.match(html, /灵敏/);
  assert.match(html, /标准/);
  assert.match(html, /稳健/);
  assert.match(html, /开盘快速识别/);
  assert.match(html, /波段候选事件/);
  assert.match(html, /Windows 提醒/);
  assert.match(html, /高级参数/);
  assert.match(html, /V4\.0/);
  assert.match(html, /连接/);
  for (const label of [
    "波段幅度 %",
    "反转幅度 %",
    "最少 K 线",
    "确认分",
    "候选分",
    "增强分",
    "候选反转",
    "增强反转",
    "有效 K 线",
    "开盘最少 K 线",
  ]) {
    assert.match(html, new RegExp(label));
  }
  assert.match(html, /波段与多尺度动能信号仅作提醒 · 不自动交易/);

  // Event states remain a source-level V4 contract even when SSR has no live events.
  for (const state of ["CANDIDATE", "STRENGTHENING", "CONFIRMED", "INVALIDATED"]) {
    assert.match(page, new RegExp(state));
  }
  assert.match(page, /rule_name: "分时顶底策略 V4 候选\/确认双层"/);
  assert.match(page, /eventStateLabel/);
  assert.match(page, /eventTitle/);

  assert.doesNotMatch(html, /AI NATIVE|QUANT COPILOT|控制中心|WORKSPACE/);
  assert.doesNotMatch(html, /系统现在看到什么|观察结构|证据增强|确认提醒/);
  assert.doesNotMatch(html, /分时顶底事件策略 V4\.0|候选高召回 \+ 确认高精度/);
  assert.doesNotMatch(html, /自适应多因子盘中策略 V2|量比阈值|ATR 扩展倍数/);
  assert.doesNotMatch(html, /预制策略库|示例行情|initialSignals|strategyCatalog/i);
  assert.doesNotMatch(html, /候选分时顶·观察卖点|候选分时底·观察买点|增强候选分时|分时顶 · 卖出提醒|分时底 · 买入提醒/);
});

test("connects the frontend to V4 swing and multiscale MACD-V events", async () => {
  const [page, layout, packageJson, backend, swingEngine, macdEngine, toast, launcher] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
    readFile(new URL("../backend/server.py", import.meta.url), "utf8"),
    readFile(new URL("../backend/swing_v3.py", import.meta.url), "utf8"),
    readFile(new URL("../backend/macd_divergence.py", import.meta.url), "utf8"),
    readFile(new URL("../backend/notify_toast.ps1", import.meta.url), "utf8"),
    readFile(new URL("../backend/start.ps1", import.meta.url), "utf8"),
  ]);

  for (const field of [
    "sensitivity",
    "min_swing_pct",
    "min_swing_range_mult",
    "reversal_pct",
    "reversal_range_mult",
    "min_leg_bars",
    "min_confidence",
    "warmup_bars",
    "opening_guard_minutes",
    "cooldown_seconds",
    "notifications_enabled",
    "swing_strategy_enabled",
    "macd_strategy_enabled",
    "opening_fast_enabled",
    "opening_fast_window_minutes",
    "opening_fast_min_bars",
    "opening_fast_gap_pct",
    "opening_fast_min_swing_pct",
    "opening_fast_swing_range_mult",
    "opening_fast_reversal_pct",
    "opening_fast_reversal_range_mult",
    "opening_fast_min_confidence",
    "candidate_alerts_enabled",
    "macd_alerts",
    "strategy_kind",
    "strategy_label",
    "scale_label",
    "scale_threshold_pct",
    "consensus_pct",
    "momentum_stage_label",
    "macdv",
    "advice_level",
    "candidate_notifications_enabled",
    "candidate_min_confidence",
    "candidate_strengthening_confidence",
    "candidate_reversal_fraction",
    "candidate_strengthening_reversal_fraction",
    "candidate_ttl_bars",
    "opening_candidate_min_bars",
  ]) {
    assert.match(page, new RegExp(field));
  }

  for (const field of [
    "analytics",
    "ready",
    "decision_bars",
    "warmup_progress",
    "phase_label",
    "candidate_price",
    "leg_amplitude_pct",
    "reversal_progress",
    "blocked_reasons",
    "side",
    "turning_point",
    "extreme_time",
    "extreme_timestamp",
    "confirm_timestamp",
    "extreme_price",
    "confirm_price",
    "confirm_time",
    "lag_bars",
    "confidence",
    "confirmations",
    "active_channel",
    "active_channel_label",
    "opening_fast_active",
    "opening_fast_bars",
    "opening_fast_status",
    "regular_ready",
    "regular_warmup_progress",
    "backfill_status",
    "first_open",
    "pre_close",
    "opening_gap_pct",
    "channel_label",
    "pattern",
    "turning_events",
    "event_id",
    "revision",
    "event_state",
    "signal_level",
    "created_time",
    "created_timestamp",
    "updated_time",
    "updated_timestamp",
    "observed_price",
    "observed_time",
    "observed_timestamp",
    "notification_kind",
    "strategy_version",
    "rationale",
    "channel",
    "active_turn_event",
    "candidate_alerts_enabled",
  ]) {
    assert.match(page, new RegExp(field));
  }

  assert.match(page, /rule_name: "分时顶底策略 V4 候选\/确认双层"/);
  assert.match(page, /candidate_min_confidence: 55,/);
  assert.match(page, /candidate_strengthening_confidence: 70,/);
  assert.match(page, /candidate_reversal_fraction: 0\.35,/);
  assert.match(page, /candidate_strengthening_reversal_fraction: 0\.55,/);
  assert.match(page, /candidate_ttl_bars: 15,/);
  assert.match(page, /opening_candidate_min_bars: 1,/);
  assert.match(page, /candidate_min_confidence: merged\.candidate_min_confidence \?\? 55,/);
  assert.match(page, /candidate_strengthening_confidence: merged\.candidate_strengthening_confidence \?\? 70,/);
  assert.match(page, /candidate_reversal_fraction: merged\.candidate_reversal_fraction \?\? 0\.35,/);
  assert.match(page, /candidate_strengthening_reversal_fraction: merged\.candidate_strengthening_reversal_fraction \?\? 0\.55,/);
  assert.match(page, /candidate_ttl_bars: merged\.candidate_ttl_bars \?\? 15,/);
  assert.match(page, /opening_candidate_min_bars: merged\.opening_candidate_min_bars \?\? 1,/);
  assert.match(page, /min=['"]50['"] max=['"]90['"] step=['"]1['"] value=\{rule\.candidate_min_confidence\}/);
  assert.match(page, /min=['"]55['"] max=['"]95['"] step=['"]1['"] value=\{rule\.candidate_strengthening_confidence\}/);
  assert.match(page, /min=['"]0\.10['"] max=['"]0\.90['"] step=['"]0\.01['"] value=\{rule\.candidate_reversal_fraction\}/);
  assert.match(page, /min=['"]0\.20['"] max=['"]1\.00['"] step=['"]0\.01['"] value=\{rule\.candidate_strengthening_reversal_fraction\}/);
  assert.match(page, /min=['"]3['"] max=['"]60['"] step=['"]1['"] value=\{rule\.candidate_ttl_bars\}/);
  assert.match(page, /min=['"]1['"] max=['"]5['"] step=['"]1['"] value=\{rule\.opening_candidate_min_bars\}/);

  assert.match(page, /\/api\/state/);
  assert.match(page, /\/api\/monitor/);
  assert.match(page, /\/api\/notify\/test/);
  assert.match(page, /useState\("--:--:--"\)/);
  assert.match(page, /setTimeout\(updateClock, 0\)/);
  assert.doesNotMatch(page, /useState\(new Date/);
  assert.doesNotMatch(page, /Date\.now|Math\.random/);
  assert.match(page, /key={eventIdKey\(event\)}/);
  assert.match(page, /latestEventViews/);
  assert.match(page, /eventViewsForCode/);
  assert.match(page, /turningEvents\.filter\(\(event\) => event\.code === code\)/);
  assert.match(page, /if \(scoped\.length\) swingViews = scoped\.map\(swingEventToView\)/);
  assert.match(page, /signals\.filter\(\(signal\) => signal\.code === code\)/);
  assert.match(page, /macdAlerts\.filter\(\(alert\) => alert\.code === code\)/);
  assert.match(page, /MULTISCALE_MACDV/);
  assert.match(page, /MDC-MACDV-2\.0/);
  assert.match(page, /toggleStrategy/);
  assert.doesNotMatch(page, /!event\.code \|\| !code \|\| event\.code === code/);
  assert.match(page, /notification_kind: "CANDIDATE" \| "CONFIRMED" \| "NONE";\s+strategy_version: "V4\.0";\s+code: string;/);
  assert.doesNotMatch(page, /volume_ratio_threshold|atr_extension|StrategyMetrics|emaDirection|自适应多因子盘中策略 V2/);

  assert.match(layout, /title: "feels-quanty · 盘中信号工作台"/);
  assert.match(packageJson, /"backend"/);
  assert.match(backend, /SwingV3Engine/);
  assert.match(backend, /DecisionBarAggregator/);
  assert.match(backend, /parse_wsi_bars/);
  assert.match(backend, /w\.wsi\(code, 'open,high,low,close,volume,amt'/);
  assert.match(backend, /'analytics': dict\(self\.analytics\)/);
  assert.match(swingEngine, /'strategy_version': 'V4\.0'/);
  assert.match(swingEngine, /OPENING_FAST/);
  assert.match(swingEngine, /GAP_REJECTION/);
  assert.match(swingEngine, /'extreme_timestamp'/);
  assert.match(swingEngine, /'confirm_timestamp'/);
  assert.match(swingEngine, /'reversal_progress'/);
  assert.match(macdEngine, /STRATEGY_VERSION = 'MDC-MACDV-2\.0'/);
  assert.match(macdEngine, /def _directional_change/);
  assert.match(macdEngine, /def _momentum_stage/);
  assert.match(macdEngine, /'notification_kind': notification_kind/);
  assert.match(toast, /ShowBalloonTip/);
  assert.match(launcher, /Python27|py\.exe/);
  await assert.rejects(access(new URL("../app/_sites-preview/", import.meta.url)));
});
