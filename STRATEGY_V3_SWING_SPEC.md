# 分时波段顶底策略 V3（因果、非重绘）

## 1. 目标与边界

V3 的目标不是高频择时，也不是寻找任意多因子事件，而是识别一段分时上涨或下跌结束后的局部波峰/波谷：

- 上涨波段结束并转弱时发出 `SELL`；
- 下跌波段结束并转强时发出 `BUY`；
- 每个完整波段最多一个信号，信号方向必须自然交替；
- 只使用信号发生时已经收到的数据，禁止 ZigZag/分形式未来函数或事后重绘；
- 系统无法在最高价出现的同一瞬间知道它就是顶。图上可以把已确认的顶标在真实峰值处，但必须同时保留确认时间，Windows 提醒只能在确认发生时发送。

本策略仍然只提醒、不自动交易，也不声称能捕捉绝对最高点或最低点。

## 2. 数据层

- 继续使用 WindPy `wsq` 约每 1 秒轮询实时快照并去重。
- 保留现有 30 秒微 K，供图表展示和数据质量检查。
- 新增 60 秒决策 K，由 30 秒微 K 聚合，信号引擎只在 60 秒决策 K 完成后推进一次。
- 60 秒决策 K 字段：`open/high/low/close/vwap/volume/amount/pct_change/time/timestamp`。
- 累计成交量/成交额必须继续按非负增量处理。
- 跨自然日、跨午休、数据间隔超过 120 秒时重置未完成波段，不得把断裂两侧拼成一个波段。
- 开盘保护默认 5 分钟；集合竞价、午休、收盘后不发信号。

## 3. 核心算法：自适应 Directional Change 状态机

每个 WindCode 独立维护以下状态：

- `BOOTSTRAP`：尚未形成可识别波段；
- `TRACKING_UP`：上涨波段，持续更新候选峰值；
- `TRACKING_DOWN`：下跌波段，持续更新候选谷值。

### 3.1 波段启动

从锚点向上或向下的幅度达到“最小波段阈值”后进入对应状态。

最小波段阈值采用价格与波动率的较大者：

```text
min_swing_abs = max(anchor_price * min_swing_pct / 100,
                    robust_range * min_swing_range_mult)
```

其中 `robust_range` 为最近最多 10 根已完成 60 秒 K 的 True Range 中位数；样本不足时可用已有 K，但至少需要 6 根决策 K。

标准档默认：

- `min_swing_pct = 0.45`
- `min_swing_range_mult = 1.20`
- `min_leg_bars = 3`

### 3.2 候选顶与 SELL 确认

处于 `TRACKING_UP` 时：

1. 每根决策 K 用其 `high` 更新候选峰值和峰值时间；
2. 计算当前 `close` 相对候选峰值的回撤；
3. 回撤阈值采用固定百分比与波动率的较大者：

```text
reversal_abs = max(peak_price * reversal_pct / 100,
                   robust_range * reversal_range_mult)
```

标准档默认：

- `reversal_pct = 0.28`
- `reversal_range_mult = 0.45`

满足以下硬门槛后才可确认顶：

- 上涨波段幅度达到 `min_swing_abs`；
- 波段持续至少 `min_leg_bars`；
- 从候选峰值到当前收盘的回撤达到 `reversal_abs`；
- 当前收盘低于候选峰值所在 K 的收盘，且短线动量已经转负。

再按以下证据评分：

- 波段成熟度与幅度：25 分；
- 回撤达到自适应阈值：30 分；
- 峰值 K 上影/收盘位置体现冲高回落：15 分；
- 跌破前一根决策 K 的低点或短线结构位：15 分；
- 正动量衰减并转负：10 分；
- 峰值或反转 K 的量能达到近 10 根中位数 1.2 倍：5 分（仅加分，不作硬门槛）。

默认 `min_confidence = 70`。通过后发出一个 `SELL`，把状态切换为 `TRACKING_DOWN`，不得在下一个已确认底之前重复发 SELL。

### 3.3 候选底与 BUY 确认

完全对称：持续更新候选最低价；价格从候选谷值反弹达到自适应阈值，且波段成熟、动量转正并达到置信门槛后发 `BUY`，随后切换到 `TRACKING_UP`。

## 4. 灵敏度预设

前端默认只暴露易理解的灵敏度预设，同时提供高级参数展开区。

| 参数 | 灵敏 | 标准（默认） | 稳健 |
|---|---:|---:|---:|
| `min_swing_pct` | 0.30 | 0.45 | 0.65 |
| `min_swing_range_mult` | 0.90 | 1.20 | 1.50 |
| `reversal_pct` | 0.20 | 0.28 | 0.38 |
| `reversal_range_mult` | 0.35 | 0.45 | 0.60 |
| `min_leg_bars` | 2 | 3 | 4 |
| `min_confidence` | 65 | 70 | 78 |

`cooldown_seconds = 120` 只作为额外保险；主要去重由波段状态自然交替完成。

## 5. 信号与分析契约

每个信号必须包含：

- `strategy_version = "V3"`
- `turning_point = "TOP" | "BOTTOM"`
- `side = "SELL" | "BUY"`
- `extreme_price`、`extreme_time`、`extreme_timestamp`
- `confirm_price`、`confirm_time`、`confirm_timestamp`
- `lag_bars`
- `swing_pct`、`reversal_pct_actual`、`reversal_threshold_pct`
- `confidence`、`confirmations`、`rationale`
- 保留兼容字段 `price/time/timestamp/change/source/strategy`

每个标的的 `analytics` 必须包含：

- `ready`、`decision_bars`、`warmup_target`
- `phase`、`phase_label`
- `candidate_type`、`candidate_price`、`candidate_time`
- `leg_start_price`、`leg_amplitude_pct`
- `reversal_threshold_pct`、`reversal_progress`
- `robust_range`、`blocked_reasons`、`last_updated`

## 6. 前端效果

- 页面主标题与说明改为“分时波段顶底 V3”，不再强调通用多因子或四类交易模块。
- 参数区显示“灵敏 / 标准 / 稳健”预设，默认标准；高级区可调最小波段、反转确认、最短波段和置信度。
- 每个标的状态卡显示“寻找波段 / 跟踪上涨候选顶 / 跟踪下跌候选底”、候选价、波段幅度与反转确认进度。
- 图表在 `extreme_timestamp` 处画明显红色向下箭头或绿色向上箭头；在 `confirm_timestamp` 处画较小确认点，并用细线连接。
- 文案必须明确：例如“11:14 峰值 459.00，于 11:15 确认为顶；确认价 455.99，回撤 0.66%”。不得把确认时间隐藏，造成最高点即时预测的假象。
- 信号流展示“分时顶 / 分时底”、峰谷价格、确认延迟、波段幅度、实际回撤和确认依据。
- 保留 Windows Toast、WindPy 状态、关注列表、hydration-safe 时钟和 localhost 接入。

## 7. 截图真实片段回放验收

必须把 `301377.SZ` 以下片段固化为确定性测试（可按 60 秒聚合）：

- 11:09:30：高 457.49，低 456.24，收 456.59
- 11:10:00～11:12:59：先回落到 454.78，随后上行至 457.89
- 11:13:00～11:13:59：最高 458.99，收 458.99
- 11:14:00～11:14:59：最高 459.00，最低/收盘约 455.99
- 随后继续回落

标准档期望：

- 产生且只产生一个 `SELL`；
- `extreme_price = 459.00`；
- `extreme_time` 落在 11:14；
- `confirm_time` 不晚于 11:15:00 对应的首个可用确认时点；
- 不得等到 11:19、价格 452.19 才触发；
- 信号标记落在峰值处，但提醒时间保留在确认时点。

另需覆盖：平坦噪声无信号、持续单边上涨不提前猜顶、顶部确认、底部确认、同向不重复、信号自然交替、断档重置、跨日重置、午休阻断、灵敏度预设差异、无未来数据/无重绘。

## 8. 兼容、验证与禁止项

- 继续兼容 Python 2.7，不新增第三方 Python 依赖。
- 保留 `/api/health`、`/api/state`、`/api/watchlist`、`/api/config`、`/api/monitor`、`/api/notify/test`。
- 保留中文路径 Windows Toast 修复、`127.0.0.1:8765` 绑定、一键启动脚本。
- 不得修改系统代理、路由、防火墙或公司内网设置；不得部署外网；不得伪造行情或示例信号。
- V2 信号历史不应混入 V3；后端重启后重新预热。
- 完成后运行 Python 2.7 编译、全部后端回放测试、`npm test`、`npm run lint`、`git diff --check`。
