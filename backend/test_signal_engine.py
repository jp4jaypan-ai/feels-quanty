# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import os
import sys
import datetime
import io
import shutil
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import server
from server import (MicroBarAggregator, QuoteDeduper, default_config, normalize_config,
                    parse_wsi_bars)
from macd_divergence import MacdDivergenceEngine
from swing_v3 import DecisionBarAggregator, SwingV3Engine


def test_duplicate_quotes_and_incremental_bar_volume():
    deduper = QuoteDeduper()
    aggregate = MicroBarAggregator()
    quote = {'rt_time': 100000, 'price': 10.0, 'volume_total': 100.0,
             'amount_total': 1000.0, 'vwap': 10.0, 'epoch': 36000}
    assert deduper.is_duplicate('000001.SZ', quote) is False
    aggregate.update('000001.SZ', quote)
    assert deduper.is_duplicate('000001.SZ', quote) is True
    quote2 = dict(quote, rt_time=100001, price=10.1, volume_total=120.0,
                  amount_total=1200.0, epoch=36001)
    assert deduper.is_duplicate('000001.SZ', quote2) is False
    aggregate.update('000001.SZ', quote2)
    quote3 = dict(quote2, rt_time=100030, volume_total=150.0,
                  amount_total=1500.0, epoch=36030)
    event = aggregate.update('000001.SZ', quote3)
    assert event['completed'][0]['volume'] == 20.0
    assert event['completed'][0]['amount'] == 200.0


def test_pct_change_survives_microbar_aggregation():
    aggregate = MicroBarAggregator()
    quote = {'price': 10.0, 'pct_change': 1.0, 'volume_total': 100.0,
             'amount_total': 1000.0, 'vwap': 10.0, 'epoch': 36000}
    event = aggregate.update('000001.SZ', quote)
    assert event['current']['pct_change'] == 1.0
    event = aggregate.update('000001.SZ', dict(
        quote, price=10.1, pct_change=1.25, volume_total=120.0,
        amount_total=1200.0, epoch=36001))
    assert event['current']['pct_change'] == 1.25
    event = aggregate.update('000001.SZ', dict(
        quote, price=10.2, pct_change=1.5, volume_total=150.0,
        amount_total=1500.0, epoch=36030))
    assert event['completed'][0]['pct_change'] == 1.25
    assert event['current']['pct_change'] == 1.5


def test_pre_close_survives_quote_to_completed_microbar():
    aggregate = MicroBarAggregator()
    first = aggregate.update('000001.SZ', {
        'price': 10.0, 'pct_change': 1.0, 'volume_total': 100.0,
        'amount_total': 1000.0, 'vwap': 10.0, 'pre_close': 9.5,
        'epoch': 34200, 'time': '09:30:00',
    })
    assert first['current']['pre_close'] == 9.5
    second = aggregate.update('000001.SZ', {
        'price': 10.1, 'pct_change': 1.1, 'volume_total': 120.0,
        'amount_total': 1200.0, 'vwap': 10.05, 'pre_close': 9.5,
        'epoch': 34230, 'time': '09:30:30',
    })
    assert second['completed'][0]['pre_close'] == 9.5
    decision = DecisionBarAggregator().consume('000001.SZ', second['completed'])
    assert decision == []


class FakeWsiResult(object):
    ErrorCode = 0
    Fields = ['CLOSE', 'AMT', 'OPEN', 'VOLUME', 'LOW', 'HIGH']
    Times = [datetime.datetime(2026, 8, 12, 9, 30), datetime.datetime(2026, 8, 12, 9, 31), datetime.datetime(2026, 8, 12, 9, 32)]
    Data = [
        [10.1, 10.2, 10.3], [1010.0, 1020.0, 1030.0],
        [10.0, 10.1, 10.2], [100.0, 110.0, 120.0],
        [9.9, 10.0, 10.1], [10.2, 10.3, 10.4],
    ]


def test_wsi_field_order_changes_are_normalized_and_incomplete_minute_dropped():
    result = parse_wsi_bars(FakeWsiResult(), pre_close=9.8,
                            end_time=datetime.datetime(2026, 8, 12, 9, 31))
    assert len(result) == 2
    assert result[0]['open'] == 10.0 and result[0]['high'] == 10.2
    assert result[0]['low'] == 9.9 and result[0]['close'] == 10.1
    assert result[0]['volume'] == 100.0 and result[0]['amount'] == 1010.0
    assert result[0]['pre_close'] == 9.8 and result[0]['first_open'] == 10.0
    assert result[-1]['time'] == '09:31:00'


def test_wsi_error_and_empty_data_are_safe_inputs():
    class ErrorResult(object):
        ErrorCode = -1
        Data, Fields, Times = [], [], []
    failed = False
    try:
        parse_wsi_bars(ErrorResult(), pre_close=10.0)
    except RuntimeError:
        failed = True
    assert failed

    class EmptyResult(object):
        ErrorCode = 0
        Data, Fields, Times = [], [], []
    assert parse_wsi_bars(EmptyResult(), pre_close=10.0) == []


def test_new_natural_day_resets_microbar_history_and_cumulative_values():
    aggregate = MicroBarAggregator()
    code = '000001.SZ'
    day_one = server.time.mktime((2026, 8, 11, 14, 59, 0, 0, 0, -1))
    day_two = server.time.mktime((2026, 8, 12, 9, 30, 0, 0, 0, -1))
    quote = {'price': 10.0, 'pct_change': 1.0, 'volume_total': 100.0,
             'amount_total': 1000.0, 'vwap': 10.0, 'epoch': day_one}
    aggregate.update(code, quote)
    previous_day = aggregate.update(code, dict(
        quote, price=10.1, pct_change=1.2, volume_total=120.0,
        amount_total=1200.0, epoch=day_one + 31))
    assert len(previous_day['completed']) == 1
    new_day = aggregate.update(code, dict(
        quote, price=9.8, pct_change=-0.5, volume_total=10.0,
        amount_total=98.0, epoch=day_two))
    assert new_day['completed'] == []
    assert len(new_day['bars']) == 1
    assert new_day['current']['volume'] == 0.0
    assert aggregate.cumulative[code] == {'volume': 10.0, 'amount': 98.0}


def test_v3_config_normalization_and_presets():
    standard = default_config()
    assert standard['strategy_version'] == 'V4.0'
    assert standard['rule_name'] == u'分时顶底策略 V4 候选/确认双层'
    assert standard['sensitivity'] == 'standard'
    assert standard['min_swing_pct'] == 0.45
    assert standard['swing_strategy_enabled'] is True
    assert standard['macd_strategy_enabled'] is True
    assert standard['opening_fast_enabled'] is True
    assert standard['opening_fast_min_bars'] == 2
    assert standard['opening_fast_gap_pct'] == 1.0
    assert standard['opening_fast_min_confidence'] == 85
    assert standard['candidate_alerts_enabled'] is True
    assert standard['candidate_notifications_enabled'] is True
    assert standard['candidate_min_confidence'] == 55
    assert standard['candidate_strengthening_confidence'] == 70
    assert standard['candidate_reversal_fraction'] == 0.35
    assert standard['candidate_strengthening_reversal_fraction'] == 0.55
    assert standard['candidate_ttl_bars'] == 15
    assert standard['opening_candidate_min_bars'] == 1
    assert standard['early_confirm_enabled'] is True
    assert standard['early_confirm_reversal_fraction'] == 0.60
    assert standard['early_confirm_min_evidence'] == 3
    sensitive = normalize_config({'sensitivity': 'sensitive', 'notifications_enabled': 'false'})
    assert sensitive['min_swing_pct'] == 0.30
    assert sensitive['notifications_enabled'] is False
    switches = normalize_config({
        'swing_strategy_enabled': 'false',
        'macd_strategy_enabled': 'true',
    })
    assert switches['swing_strategy_enabled'] is False
    assert switches['macd_strategy_enabled'] is True
    custom = normalize_config({'sensitivity': 'standard', 'reversal_pct': 0.33})
    assert custom['reversal_pct'] == 0.33
    bounded = normalize_config({'opening_fast_min_confidence': 1, 'opening_fast_gap_pct': 99})
    assert bounded['opening_fast_min_confidence'] == 85
    assert bounded['opening_fast_gap_pct'] == 10.0
    bounded = normalize_config({
        'candidate_min_confidence': 90,
        'candidate_strengthening_confidence': 55,
        'candidate_reversal_fraction': 0.90,
        'candidate_strengthening_reversal_fraction': 0.20,
        'candidate_ttl_bars': 1,
        'opening_candidate_min_bars': 9,
        'early_confirm_reversal_fraction': 0.1,
        'early_confirm_min_evidence': 9,
    })
    assert bounded['candidate_strengthening_confidence'] == 90
    assert bounded['candidate_strengthening_reversal_fraction'] == 0.9
    assert bounded['candidate_ttl_bars'] == 3
    assert bounded['opening_candidate_min_bars'] == 5
    assert bounded['early_confirm_reversal_fraction'] == 0.5
    assert bounded['early_confirm_min_evidence'] == 6


def test_monitor_uses_v3_engine_and_decision_aggregator():
    monitor = server.WindMonitor(server.SharedState())
    assert isinstance(monitor.engine, SwingV3Engine)
    assert isinstance(monitor.macd_engine, MacdDivergenceEngine)
    assert isinstance(monitor.decision_aggregator, DecisionBarAggregator)
    assert monitor.state.config['strategy_version'] == 'V4.0'


def test_backfill_warms_engine_without_signal_flow_or_chart_bars():
    monitor = server.WindMonitor(server.SharedState())
    fixed = datetime.datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)

    class FakeWind(object):
        def __init__(self):
            self.calls = []

        def wsi(self, *args):
            self.calls.append(args)
            class Result(object):
                ErrorCode = 0
                Fields = ['OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME', 'AMT']
                Data = [[10.0, 10.1], [10.2, 10.3], [9.9, 10.0],
                        [10.1, 10.2], [100.0, 110.0], [1010.0, 1122.0]]
            result = Result()
            result.Times = [fixed.replace(hour=9, minute=30), fixed.replace(hour=9, minute=31)]
            return result

    original_w, original_latest, original_notify = server.w, server.latest_completed_minute, server.send_notification
    fake = FakeWind()
    notifications = []
    server.w = fake
    server.latest_completed_minute = lambda: fixed
    server.send_notification = lambda *args: notifications.append(args)
    try:
        monitor._backfill_code('000010.SZ', 9.8, default_config())
    finally:
        server.w, server.latest_completed_minute, server.send_notification = original_w, original_latest, original_notify
    assert fake.calls and fake.calls[0][1] == 'open,high,low,close,volume,amt'
    assert monitor.state.signals == []
    assert notifications == []
    assert monitor.state.turning_events == []
    assert '000010.SZ' not in monitor.state.bars
    assert len(monitor.engine.states['000010.SZ']['bars']) == 2
    assert monitor.state.analytics['000010.SZ']['backfill_status'] == 'ok'
    assert monitor.state.analytics['000010.SZ']['backfill_reason'].startswith(u'已回填')
    assert monitor.state.analytics['000010.SZ']['active_turn_event'] is None


def test_backfill_failure_is_recorded_and_does_not_raise():
    monitor = server.WindMonitor(server.SharedState())
    fixed = datetime.datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)

    class ErrorWind(object):
        def wsi(self, *args):
            class Result(object):
                ErrorCode = 9
                Data, Fields, Times = [], [], []
            return Result()

    original_w, original_latest = server.w, server.latest_completed_minute
    server.w, server.latest_completed_minute = ErrorWind(), lambda: fixed
    try:
        monitor._backfill_code('000011.SZ', 9.8, default_config())
    finally:
        server.w, server.latest_completed_minute = original_w, original_latest
    assert monitor.state.analytics['000011.SZ']['backfill_status'] == 'failed'
    assert 'wsi error' in monitor.state.analytics['000011.SZ']['backfill_reason']


def test_backfill_accepts_exactly_one_completed_opening_minute():
    monitor = server.WindMonitor(server.SharedState())
    fixed = datetime.datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)

    class OneMinuteWind(object):
        def __init__(self):
            self.calls = []

        def wsi(self, *args):
            self.calls.append(args)
            class Result(object):
                ErrorCode = 0
                Fields = ['OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME', 'AMT']
                Data = [[10.0], [10.2], [9.9], [10.1], [100.0], [1010.0]]
                Times = [fixed]
            return Result()

    original_w, original_latest = server.w, server.latest_completed_minute
    fake = OneMinuteWind()
    server.w, server.latest_completed_minute = fake, lambda: fixed
    try:
        monitor._backfill_code('000012.SZ', 9.8, default_config())
    finally:
        server.w, server.latest_completed_minute = original_w, original_latest
    assert len(fake.calls) == 1
    assert len(monitor.engine.states['000012.SZ']['bars']) == 1
    assert monitor.state.analytics['000012.SZ']['backfill_status'] == 'ok'


def test_quote_clock_regression_resets_realtime_cursors_before_open():
    monitor = server.WindMonitor(server.SharedState())
    code = '000013.SZ'
    day = datetime.datetime.now().date()
    old_epoch = time.mktime(datetime.datetime.combine(day, datetime.time(15, 0)).timetuple())
    open_epoch = time.mktime(datetime.datetime.combine(day, datetime.time(9, 30)).timetuple())
    monitor.state.quotes[code] = {'epoch': old_epoch}
    monitor.aggregator.current[code] = {'_bucket': old_epoch}
    monitor.decision_aggregator.last_seen[code] = old_epoch
    monitor.deduper.last_keys[code] = ('stale',)
    monitor.engine.states[code] = monitor.engine._new_state()
    monitor.macd_engine.states[code] = monitor.macd_engine._new_state()
    monitor.backfill_days[code] = day
    monitor.state.bars[code] = [{'timestamp': old_epoch}]

    reset = monitor._reset_on_quote_clock_regression(
        code, {'epoch': open_epoch}, default_config())

    assert reset is True
    assert code not in monitor.aggregator.current
    assert code not in monitor.decision_aggregator.last_seen
    assert code not in monitor.deduper.last_keys
    assert code not in monitor.engine.states
    assert code not in monitor.macd_engine.states
    assert code not in monitor.backfill_days
    assert code not in monitor.state.bars


def test_unicode_notification_path_is_preserved():
    assert server.notification_path().lower().endswith('notify_toast.ps1')


def test_server_same_bar_candidate_and_confirmation_only_notifies_confirmation():
    monitor = server.WindMonitor(server.SharedState())
    code = '000099.SZ'
    candidate = {
        'event_id': 'EVT-SAME-BAR', 'code': code, 'revision': 1,
        'event_state': 'CANDIDATE', 'signal_level': 'CANDIDATE',
        'side': 'SELL', 'turning_point': 'TOP', 'extreme_price': 10.5,
        'extreme_time': '10:00:00', 'observed_price': 10.2,
        'observed_time': '10:00:00', 'notification_kind': 'CANDIDATE',
        'strategy_version': 'V4.0',
    }
    confirmed = dict(candidate, revision=2, event_state='CONFIRMED',
                     signal_level='CONFIRMED', notification_kind='CONFIRMED',
                     confirm_price=10.0, confirm_time='10:01:00',
                     confirm_timestamp=1.0, confidence=90)
    decision = {'timestamp': 1.0, 'time': '10:00:00', 'confirm_timestamp': 61.0,
                'confirm_time': '10:01:00', 'open': 10.0, 'high': 10.5,
                'low': 9.9, 'close': 10.0, 'volume': 100.0, 'amount': 1000.0}

    class FakeWind(object):
        def wsq(self, *args):
            class Result(object):
                ErrorCode = 0
                Codes = [code]
                Data = [[10.0], [0.0], [100.0], [1000.0], [10.0], [9.9],
                        [9.8], [10.0], [9.9], [10.1], ['10:00:00']]
            return Result()

    class FakeAggregator(object):
        last_unique_at = {}

        def update(self, item_code, quote):
            return {'bars': [], 'completed': [decision], 'current': {}, 'issues': []}

    class FakeDecisionAggregator(object):
        def consume(self, item_code, completed):
            return list(completed)

    class FakeEngine(object):
        def __init__(self):
            self.drained = False

        def process(self, item_code, item, item_config):
            return {'candidate_alerts_enabled': True}, dict(confirmed)

        def drain_event_updates(self, item_code):
            if self.drained:
                return []
            self.drained = True
            return [dict(candidate), dict(confirmed)]

        def mark_stale(self, analytics, item_config):
            return analytics

        def reset_code(self, item_code):
            return None

    original_w = server.w
    original_send = server.send_notification
    original_backfill = monitor._backfill_before_realtime
    monitor.engine = FakeEngine()
    monitor.aggregator = FakeAggregator()
    monitor.decision_aggregator = FakeDecisionAggregator()
    notifications = []
    server.w = FakeWind()
    server.send_notification = lambda *args: notifications.append(args)
    monitor._backfill_before_realtime = lambda item_code, quote, item_config: None
    try:
        monitor.poll([code], default_config())
    finally:
        server.w = original_w
        server.send_notification = original_send
        monitor._backfill_before_realtime = original_backfill
    assert len(notifications) == 1
    assert notifications[0][2] == 'Confirmed'
    assert monitor.state.turning_events[0]['event_state'] == 'CONFIRMED'
    assert len(monitor.state.signals) == 1


def test_server_macd_divergence_notifies_and_enters_its_own_frontend_stream():
    monitor = server.WindMonitor(server.SharedState())
    code = '000098.SZ'
    timestamp = server.quote_epoch('10:00:00')
    decision = {
        'timestamp': timestamp,
        'time': '10:00:00',
        'confirm_timestamp': timestamp + 60.0,
        'confirm_time': '10:01:00',
        'open': 10.0,
        'high': 10.2,
        'low': 9.9,
        'close': 10.0,
        'volume': 100.0,
        'amount': 1000.0,
    }
    macd_alert = {
        'id': 'MACD-SELL-TEST',
        'event_id': 'MACD-SELL-TEST',
        'revision': 1,
        'strategy_version': server.MACD_STRATEGY_VERSION,
        'notification_kind': 'CONFIRMED',
        'code': code,
        'side': 'SELL',
        'module_label': u'中级顶部确认',
        'scale_label': u'中级',
        'scale_threshold_pct': 0.65,
        'leg_amplitude_pct': 1.80,
        'leg_bars': 8,
        'consensus_pct': 60.0,
        'macdv': 42.0,
        'momentum_stage_label': u'上行动能回落',
        'extreme_price': 10.2,
        'extreme_time': '09:58:00',
        'price_delta_pct': 0.25,
        'dif_slope_pct_per_bar': -0.01234,
        'confirm_time': '10:01:00',
        'confirm_price': 10.0,
        'confidence': 82,
    }

    class FakeWind(object):
        def wsq(self, *args):
            class Result(object):
                ErrorCode = 0
                Codes = [code]
                Data = [[10.0], [0.0], [100.0], [1000.0], [10.2], [9.9],
                        [9.8], [10.0], [9.9], [10.1], ['10:00:00']]
            return Result()

    class FakeAggregator(object):
        last_unique_at = {}

        def update(self, item_code, quote):
            return {
                'bars': [],
                'completed': [decision],
                'current': {},
                'issues': [],
            }

    class FakeDecisionAggregator(object):
        def consume(self, item_code, completed):
            return list(completed)

    class FakeSwingEngine(object):
        def process(self, item_code, item, item_config):
            return {'candidate_alerts_enabled': True}, None

        def drain_event_updates(self, item_code):
            return []

        def mark_stale(self, analytics, item_config):
            return analytics

        def reset_code(self, item_code):
            return None

    class FakeMacdEngine(object):
        def __init__(self):
            self.sent = False

        def process(self, item_code, item):
            if self.sent:
                return None
            self.sent = True
            return dict(macd_alert)

        def reset_code(self, item_code):
            return None

    original_w = server.w
    original_send = server.send_notification
    original_backfill = monitor._backfill_before_realtime
    monitor.engine = FakeSwingEngine()
    monitor.macd_engine = FakeMacdEngine()
    monitor.aggregator = FakeAggregator()
    monitor.decision_aggregator = FakeDecisionAggregator()
    notifications = []
    server.w = FakeWind()
    server.send_notification = lambda *args: notifications.append(args)
    monitor._backfill_before_realtime = lambda item_code, quote, item_config: None
    try:
        monitor.poll([code], default_config())
    finally:
        server.w = original_w
        server.send_notification = original_send
        monitor._backfill_before_realtime = original_backfill
    assert len(notifications) == 1
    assert u'中级顶部确认' in notifications[0][0]
    assert u'卖出建议' in notifications[0][0]
    assert notifications[0][2] == 'Confirmed'
    assert monitor.state.signals == []
    assert monitor.state.turning_events == []
    assert monitor.state.macd_alerts[0]['id'] == 'MACD-SELL-TEST'
    assert monitor.state.snapshot()['macd_alerts'][0]['id'] == 'MACD-SELL-TEST'


def test_strategy_switches_gate_streams_and_notifications_but_keep_engines_warm():
    code = '000097.SZ'
    timestamp = server.quote_epoch('10:00:00')
    decision = {
        'timestamp': timestamp,
        'time': '10:00:00',
        'confirm_timestamp': timestamp + 60.0,
        'confirm_time': '10:01:00',
        'open': 10.0,
        'high': 10.2,
        'low': 9.9,
        'close': 10.0,
        'volume': 100.0,
        'amount': 1000.0,
    }
    swing_signal = {
        'id': 901,
        'event_id': 'SWING-SELL-TEST',
        'code': code,
        'side': 'SELL',
    }
    swing_update = {
        'event_id': 'SWING-SELL-TEST',
        'revision': 1,
        'event_state': 'CONFIRMED',
        'signal_level': 'CONFIRMED',
        'notification_kind': 'CONFIRMED',
        'code': code,
        'side': 'SELL',
        'extreme_price': 10.2,
        'extreme_time': '09:59:00',
        'extreme_timestamp': timestamp - 60.0,
        'observed_price': 10.0,
        'observed_timestamp': timestamp,
        'updated_timestamp': timestamp,
        'confirm_price': 10.0,
        'confirm_time': '10:00:00',
        'confidence': 82,
    }
    macd_alert = {
        'id': 'MACD-SELL-SWITCH-TEST',
        'event_id': 'MACD-SELL-SWITCH-TEST',
        'revision': 1,
        'strategy_version': server.MACD_STRATEGY_VERSION,
        'notification_kind': 'CONFIRMED',
        'code': code,
        'side': 'SELL',
        'module_label': u'中级顶部确认',
        'scale_label': u'中级',
        'scale_threshold_pct': 0.65,
        'leg_amplitude_pct': 1.80,
        'leg_bars': 8,
        'consensus_pct': 60.0,
        'macdv': 42.0,
        'momentum_stage_label': u'上行动能回落',
        'extreme_price': 10.2,
        'extreme_time': '09:58:00',
        'price_delta_pct': 0.25,
        'dif_slope_pct_per_bar': -0.01234,
        'confirm_time': '10:01:00',
        'confirm_price': 10.0,
        'confidence': 82,
    }

    class FakeWind(object):
        def wsq(self, *args):
            class Result(object):
                ErrorCode = 0
                Codes = [code]
                Data = [[10.0], [0.0], [100.0], [1000.0], [10.2], [9.9],
                        [9.8], [10.0], [9.9], [10.1], ['10:00:00']]
            return Result()

    class FakeAggregator(object):
        last_unique_at = {}

        def update(self, item_code, quote):
            return {
                'bars': [],
                'completed': [decision],
                'current': {},
                'issues': [],
            }

    class FakeDecisionAggregator(object):
        def consume(self, item_code, completed):
            return list(completed)

    class FakeSwingEngine(object):
        def __init__(self):
            self.processed = 0

        def process(self, item_code, item, item_config):
            self.processed += 1
            return {'candidate_alerts_enabled': True}, dict(swing_signal)

        def drain_event_updates(self, item_code):
            return [dict(swing_update)]

        def mark_stale(self, analytics, item_config):
            return analytics

        def reset_code(self, item_code):
            return None

    class FakeMacdEngine(object):
        def __init__(self, notification_kind='CONFIRMED'):
            self.processed = 0
            self.notification_kind = notification_kind

        def process(self, item_code, item):
            self.processed += 1
            result = dict(macd_alert)
            result['notification_kind'] = self.notification_kind
            return result

        def reset_code(self, item_code):
            return None

    def run_case(swing_enabled, macd_enabled, macd_notification_kind='CONFIRMED'):
        monitor = server.WindMonitor(server.SharedState())
        monitor.engine = FakeSwingEngine()
        monitor.macd_engine = FakeMacdEngine(macd_notification_kind)
        monitor.aggregator = FakeAggregator()
        monitor.decision_aggregator = FakeDecisionAggregator()
        monitor._backfill_before_realtime = (
            lambda item_code, quote, item_config: None)
        notifications = []
        original_w = server.w
        original_send = server.send_notification
        server.w = FakeWind()
        server.send_notification = lambda *args: notifications.append(args)
        config = dict(
            default_config(),
            swing_strategy_enabled=swing_enabled,
            macd_strategy_enabled=macd_enabled,
        )
        try:
            monitor.poll([code], config)
        finally:
            server.w = original_w
            server.send_notification = original_send
        return monitor, notifications

    disabled, notifications = run_case(False, False)
    assert disabled.engine.processed == 1
    assert disabled.macd_engine.processed == 1
    assert disabled.state.signals == []
    assert disabled.state.turning_events == []
    assert disabled.state.macd_alerts == []
    assert notifications == []

    swing_only, notifications = run_case(True, False)
    assert len(swing_only.state.signals) == 1
    assert len(swing_only.state.turning_events) == 1
    assert swing_only.state.macd_alerts == []
    assert len(notifications) == 1

    macd_only, notifications = run_case(False, True)
    assert macd_only.state.signals == []
    assert macd_only.state.turning_events == []
    assert len(macd_only.state.macd_alerts) == 1
    assert len(notifications) == 1

    combined, notifications = run_case(True, True)
    assert len(combined.state.signals) == 1
    assert len(combined.state.turning_events) == 1
    assert len(combined.state.macd_alerts) == 1
    assert len(notifications) == 2

    observation, notifications = run_case(False, True, 'NONE')
    assert len(observation.state.macd_alerts) == 1
    assert notifications == []


def cache_decision_bar(day, minute_index, close):
    moment = datetime.datetime.combine(
        day, datetime.time(9, 30)) + datetime.timedelta(minutes=minute_index)
    timestamp = time.mktime(moment.timetuple())
    return {
        'timestamp': timestamp,
        'time': moment.strftime('%H:%M:%S'),
        'confirm_timestamp': timestamp + 60.0,
        'confirm_time': datetime.datetime.fromtimestamp(
            timestamp + 60.0).strftime('%H:%M:%S'),
        'open': close - 0.02,
        'high': close + 0.05,
        'low': close - 0.05,
        'close': close,
        'volume': 100.0 + minute_index,
        'amount': (100.0 + minute_index) * close,
        'vwap': close,
        'pct_change': 0.0,
        'pre_close': 9.8,
        'first_open': 10.0,
        'opening_gap_pct': (10.0 - 9.8) / 9.8 * 100.0,
        'micro_bars': [],
    }


def cache_micro_bar(day, seconds_offset, close):
    moment = datetime.datetime.combine(
        day, datetime.time(9, 30)) + datetime.timedelta(seconds=seconds_offset)
    timestamp = time.mktime(moment.timetuple())
    return {
        'timestamp': timestamp,
        'time': moment.strftime('%H:%M:%S'),
        'open': close,
        'high': close + 0.02,
        'low': close - 0.02,
        'close': close,
        'volume': 50.0,
        'amount': close * 50.0,
        'vwap': close,
        'pct_change': 0.0,
        'pre_close': 9.8,
        'first_open': 10.0,
        'opening_gap_pct': (10.0 - 9.8) / 9.8 * 100.0,
    }


def test_intraday_cache_round_trip_and_corrupt_fallback():
    root = tempfile.mkdtemp(prefix='quant-cache-')
    path = os.path.join(root, 'intraday.json')
    day = datetime.date(2026, 8, 13)
    cache = server.IntradayCache(path, today_provider=lambda: day)
    code = '000020.SZ'
    try:
        payload = {
            'codes': [code],
            'config': dict(default_config(), rule_name=u'\u4e2d\u6587\u7f13\u5b58'),
            'micro_bars': {code: [cache_micro_bar(day, 0, 10.0)]},
            'decision_bars': {code: [cache_decision_bar(day, 0, 10.0)]},
            'signals': [{'code': code, 'id': 1}],
            'turning_events': [{'code': code, 'event_id': 'EVT-CACHE'}],
            'macd_alerts': [{'code': code, 'id': 'MACD-CACHE'}],
        }
        assert cache.save(payload) is True
        assert os.path.exists(path)
        assert [name for name in os.listdir(root) if '.tmp-' in name] == []
        loaded = cache.load()
        assert cache.status == 'loaded'
        assert loaded['codes'] == [code]
        assert loaded['config']['rule_name'] == u'\u4e2d\u6587\u7f13\u5b58'
        assert len(loaded['micro_bars'][code]) == 1
        assert len(loaded['decision_bars'][code]) == 1
        assert loaded['macd_alerts'][0]['id'] == 'MACD-CACHE'
        with io.open(path, 'w', encoding='utf-8') as handle:
            handle.write(u'{broken json')
        fallback = cache.load()
        assert cache.status == 'corrupt'
        assert cache.last_error
        assert fallback['decision_bars'] == {}
        assert fallback['signals'] == []
        assert fallback['macd_alerts'] == []
    finally:
        shutil.rmtree(root)


def test_intraday_cache_new_day_keeps_settings_but_drops_market_state():
    root = tempfile.mkdtemp(prefix='quant-cache-day-')
    path = os.path.join(root, 'intraday.json')
    day_one = datetime.date(2026, 8, 12)
    day_two = datetime.date(2026, 8, 13)
    code = '000021.SZ'
    try:
        writer = server.IntradayCache(path, today_provider=lambda: day_one)
        assert writer.save({
            'codes': [code],
            'config': dict(default_config(), sensitivity='sensitive'),
            'micro_bars': {code: [cache_micro_bar(day_one, 0, 10.0)]},
            'decision_bars': {code: [cache_decision_bar(day_one, 0, 10.0)]},
            'signals': [{'code': code, 'id': 1}],
            'turning_events': [{'code': code, 'event_id': 'EVT-YESTERDAY'}],
            'macd_alerts': [{'code': code, 'id': 'MACD-YESTERDAY'}],
        })
        reader = server.IntradayCache(path, today_provider=lambda: day_two)
        loaded = reader.load()
        assert reader.status == 'new_day'
        assert loaded['codes'] == [code]
        assert loaded['config']['sensitivity'] == 'sensitive'
        assert loaded['micro_bars'] == {}
        assert loaded['decision_bars'] == {}
        assert loaded['signals'] == []
        assert loaded['turning_events'] == []
        assert loaded['macd_alerts'] == []
    finally:
        shutil.rmtree(root)


def test_monitor_restart_replays_cache_without_notifications_or_warmup():
    root = tempfile.mkdtemp(prefix='quant-cache-replay-')
    path = os.path.join(root, 'intraday.json')
    day = datetime.date.today()
    code = '000022.SZ'
    decisions = [
        cache_decision_bar(day, index, 10.0 + index * 0.05)
        for index in range(8)
    ]
    micros = [
        cache_micro_bar(day, index * 30, 10.0 + index * 0.01)
        for index in range(8)
    ]
    cache = server.IntradayCache(path, today_provider=lambda: day)
    original_notify = server.send_notification
    notifications = []
    try:
        assert cache.save({
            'codes': [code],
            'config': default_config(),
            'micro_bars': {code: micros},
            'decision_bars': {code: decisions},
            'signals': [{'code': code, 'id': 'RESTORED-SIGNAL'}],
            'macd_alerts': [
                {'code': code, 'id': 'RESTORED-MACD',
                 'strategy_version': server.MACD_STRATEGY_VERSION},
                {'code': code, 'id': 'LEGACY-MACD',
                 'strategy_version': 'MACD-DIV-1.0'},
            ],
            'turning_events': [
                {'code': code, 'event_id': 'RESTORED-EVENT',
                 'event_state': 'CONFIRMED'},
                {'code': code, 'event_id': 'STALE-CANDIDATE',
                 'event_state': 'CANDIDATE'},
            ],
        })
        payload = cache.load()
        state = server.SharedState()
        monitor = server.WindMonitor(state, cache)
        server.send_notification = lambda *args: notifications.append(args)
        monitor.restore_cache(payload)
        assert len(monitor.engine.states[code]['bars']) == 8
        assert len(monitor.macd_engine.states[code]['records']) == 8
        assert state.macd_alerts[0]['id'] == 'RESTORED-MACD'
        assert state.analytics[code]['ready'] is True
        assert state.analytics[code]['warmup_progress'] == 100
        assert state.analytics[code]['backfill_status'] == 'cache'
        assert u'\u65e0\u9700\u9884\u70ed' in state.analytics[code]['backfill_reason']
        assert len(state.bars[code]) == len(micros)
        assert state.signals[0]['id'] == 'RESTORED-SIGNAL'
        assert state.turning_events[0]['event_id'] == 'RESTORED-EVENT'
        assert len(state.turning_events) == 1
        assert state.cache_status == 'loaded'
        assert notifications == []
    finally:
        server.send_notification = original_notify
        shutil.rmtree(root)


def test_fresh_cache_skips_wsi_entirely():
    code = '000023.SZ'
    fixed = datetime.datetime.combine(datetime.date.today(), datetime.time(10, 0))
    minute_index = int((fixed - datetime.datetime.combine(
        fixed.date(), datetime.time(9, 30))).total_seconds() // 60)
    decision = cache_decision_bar(fixed.date(), minute_index, 10.0)
    monitor = server.WindMonitor(server.SharedState())
    monitor.restore_cache({
        'codes': [code],
        'config': default_config(),
        'decision_bars': {code: [decision]},
    })

    class NoWsiWind(object):
        def __init__(self):
            self.calls = []

        def wsi(self, *args):
            self.calls.append(args)
            raise AssertionError('fresh cache must not call WSI')

    original_w, original_latest = server.w, server.latest_completed_minute
    fake = NoWsiWind()
    server.w, server.latest_completed_minute = fake, lambda: fixed
    try:
        monitor._backfill_code(code, 9.8, default_config())
    finally:
        server.w, server.latest_completed_minute = original_w, original_latest
    assert fake.calls == []
    assert len(monitor.engine.states[code]['bars']) == 1
    assert monitor.state.analytics[code]['backfill_status'] == 'cache'
    assert 'WSI' in monitor.state.analytics[code]['backfill_reason']


def test_cached_tail_only_fetches_and_replays_missing_wsi_minutes():
    code = '000024.SZ'
    day = datetime.date.today()
    fixed = datetime.datetime.combine(day, datetime.time(9, 33))
    cached = [
        cache_decision_bar(day, 0, 10.0),
        cache_decision_bar(day, 1, 10.1),
    ]
    monitor = server.WindMonitor(server.SharedState())
    monitor.restore_cache({
        'codes': [code],
        'config': default_config(),
        'decision_bars': {code: cached},
    })

    class GapWind(object):
        def __init__(self):
            self.calls = []

        def wsi(self, *args):
            self.calls.append(args)
            class Result(object):
                ErrorCode = 0
                Fields = ['OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME', 'AMT']
                Data = [
                    [10.1, 10.2], [10.3, 10.4], [10.0, 10.1],
                    [10.2, 10.3], [120.0, 130.0], [1224.0, 1339.0],
                ]
                Times = [
                    datetime.datetime.combine(day, datetime.time(9, 32)),
                    datetime.datetime.combine(day, datetime.time(9, 33)),
                ]
            return Result()

    original_w, original_latest = server.w, server.latest_completed_minute
    fake = GapWind()
    server.w, server.latest_completed_minute = fake, lambda: fixed
    try:
        monitor._backfill_code(code, 9.8, default_config())
    finally:
        server.w, server.latest_completed_minute = original_w, original_latest
    assert len(fake.calls) == 1
    assert fake.calls[0][2].endswith('09:32:00')
    assert len(monitor.engine.states[code]['bars']) == 4
    assert len(monitor.decision_history[code]) == 4
    assert len(set(item['timestamp'] for item in monitor.decision_history[code])) == 4
    assert monitor.state.analytics[code]['backfill_status'] == 'ok'
    assert 'WSI' in monitor.state.analytics[code]['backfill_reason']


def main():
    tests = [value for name, value in globals().items() if name.startswith('test_')]
    for test in tests:
        test()
        print('PASS', test.__name__)
    print('backend integration tests passed: %d' % len(tests))


if __name__ == '__main__':
    main()
