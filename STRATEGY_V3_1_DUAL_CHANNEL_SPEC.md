# 分时波段顶底策略 V3.1：双通道方案（冻结施工规格）

## 1. 目标

在保留 V3 因果、非重绘分时顶底逻辑的前提下，解决两个盲区：

1. 早盘前 5 分钟出现明显冲高回落或杀跌回收时，不必等到 09:36 才提醒；
2. 盘中后端重启或新增 WindCode 时，不必重新空等 6 分钟。

仍然只提醒、不自动交易；30 秒 K 线只用于图表，所有信号继续在完整 60 秒 K 线收盘后确认。

## 2. 双通道总览

### 2.1 通道 A：开盘强信号 OPENING_FAST

- 只在上午开盘后的前 5 个完整分钟内工作，即决策 K 起点 `09:30:00 <= t < 09:35:00`。
- 至少积累 2 根完整 60 秒 K，最早确认时间为 09:32。
- 每个 WindCode 每个自然日最多发 1 次开盘强信号。
- 识别两种形态：
  - `GAP_REJECTION`：高开冲高回落 SELL / 低开杀跌回收 BUY；
  - `IMPULSE_REVERSAL`：无明显跳空，但开盘短时单向脉冲后强反转。
- 单纯高开、低开、单边上涨或单边下跌均不得触发。
- 快通道信号必须更新同一套波段状态，常规通道不得随后重复发出同方向信号。

### 2.2 通道 B：常规波段 REGULAR

- 保持当前 V3 Directional Change 状态机。
- 默认 `warmup_bars=6`、`opening_guard_minutes=5`。
- 第一根可发常规信号的决策 K 起点为 09:35，确认时间约 09:36。
- 继续使用灵敏 / 标准 / 稳健三档及自然方向交替。

### 2.3 仲裁规则

- 09:30–09:35：常规状态机继续积累锚点和候选峰谷，但只有快通道可以发信号。
- 快通道一旦触发，写入 `last_signal_side`、`last_signal_at` 并切换为对应反向跟踪状态。
- 09:35 后快通道关闭，常规通道接管。
- 两通道共享同一状态、同一去重和冷却约束，禁止各自独立产生重复信号。

## 3. 开盘快通道硬门槛

默认配置：

```text
opening_fast_enabled = true
opening_fast_window_minutes = 5
opening_fast_min_bars = 2
opening_fast_gap_pct = 1.00
opening_fast_min_swing_pct = 0.80
opening_fast_swing_range_mult = 1.80
opening_fast_reversal_pct = 0.35
opening_fast_reversal_range_mult = 0.70
opening_fast_min_confidence = 85
```

开盘快通道参数不随“灵敏”预设自动降低，避免开盘噪声放大；可在高级参数中手工调整，但必须经过后端边界归一化。

### 3.1 自适应阈值

```text
fast_swing_abs = max(reference_price * opening_fast_min_swing_pct / 100,
                     robust_range * opening_fast_swing_range_mult)

fast_reversal_abs = max(extreme_price * opening_fast_reversal_pct / 100,
                        robust_range * opening_fast_reversal_range_mult)
```

`reference_price` 优先使用昨收；昨收缺失时使用首根分钟 K 的开盘价。昨收缺失时禁用 GAP_REJECTION，但 IMPULSE_REVERSAL 仍可工作。

### 3.2 SELL：开盘分时顶

必须同时满足：

1. 至少 2 根完整分钟 K；
2. 上下文满足其一：
   - 首开相对昨收高开达到 `opening_fast_gap_pct`；或
   - 首开/此前低点到候选峰值的上行幅度达到 `fast_swing_abs`；
3. 候选峰值到当前收盘回撤达到 `fast_reversal_abs`；
4. 当前收盘严格低于前一根完整分钟 K 的最低价（结构破位，硬门槛）；
5. 置信分达到 `opening_fast_min_confidence`。

### 3.3 BUY：开盘分时底

完全对称：

1. 至少 2 根完整分钟 K；
2. 低开达到跳空门槛，或首开/此前高点到候选谷值的下行幅度达到 `fast_swing_abs`；
3. 当前收盘从候选谷值反弹达到 `fast_reversal_abs`；
4. 当前收盘严格高于前一根完整分钟 K 的最高价；
5. 置信分达到快通道门槛。

### 3.4 快通道评分

硬门槛全部通过后从 65 分起：

- 跳空方向与反转方向一致：+10；
- 候选极值 K 出现明显上影/下影或收盘落在反向 35% 区域：+10；
- 实际反转达到阈值 1.35 倍：+5；
- 实际波段达到阈值 1.25 倍：+5；
- 极值后第二根连续反向收盘或更强结构破位：+5；
- 最高 100，默认至少 85 才提醒。

量能不作为开盘快通道硬门槛，因为前两分钟样本不足且开盘量天然偏高。

## 4. 数据字段与传播

实时链路必须把 `pre_close` 从 WindPy quote 依次传入：

```text
wsq quote -> MicroBarAggregator -> 30s completed bar
          -> DecisionBarAggregator -> 60s decision bar -> SwingV3Engine
```

保留 `first_open`、`pre_close`、`opening_gap_pct` 于当日每代码状态。

不得把昨收至今开盘的跳空幅度直接当成普通日内波段；它只能作为快通道 GAP_REJECTION 的上下文。

## 5. 盘中重启 / 新增代码回填

### 5.1 已验证的本机 WindPy 调用

本机实测可用：

```python
w.wsi(
    code,
    "open,high,low,close,volume,amt",
    begin_time,
    latest_completed_minute,
    "BarSize=1"
)
```

返回字段规范化为 `open/high/low/close/volume/amount`，`Times` 是分钟 K 起点。

### 5.2 回填规则

- WindPy 连接成功后、开始实时推进前，每个代码每个自然日最多回填一次。
- 仅在已有至少 1 根完整历史分钟 K 时回填。
- 结束时间只能是“当前时刻之前最新完成的分钟”，禁止将未完成分钟送入引擎。
- 可以查询当日 09:30 至当前，午休或超过 120 秒的断档继续由引擎原有逻辑重置状态。
- 回填 K 只送入 `SwingV3Engine` 预热状态，不伪造成 30 秒 K，不写入图表。
- 回放期间产生的历史信号用于推进内部方向状态，但：
  - 不插入前端信号流；
  - 不发送 Windows Toast；
  - 不计入本次运行的信号数量。
- 回填失败不得导致监控失败；记录 `backfill_status=failed` 和原因，然后退化为实时预热。
- 新增 WindCode 且监控已运行时，也执行一次相同回填。

## 6. 配置与契约

### 6.1 config 新增字段

- `opening_fast_enabled`
- `opening_fast_window_minutes`
- `opening_fast_min_bars`
- `opening_fast_gap_pct`
- `opening_fast_min_swing_pct`
- `opening_fast_swing_range_mult`
- `opening_fast_reversal_pct`
- `opening_fast_reversal_range_mult`
- `opening_fast_min_confidence`

所有字段必须有 Python 2.7 兼容的默认值、类型转换和上下界。

### 6.2 signal 新增字段

每个信号新增：

- `channel = OPENING_FAST | REGULAR`
- `channel_label = 开盘强信号 | 常规波段`
- `pattern = GAP_REJECTION | IMPULSE_REVERSAL | DIRECTIONAL_CHANGE`
- `first_open`
- `pre_close`
- `opening_gap_pct`

现有 `extreme_*`、`confirm_*`、`lag_bars`、`side` 等字段不变。

### 6.3 analytics 新增字段

- `active_channel`
- `active_channel_label`
- `opening_fast_enabled`
- `opening_fast_active`
- `opening_fast_bars`
- `opening_fast_min_bars`
- `opening_fast_status`
- `regular_ready`
- `regular_warmup_progress`
- `backfill_status`

## 7. 前端

- 规则区新增“开盘强信号通道”开关，默认开启。
- 主配置直接展示：
  - 最早确认：2 分钟；
  - 有效窗口：开盘前 5 分钟；
  - 强波段 0.80%；
  - 强反转 0.35%；
  - 最低 85 分。
- 其余快通道参数放入高级设置。
- 状态卡明确显示当前阶段：
  - “开盘强信号观察（2/2）”
  - “标准波段预热（4/6）”
  - “常规波段追踪”
  - “盘中历史已回填”
- 信号卡显示“开盘强信号”或“常规波段”徽标和具体 pattern。
- 页面说明必须写明：最早 09:32 确认，不是最高/最低价即时预测。

## 8. 必须新增的确定性测试

1. 两根分钟 K 形成高开冲高回落，09:32 产生唯一 SELL；
2. 两根分钟 K 形成低开杀跌回收，09:32 产生唯一 BUY；
3. 高开后继续上涨，不发 SELL；
4. 低开后继续下跌，不发 BUY；
5. 小幅开盘噪声无信号；
6. 无昨收时禁用 GAP_REJECTION，但强脉冲反转仍可触发；
7. 快通道每天每代码最多一个信号；
8. 快通道 SELL 后常规通道不得重复 SELL，必须先有 BUY；
9. 09:35 后快通道关闭；
10. 原 301377.SZ 11:14/11:15 回放结果保持不变且标记为 REGULAR；
11. pre_close 从 quote 贯穿到决策 K；
12. WSI 解析字段顺序变化仍正确；
13. WSI 丢字段、ErrorCode 非 0、空数据时安全退化；
14. 回填不发送 Toast、不写历史信号流，但引擎完成预热；
15. 回填剔除当前未完成分钟；
16. Python 2.7 编译、前端契约、hydration-safe 时钟、Windows Toast 均保持通过。

## 9. 验收命令与运行态

必须通过：

```powershell
C:\Python27\python.exe -m py_compile backend\server.py backend\swing_v3.py
C:\Python27\python.exe backend\test_swing_v3.py
C:\Python27\python.exe backend\test_signal_engine.py
npm run lint
npm test
git diff --check
```

完成后由主代理精确重启 3001/8765 项目进程，恢复现有 WindCode、监控开启和通知配置，再验证：

- `/api/state` 为 V3.1 双通道配置；
- WindPy connected；
- signals 不混入回填历史；
- Windows 测试提醒成功；
- localhost:3001 返回 200；
- 不修改代理、路由、防火墙或任何公司内网设置。
