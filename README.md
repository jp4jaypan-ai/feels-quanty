# feels-quanty

本地只读盯盘工具：使用 WindPy 实时行情识别分时波段顶/底，发送 Windows 提醒，不自动下单。

## Prerequisites

- Node.js `>=22.13.0`

## 一键启动

1. 登录并保持 Wind 金融终端运行。
2. 双击 `start_quant_assistant.bat`。
3. 脚本会启动 WindPy 后端和前端，并自动打开 `http://localhost:3001`。
4. 在启动窗口按 `Ctrl+C` 可停止由脚本启动的服务。

运行环境要求 Node.js `>=22.13.0`，WindPy Python 位于 `C:\Python27\python.exe`。运行日志写入 `work/`。

## 策略如何工作

- WindPy 约每秒读取一次实时快照并去重。
- 30 秒聚合 K 线仅用于分时图展示；完整的 60 秒 K 线用于策略决策。
- 开盘强信号通道只在 09:30–09:35 工作，至少两根完整 60 秒 K 后确认，最早 09:32；必须同时满足强波段、强反转和结构破位。单纯高开、低开或单边行情不触发，每代码每天最多一次。
- 常规波段通道继续积累同一套状态，09:35 后接管；两通道共享去重、冷却和自然方向交替。
- 引擎持续跟踪候选峰值/谷值；只有波段幅度、反转幅度和置信分达到门槛才提醒。
- 图上大箭头标记实际峰谷，小圆点标记系统确认时刻。系统不会声称在最高/最低价格出现的瞬间已经知道它是顶/底。
- 分时顶发 `SELL` 提醒，分时底发 `BUY` 提醒；信号方向自然交替，同一波段不会连续重复。
- 默认使用“标准”档；前端还提供“灵敏”和“稳健”预设。
- 后端每个完整决策分钟会把当日 30 秒图表 K、60 秒决策 K、信号与事件原子写入 work/intraday_cache.json。
- 同一交易日重启时会先按时间顺序回放缓存，立即恢复策略状态且不重复发 Toast；缓存已覆盖最近完整分钟时不会调用 WSI，有断档时只从缓存尾部下一分钟补齐。
- 跨自然日只保留自选股和策略配置，上一交易日行情与信号不会带入当天；缓存损坏时自动退化为 WSI 回填或实时预热。
- 系统并行维护“分时波段”和“多尺度动能”两套策略；设置中可分别启停，也可同时运行。多尺度动能用 MDC 自动判定微/小/中/大级别，用 ATR 归一的 MACD-V 判断动能阶段；观察与候选进入前端，只有中/大级确认发送 Windows 提醒。关闭后仍持续维护当日指标上下文，重新开启不需要重新预热。完整口径见 MACD_DIVERGENCE_SPEC.md。

完整策略口径见 `STRATEGY_V3_SWING_SPEC.md` 和冻结施工规格 `STRATEGY_V3_1_DUAL_CHANNEL_SPEC.md`。

## 开发与验证

- C:\Python27\python.exe backend\test_macd_divergence.py：运行 MDC + MACD-V 自动定级、门控、去重与非重绘测试。

- `npm run dev`：启动前端开发服务。
- `npm run backend`：启动本地 WindPy 后端。
- `npm run lint`：检查前端代码。
- `npm test`：构建并验证 V3.1 双通道前端契约。
- `C:\Python27\python.exe backend\test_swing_v3.py`：运行策略回放与非重绘测试。
- `C:\Python27\python.exe backend\test_signal_engine.py`：运行后端集成测试。
- `C:\Python27\python.exe -m py_compile backend\server.py backend\swing_v3.py`：运行 Python 2.7 编译检查。

## 边界

这是辅助提醒，不是交易指令，也不保证捕捉绝对最高点或最低点。请先通过回放、模拟和人工复核评估参数，再用于日常盯盘。
