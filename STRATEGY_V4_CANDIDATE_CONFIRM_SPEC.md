# 分时顶底策略 V4 候选/确认双层规格

## 1. 目标与兼容边界

V4.0 在现有 V3.1 双通道基础上增加“候选高召回、确认高精度”的转折事件层。输入仍必须是因完整两根 30 秒微型K合成的完整 60 秒决策K；事件和确认只能使用当前决策K及其之前的数据，禁止使用未来K线或回看修正。

现有接口保持不变：

```python
analytics, confirmed_signal = engine.process(code, bar, config)
```

`confirmed_signal` 仍只在原确认硬门槛全部通过时返回；服务端 `state.signals` 仍只保存确认信号。事件更新通过 `engine.drain_event_updates(code)` 读取并清空，未消费队列按代码有界保存。

## 2. 配置规范化

默认值和归一化范围如下：

| 配置 | 默认值 | 归一化范围/规则 |
| --- | ---: | --- |
| `candidate_alerts_enabled` | `true` | Boolean |
| `candidate_notifications_enabled` | `true` | Boolean |
| `candidate_min_confidence` | `55` | 整数 `50..90` |
| `candidate_strengthening_confidence` | `70` | 整数 `55..95`，归一化后不低于 `candidate_min_confidence` |
| `candidate_reversal_fraction` | `0.35` | `0.10..0.90` |
| `candidate_strengthening_reversal_fraction` | `0.55` | `0.20..1.00`，归一化后不低于 `candidate_reversal_fraction` |
| `candidate_ttl_bars` | `15` | 整数 `3..60` |
| `opening_candidate_min_bars` | `1` | 整数 `1..5` |

`strategy_version` 固定为 `V4.0`，`rule_name` 固定为 `分时顶底策略 V4 候选/确认双层`。原有 V3.1 配置、确认参数、开盘快速通道参数和 legacy 信号字段继续保留。

## 3. 事件状态与字段

状态迁移：

```text
CANDIDATE -> STRENGTHENING -> CONFIRMED
       \-> INVALIDATED
```

创新更高的顶或更低的底时，沿用同一个 `event_id`，`revision` 递增并更新极值字段；若此前为 `STRENGTHENING`，创新极值后重置为 `CANDIDATE`。不会为同一极值创建第二个候选，也不会重复发送候选通知。TTL、午休、跨日或超过 120 秒断档会把活动候选置为 `INVALIDATED`，并在 `reason` 中记录原因；失效后的同一极值不得立即重建，必须先出现新的更高/更低极值。

`active_turn_events[side]` 和 analytics 的 `active_turn_event` 只表示尚未确认的活动候选。候选升级为 `CONFIRMED` 或直接确认时，确认副本仍进入事件更新队列并保存到 `last_turn_event`，但立即从该方向的活动候选中清除；`active_turn_event` 随后指向另一方向仍在活动的候选，或为 `null`。

每个事件至少包含：

```text
event_id, revision, event_state, signal_level, side, turning_point,
created_time, created_timestamp, updated_time, updated_timestamp,
extreme_price, extreme_time, extreme_timestamp,
observed_price, observed_time, observed_timestamp,
confirm_price, confirm_time, confirm_timestamp,
confidence, confirmations, rationale,
channel, channel_label, pattern, notification_kind, strategy_version
```

`signal_level` 只能是 `CANDIDATE` 或 `CONFIRMED`；失效事件保留 `signal_level=CANDIDATE` 并使用 `event_state=INVALIDATED`。候选的 `pattern` 固定为 `EARLY_REVERSAL_WATCH`；确认后为现有 `GAP_REJECTION`、`IMPULSE_REVERSAL` 或 `DIRECTIONAL_CHANGE`。未确认时确认字段为 `null`。确认 legacy signal 必须带相同的 `event_id`、`revision`、`event_state=CONFIRMED`、`signal_level=CONFIRMED`。

## 4. 常规候选规则

常规候选只在 `TRACKING_UP` / `TRACKING_DOWN` 且当前交易时段可提醒时判断。波段必须同时达到现有自适应 `min_swing` 和 `min_leg_bars`；仅因波段足够大、单边上涨/下跌或平坦噪声不得建候选。

五类早期证据为：

1. 极值K拒绝形态；
2. 当前收盘相对上一分钟收盘反向；
3. 从极值的反转进度达到 `candidate_reversal_fraction`；
4. 结构突破上一分钟低点/高点；
5. 极值或当前量比至少 `1.2`。

候选必须至少具备前 3 类中的一类（拒绝、反向收盘动量、反转进度）。候选分数固定为：

```text
40 基础
+10 波段和完整K根数达标
+15 拒绝形态
+10 反向收盘动量
+10 反转进度
+10 结构突破
+ 5 量能
```

分数封顶 100，达到 `candidate_min_confidence` 才创建候选。达到 `candidate_strengthening_confidence`、反转进度达到 `candidate_strengthening_reversal_fraction` 且五类证据至少两类时进入 `STRENGTHENING`。原确认硬门槛和 `min_confidence` 不变；候选不得绕过确认门槛直接产生 legacy signal。

候选从最近极值起达到 `candidate_ttl_bars` 根完整 60 秒K仍未确认即失效。事件更新由 `drain_event_updates(code)` 取得后清空；引擎未消费队列最多保留 200 条，服务端 `turning_events` 按 `event_id` upsert、最新在前且最多 100 条。

## 5. 开盘候选与快速确认

开盘候选仍只使用完整 60 秒K。存在昨收且跳空方向满足条件时，最早 1 根完整K（约 09:31 可见）即可候选；没有昨收时，脉冲候选至少需要 2 根完整K。上下文必须满足跳空方向，或 prior impulse 至少为 `0.65 * opening_fast swing threshold`。

此外至少需要拒绝形态、反向收盘动量、或从极值反转达到 `0.35 * opening fast reversal threshold` 中的一项。单纯高开继续上涨或低开继续下跌不产生候选。每个方向最多保留一个活动开盘候选；每天最多一个开盘确认的既有规则保持不变。

候选可被现有从 09:32 起生效的 `OPENING_FAST` 确认升级为同一 `event_id`。若确认直接发生而没有候选，则创建直接 `CONFIRMED` 事件。

开盘候选是旁路观察层：候选阶段只能创建或更新事件，绝不能调用 `_set_fast_tracking_state` 或改写 legacy 的 `phase`、`candidate_*`、`leg_start_*`。只有 `_process_opening_fast` 的原确认硬门槛通过后，才允许写入这些 legacy 波段状态。候选开关只能改变事件更新，不能改变同一组开盘K的 legacy 状态或最终确认核心字段。

## 6. 服务端与通知语义

`SharedState` 新增 `turning_events` 数组并在 `/api/state` snapshot 返回；`signals` 只返回确认信号。实时处理每根 decision bar 后调用 `drain_event_updates`，按 `event_id` upsert。若同一事件同一根K同时产生候选和确认，只保留最终 `CONFIRMED` 通知。

- 候选：仅首次创建，且 `candidate_notifications_enabled`、`candidate_alerts_enabled`、`notifications_enabled` 同时为真时通知；使用较弱、较短的 `Info` 提示。
- `STRENGTHENING`、极值更新、`INVALIDATED`：不弹窗。
- 确认：按原 `notifications_enabled` 规则通知；使用更明显、更长的 `Warning` 提示。
- `send_notification(title, message)` 旧两参数调用继续有效，也可传第三参数 `Candidate` 或 `Confirmed`。
- 回填逐根 drain 并丢弃事件更新，不写 `turning_events`、不 Toast，不影响历史K对引擎预热；`discard_event_state` 后 analytics 的 `active_turn_event` 必须为 `null`。

## 7. 因果边界

决策K只有在两个 30 秒微型K均已完成后才进入引擎。当前K可使用其 OHLC、成交量、时间、上一根完整K和此前已保存的波段结构；任何尚未完成的微型K、未来K或未来极值均不得参与候选、强化或确认。事件的 `created_time`/`created_timestamp`、`observed_time`/`observed_timestamp` 和每次更新的 `updated_time`/`updated_timestamp` 必须使用当前完整K的 `bar.confirm_time`/`bar.confirm_timestamp`；只有 `extreme_time`/`extreme_timestamp` 表示极值K的起点。因此首根 09:30 K 的候选最早只能在 09:31 的确认时间显示为已知，不能声称 09:30 已知。

跨日、午休和超过 120 秒数据断档在结构重置前先失效活动候选；结构重置同时清空 `invalidated_extremes`。该映射只在同一连续结构内用于阻止 TTL 失效后的同一极值立即重建，不能跨午休、跨日或断档封锁新的结构。

## 8. 验收命令

在项目根目录 `D:\shpan\YUN\股票\量化` 执行：

```powershell
C:\Python27\python.exe -m py_compile backend\server.py backend\swing_v3.py
C:\Python27\python.exe backend\test_swing_v3.py
C:\Python27\python.exe backend\test_signal_engine.py
```

验收应覆盖：常规候选无 legacy signal、创新极值同事件且候选通知不重复、`STRENGTHENING`、同事件确认、TTL 失效和新极值重建、单边/平坦无候选、开盘首分钟跳空拒绝、09:32 同事件确认、回填隔离及服务端同K只通知确认。
