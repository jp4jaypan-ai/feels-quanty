"use client";

import { useEffect, useRef, useState } from "react";

type RuleConfig = {
  strategy_version: "V4.0";
  rule_name: string;
  sensitivity: "sensitive" | "standard" | "robust";
  min_swing_pct: number;
  min_swing_range_mult: number;
  reversal_pct: number;
  reversal_range_mult: number;
  min_leg_bars: number;
  min_confidence: number;
  warmup_bars: number;
  opening_guard_minutes: number;
  cooldown_seconds: number;
  notifications_enabled: boolean;
  swing_strategy_enabled: boolean;
  macd_strategy_enabled: boolean;
  opening_fast_enabled: boolean;
  opening_fast_window_minutes: number;
  opening_fast_min_bars: number;
  opening_fast_gap_pct: number;
  opening_fast_min_swing_pct: number;
  opening_fast_swing_range_mult: number;
  opening_fast_reversal_pct: number;
  opening_fast_reversal_range_mult: number;
  opening_fast_min_confidence: number;
  candidate_alerts_enabled: boolean;
  candidate_notifications_enabled: boolean;
  candidate_min_confidence: number;
  candidate_strengthening_confidence: number;
  candidate_reversal_fraction: number;
  candidate_strengthening_reversal_fraction: number;
  candidate_ttl_bars: number;
  opening_candidate_min_bars: number;
};

type EventState = "CANDIDATE" | "STRENGTHENING" | "CONFIRMED" | "INVALIDATED";
type SignalLevel = "CANDIDATE" | "CONFIRMED";
type EventChannel = "OPENING_FAST" | "REGULAR";
type EventPattern = "EARLY_REVERSAL_WATCH" | "GAP_REJECTION" | "IMPULSE_REVERSAL" | "DIRECTIONAL_CHANGE" | "MACD_DIVERGENCE" | "MULTISCALE_MACDV";
type StrategyKind = "SWING" | "MACD";

type Quote = {
  code: string;
  price: number;
  pct_change: number;
  change: string;
  volume_total: number | null;
  amount_total: number | null;
  high: number | null;
  low: number | null;
  pre_close: number | null;
  vwap: number | null;
  bid1: number | null;
  ask1: number | null;
  time: string;
  updated_at: string;
};

type Bar = {
  timestamp: number;
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  vwap: number | null;
  volume: number;
  amount: number;
};

type Analytics = {
  ready: boolean;
  decision_bars: number;
  warmup_bars: number;
  warmup_target: number;
  warmup_progress: number;
  phase: "BOOTSTRAP" | "TRACKING_UP" | "TRACKING_DOWN";
  phase_label: string;
  regime: string;
  regime_label: string;
  candidate_type: "TOP" | "BOTTOM" | null;
  candidate_price: number | null;
  candidate_time: string | null;
  candidate_timestamp: number | null;
  leg_start_price: number | null;
  leg_amplitude_pct: number;
  reversal_threshold_pct: number;
  reversal_progress: number;
  robust_range: number;
  blocked_reasons: string[];
  last_updated: string | null;
  last_bar_time: string | null;
  active_channel: "OPENING_FAST" | "REGULAR";
  active_channel_label: string;
  opening_fast_enabled: boolean;
  opening_fast_active: boolean;
  opening_fast_bars: number;
  opening_fast_min_bars: number;
  opening_fast_status: string;
  regular_ready: boolean;
  regular_warmup_progress: number;
  backfill_status: "not_run" | "ok" | "skipped" | "failed";
  backfill_reason: string | null;
  first_open: number | null;
  pre_close: number | null;
  opening_gap_pct: number | null;
  last_signal_side: "BUY" | "SELL" | null;
  last_signal_channel: "OPENING_FAST" | "REGULAR" | null;
  active_turn_event?: TurningEvent | null;
  candidate_alerts_enabled?: boolean;
};

type Signal = {
  id: number;
  timestamp: number;
  code: string;
  side: "BUY" | "SELL";
  price: number;
  change: string;
  time: string;
  strategy: string;
  strategy_version: string;
  turning_point: "TOP" | "BOTTOM";
  module: string;
  module_label: string;
  regime: string;
  regime_label: string;
  extreme_price: number;
  extreme_time: string;
  extreme_timestamp: number;
  confirm_price: number;
  confirm_time: string;
  confirm_timestamp: number;
  lag_bars: number;
  swing_pct: number;
  reversal_pct_actual: number;
  reversal_threshold_pct: number;
  confidence: number;
  confirmations: string[];
  rationale: string;
  source: string;
  channel: EventChannel;
  channel_label: string;
  pattern: EventPattern;
  first_open: number | null;
  pre_close: number | null;
  opening_gap_pct: number | null;
  event_id?: number | string;
  revision?: number;
  event_state?: EventState;
  signal_level?: SignalLevel;
};

type TurningEvent = {
  event_id: number | string;
  revision: number;
  event_state: EventState;
  signal_level: SignalLevel;
  side: "BUY" | "SELL";
  turning_point: "TOP" | "BOTTOM";
  created_time: string;
  created_timestamp: number;
  updated_time: string;
  updated_timestamp: number;
  extreme_price: number;
  extreme_time: string;
  extreme_timestamp: number;
  observed_price: number;
  observed_time: string;
  observed_timestamp: number;
  confirm_price: number | null;
  confirm_time: string | null;
  confirm_timestamp: number | null;
  confidence: number;
  confirmations: string[];
  rationale: string;
  channel: EventChannel;
  channel_label: string;
  pattern: EventPattern;
  notification_kind: "CANDIDATE" | "CONFIRMED" | "NONE";
  strategy_version: "V4.0";
  code: string;
};

type MacdAlert = {
  id: string;
  event_id: string;
  revision: number;
  event_state: EventState;
  signal_level: SignalLevel;
  notification_kind: "CONFIRMED" | "NONE";
  advice_level: "WATCH" | "CANDIDATE" | "CONFIRMED";
  advice_label: string;
  action_label: string;
  code: string;
  strategy_version: string;
  strategy: string;
  module: "multiscale_macdv" | "macd_divergence";
  module_label: string;
  side: "BUY" | "SELL";
  turning_point: "TOP" | "BOTTOM";
  scale_code: "MICRO" | "SMALL" | "MEDIUM" | "LARGE";
  scale_label: string;
  scale_rank: number;
  scale_threshold_pct: number;
  triggered_scales: string[];
  triggered_scale_labels: string[];
  aligned_scales: string[];
  aligned_scale_labels: string[];
  consensus_pct: number;
  regime: string;
  regime_label: string;
  momentum_stage: string;
  momentum_stage_label: string;
  macdv: number;
  macdv_signal: number;
  macdv_histogram: number;
  macdv_slope: number;
  divergence: boolean;
  divergence_type: "BEARISH_REGULAR" | "BULLISH_REGULAR" | "NONE";
  divergence_label: string;
  previous_extreme_price: number | null;
  previous_extreme_time: string | null;
  previous_extreme_timestamp: number | null;
  extreme_price: number;
  extreme_time: string;
  extreme_timestamp: number;
  created_time: string;
  created_timestamp: number;
  observed_price: number;
  observed_time: string;
  observed_timestamp: number;
  updated_time: string;
  updated_timestamp: number;
  confirm_price: number;
  confirm_time: string;
  confirm_timestamp: number;
  timestamp: number;
  price_delta_pct: number;
  price_slope_pct_per_bar: number;
  dif_delta_pct: number;
  dif_slope_pct_per_bar: number;
  histogram_slope_pct_per_bar: number;
  recent_histogram_slope_pct_per_bar: number;
  reversal_pct: number;
  leg_start_price: number;
  leg_start_time: string;
  leg_amplitude_pct: number;
  leg_bars: number;
  structure_ok: boolean;
  volume_ratio: number;
  confirmations: string[];
  channel: EventChannel;
  channel_label: string;
  pattern: EventPattern;
  confidence: number;
  rationale: string;
  source: string;
};

type EventView = Omit<TurningEvent, "strategy_version"> & {
  strategy_version: string;
  strategy_kind: StrategyKind;
  strategy_label: string;
  scale_code?: MacdAlert["scale_code"];
  scale_label?: string;
  scale_threshold_pct?: number;
  consensus_pct?: number;
  momentum_stage?: string;
  momentum_stage_label?: string;
  macdv?: number;
  divergence_label?: string;
  advice_level?: MacdAlert["advice_level"];
  action_label?: string;
  leg_amplitude_pct?: number;
  leg_bars?: number;
};

type BackendState = {
  ok: boolean;
  windpy_available: boolean;
  connected: boolean;
  monitoring: boolean;
  codes: string[];
  config: Partial<RuleConfig>;
  last_error: string | null;
  last_update: string | null;
  quotes: Record<string, Quote>;
  bars: Record<string, Bar[]>;
  analytics: Record<string, Analytics>;
  signals: Signal[];
  turning_events?: TurningEvent[];
  macd_alerts?: MacdAlert[];
  server_time: string;
};

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8765";

const emptyRule: RuleConfig = {
  strategy_version: "V4.0",
  rule_name: "分时顶底策略 V4 候选/确认双层",
  sensitivity: "standard",
  min_swing_pct: 0.45,
  min_swing_range_mult: 1.2,
  reversal_pct: 0.28,
  reversal_range_mult: 0.45,
  min_leg_bars: 3,
  min_confidence: 70,
  warmup_bars: 6,
  opening_guard_minutes: 5,
  cooldown_seconds: 120,
  notifications_enabled: true,
  swing_strategy_enabled: true,
  macd_strategy_enabled: true,
  opening_fast_enabled: true,
  opening_fast_window_minutes: 5,
  opening_fast_min_bars: 2,
  opening_fast_gap_pct: 1,
  opening_fast_min_swing_pct: 0.8,
  opening_fast_swing_range_mult: 1.8,
  opening_fast_reversal_pct: 0.35,
  opening_fast_reversal_range_mult: 0.7,
  opening_fast_min_confidence: 85,
  candidate_alerts_enabled: true,
  candidate_notifications_enabled: true,
  candidate_min_confidence: 55,
  candidate_strengthening_confidence: 70,
  candidate_reversal_fraction: 0.35,
  candidate_strengthening_reversal_fraction: 0.55,
  candidate_ttl_bars: 15,
  opening_candidate_min_bars: 1,
};

function mergeRule(value: Partial<RuleConfig> | null | undefined): RuleConfig {
  const merged = { ...emptyRule, ...(value ?? {}) };
  return {
    ...merged,
    strategy_version: "V4.0",
    rule_name: "分时顶底策略 V4 候选/确认双层",
    swing_strategy_enabled: merged.swing_strategy_enabled ?? true,
    macd_strategy_enabled: merged.macd_strategy_enabled ?? true,
    opening_fast_enabled: merged.opening_fast_enabled ?? true,
    opening_fast_window_minutes: merged.opening_fast_window_minutes ?? 5,
    opening_fast_min_bars: merged.opening_fast_min_bars ?? 2,
    opening_fast_gap_pct: merged.opening_fast_gap_pct ?? 1,
    opening_fast_min_swing_pct: merged.opening_fast_min_swing_pct ?? 0.8,
    opening_fast_swing_range_mult: merged.opening_fast_swing_range_mult ?? 1.8,
    opening_fast_reversal_pct: merged.opening_fast_reversal_pct ?? 0.35,
    opening_fast_reversal_range_mult: merged.opening_fast_reversal_range_mult ?? 0.7,
    opening_fast_min_confidence: merged.opening_fast_min_confidence ?? 85,
    candidate_alerts_enabled: merged.candidate_alerts_enabled ?? true,
    candidate_notifications_enabled: merged.candidate_notifications_enabled ?? true,
    candidate_min_confidence: merged.candidate_min_confidence ?? 55,
    candidate_strengthening_confidence: merged.candidate_strengthening_confidence ?? 70,
    candidate_reversal_fraction: merged.candidate_reversal_fraction ?? 0.35,
    candidate_strengthening_reversal_fraction: merged.candidate_strengthening_reversal_fraction ?? 0.55,
    candidate_ttl_bars: merged.candidate_ttl_bars ?? 15,
    opening_candidate_min_bars: merged.opening_candidate_min_bars ?? 1,
  };
}

const sensitivityPresets: Record<RuleConfig["sensitivity"], Partial<RuleConfig>> = {
  sensitive: { min_swing_pct: 0.3, min_swing_range_mult: 0.9, reversal_pct: 0.2, reversal_range_mult: 0.35, min_leg_bars: 2, min_confidence: 65 },
  standard: { min_swing_pct: 0.45, min_swing_range_mult: 1.2, reversal_pct: 0.28, reversal_range_mult: 0.45, min_leg_bars: 3, min_confidence: 70 },
  robust: { min_swing_pct: 0.65, min_swing_range_mult: 1.5, reversal_pct: 0.38, reversal_range_mult: 0.6, min_leg_bars: 4, min_confidence: 78 },
};

function metricText(value: number | null | undefined, digits = 2, suffix = "") {
  return value == null || !Number.isFinite(value) ? "--" : `${value.toFixed(digits)}${suffix}`;
}

function shortTime(value: string | null | undefined) {
  if (!value) return "--";
  return value.length > 8 ? value.slice(-8) : value;
}

function eventIdKey(event: Pick<TurningEvent, "event_id">) {
  return String(event.event_id);
}

function latestEventViews(events: EventView[]) {
  const latest = new Map<string, EventView>();
  events.forEach((event) => {
    const key = eventIdKey(event);
    const current = latest.get(key);
    if (!current || event.revision > current.revision || (event.revision === current.revision && event.updated_timestamp >= current.updated_timestamp)) {
      latest.set(key, event);
    }
  });
  return Array.from(latest.values()).sort((left, right) => right.updated_timestamp - left.updated_timestamp);
}

function legacySignalToEvent(signal: Signal): EventView {
  const referencePrice = Number.isFinite(signal.confirm_price) ? signal.confirm_price : signal.price;
  const referenceTime = signal.confirm_time || signal.time;
  const referenceTimestamp = Number.isFinite(signal.confirm_timestamp) ? signal.confirm_timestamp : signal.timestamp;
  return {
    event_id: signal.event_id ?? signal.id,
    revision: signal.revision ?? 0,
    event_state: signal.event_state ?? "CONFIRMED",
    signal_level: signal.signal_level ?? "CONFIRMED",
    side: signal.side,
    turning_point: signal.turning_point,
    created_time: signal.extreme_time,
    created_timestamp: signal.extreme_timestamp,
    updated_time: referenceTime,
    updated_timestamp: referenceTimestamp,
    extreme_price: signal.extreme_price,
    extreme_time: signal.extreme_time,
    extreme_timestamp: signal.extreme_timestamp,
    observed_price: referencePrice,
    observed_time: referenceTime,
    observed_timestamp: referenceTimestamp,
    confirm_price: signal.confirm_price,
    confirm_time: signal.confirm_time,
    confirm_timestamp: signal.confirm_timestamp,
    confidence: signal.confidence,
    confirmations: signal.confirmations ?? [],
    rationale: signal.rationale,
    channel: signal.channel,
    channel_label: signal.channel_label,
    pattern: signal.pattern,
    notification_kind: "CONFIRMED",
    strategy_version: signal.strategy_version || "V3.1",
    strategy_kind: "SWING",
    strategy_label: "分时波段",
    code: signal.code,
  };
}

function swingEventToView(event: TurningEvent): EventView {
  return {
    ...event,
    strategy_kind: "SWING",
    strategy_label: "分时波段",
  };
}

function macdAlertToEvent(alert: MacdAlert): EventView {
  return {
    event_id: alert.event_id || alert.id,
    revision: alert.revision ?? 1,
    event_state: alert.event_state || "CONFIRMED",
    signal_level: alert.signal_level || "CONFIRMED",
    side: alert.side,
    turning_point: alert.turning_point,
    created_time: alert.created_time || alert.extreme_time,
    created_timestamp: alert.created_timestamp || alert.extreme_timestamp,
    updated_time: alert.updated_time || alert.confirm_time,
    updated_timestamp: alert.updated_timestamp || alert.confirm_timestamp,
    extreme_price: alert.extreme_price,
    extreme_time: alert.extreme_time,
    extreme_timestamp: alert.extreme_timestamp,
    observed_price: alert.observed_price,
    observed_time: alert.observed_time,
    observed_timestamp: alert.observed_timestamp || alert.confirm_timestamp,
    confirm_price: alert.confirm_price,
    confirm_time: alert.confirm_time,
    confirm_timestamp: alert.confirm_timestamp,
    confidence: alert.confidence,
    confirmations: alert.confirmations ?? [],
    rationale: alert.rationale,
    channel: alert.channel || "REGULAR",
    channel_label: alert.channel_label || "MDC · MACD-V",
    pattern: alert.pattern || "MULTISCALE_MACDV",
    notification_kind: alert.notification_kind || "NONE",
    strategy_version: alert.strategy_version || "MDC-MACDV-2.0",
    strategy_kind: "MACD",
    strategy_label: "多尺度动能",
    scale_code: alert.scale_code,
    scale_label: alert.scale_label,
    scale_threshold_pct: alert.scale_threshold_pct,
    consensus_pct: alert.consensus_pct,
    momentum_stage: alert.momentum_stage,
    momentum_stage_label: alert.momentum_stage_label,
    macdv: alert.macdv,
    divergence_label: alert.divergence_label,
    advice_level: alert.advice_level,
    action_label: alert.action_label,
    leg_amplitude_pct: alert.leg_amplitude_pct,
    leg_bars: alert.leg_bars,
    code: alert.code,
  };
}

function eventViewsForCode(
  turningEvents: TurningEvent[] | undefined,
  signals: Signal[],
  macdAlerts: MacdAlert[],
  code: string,
  swingEnabled = true,
  macdEnabled = true,
) {
  let swingViews: EventView[] = [];
  if (swingEnabled && turningEvents?.length) {
    const scoped = turningEvents.filter((event) => event.code === code);
    if (scoped.length) swingViews = scoped.map(swingEventToView);
  }
  if (swingEnabled && swingViews.length === 0) {
    swingViews = signals.filter((signal) => signal.code === code).map(legacySignalToEvent);
  }
  const macdViews = macdEnabled
    ? macdAlerts.filter((alert) => alert.code === code).map(macdAlertToEvent)
    : [];
  return latestEventViews([...swingViews, ...macdViews]);
}

function eventPointLabel(turningPoint: TurningEvent["turning_point"]) {
  return turningPoint === "TOP" ? "顶" : "底";
}

function eventTitle(event: EventView) {
  if (event.strategy_kind === "MACD") {
    const scale = event.scale_label || "自适应";
    const point = event.turning_point === "TOP" ? "顶部" : "底部";
    if (event.event_state === "CONFIRMED") return scale + point + "确认";
    if (event.event_state === "STRENGTHENING") return scale + point + "候选";
    return scale + point + "观察";
  }
  const point = eventPointLabel(event.turning_point);
  if (event.event_state === "CANDIDATE") return "候选" + point + "部";
  if (event.event_state === "STRENGTHENING") return point + "部增强";
  if (event.event_state === "INVALIDATED") return "候选失效";
  return event.side === "SELL" ? "卖出提醒" : "买入提醒";
}

function eventChartLabel(event: EventView) {
  if (event.strategy_kind === "MACD") {
    return (event.scale_label || "尺度") + eventPointLabel(event.turning_point);
  }
  if (event.event_state === "INVALIDATED") return "已失效";
  if (event.event_state === "STRENGTHENING") return "增强" + eventPointLabel(event.turning_point);
  if (event.event_state === "CANDIDATE") return "候选" + eventPointLabel(event.turning_point);
  return "分时" + eventPointLabel(event.turning_point);
}

function eventStateLabel(state: EventState) {
  if (state === "CANDIDATE") return "观察";
  if (state === "STRENGTHENING") return "增强";
  if (state === "CONFIRMED") return "确认";
  return "失效";
}

function channelLabel(event: EventView) {
  return event.channel_label || (event.channel === "OPENING_FAST" ? "开盘快通道" : "常规通道");
}

function eventMeta(event: EventView, code: string) {
  if (event.strategy_kind === "MACD") {
    return [
      code,
      event.momentum_stage_label,
      event.consensus_pct != null ? "一致 " + metricText(event.consensus_pct, 0, "%") : null,
    ].filter(Boolean).join(" · ");
  }
  return code + " · " + channelLabel(event);
}
async function requestJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
  });
  const payload = (await response.json()) as T & { error?: string };
  if (!response.ok) throw new Error(payload.error || `请求失败（${response.status}）`);
  return payload;
}

function PriceChart({
  bars,
  turningEvents,
  signals,
  macdAlerts,
  code,
  swingEnabled,
  macdEnabled,
}: {
  bars: Bar[];
  turningEvents: TurningEvent[];
  signals: Signal[];
  macdAlerts: MacdAlert[];
  code: string;
  swingEnabled: boolean;
  macdEnabled: boolean;
}) {
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
      context.strokeStyle = "rgba(21, 27, 24, 0.08)";
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

      const usableBars = bars.filter((bar) => Number.isFinite(bar.close) && bar.close > 0);
      if (usableBars.length < 2) {
        context.font = "600 12px Arial";
        context.fillStyle = "rgba(35, 42, 38, 0.62)";
        context.textAlign = "center";
        context.fillText(code ? "等待行情" : "添加一个标的", width / 2, height / 2 - 6);
        context.font = "500 10px Arial";
        context.fillStyle = "rgba(100, 108, 103, 0.68)";
        context.fillText("真实报价会显示在这里", width / 2, height / 2 + 17);
        context.textAlign = "left";
        return;
      }

      const visibleEvents = eventViewsForCode(
        turningEvents,
        signals,
        macdAlerts,
        code,
        swingEnabled,
        macdEnabled,
      ).slice(0, 10);
      const plottedPrices = usableBars.flatMap((bar) => [bar.low, bar.high, bar.close]);
      visibleEvents.forEach((event) => {
        [event.extreme_price, event.observed_price, event.confirm_price].forEach((value) => {
          if (value != null && Number.isFinite(value)) plottedPrices.push(value);
        });
      });
      const min = Math.min(...plottedPrices) * 0.998;
      const max = Math.max(...plottedPrices) * 1.002;
      const x = (index: number) => padding.left + (index / (usableBars.length - 1)) * chartWidth;
      const y = (value: number) => padding.top + ((max - value) / Math.max(max - min, 0.0001)) * chartHeight;

      const drawSeries = (values: number[], color: string, lineWidth: number, dashed = false) => {
        if (values.length < 2) return;
        context.beginPath();
        context.setLineDash(dashed ? [5, 5] : []);
        values.forEach((value, index) => {
          if (index === 0) context.moveTo(x(index), y(value));
          else context.lineTo(x(index), y(value));
        });
        context.strokeStyle = color;
        context.lineWidth = lineWidth;
        context.stroke();
        context.setLineDash([]);
      };

      const area = context.createLinearGradient(0, padding.top, 0, height - padding.bottom);
      area.addColorStop(0, "rgba(91, 92, 240, 0.12)");
      area.addColorStop(1, "rgba(91, 92, 240, 0)");
      context.beginPath();
      usableBars.forEach((bar, index) => {
        if (index === 0) context.moveTo(x(index), y(bar.close));
        else context.lineTo(x(index), y(bar.close));
      });
      context.lineTo(x(usableBars.length - 1), height - padding.bottom);
      context.lineTo(x(0), height - padding.bottom);
      context.closePath();
      context.fillStyle = area;
      context.fill();

      drawSeries(usableBars.map((bar) => bar.close), "#5b5cf0", 2.6);
      const vwapBars = usableBars.filter((bar) => bar.vwap && bar.vwap > min && bar.vwap < max);
      if (vwapBars.length > 1) drawSeries(vwapBars.map((bar) => bar.vwap as number), "rgba(194, 137, 43, 0.92)", 1.5, true);

      const nearestIndex = (timestamp: number) => {
        let closestIndex = -1;
        let closestDistance = Number.POSITIVE_INFINITY;
        usableBars.forEach((bar, index) => {
          const distance = Math.abs(bar.timestamp - timestamp);
          if (distance < closestDistance) {
            closestDistance = distance;
            closestIndex = index;
          }
        });
        return closestIndex >= 0 && closestDistance <= 120 ? closestIndex : -1;
      };

      visibleEvents.forEach((event) => {
        const extremeIndex = nearestIndex(event.extreme_timestamp);
        if (extremeIndex < 0) return;
        const extremeX = x(extremeIndex);
        const extremeY = y(event.extreme_price);
        const color = event.event_state === "CONFIRMED"
          ? event.side === "BUY" ? "#15986a" : "#e45164"
          : event.event_state === "INVALIDATED" ? "#9aa19d"
            : event.event_state === "STRENGTHENING" ? "#d88d19" : "#c48a2d";
        const referenceTimestamp = event.event_state === "CONFIRMED" && event.confirm_timestamp != null
          ? event.confirm_timestamp
          : event.observed_timestamp;
        const referencePrice = event.event_state === "CONFIRMED" && event.confirm_price != null
          ? event.confirm_price
          : event.observed_price;
        const referenceIndex = nearestIndex(referenceTimestamp);

        if (referenceIndex >= 0 && referenceIndex !== extremeIndex) {
          const referenceX = x(referenceIndex);
          const referenceY = y(referencePrice);
          context.beginPath();
          context.setLineDash([4, 4]);
          context.moveTo(extremeX, extremeY);
          context.lineTo(referenceX, referenceY);
          context.strokeStyle = color;
          context.lineWidth = 1;
          context.globalAlpha = event.event_state === "INVALIDATED" ? 0.35 : 0.72;
          context.stroke();
          context.setLineDash([]);
          context.globalAlpha = 1;
          context.beginPath();
          context.arc(referenceX, referenceY, 3.5, 0, Math.PI * 2);
          context.fillStyle = color;
          context.globalAlpha = event.event_state === "INVALIDATED" ? 0.35 : 0.9;
          context.fill();
          context.beginPath();
          context.arc(referenceX, referenceY, 7, 0, Math.PI * 2);
          context.strokeStyle = color;
          context.globalAlpha = event.event_state === "INVALIDATED" ? 0.3 : 0.55;
          context.stroke();
          context.globalAlpha = 1;
        }

        if (event.event_state === "CANDIDATE") {
          context.beginPath();
          context.setLineDash([5, 4]);
          context.arc(extremeX, extremeY, 11, 0, Math.PI * 2);
          context.strokeStyle = color;
          context.lineWidth = 1.5;
          context.stroke();
          context.setLineDash([]);
          context.beginPath();
          context.arc(extremeX, extremeY, 3.5, 0, Math.PI * 2);
          context.strokeStyle = color;
          context.lineWidth = 1;
          context.stroke();
        } else if (event.event_state === "STRENGTHENING") {
          context.beginPath();
          context.arc(extremeX, extremeY, 7, 0, Math.PI * 2);
          context.fillStyle = color;
          context.fill();
          context.beginPath();
          context.setLineDash([4, 3]);
          context.arc(extremeX, extremeY, 12, 0, Math.PI * 2);
          context.strokeStyle = color;
          context.lineWidth = 1;
          context.stroke();
          context.setLineDash([]);
        } else if (event.event_state === "INVALIDATED") {
          context.beginPath();
          context.setLineDash([3, 3]);
          context.arc(extremeX, extremeY, 9, 0, Math.PI * 2);
          context.strokeStyle = color;
          context.globalAlpha = 0.42;
          context.stroke();
          context.setLineDash([]);
          context.beginPath();
          context.moveTo(extremeX - 5, extremeY - 5);
          context.lineTo(extremeX + 5, extremeY + 5);
          context.moveTo(extremeX + 5, extremeY - 5);
          context.lineTo(extremeX - 5, extremeY + 5);
          context.stroke();
          context.globalAlpha = 1;
        } else if (event.strategy_kind === "MACD") {
          context.beginPath();
          context.moveTo(extremeX, extremeY - 8);
          context.lineTo(extremeX + 8, extremeY);
          context.lineTo(extremeX, extremeY + 8);
          context.lineTo(extremeX - 8, extremeY);
          context.closePath();
          context.fillStyle = color;
          context.fill();
          context.beginPath();
          context.arc(extremeX, extremeY, 13, 0, Math.PI * 2);
          context.strokeStyle = color;
          context.globalAlpha = 0.32;
          context.lineWidth = 1;
          context.stroke();
          context.globalAlpha = 1;
        } else {
          const direction = event.side === "SELL" ? 1 : -1;
          context.beginPath();
          context.moveTo(extremeX, extremeY + direction * 2);
          context.lineTo(extremeX - 7, extremeY - direction * 10);
          context.lineTo(extremeX + 7, extremeY - direction * 10);
          context.closePath();
          context.fillStyle = color;
          context.fill();
          context.beginPath();
          context.arc(extremeX, extremeY, 12, 0, Math.PI * 2);
          context.strokeStyle = color;
          context.globalAlpha = 0.42;
          context.lineWidth = 1;
          context.stroke();
          context.globalAlpha = 1;
        }
        context.font = "700 10px Arial";
        context.fillStyle = color;
        context.globalAlpha = event.event_state === "INVALIDATED" ? 0.48 : 1;
        context.fillText(eventChartLabel(event), extremeX - 18, extremeY + (event.turning_point === "BOTTOM" ? 27 : -18));
        context.globalAlpha = 1;
      });

      context.font = "600 10px Arial";
      context.fillStyle = "rgba(76, 84, 79, 0.72)";
      const labels = usableBars.length > 20 ? [usableBars[0], usableBars[Math.floor(usableBars.length / 2)], usableBars[usableBars.length - 1]] : usableBars;
      labels.forEach((bar, index) => {
        const sourceIndex = usableBars.indexOf(bar);
        const labelX = x(sourceIndex);
        context.fillText(bar.time, labelX - (index === labels.length - 1 ? 30 : 12), height - 8);
      });
    };

    draw();
    window.addEventListener("resize", draw);
    return () => window.removeEventListener("resize", draw);
  }, [bars, turningEvents, signals, macdAlerts, code, swingEnabled, macdEnabled]);

  return <div className="chart-canvas-wrap"><canvas ref={canvasRef} aria-label={`${code || "标的"} 实时价格图`} /></div>;
}

function AppMark() {
  return <span className="app-mark">Q</span>;
}

function LineIcon({ name }: { name: "bell" | "settings" | "play" | "pause" | "plus" | "close" }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      {name === "bell" && <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></>}
      {name === "settings" && <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" /></>}
      {name === "play" && <path d="m9 7 8 5-8 5Z" />}
      {name === "pause" && <><path d="M9 7v10" /><path d="M15 7v10" /></>}
      {name === "plus" && <><path d="M12 5v14" /><path d="M5 12h14" /></>}
      {name === "close" && <><path d="m6 6 12 12" /><path d="M18 6 6 18" /></>}
    </svg>
  );
}

export default function Home() {
  const [backendState, setBackendState] = useState<BackendState | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [codes, setCodes] = useState<string[]>([]);
  const [selectedCode, setSelectedCode] = useState("");
  const [draftCode, setDraftCode] = useState("");
  const [rule, setRule] = useState<RuleConfig>(emptyRule);
  const [soundOn, setSoundOn] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);
  const [clock, setClock] = useState("--:--:--");
  const ruleLoaded = useRef(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const monitoring = backendState?.monitoring ?? false;
  const connected = backendState?.connected ?? false;
  const quotes = backendState?.quotes ?? {};
  const analytics = backendState?.analytics ?? {};
  const bars = backendState?.bars?.[selectedCode] ?? [];
  const signals = backendState?.signals ?? [];
  const turningEvents = backendState?.turning_events ?? [];
  const macdAlerts = backendState?.macd_alerts ?? [];
  const activeQuote = quotes[selectedCode];
  const selectedAnalytics = analytics[selectedCode];
  const swingEnabled = rule.swing_strategy_enabled;
  const macdEnabled = rule.macd_strategy_enabled;
  const anyStrategyEnabled = swingEnabled || macdEnabled;
  const swingReady = swingEnabled && (selectedAnalytics?.ready ?? false);
  const macdReady = macdEnabled && (selectedAnalytics?.decision_bars ?? 0) >= 35;
  const anyStrategyReady = swingReady || macdReady;
  const activeTurnEvent = swingEnabled && selectedAnalytics?.active_turn_event
    ? swingEventToView(selectedAnalytics.active_turn_event)
    : null;
  const selectedEvents = eventViewsForCode(
    turningEvents,
    signals,
    macdAlerts,
    selectedCode,
    swingEnabled,
    macdEnabled,
  );
  const visibleEvents = selectedEvents.slice(0, 6);
  const activeCandidateCount = selectedEvents.filter((event) => event.event_state === "CANDIDATE" || event.event_state === "STRENGTHENING").length;
  const confirmedEventCount = selectedEvents.filter((event) => event.event_state === "CONFIRMED").length;

  useEffect(() => {
    let alive = true;
    const refresh = async () => {
      try {
        const value = await requestJson<BackendState>("/api/state");
        if (!alive) return;
        setBackendState(value);
        setBackendError(null);
        setCodes(value.codes);
        setSelectedCode((current) => value.codes.includes(current) ? current : value.codes[0] || "");
        if (!ruleLoaded.current) {
          setRule(mergeRule(value.config));
          setSoundOn(value.config.notifications_enabled !== false);
          ruleLoaded.current = true;
        }
      } catch (error) {
        if (!alive) return;
        setBackendError(error instanceof Error ? error.message : "后端暂不可用");
      }
    };
    refresh();
    const timer = window.setInterval(refresh, 1000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    const updateClock = () => setClock(new Date().toLocaleTimeString("zh-CN", { hour12: false }));
    const initialTimer = window.setTimeout(updateClock, 0);
    const timer = window.setInterval(updateClock, 1000);
    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 3200);
    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    if (!drawerOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setDrawerOpen(false);
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [drawerOpen]);

  const showNotice = (message: string) => setNotice(message);
  const applySensitivity = (sensitivity: RuleConfig["sensitivity"]) => {
    setRule((current) => ({ ...current, ...sensitivityPresets[sensitivity], sensitivity }));
  };

  const persistCodes = async (nextCodes: string[]) => {
    try {
      await requestJson("/api/watchlist", { method: "POST", body: JSON.stringify({ codes: nextCodes }) });
      setCodes(nextCodes);
      setSelectedCode((current) => current || nextCodes[0] || "");
      showNotice(`${nextCodes.length} 个标的已写入今日监控`);
    } catch (error) {
      showNotice(error instanceof Error ? error.message : "关注列表写入失败");
    }
  };

  const addCode = () => {
    const normalized = draftCode.trim().toUpperCase();
    if (!normalized) return;
    if (!/^[0-9A-Z_-]+(\.[A-Z]+)?$/.test(normalized)) {
      showNotice("WindCode 格式不正确，例如 600519.SH");
      return;
    }
    if (codes.includes(normalized)) {
      setSelectedCode(normalized);
      setDraftCode("");
      showNotice("这个标的已经在今日监控中");
      return;
    }
    setDraftCode("");
    persistCodes([...codes, normalized]);
  };

  const removeCode = (code: string) => {
    const nextCodes = codes.filter((item) => item !== code);
    setSelectedCode((current) => current === code ? (nextCodes[0] || "") : current);
    persistCodes(nextCodes);
  };

  const saveRule = async () => {
    try {
      const saved = await requestJson<{ config: Partial<RuleConfig> }>("/api/config", { method: "POST", body: JSON.stringify(rule) });
      setRule(mergeRule(saved.config));
      setSoundOn(saved.config.notifications_enabled !== false);
      showNotice("V4.0 参数已保存：候选高召回，确认高精度；仅提醒，不自动交易");
    } catch (error) {
      showNotice(error instanceof Error ? error.message : "规则保存失败");
    }
  };

  const toggleMonitoring = async () => {
    if (!monitoring && codes.length === 0) {
      showNotice("请先添加至少一个 WindCode");
      return;
    }
    try {
      const next = await requestJson<{ state: BackendState }>("/api/monitor", {
        method: "POST",
        body: JSON.stringify({ running: !monitoring, codes, config: rule }),
      });
      setBackendState(next.state);
      showNotice(next.state.monitoring ? "WindPy 监控已启动" : "监控已暂停");
    } catch (error) {
      showNotice(error instanceof Error ? error.message : "监控状态切换失败");
    }
  };

  const testNotification = async () => {
    try {
      await requestJson("/api/notify/test", { method: "POST", body: "{}" });
      showNotice("已触发 Windows 提醒测试");
    } catch (error) {
      showNotice(error instanceof Error ? error.message : "提醒测试失败");
    }
  };

  const toggleSound = async () => {
    const nextEnabled = !soundOn;
    try {
      const saved = await requestJson<{ config: Partial<RuleConfig> }>('/api/config', {
        method: 'POST',
        body: JSON.stringify({ ...rule, notifications_enabled: nextEnabled }),
      });
      setRule(mergeRule(saved.config));
      setSoundOn(saved.config.notifications_enabled !== false);
      showNotice(saved.config.notifications_enabled !== false ? '\u5df2\u5f00\u542f Windows \u63d0\u9192' : '\u5df2\u5173\u95ed Windows \u63d0\u9192');
    } catch (error) {
      showNotice(error instanceof Error ? error.message : '\u63d0\u9192\u72b6\u6001\u66f4\u65b0\u5931\u8d25');
    }
  };

  const toggleStrategy = async (
    field: "swing_strategy_enabled" | "macd_strategy_enabled",
    label: string,
  ) => {
    const previous = rule;
    const nextRule = { ...rule, [field]: !rule[field] };
    setRule(nextRule);
    try {
      const saved = await requestJson<{ config: Partial<RuleConfig> }>("/api/config", {
        method: "POST",
        body: JSON.stringify(nextRule),
      });
      const normalized = mergeRule(saved.config);
      setRule(normalized);
      showNotice(normalized[field] ? label + "已开启" : label + "已关闭");
    } catch (error) {
      setRule(previous);
      showNotice(error instanceof Error ? error.message : label + "状态更新失败");
    }
  };
  const statusText = backendError ? "后端未连接" : connected ? "WindPy 已连接" : backendState?.windpy_available ? "WindPy 待启动" : "等待 WindPy";
  const statusClass = backendError ? "error" : connected ? "connected" : "demo";

  const currentEvent = activeTurnEvent ?? selectedEvents[0];
  const currentEventState = currentEvent?.event_state;
  const stateRailIndex = currentEventState === 'CONFIRMED' ? 2 : currentEventState === 'STRENGTHENING' ? 1 : currentEventState === 'CANDIDATE' ? 0 : anyStrategyReady ? 0 : -1;
  const decisionTitle = currentEvent
    ? eventTitle(currentEvent)
    : !anyStrategyEnabled
      ? '策略已关闭'
      : anyStrategyReady
        ? '观察中'
        : monitoring
          ? '预热中'
          : '待机';
  const decisionDescription = currentEvent?.rationale
    || (!anyStrategyEnabled ? '在设置中开启分时波段、多尺度动能或两者。' : null)
    || selectedAnalytics?.blocked_reasons?.[0]
    || backendError
    || '等待行情形成结构。';
  const decisionPrice = currentEvent?.event_state === 'CONFIRMED' && currentEvent.confirm_price != null ? currentEvent.confirm_price : currentEvent?.observed_price ?? activeQuote?.price;
  const decisionIsConfirmed = currentEventState === 'CONFIRMED';
  const decisionStateClass = decisionIsConfirmed ? (currentEvent?.side === 'SELL' ? 'sell' : 'buy') : currentEventState?.toLowerCase() || 'idle';
  const reversalProgress = currentEvent?.strategy_kind === 'MACD'
    ? Math.max(0, Math.min(100, Math.round(currentEvent.consensus_pct ?? 0)))
    : selectedAnalytics?.reversal_progress ?? 0;
  const progressLabel = currentEvent?.strategy_kind === 'MACD' ? '多尺度一致' : '反转进度';
  const referenceTime = currentEvent?.event_state === 'CONFIRMED' ? currentEvent.confirm_time : currentEvent?.observed_time;

  return (
    <main className='quant-shell'>
      <header className='topline'>
        <div className='wordmark'><AppMark /><strong>feels-quanty</strong></div>
        <div className='ticker-strip' aria-label='今日标的'>
          {codes.map((code) => <button type='button' className={'ticker-pill ' + (selectedCode === code ? 'active' : '')} key={code} onClick={() => setSelectedCode(code)}><span>{code}</span><b>{quotes[code]?.price != null ? quotes[code].price.toFixed(2) : '--'}</b><em className={(quotes[code]?.pct_change ?? 0) < 0 ? 'negative' : 'positive'}>{quotes[code]?.change ?? ''}</em></button>)}
          <button type='button' className='add-ticker' aria-label='添加 WindCode' onClick={() => setDrawerOpen(true)}><LineIcon name='plus' /><span>{codes.length ? '' : '添加标的'}</span></button>
        </div>
        <div className='top-actions'>
          <span className={'tiny-status ' + statusClass}><i />{monitoring ? 'LIVE' : statusText}</span>
          <span className='clock'>{clock}</span>
          <button type='button' className={'round-action ' + (soundOn ? 'active' : '')} aria-label={soundOn ? '关闭 Windows 提醒' : '开启 Windows 提醒'} aria-pressed={soundOn} onClick={toggleSound}><LineIcon name='bell' /></button>
          <button type='button' className='round-action' aria-label='打开设置' aria-expanded={drawerOpen} onClick={() => setDrawerOpen(true)}><LineIcon name='settings' /></button>
          <button type='button' className={'run-button ' + (monitoring ? 'stop' : '')} onClick={toggleMonitoring}><LineIcon name={monitoring ? 'pause' : 'play'} /><span>{monitoring ? '暂停' : '启动'}</span></button>
        </div>
      </header>

      <section className='canvas'>
        <section className='market'>
          <header className='market-heading'>
            <div className='instrument'>
              <div><span>{selectedCode || '未选择标的'}</span><small>{activeQuote ? 'WindPy · ' + activeQuote.time : 'WindPy'}</small></div>
              <div className='last-price'><strong>{activeQuote ? activeQuote.price.toFixed(2) : '--'}</strong><em className={activeQuote && activeQuote.pct_change < 0 ? 'negative' : 'positive'}>{activeQuote?.change ?? '--'}</em></div>
            </div>
            <div className={'headline-signal ' + decisionStateClass}><i /><div><small>{currentEvent ? currentEvent.strategy_label + ' · ' + eventStateLabel(currentEvent.event_state) : !anyStrategyEnabled ? '未启用策略' : monitoring ? '扫描中' : '未启动'}</small><strong>{decisionTitle}</strong></div><b>{currentEvent ? metricText(currentEvent.confidence, 0) : '--'}</b></div>
          </header>

          <div className='market-grid'>
            <section className='chart-pane' aria-label='分时价格图'>
              <div className='chart-key'><span><i className='key-price' />价格</span><span><i className='key-vwap' />VWAP</span><div className='strategy-live-set'><em className={swingEnabled ? 'on' : ''}>波段</em><em className={macdEnabled ? 'on macd' : 'macd'}>尺度动能</em></div><b>{bars.length ? bars.length + ' 根 30 秒 K' : '等待数据'}</b></div>
              <PriceChart bars={bars} turningEvents={turningEvents} signals={signals} macdAlerts={macdAlerts} code={selectedCode} swingEnabled={swingEnabled} macdEnabled={macdEnabled} />
            </section>

            <aside className={'signal-pane ' + decisionStateClass}>
              <div className='signal-pane-top'><span>{currentEvent ? currentEvent.strategy_label + ' · ' + eventStateLabel(currentEvent.event_state) : '当前'}</span><time>{shortTime(referenceTime || activeQuote?.time)}</time></div>
              <h1>{decisionTitle}</h1>
              <p>{decisionDescription}</p>
              <div className='signal-numbers'>
                <div><span>参考</span><strong>{metricText(decisionPrice)}</strong></div>
                <div><span>极值</span><strong>{metricText(currentEvent?.extreme_price)}</strong></div>
              </div>
              <div className='progress-line'><span>{progressLabel}</span><b>{reversalProgress}%</b><i><em style={{ width: reversalProgress + '%' }} /></i></div>
              <div className='signal-stages' aria-label='信号阶段'>
                {['观察', '增强', '确认'].map((label, index) => <span className={stateRailIndex === index ? 'current' : stateRailIndex > index ? 'done' : ''} key={label}><i />{label}</span>)}
              </div>
              <div className={'decision-call ' + (decisionIsConfirmed ? 'confirmed' : '')}><strong>{decisionIsConfirmed ? currentEvent?.side === 'SELL' ? '卖出建议' : '买入建议' : '继续观察'}</strong><span>{decisionIsConfirmed ? currentEvent?.strategy_kind === 'MACD' ? (currentEvent.scale_label || '自动定级') + ' · 动能已确认' : '策略已确认' : '候选不是操作'}</span></div>
            </aside>
          </div>
        </section>

        <section className='activity' aria-labelledby='activity-title'>
          <header><div><h2 id='activity-title'>事件</h2><span>{activeCandidateCount} 观察 · {confirmedEventCount} 确认</span></div></header>
          <div className='event-list'>
            {visibleEvents.length === 0 && <div className='event-empty'><i />{!anyStrategyEnabled ? '策略已关闭' : !anyStrategyReady && monitoring ? '预热中' : '暂无事件'}</div>}
            {visibleEvents.map((event) => {
              const isConfirmed = event.event_state === 'CONFIRMED';
              const referenceIsConfirm = isConfirmed && event.confirm_price != null;
              const eventPrice = referenceIsConfirm ? event.confirm_price : event.observed_price;
              const eventTime = referenceIsConfirm ? event.confirm_time : event.observed_time;
              const eventClass = isConfirmed ? event.side.toLowerCase() : event.event_state.toLowerCase();
              return <button type='button' className={'event-row ' + eventClass} key={eventIdKey(event)} onClick={() => showNotice((event.code || selectedCode || '当前标的') + ' · ' + event.rationale)}><time>{shortTime(event.updated_time || eventTime)}</time><i className='event-dot' /><div><strong>{eventTitle(event)}<em className={'strategy-tag ' + event.strategy_kind.toLowerCase()}>{event.strategy_label}</em></strong><span>{eventMeta(event, event.code || selectedCode)}</span></div><div className='event-prices'><span>{metricText(event.extreme_price)}</span><i>→</i><b>{metricText(eventPrice)}</b></div><em>{metricText(event.confidence, 0)}</em></button>;
            })}
          </div>
        </section>

        <footer className='quiet-footer'><span className={'connection-line ' + statusClass}><i />{statusText}{backendState?.last_update ? ' · ' + backendState.last_update : ''}</span><span>波段与多尺度动能信号仅作提醒 · 不自动交易</span></footer>
      </section>

      <div className={'settings-layer ' + (drawerOpen ? 'open' : '')} aria-hidden={!drawerOpen}>
        <button type='button' className='settings-backdrop' aria-label='关闭设置' onClick={() => setDrawerOpen(false)} />
        <aside className='settings-sheet' role='dialog' aria-modal='true' aria-labelledby='settings-title'>
          <header className='settings-header'><h2 id='settings-title'>设置</h2><button type='button' aria-label='关闭设置' onClick={() => setDrawerOpen(false)}><LineIcon name='close' /></button></header>
          <div className='settings-scroll'>
            <section className='settings-block'>
              <label className='settings-label'>今日标的</label>
              <div className='ticker-input'><input value={draftCode} onChange={(event) => setDraftCode(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') addCode(); }} placeholder='600519.SH' aria-label='添加 WindCode' /><button type='button' onClick={addCode}>添加</button></div>
              <div className='ticker-editor'>{codes.map((code) => <button type='button' className={selectedCode === code ? 'active' : ''} key={code} onClick={() => setSelectedCode(code)}><span>{code}</span><b aria-label={'删除 ' + code} onClick={(event) => { event.stopPropagation(); removeCode(code); }}>×</b></button>)}</div>
            </section>

            <section className='settings-block'>
              <div className='strategy-setting-head'><label className='settings-label'>运行策略</label><span>{swingEnabled && macdEnabled ? '双策略' : swingEnabled ? '分时波段' : macdEnabled ? '多尺度动能' : '仅行情'}</span></div>
              <div className='strategy-switches'>
                <button type='button' aria-pressed={swingEnabled} className={swingEnabled ? 'active' : ''} onClick={() => toggleStrategy('swing_strategy_enabled', '分时波段')}><i className='strategy-symbol swing'>S</i><span><strong>分时波段</strong><small>价格结构与反转</small></span><em /></button>
                <button type='button' aria-pressed={macdEnabled} className={macdEnabled ? 'active' : ''} onClick={() => toggleStrategy('macd_strategy_enabled', '多尺度动能')}><i className='strategy-symbol macd'>M</i><span><strong>多尺度动能</strong><small>自动定级 · MACD-V</small></span><em /></button>
              </div>
            </section>

            <section className='settings-block'>
              <label className='settings-label'>模式</label>
              <div className='mode-switch' aria-label='策略灵敏度'>{(['sensitive', 'standard', 'robust'] as const).map((mode) => <button type='button' className={rule.sensitivity === mode ? 'active' : ''} key={mode} onClick={() => applySensitivity(mode)}>{mode === 'sensitive' ? '灵敏' : mode === 'robust' ? '稳健' : '标准'}</button>)}</div>
            </section>

            <section className='toggle-list'>
              <button type='button' className='setting-toggle' aria-pressed={rule.opening_fast_enabled} onClick={() => setRule({ ...rule, opening_fast_enabled: !rule.opening_fast_enabled })}><span>开盘快速识别</span><i className={rule.opening_fast_enabled ? 'on' : ''} /></button>
              <button type='button' className='setting-toggle' aria-pressed={rule.candidate_alerts_enabled} onClick={() => setRule({ ...rule, candidate_alerts_enabled: !rule.candidate_alerts_enabled })}><span>波段候选事件</span><i className={rule.candidate_alerts_enabled ? 'on' : ''} /></button>
              <button type='button' className='setting-toggle' aria-pressed={soundOn} onClick={toggleSound}><span>Windows 提醒</span><i className={soundOn ? 'on' : ''} /></button>
              <button type='button' className='setting-toggle' aria-pressed={rule.candidate_notifications_enabled} disabled={!soundOn} onClick={() => setRule({ ...rule, candidate_notifications_enabled: !rule.candidate_notifications_enabled })}><span>波段候选弹窗</span><i className={rule.candidate_notifications_enabled && soundOn ? 'on' : ''} /></button>
            </section>

            <details className='parameter-details'>
              <summary><span>高级参数</span><b>V4.0</b></summary>
              <div className='parameter-groups'>
                <section><h3>常规</h3><div className='parameter-grid'>
                  <label><span>波段幅度 %</span><input type='number' min='0.05' max='5' step='0.05' value={rule.min_swing_pct} onChange={(event) => setRule({ ...rule, min_swing_pct: Number(event.target.value) })} /></label>
                  <label><span>波动倍数</span><input type='number' min='0.1' max='5' step='0.05' value={rule.min_swing_range_mult} onChange={(event) => setRule({ ...rule, min_swing_range_mult: Number(event.target.value) })} /></label>
                  <label><span>反转幅度 %</span><input type='number' min='0.05' max='3' step='0.01' value={rule.reversal_pct} onChange={(event) => setRule({ ...rule, reversal_pct: Number(event.target.value) })} /></label>
                  <label><span>反转倍数</span><input type='number' min='0.1' max='3' step='0.05' value={rule.reversal_range_mult} onChange={(event) => setRule({ ...rule, reversal_range_mult: Number(event.target.value) })} /></label>
                  <label><span>最少 K 线</span><input type='number' min='2' max='20' step='1' value={rule.min_leg_bars} onChange={(event) => setRule({ ...rule, min_leg_bars: Number(event.target.value) })} /></label>
                  <label><span>确认分</span><input type='number' min='50' max='100' step='1' value={rule.min_confidence} onChange={(event) => setRule({ ...rule, min_confidence: Number(event.target.value) })} /></label>
                  <label><span>预热 K 线</span><input type='number' min='4' max='30' step='1' value={rule.warmup_bars} onChange={(event) => setRule({ ...rule, warmup_bars: Number(event.target.value) })} /></label>
                  <label><span>开盘保护</span><input type='number' min='0' max='30' step='1' value={rule.opening_guard_minutes} onChange={(event) => setRule({ ...rule, opening_guard_minutes: Number(event.target.value) })} /></label>
                  <label><span>冷却秒数</span><input type='number' min='0' max='3600' step='10' value={rule.cooldown_seconds} onChange={(event) => setRule({ ...rule, cooldown_seconds: Number(event.target.value) })} /></label>
                </div></section>
                <section><h3>开盘</h3><div className='parameter-grid'>
                  <label><span>窗口分钟</span><input type='number' min='1' max='30' step='1' value={rule.opening_fast_window_minutes} onChange={(event) => setRule({ ...rule, opening_fast_window_minutes: Number(event.target.value) })} /></label>
                  <label><span>最少 K 线</span><input type='number' min='1' max='5' step='1' value={rule.opening_fast_min_bars} onChange={(event) => setRule({ ...rule, opening_fast_min_bars: Number(event.target.value) })} /></label>
                  <label><span>跳空 %</span><input type='number' min='0.1' max='10' step='0.05' value={rule.opening_fast_gap_pct} onChange={(event) => setRule({ ...rule, opening_fast_gap_pct: Number(event.target.value) })} /></label>
                  <label><span>波段 %</span><input type='number' min='0.1' max='10' step='0.05' value={rule.opening_fast_min_swing_pct} onChange={(event) => setRule({ ...rule, opening_fast_min_swing_pct: Number(event.target.value) })} /></label>
                  <label><span>波动倍数</span><input type='number' min='0.1' max='10' step='0.05' value={rule.opening_fast_swing_range_mult} onChange={(event) => setRule({ ...rule, opening_fast_swing_range_mult: Number(event.target.value) })} /></label>
                  <label><span>反转 %</span><input type='number' min='0.05' max='5' step='0.05' value={rule.opening_fast_reversal_pct} onChange={(event) => setRule({ ...rule, opening_fast_reversal_pct: Number(event.target.value) })} /></label>
                  <label><span>反转倍数</span><input type='number' min='0.1' max='5' step='0.05' value={rule.opening_fast_reversal_range_mult} onChange={(event) => setRule({ ...rule, opening_fast_reversal_range_mult: Number(event.target.value) })} /></label>
                  <label><span>确认分</span><input type='number' min='50' max='100' step='1' value={rule.opening_fast_min_confidence} onChange={(event) => setRule({ ...rule, opening_fast_min_confidence: Number(event.target.value) })} /></label>
                </div></section>
                <section><h3>候选</h3><div className='parameter-grid'>
                  <label><span>候选分</span><input type='number' min='50' max='90' step='1' value={rule.candidate_min_confidence} onChange={(event) => setRule({ ...rule, candidate_min_confidence: Number(event.target.value) })} /></label>
                  <label><span>增强分</span><input type='number' min='55' max='95' step='1' value={rule.candidate_strengthening_confidence} onChange={(event) => setRule({ ...rule, candidate_strengthening_confidence: Number(event.target.value) })} /></label>
                  <label><span>候选反转</span><input type='number' min='0.10' max='0.90' step='0.01' value={rule.candidate_reversal_fraction} onChange={(event) => setRule({ ...rule, candidate_reversal_fraction: Number(event.target.value) })} /></label>
                  <label><span>增强反转</span><input type='number' min='0.20' max='1.00' step='0.01' value={rule.candidate_strengthening_reversal_fraction} onChange={(event) => setRule({ ...rule, candidate_strengthening_reversal_fraction: Number(event.target.value) })} /></label>
                  <label><span>有效 K 线</span><input type='number' min='3' max='60' step='1' value={rule.candidate_ttl_bars} onChange={(event) => setRule({ ...rule, candidate_ttl_bars: Number(event.target.value) })} /></label>
                  <label><span>开盘最少 K 线</span><input type='number' min='1' max='5' step='1' value={rule.opening_candidate_min_bars} onChange={(event) => setRule({ ...rule, opening_candidate_min_bars: Number(event.target.value) })} /></label>
                </div></section>
              </div>
            </details>

            <details className='connection-details'><summary>连接</summary><dl><div><dt>WindPy</dt><dd>{backendState?.windpy_available ? '可用' : '未连接'}</dd></div><div><dt>行情</dt><dd>{connected ? '已连接' : '未连接'}</dd></div><div><dt>更新</dt><dd>{backendState?.last_update || '--'}</dd></div><div><dt>错误</dt><dd>{backendState?.last_error || backendError || '无'}</dd></div></dl></details>
          </div>
          <footer className='settings-actions'><button type='button' className='test-button' onClick={testNotification}>测试提醒</button><button type='button' className='save-button' onClick={() => { saveRule(); setDrawerOpen(false); }}>保存</button></footer>
        </aside>
      </div>
      {notice && <div className='toast' role='status'>{notice}</div>}
    </main>
  );
}
