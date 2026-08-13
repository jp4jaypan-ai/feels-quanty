# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import datetime
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from swing_v3 import DecisionBarAggregator, SwingV3Engine, default_config


BASE_DAY = datetime.datetime(2026, 8, 12)


def stamp(text, day_offset=0):
    hour, minute, second = [int(part) for part in text.split(':')]
    value = BASE_DAY + datetime.timedelta(days=day_offset, hours=hour, minutes=minute, seconds=second)
    return time.mktime(value.timetuple())


def bar(text, open_price, high, low, close, volume=1000.0, day_offset=0,
        pre_close=None, first_open=None, opening_gap_pct=None):
    timestamp = stamp(text, day_offset)
    return {
        'timestamp': timestamp, 'time': text,
        'confirm_timestamp': timestamp + 60,
        'confirm_time': datetime.datetime.fromtimestamp(timestamp + 60).strftime('%H:%M:%S'),
        'open': open_price, 'high': high, 'low': low, 'close': close,
        'volume': volume, 'amount': volume * close, 'vwap': close,
        'pct_change': 0.0,
        'pre_close': pre_close, 'first_open': first_open,
        'opening_gap_pct': opening_gap_pct,
    }


def screenshot_bars():
    return [
        bar('11:09:00', 456.60, 457.49, 455.06, 455.06, 267100),
        bar('11:10:00', 455.06, 456.00, 454.78, 455.78, 11663),
        bar('11:11:00', 455.78, 458.00, 455.78, 457.77, 28700),
        bar('11:12:00', 456.81, 457.89, 456.62, 457.89, 15800),
        bar('11:13:00', 457.89, 458.99, 456.30, 458.99, 28186),
        bar('11:14:00', 459.00, 459.00, 455.99, 455.99, 26700),
        bar('11:15:00', 456.40, 456.49, 455.60, 456.47, 11700),
        bar('11:16:00', 456.45, 456.45, 452.91, 452.91, 12500),
        bar('11:17:00', 452.91, 454.00, 452.86, 453.99, 9100),
        bar('11:18:00', 453.55, 453.57, 452.55, 452.57, 4600),
        bar('11:19:00', 452.31, 452.57, 451.80, 452.57, 6900),
    ]


def feed(engine, bars, config=None, code='301377.SZ'):
    signals, analytics = [], None
    for item in bars:
        analytics, signal = engine.process(code, item, config or default_config())
        if signal:
            signals.append(signal)
    return analytics, signals


def feed_with_events(engine, bars, config=None, code='301377.SZ'):
    signals, events, analytics = [], [], None
    for item in bars:
        analytics, signal = engine.process(code, item, config or default_config())
        events.extend(engine.drain_event_updates(code))
        if signal:
            signals.append(signal)
    return analytics, signals, events


def regular_candidate_bars(include_confirmation=False, new_extreme=False):
    bars = [
        bar('10:00:00', 100.0, 100.1, 99.9, 100.0, 1000),
        bar('10:01:00', 100.0, 100.6, 99.95, 100.5, 1000),
        bar('10:02:00', 100.5, 101.1, 100.4, 101.0, 1000),
        bar('10:03:00', 101.0, 101.3, 100.8, 101.1, 1000),
        bar('10:04:00', 101.1, 101.25, 100.9, 100.95, 1000),
    ]
    if new_extreme:
        bars.append(bar('10:05:00', 100.95, 101.6, 100.8, 101.5, 1000))
    if include_confirmation:
        if not new_extreme:
            bars.append(bar('10:05:00', 100.95, 101.6, 100.8, 101.5, 1000))
        bars.append(bar('10:06:00', 101.5, 101.55, 100.6, 100.7, 1000))
    return bars


def test_decision_aggregator_combines_two_micro_bars_causally():
    aggregate = DecisionBarAggregator()
    micro = [
        dict(bar('10:00:00', 10.0, 10.2, 9.9, 10.1, 100, pre_close=9.8, first_open=10.0), timestamp=stamp('10:00:00'), time='10:00:00'),
        dict(bar('10:00:30', 10.1, 10.4, 10.0, 10.3, 200, pre_close=9.8, first_open=10.0), timestamp=stamp('10:00:30'), time='10:00:30'),
    ]
    assert aggregate.consume('000001.SZ', micro[:1]) == []
    result = aggregate.consume('000001.SZ', micro)
    assert len(result) == 1
    assert result[0]['open'] == 10.0 and result[0]['high'] == 10.4
    assert result[0]['low'] == 9.9 and result[0]['close'] == 10.3
    assert result[0]['time'] == '10:00:00' and result[0]['confirm_time'] == '10:01:00'
    assert result[0]['pre_close'] == 9.8 and result[0]['first_open'] == 10.0
    assert len(result[0]['micro_bars']) == 2
    assert [item['close'] for item in result[0]['micro_bars']] == [10.1, 10.3]


def test_decision_aggregator_drops_incomplete_physical_minute():
    aggregate = DecisionBarAggregator()
    missing_first_half = dict(bar('10:00:30', 10.1, 10.2, 10.0, 10.1, 100),
                              timestamp=stamp('10:00:30'), time='10:00:30')
    assert aggregate.consume('000001.SZ', [missing_first_half]) == []
    next_first = dict(bar('10:01:00', 10.1, 10.3, 10.0, 10.2, 100),
                      timestamp=stamp('10:01:00'), time='10:01:00')
    next_second = dict(bar('10:01:30', 10.2, 10.4, 10.1, 10.3, 100),
                       timestamp=stamp('10:01:30'), time='10:01:30')
    assert aggregate.consume('000001.SZ', [next_first]) == []
    result = aggregate.consume('000001.SZ', [next_second])
    assert len(result) == 1 and result[0]['parts'] == 2
    assert result[0]['time'] == '10:01:00' and result[0]['confirm_time'] == '10:02:00'


def test_regular_accelerated_confirmation_uses_completed_micro_sequence():
    config = dict(default_config('robust'), opening_fast_enabled=False,
                  opening_guard_minutes=0, warmup_bars=4, cooldown_seconds=0)
    bars = [
        bar('10:00:00', 100.0, 100.1, 99.9, 100.0, 1000),
        bar('10:01:00', 100.0, 100.5, 99.95, 100.45, 1000),
        bar('10:02:00', 100.45, 101.05, 100.4, 101.0, 1000),
        bar('10:03:00', 101.0, 102.0, 100.95, 101.7, 2000),
    ]
    bars[-1]['micro_bars'] = [
        dict(bar('10:03:00', 101.0, 102.0, 100.95, 101.95, 1100),
             timestamp=stamp('10:03:00'), time='10:03:00'),
        dict(bar('10:03:30', 101.95, 101.98, 101.65, 101.7, 900),
             timestamp=stamp('10:03:30'), time='10:03:30'),
    ]

    legacy_config = dict(config, early_confirm_enabled=False)
    _, legacy_signals = feed(SwingV3Engine(), bars, legacy_config, 'LEGACY.SZ')
    assert legacy_signals == []

    _, signals = feed(SwingV3Engine(), bars, config, 'FAST.SZ')
    assert len(signals) == 1
    signal = signals[0]
    assert signal['side'] == 'SELL'
    assert signal['extreme_time'] == '10:03:00'
    assert signal['confirm_time'] == '10:04:00'
    assert signal['confirmation_mode'] == 'ACCELERATED'
    assert signal['reversal_pct_actual'] < signal['reversal_threshold_pct']
    assert any(u'30秒子K' in item for item in signal['confirmations'])


def test_strict_last_micro_reclaim_confirms_fast_opposite_v_turn():
    config = dict(default_config('robust'), opening_fast_enabled=False,
                  opening_guard_minutes=0, warmup_bars=4, cooldown_seconds=0)
    bars = [
        bar('10:00:00', 100.0, 100.1, 99.9, 100.0, 1000),
        bar('10:01:00', 100.0, 100.5, 99.95, 100.45, 1000),
        bar('10:02:00', 100.45, 101.05, 100.4, 101.0, 1000),
        bar('10:03:00', 101.0, 102.0, 100.95, 101.7, 2000),
        bar('10:04:00', 101.7, 101.72, 100.5, 101.2, 2500),
    ]
    bars[3]['micro_bars'] = [
        dict(bar('10:03:00', 101.0, 102.0, 100.95, 101.95, 1100),
             timestamp=stamp('10:03:00'), time='10:03:00'),
        dict(bar('10:03:30', 101.95, 101.98, 101.65, 101.7, 900),
             timestamp=stamp('10:03:30'), time='10:03:30'),
    ]
    bars[4]['micro_bars'] = [
        dict(bar('10:04:00', 101.7, 101.72, 101.2, 101.2, 1200),
             timestamp=stamp('10:04:00'), time='10:04:00'),
        dict(bar('10:04:30', 101.2, 101.25, 100.5, 101.2, 1300),
             timestamp=stamp('10:04:30'), time='10:04:30'),
    ]

    _, signals = feed(SwingV3Engine(), bars, config, 'V-TURN.SZ')
    assert [signal['side'] for signal in signals] == ['SELL', 'BUY']
    assert signals[0]['confirm_time'] == '10:04:00'
    assert signals[1]['extreme_time'] == '10:04:00'
    assert signals[1]['confirm_time'] == '10:05:00'
    assert signals[1]['confirmation_mode'] == 'ACCELERATED'
    assert any(u'最后一根30秒子K' in item for item in signals[1]['confirmations'])


def rapid_reversal_bars():
    return [
        bar('10:00:00', 100.0, 100.1, 99.9, 100.0),
        bar('10:01:00', 100.0, 100.6, 100.0, 100.5),
        bar('10:02:00', 100.5, 101.1, 100.4, 101.0),
        bar('10:03:00', 101.5, 101.6, 100.8, 100.8),
        bar('10:04:00', 100.8, 101.0, 99.5, 99.5),
        bar('10:05:00', 99.5, 100.3, 99.4, 100.3),
        bar('10:06:00', 100.3, 100.5, 100.0, 100.5),
    ]


def test_minimum_leg_bars_is_enforced_after_direction_switch():
    config = dict(default_config('sensitive'), warmup_bars=4, min_leg_bars=4,
                  min_confidence=50, min_swing_pct=0.1, min_swing_range_mult=0.1,
                  reversal_pct=0.1, reversal_range_mult=0.1, cooldown_seconds=0)
    engine, signals = SwingV3Engine(), []
    for index, item in enumerate(rapid_reversal_bars()):
        _, signal = engine.process('000001.SZ', item, config)
        if signal:
            signals.append(signal)
        if index in (4, 5):
            assert signal is None
    assert [signal['side'] for signal in signals] == ['SELL', 'BUY']
    assert signals[1]['confirm_time'] == '10:07:00'


def test_secondary_cooldown_blocks_too_rapid_opposite_signal():
    config = dict(default_config('sensitive'), warmup_bars=4, min_leg_bars=2,
                  min_confidence=50, min_swing_pct=0.1, min_swing_range_mult=0.1,
                  reversal_pct=0.1, reversal_range_mult=0.1, cooldown_seconds=180)
    _, signals = feed(SwingV3Engine(), rapid_reversal_bars(), config, '000001.SZ')
    assert [signal['side'] for signal in signals] == ['SELL', 'BUY']
    assert signals[0]['confirm_time'] == '10:04:00'
    assert signals[1]['confirm_time'] == '10:07:00'


def test_301377_real_replay_confirms_459_top_without_late_sell():
    engine = SwingV3Engine()
    bars = screenshot_bars()
    signals = []
    for index, item in enumerate(bars):
        _, signal = engine.process('301377.SZ', item, default_config())
        if index < 5:
            assert signal is None
        if signal:
            signals.append(signal)
    assert len(signals) == 1
    signal = signals[0]
    assert signal['side'] == 'SELL' and signal['turning_point'] == 'TOP'
    assert signal['channel'] == 'REGULAR' and signal['pattern'] == 'DIRECTIONAL_CHANGE'
    assert signal['extreme_price'] == 459.0
    assert signal['extreme_time'] == '11:14:00'
    assert signal['confirm_time'] == '11:15:00'
    assert signal['confirm_price'] == 455.99
    assert signal['confirm_timestamp'] > signal['extreme_timestamp']


def test_flat_noise_has_no_signal():
    bars = []
    for index in range(20):
        price = 100.0 + (0.02 if index % 2 else -0.02)
        text = '10:%02d:00' % index
        bars.append(bar(text, price, price + 0.02, price - 0.02, price, 1000))
    _, signals = feed(SwingV3Engine(), bars)
    assert signals == []


def test_monotonic_uptrend_does_not_guess_top():
    bars = []
    for index in range(16):
        price = 100.0 + index * 0.35
        text = '10:%02d:00' % index
        bars.append(bar(text, price - 0.1, price + 0.2, price - 0.15, price, 1200))
    analytics, signals = feed(SwingV3Engine(), bars)
    assert signals == []
    assert analytics['phase'] == 'TRACKING_UP'


def test_bottom_confirmation_and_natural_alternation():
    engine = SwingV3Engine()
    bars = []
    prices = [100.0, 99.6, 99.1, 98.6, 98.1, 97.5, 98.2, 99.0, 100.0, 100.8, 101.5, 100.7]
    for index, price in enumerate(prices):
        text = '10:%02d:00' % index
        high = price + (0.15 if index != 6 else 0.35)
        low = price - (0.15 if index != 5 else 0.45)
        bars.append(bar(text, price, high, low, price, 1800))
    _, signals = feed(engine, bars, dict(default_config('sensitive'), warmup_bars=4))
    assert signals
    assert signals[0]['side'] == 'BUY'
    assert all(signals[index]['side'] != signals[index - 1]['side'] for index in range(1, len(signals)))


def test_gap_and_new_day_reset_structure():
    engine = SwingV3Engine()
    config = dict(default_config('sensitive'), warmup_bars=4)
    feed(engine, [
        bar('10:00:00', 100, 100.2, 99.8, 100),
        bar('10:01:00', 100, 100.7, 99.9, 100.6),
        bar('10:02:00', 100.6, 101.2, 100.5, 101.1),
        bar('10:03:00', 101.1, 101.8, 101.0, 101.7),
    ], config)
    analytics, signal = engine.process('301377.SZ', bar('10:07:00', 101.7, 101.8, 100.4, 100.5), config)
    assert signal is None
    assert any(u'断档' in reason for reason in analytics['blocked_reasons'])
    analytics, signal = engine.process('301377.SZ', bar('10:08:00', 100.5, 100.7, 99.9, 100.0, day_offset=1), config)
    assert signal is None
    assert analytics['decision_bars'] == 1


def test_lunch_bar_is_blocked_and_resets():
    engine = SwingV3Engine()
    analytics, signal = engine.process('000001.SZ', bar('11:31:00', 100, 101, 99, 100), default_config())
    assert signal is None and analytics['decision_bars'] == 0
    assert any(u'午间休市' in reason for reason in analytics['blocked_reasons'])


def test_preopen_auction_bar_does_not_contaminate_opening_state():
    engine = SwingV3Engine()
    analytics, signal = engine.process(
        '000018.SZ', bar('09:29:00', 101.0, 101.2, 100.8, 101.1, pre_close=100.0),
        default_config())
    assert signal is None and analytics['decision_bars'] == 0
    analytics, signals = feed(engine, opening_gap_sell_bars(), default_config(), '000018.SZ')
    assert len(signals) == 1
    assert signals[0]['confirm_time'] == '09:32:00'
    assert analytics['opening_fast_bars'] == 2


def test_sensitivity_presets_differ():
    prices = [100.0, 100.15, 100.35, 100.55, 100.72, 100.85, 100.55]
    bars = [bar('10:%02d:00' % index, value, value + 0.05, value - 0.05, value, 1000)
            for index, value in enumerate(prices)]
    _, sensitive = feed(SwingV3Engine(), bars, dict(default_config('sensitive'), warmup_bars=4))
    _, robust = feed(SwingV3Engine(), bars, dict(default_config('robust'), warmup_bars=4))
    assert len(sensitive) >= len(robust)
    assert sensitive or not robust


def test_emitted_signal_never_repaints_after_future_bars():
    engine = SwingV3Engine()
    bars = screenshot_bars()
    _, signals = feed(engine, bars[:6])
    assert len(signals) == 1
    snapshot = dict(signals[0])
    feed(engine, bars[6:])
    assert signals[0] == snapshot


def opening_gap_sell_bars():
    return [
        bar('09:30:00', 102.0, 103.0, 101.8, 102.8, pre_close=100.0),
        bar('09:31:00', 102.8, 103.2, 100.8, 100.8, pre_close=100.0),
    ]


def opening_gap_buy_bars():
    return [
        bar('09:30:00', 98.0, 98.2, 97.0, 97.2, pre_close=100.0),
        bar('09:31:00', 97.2, 99.5, 96.0, 99.5, pre_close=100.0),
    ]


def test_opening_fast_gap_rejection_sell_at_0932_once():
    engine = SwingV3Engine()
    analytics, signals = feed(engine, opening_gap_sell_bars(), default_config(), '000001.SZ')
    assert len(signals) == 1
    signal = signals[0]
    assert signal['side'] == 'SELL' and signal['channel'] == 'OPENING_FAST'
    assert signal['pattern'] == 'GAP_REJECTION'
    assert signal['confirm_time'] == '09:32:00'
    assert signal['first_open'] == 102.0 and signal['pre_close'] == 100.0
    assert signal['opening_gap_pct'] == 2.0
    assert analytics['opening_fast_signal_emitted'] if 'opening_fast_signal_emitted' in analytics else True


def test_opening_fast_gap_rejection_buy_at_0932_once():
    _, signals = feed(SwingV3Engine(), opening_gap_buy_bars(), default_config(), '000002.SZ')
    assert len(signals) == 1
    assert signals[0]['side'] == 'BUY'
    assert signals[0]['channel'] == 'OPENING_FAST'
    assert signals[0]['pattern'] == 'GAP_REJECTION'
    assert signals[0]['confirm_time'] == '09:32:00'


def test_opening_fast_monotonic_gap_does_not_guess_top_or_bottom():
    up = [
        bar('09:30:00', 102.0, 103.0, 101.8, 102.9, pre_close=100.0),
        bar('09:31:00', 102.9, 104.2, 102.7, 104.0, pre_close=100.0),
    ]
    down = [
        bar('09:30:00', 98.0, 98.2, 97.0, 97.1, pre_close=100.0),
        bar('09:31:00', 97.1, 97.3, 95.8, 96.0, pre_close=100.0),
    ]
    assert feed(SwingV3Engine(), up, default_config(), '000003.SZ')[1] == []
    assert feed(SwingV3Engine(), down, default_config(), '000004.SZ')[1] == []


def test_opening_fast_small_noise_has_no_signal():
    bars = [
        bar('09:30:00', 100.0, 100.2, 99.9, 100.1, pre_close=100.0),
        bar('09:31:00', 100.1, 100.25, 99.95, 100.05, pre_close=100.0),
        bar('09:32:00', 100.05, 100.2, 99.98, 100.1, pre_close=100.0),
    ]
    assert feed(SwingV3Engine(), bars, default_config(), '000005.SZ')[1] == []


def test_opening_fast_reversal_leg_cannot_count_as_the_prior_impulse():
    down_without_prior_rise = [
        bar('09:30:00', 100.0, 100.05, 99.95, 100.0),
        bar('09:31:00', 100.0, 100.0, 98.4, 98.4),
    ]
    up_without_prior_fall = [
        bar('09:30:00', 100.0, 100.05, 99.95, 100.0),
        bar('09:31:00', 100.0, 101.6, 100.0, 101.6),
    ]
    assert feed(SwingV3Engine(), down_without_prior_rise, default_config(), '000015.SZ')[1] == []
    assert feed(SwingV3Engine(), up_without_prior_fall, default_config(), '000016.SZ')[1] == []


def test_opening_fast_without_pre_close_allows_impulse_reversal():
    bars = [
        bar('09:30:00', 100.0, 100.4, 99.8, 100.3),
        bar('09:31:00', 100.3, 101.5, 100.2, 101.4),
        bar('09:32:00', 101.4, 102.8, 101.2, 102.7),
        bar('09:33:00', 102.7, 104.0, 102.5, 103.9),
        bar('09:34:00', 103.9, 104.2, 102.0, 102.0),
    ]
    _, signals = feed(SwingV3Engine(), bars, default_config(), '000006.SZ')
    assert len(signals) == 1
    assert signals[0]['side'] == 'SELL'
    assert signals[0]['channel'] == 'OPENING_FAST'
    assert signals[0]['pattern'] == 'IMPULSE_REVERSAL'
    assert signals[0]['pre_close'] is None


def test_opening_fast_signal_naturally_alternates_and_regular_never_duplicates_sell():
    engine = SwingV3Engine()
    bars = opening_gap_sell_bars() + [
        bar('09:32:00', 100.8, 101.0, 99.0, 99.1, pre_close=100.0),
        bar('09:33:00', 99.1, 99.3, 98.7, 98.9, pre_close=100.0),
        bar('09:34:00', 98.9, 99.0, 98.0, 98.2, pre_close=100.0),
        bar('09:35:00', 98.2, 98.4, 97.5, 97.6, pre_close=100.0),
        bar('09:36:00', 97.6, 99.2, 97.4, 99.2, pre_close=100.0),
    ]
    _, signals = feed(engine, bars, default_config(), '000007.SZ')
    assert signals[0]['side'] == 'SELL' and signals[0]['channel'] == 'OPENING_FAST'
    assert not any(item['side'] == 'SELL' for item in signals[1:])
    assert all(item['side'] != signals[index - 1]['side'] for index, item in enumerate(signals[1:], 1))


def test_opening_fast_is_closed_from_0935_onward():
    bars = [
        bar('09:35:00', 102.0, 103.0, 101.8, 102.8, pre_close=100.0),
        bar('09:36:00', 102.8, 103.2, 100.8, 100.8, pre_close=100.0),
    ]
    analytics, signals = feed(SwingV3Engine(), bars, default_config(), '000008.SZ')
    assert signals == []
    assert analytics['opening_fast_active'] is False
    assert analytics['opening_fast_status'] == u'开盘强信号窗口已结束'


def test_last_signal_channel_survives_session_reset():
    engine = SwingV3Engine()
    _, signals = feed(engine, opening_gap_sell_bars(), default_config(), '000017.SZ')
    assert signals and signals[0]['channel'] == 'OPENING_FAST'
    analytics, signal = engine.process(
        '000017.SZ', bar('11:31:00', 100.0, 100.2, 99.8, 100.0, pre_close=100.0),
        default_config())
    assert signal is None
    assert analytics['last_signal_side'] == 'SELL'
    assert analytics['last_signal_channel'] == 'OPENING_FAST'


def test_regular_light_reversal_creates_candidate_without_legacy_signal():
    config = dict(default_config(), opening_fast_enabled=False, warmup_bars=4,
                  reversal_pct=0.30, reversal_range_mult=1.0,
                  min_confidence=100, cooldown_seconds=0)
    analytics, signals, events = feed_with_events(
        SwingV3Engine(), regular_candidate_bars(), config, 'CANDIDATE.SZ')
    candidate_events = [item for item in events if item['notification_kind'] == 'CANDIDATE']
    assert signals == []
    assert len(candidate_events) == 1
    assert candidate_events[0]['event_state'] == 'CANDIDATE'
    assert candidate_events[0]['signal_level'] == 'CANDIDATE'
    assert candidate_events[0]['pattern'] == 'EARLY_REVERSAL_WATCH'
    assert analytics['active_turn_event']['event_id'] == candidate_events[0]['event_id']
    assert analytics['candidate_alerts_enabled'] is True


def test_regular_event_keeps_id_on_new_extreme_and_does_not_repeat_candidate_notification():
    config = dict(default_config(), opening_fast_enabled=False, warmup_bars=4,
                  reversal_pct=0.30, reversal_range_mult=1.0,
                  min_confidence=100, cooldown_seconds=0)
    _, signals, events = feed_with_events(
        SwingV3Engine(), regular_candidate_bars(new_extreme=True), config, 'EXTREME.SZ')
    assert signals == []
    candidate = [item for item in events if item['notification_kind'] == 'CANDIDATE']
    assert len(candidate) == 1
    assert len(set(item['event_id'] for item in events)) == 1
    assert events[-1]['event_state'] == 'CANDIDATE'
    assert events[-1]['extreme_price'] == 101.6
    assert events[-1]['revision'] > candidate[0]['revision']


def test_candidate_strengthens_then_confirms_with_same_event_id():
    config = dict(default_config(), opening_fast_enabled=False, warmup_bars=4,
                  reversal_pct=0.30, reversal_range_mult=1.0,
                  min_confidence=70, cooldown_seconds=0)
    _, signals, events = feed_with_events(
        SwingV3Engine(), regular_candidate_bars(include_confirmation=True),
        config, 'CONFIRM.SZ')
    assert signals and signals[0]['event_state'] == 'CONFIRMED'
    candidate = [item for item in events if item['notification_kind'] == 'CANDIDATE'][0]
    strengthening = [item for item in events if item['event_state'] == 'STRENGTHENING']
    confirmed = [item for item in events if item['notification_kind'] == 'CONFIRMED'][-1]
    assert strengthening
    assert confirmed['event_id'] == candidate['event_id'] == signals[0]['event_id']
    assert confirmed['signal_level'] == 'CONFIRMED'
    assert signals[0]['revision'] == confirmed['revision']
    assert signals[0]['pattern'] == 'DIRECTIONAL_CHANGE'


def test_candidate_ttl_invalidates_once_same_extreme_does_not_rebuild_new_extreme_can():
    bars = regular_candidate_bars() + [
        bar('10:05:00', 101.1, 101.25, 100.9, 101.1, 1000),
        bar('10:06:00', 101.1, 101.25, 100.9, 101.1, 1000),
        bar('10:07:00', 101.1, 101.3, 100.9, 101.1, 1000),
        bar('10:08:00', 101.1, 101.6, 100.8, 101.1, 1000),
    ]
    config = dict(default_config(), opening_fast_enabled=False, warmup_bars=4,
                  reversal_pct=2.0, reversal_range_mult=1.0,
                  min_confidence=100, candidate_ttl_bars=3, cooldown_seconds=0)
    _, signals, events = feed_with_events(SwingV3Engine(), bars, config, 'TTL.SZ')
    assert signals == []
    invalidated = [item for item in events if item['event_state'] == 'INVALIDATED']
    candidates = [item for item in events if item['notification_kind'] == 'CANDIDATE']
    assert len(invalidated) == 1
    assert u'3' in invalidated[0]['reason']
    assert len(candidates) == 2
    assert candidates[0]['event_id'] != candidates[-1]['event_id']
    assert invalidated[0]['event_id'] == candidates[0]['event_id']


def test_monotonic_and_flat_noise_have_no_candidate_events():
    up = [bar('10:%02d:00' % index, 100.0 + index * 0.35 - 0.1,
              100.0 + index * 0.35 + 0.2,
              100.0 + index * 0.35 - 0.15,
              100.0 + index * 0.35, 1200) for index in range(16)]
    flat = [bar('10:%02d:00' % index, 100.0 + (0.02 if index % 2 else -0.02),
                100.04, 99.96, 100.0 + (0.02 if index % 2 else -0.02), 1000)
            for index in range(16)]
    config = dict(default_config(), opening_fast_enabled=False)
    assert feed_with_events(SwingV3Engine(), up, config, 'UP.SZ')[2] == []
    assert feed_with_events(SwingV3Engine(), flat, config, 'FLAT.SZ')[2] == []


def test_opening_first_complete_bar_gap_rejection_creates_candidate_only():
    first = bar('09:30:00', 102.0, 104.0, 100.0, 100.5, 1000, pre_close=100.0)
    _, signals, events = feed_with_events(
        SwingV3Engine(), [first], default_config(), 'OPEN-CAND.SZ')
    assert signals == []
    assert len(events) == 1
    assert events[0]['event_state'] == 'CANDIDATE'
    assert events[0]['channel'] == 'OPENING_FAST'
    assert events[0]['pattern'] == 'EARLY_REVERSAL_WATCH'
    assert events[0]['extreme_time'] == '09:30:00'
    assert events[0]['created_time'] == '09:31:00'
    assert events[0]['observed_time'] == '09:31:00'
    assert events[0]['updated_time'] == '09:31:00'
    assert events[0]['created_timestamp'] == first['confirm_timestamp']
    assert events[0]['observed_timestamp'] == first['confirm_timestamp']
    assert events[0]['updated_timestamp'] == first['confirm_timestamp']


def test_opening_candidate_is_side_channel_and_toggle_preserves_legacy_state():
    bars = opening_gap_sell_bars()
    legacy_keys = (
        'phase', 'candidate_price', 'candidate_time', 'candidate_timestamp',
        'candidate_index', 'candidate_close', 'leg_start_price',
        'leg_start_time', 'leg_start_timestamp', 'leg_start_index',
        'last_signal_side', 'last_signal_at', 'last_signal_channel',
        'last_signal_pattern', 'opening_fast_signal_emitted',
        'opening_fast_signal_at')
    signal_keys = (
        'side', 'turning_point', 'channel', 'pattern', 'extreme_price',
        'extreme_time', 'extreme_timestamp', 'confirm_price', 'confirm_time',
        'confirm_timestamp', 'confidence', 'first_open', 'pre_close',
        'opening_gap_pct')
    snapshots, signals, events = [], [], []
    for code, config in (
            ('OPEN-SIDE-ON.SZ', default_config()),
            ('OPEN-SIDE-OFF.SZ', dict(default_config(), candidate_alerts_enabled=False))):
        engine = SwingV3Engine()
        per_bar = []
        code_signals, code_events = [], []
        for item in bars:
            _, signal = engine.process(code, item, config)
            state = engine.states[code]
            per_bar.append(dict((key, state.get(key)) for key in legacy_keys))
            code_events.extend(engine.drain_event_updates(code))
            if signal:
                code_signals.append(dict((key, signal.get(key)) for key in signal_keys))
        snapshots.append(per_bar)
        signals.append(code_signals)
        events.append(code_events)
    assert snapshots[0] == snapshots[1]
    assert signals[0] == signals[1]
    assert any(item['notification_kind'] == 'CANDIDATE' for item in events[0])
    assert not any(item['notification_kind'] == 'CANDIDATE' for item in events[1])


def test_confirmed_event_is_not_an_active_candidate():
    engine = SwingV3Engine()
    analytics, signals, events = feed_with_events(
        engine, opening_gap_sell_bars(), default_config(), 'CONFIRMED-HISTORY.SZ')
    state = engine.states['CONFIRMED-HISTORY.SZ']
    assert signals and events[-1]['event_state'] == 'CONFIRMED'
    assert state['last_turn_event']['event_state'] == 'CONFIRMED'
    assert state['active_turn_events']['SELL'] is None
    assert state['active_turn_events']['BUY'] is None
    assert state['active_turn_event'] is None
    assert analytics['active_turn_event'] is None


def test_invalidating_current_active_side_keeps_other_candidate_visible():
    engine = SwingV3Engine()
    code = 'TWO-SIDED-EVENT.SZ'
    config = default_config()
    state = engine.states.setdefault(code, engine._new_state())
    sell_bar = bar('10:00:00', 100.0, 102.0, 99.0, 101.0)
    buy_bar = bar('10:01:00', 101.0, 101.5, 98.0, 99.0)
    invalidate_bar = bar('10:02:00', 99.0, 100.0, 97.0, 98.0)
    sell_event = engine._new_turn_event(
        code, state, sell_bar, config, 'SELL', 65, [u'卖出候选证据'],
        'REGULAR', 'EARLY_REVERSAL_WATCH', 0, extreme_bar=sell_bar,
        notification_kind='CANDIDATE')
    engine._new_turn_event(
        code, state, buy_bar, config, 'BUY', 65, [u'买入候选证据'],
        'REGULAR', 'EARLY_REVERSAL_WATCH', 1, extreme_bar=buy_bar,
        notification_kind='CANDIDATE')
    assert state['active_turn_event']['side'] == 'BUY'

    engine._invalidate_turn_event(state, 'BUY', invalidate_bar, u'确定性测试失效')
    analytics = engine._analytics(state, config, 0.1)
    assert state['active_turn_events']['BUY'] is None
    assert state['active_turn_events']['SELL']['event_id'] == sell_event['event_id']
    assert state['active_turn_event']['event_id'] == sell_event['event_id']
    assert analytics['active_turn_event']['event_id'] == sell_event['event_id']


def test_structure_reset_clears_ttl_extreme_block_for_day_lunch_and_gap():
    cases = (
        ('RESET-DAY.SZ', bar('10:00:00', 100, 101, 99, 100),
         bar('10:01:00', 100, 101, 99, 100, day_offset=1)),
        ('RESET-LUNCH.SZ', bar('11:30:00', 100, 101, 99, 100),
         bar('11:31:00', 100, 101, 99, 100)),
        ('RESET-GAP.SZ', bar('10:00:00', 100, 101, 99, 100),
         bar('10:03:00', 100, 101, 99, 100)),
    )
    for code, previous, current in cases:
        engine = SwingV3Engine()
        state = engine.states.setdefault(code, engine._new_state())
        state['day'] = '2026-08-12'
        state['bars'] = [previous]
        state['invalidated_extremes'] = {'SELL': 104.0, 'BUY': 96.0}
        engine.process(code, current, default_config())
        assert state['invalidated_extremes'] == {}


def test_opening_candidate_ttl_runs_while_legacy_state_stays_bootstrap():
    bars = [
        bar('09:30:00', 102.0, 104.0, 100.0, 100.5, pre_close=100.0),
        bar('09:31:00', 100.5, 102.0, 100.4, 101.0, pre_close=100.0),
        bar('09:32:00', 101.0, 102.0, 100.5, 101.2, pre_close=100.0),
        bar('09:33:00', 101.2, 102.0, 100.7, 101.3, pre_close=100.0),
        bar('09:34:00', 101.3, 102.0, 100.8, 101.4, pre_close=100.0),
    ]
    config = dict(default_config(), candidate_ttl_bars=3)
    analytics, signals, events = feed_with_events(
        SwingV3Engine(), bars, config, 'OPEN-TTL.SZ')
    invalidated = [item for item in events if item['event_state'] == 'INVALIDATED']
    candidates = [item for item in events if item['notification_kind'] == 'CANDIDATE']
    assert signals == []
    assert len(candidates) == 1
    assert len(invalidated) == 1
    assert analytics['phase'] == 'BOOTSTRAP'
    assert analytics['active_turn_event'] is None


def test_opening_fast_confirmation_upgrades_opening_candidate_same_event():
    _, signals, events = feed_with_events(
        SwingV3Engine(), opening_gap_sell_bars(), default_config(), 'OPEN-UPGRADE.SZ')
    candidate = [item for item in events if item['notification_kind'] == 'CANDIDATE'][0]
    confirmed = [item for item in events if item['notification_kind'] == 'CONFIRMED'][-1]
    assert signals and signals[0]['event_id'] == candidate['event_id'] == confirmed['event_id']
    assert confirmed['channel'] == 'OPENING_FAST'
    assert confirmed['pattern'] == 'GAP_REJECTION'
    assert signals[0]['event_state'] == 'CONFIRMED'


def test_opening_monotonic_gap_has_no_candidate_events():
    up = [
        bar('09:30:00', 102.0, 103.0, 101.8, 102.9, pre_close=100.0),
        bar('09:31:00', 102.9, 104.2, 102.7, 104.0, pre_close=100.0),
    ]
    down = [
        bar('09:30:00', 98.0, 98.2, 97.0, 97.1, pre_close=100.0),
        bar('09:31:00', 97.1, 97.3, 95.8, 96.0, pre_close=100.0),
    ]
    assert feed_with_events(SwingV3Engine(), up, default_config(), 'OPEN-UP.SZ')[2] == []
    assert feed_with_events(SwingV3Engine(), down, default_config(), 'OPEN-DOWN.SZ')[2] == []


def main():
    tests = [value for name, value in globals().items() if name.startswith('test_')]
    for test in tests:
        test()
        print('PASS', test.__name__)
    print('swing v3 tests passed: %d' % len(tests))


if __name__ == '__main__':
    main()
