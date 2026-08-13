# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import datetime
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from macd_divergence import (
    MacdDivergenceEngine,
    STRATEGY_VERSION,
    _momentum_stage,
    default_macd_config,
    normalize_macd_config,
)


BASE = datetime.datetime(2026, 8, 13, 9, 30)


def linear(start, end, count):
    if count <= 1:
        return [end]
    return [
        start + (end - start) * index / float(count - 1)
        for index in range(count)
    ]


def minute_bars(values, day_offset=0):
    bars = []
    previous = values[0]
    for index, close in enumerate(values):
        moment = BASE + datetime.timedelta(days=day_offset, minutes=index)
        timestamp = time.mktime(moment.timetuple())
        bars.append({
            'timestamp': timestamp,
            'time': moment.strftime('%H:%M:%S'),
            'confirm_timestamp': timestamp + 60.0,
            'confirm_time': (
                moment + datetime.timedelta(minutes=1)).strftime('%H:%M:%S'),
            'open': previous,
            'high': close + 0.04,
            'low': close - 0.04,
            'close': close,
            'volume': 1000.0,
        })
        previous = close
    return bars


def bearish_divergence_values():
    return (
        [100.0] * 36 +
        linear(100.0, 102.0, 7) +
        linear(101.7, 100.8, 6) +
        linear(100.9, 102.2, 13) +
        [101.9, 101.6, 101.4]
    )


def bullish_divergence_values():
    return (
        [100.0] * 36 +
        linear(100.0, 98.0, 7) +
        linear(98.3, 99.2, 6) +
        linear(99.1, 97.8, 13) +
        [98.1, 98.4, 98.6]
    )


def feed(engine, values, code='TEST.SZ'):
    alerts = []
    for item in minute_bars(values):
        alert = engine.process(code, item)
        if alert is not None:
            alerts.append(alert)
    return alerts


def test_default_is_atr_normalised_multiscale_macdv():
    config = default_macd_config()
    assert config['fast_period'] == 12
    assert config['slow_period'] == 26
    assert config['signal_period'] == 9
    assert config['atr_period'] == 26
    assert config['warmup_bars'] == 35
    scales = config['scales']
    assert [item['code'] for item in scales] == [
        'MICRO', 'SMALL', 'MEDIUM', 'LARGE']
    assert [item['rank'] for item in scales] == [1, 2, 3, 4]
    assert [item['floor_pct'] for item in scales] == sorted(
        item['floor_pct'] for item in scales)
    bounded = normalize_macd_config({
        'fast_period': 1,
        'slow_period': 2,
        'signal_period': 1,
        'atr_period': 1,
        'warmup_bars': 1,
    })
    assert bounded['fast_period'] == 2
    assert bounded['slow_period'] == 3
    assert bounded['signal_period'] == 2
    assert bounded['atr_period'] == 5
    assert bounded['warmup_bars'] == 5


def test_macdv_formula_and_momentum_lifecycle_are_explicit():
    engine = MacdDivergenceEngine()
    bars = minute_bars(linear(100.0, 103.0, 40))
    for item in bars:
        engine.process('FORMULA.SZ', item)
    record = engine.states['FORMULA.SZ']['records'][-1]
    expected = record['ema_spread'] / record['atr'] * 100.0
    assert abs(record['macdv'] - expected) < 1e-10
    assert _momentum_stage(160, 140)[0] == 'RISK_UP'
    assert _momentum_stage(80, 60)[0] == 'RALLYING'
    assert _momentum_stage(80, 90)[0] == 'RETRACING'
    assert _momentum_stage(0, 10)[0] == 'RANGING'
    assert _momentum_stage(-80, -90)[0] == 'REBOUNDING'
    assert _momentum_stage(-80, -60)[0] == 'REVERSING'
    assert _momentum_stage(-160, -140)[0] == 'RISK_DOWN'


def test_bearish_sequence_upgrades_same_top_to_large_sell_once():
    alerts = feed(
        MacdDivergenceEngine(), bearish_divergence_values(), 'TOP.SZ')
    confirmed = [
        item for item in alerts if item['notification_kind'] == 'CONFIRMED']
    assert len(confirmed) == 1
    alert = confirmed[0]
    assert alert['strategy_version'] == STRATEGY_VERSION
    assert alert['side'] == 'SELL'
    assert alert['turning_point'] == 'TOP'
    assert alert['scale_code'] == 'LARGE'
    assert alert['advice_level'] == 'CONFIRMED'
    assert alert['event_state'] == 'CONFIRMED'
    assert alert['extreme_time'] == '10:31:00'
    assert alert['confirm_time'] == '10:34:00'
    assert alert['leg_amplitude_pct'] > 1.0
    assert alert['reversal_pct'] > alert['scale_threshold_pct']
    assert alert['divergence'] is True
    assert alert['confidence'] >= 78
    revisions = [item for item in alerts if item['event_id'] == alert['event_id']]
    assert len(revisions) >= 2
    assert revisions[-1]['revision'] > revisions[0]['revision']


def test_bullish_sequence_is_a_symmetric_large_buy():
    alerts = feed(
        MacdDivergenceEngine(), bullish_divergence_values(), 'BOTTOM.SZ')
    confirmed = [
        item for item in alerts if item['notification_kind'] == 'CONFIRMED']
    assert len(confirmed) == 1
    alert = confirmed[0]
    assert alert['side'] == 'BUY'
    assert alert['turning_point'] == 'BOTTOM'
    assert alert['scale_code'] == 'LARGE'
    assert alert['advice_level'] == 'CONFIRMED'
    assert alert['divergence_type'] == 'BULLISH_REGULAR'
    assert alert['macdv'] < 0
    assert alert['confidence'] >= 78


def test_scale_and_momentum_can_confirm_without_requiring_divergence():
    engine = MacdDivergenceEngine()
    state = engine._new_state()
    for code in ('MICRO', 'SMALL', 'MEDIUM'):
        state['scales'][code]['mode'] = 'DOWN'
    state['scales']['LARGE']['mode'] = 'UP'
    previous = {'macdv_histogram': 3.0}
    current = {
        'macdv_histogram': -2.0,
        'macdv_slope': -5.0,
        'macdv': 25.0,
    }
    state['records'] = [previous, current]
    primary = {
        'scale': engine.config['scales'][2],
        'threshold_pct': 0.40,
        'leg_amplitude_pct': 1.20,
        'leg_bars': 6,
    }
    result = engine._advice(
        state, 'SELL', primary, current, 60.0, False)
    assert result[0] == 'CONFIRMED'
    assert result[1] is True
    assert result[2] is True
    assert result[5] is True


def test_small_countertrend_and_late_entry_are_downgraded():
    engine = MacdDivergenceEngine()
    state = engine._new_state()
    for code in ('MICRO', 'SMALL'):
        state['scales'][code]['mode'] = 'DOWN'
    for code in ('MEDIUM', 'LARGE'):
        state['scales'][code]['mode'] = 'UP'
    previous = {'macdv_histogram': 2.0}
    current = {
        'macdv_histogram': -2.0,
        'macdv_slope': -4.0,
        'macdv': 20.0,
    }
    state['records'] = [previous, current]
    small = {
        'scale': engine.config['scales'][1],
        'threshold_pct': 0.25,
        'leg_amplitude_pct': 0.80,
        'leg_bars': 4,
    }
    result = engine._advice(state, 'SELL', small, current, 30.0, True)
    assert result[0] == 'WATCH'
    assert result[4] is True
    medium = dict(small, scale=engine.config['scales'][2],
                  leg_amplitude_pct=1.20, leg_bars=6)
    late_record = dict(current, macdv=-80.0)
    state['records'] = [previous, late_record]
    result = engine._advice(
        state, 'SELL', medium, late_record, 60.0, True)
    assert result[0] != 'CONFIRMED'
    assert result[3] is True


def test_alerts_are_deterministic_causal_and_duplicate_bar_is_ignored():
    values = bearish_divergence_values()
    bars = minute_bars(values)
    first = MacdDivergenceEngine()
    first_alerts = []
    for item in bars:
        alert = first.process('REPLAY.SZ', item)
        if alert is not None:
            first_alerts.append(alert)
    assert first.process('REPLAY.SZ', bars[-1]) is None
    second_alerts = feed(MacdDivergenceEngine(), values, 'REPLAY.SZ')
    assert [item['id'] for item in first_alerts] == [
        item['id'] for item in second_alerts]
    assert [item['revision'] for item in first_alerts] == [
        item['revision'] for item in second_alerts]
    assert [item['confirm_time'] for item in first_alerts] == [
        item['confirm_time'] for item in second_alerts]


def test_monotonic_prices_do_not_create_turning_events():
    monotonic = [100.0 + index * 0.04 for index in range(100)]
    assert feed(MacdDivergenceEngine(), monotonic, 'TREND.SZ') == []


def test_new_day_resets_every_scale_and_never_compares_with_yesterday():
    engine = MacdDivergenceEngine()
    assert feed(engine, bearish_divergence_values(), 'DAY.SZ')
    next_day = minute_bars([99.0, 99.1, 99.2], day_offset=1)
    for item in next_day:
        assert engine.process('DAY.SZ', item) is None
    state = engine.states['DAY.SZ']
    assert state['day'] == '2026-08-14'
    assert len(state['records']) == 3
    assert state['event_revisions'] == {}
    for tracker in state['scales'].values():
        assert tracker['events']['TOP'] == []
        assert tracker['events']['BOTTOM'] == []


def main():
    tests = [
        value for name, value in globals().items()
        if name.startswith('test_') and callable(value)
    ]
    for test in tests:
        test()
        print('PASS', test.__name__)
    print('Multiscale MACD-V tests passed: %d' % len(tests))


if __name__ == '__main__':
    main()
