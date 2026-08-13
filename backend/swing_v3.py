# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import datetime
import copy
import time

try:
    string_types = (basestring,)
except NameError:
    string_types = (str, bytes)


PHASE_LABELS = {
    'BOOTSTRAP': u'寻找有效波段',
    'TRACKING_UP': u'跟踪上涨候选顶',
    'TRACKING_DOWN': u'跟踪下跌候选底',
}

SENSITIVITY_PRESETS = {
    'sensitive': {
        'min_swing_pct': 0.30, 'min_swing_range_mult': 0.90,
        'reversal_pct': 0.20, 'reversal_range_mult': 0.35,
        'min_leg_bars': 2, 'min_confidence': 65,
    },
    'standard': {
        'min_swing_pct': 0.45, 'min_swing_range_mult': 1.20,
        'reversal_pct': 0.28, 'reversal_range_mult': 0.45,
        'min_leg_bars': 3, 'min_confidence': 70,
    },
    'robust': {
        'min_swing_pct': 0.65, 'min_swing_range_mult': 1.50,
        'reversal_pct': 0.38, 'reversal_range_mult': 0.60,
        'min_leg_bars': 4, 'min_confidence': 78,
    },
}


def number(value, default=None):
    try:
        value = float(value)
        if value != value or value in (float('inf'), float('-inf')):
            return default
        return value
    except (TypeError, ValueError):
        return default


def clean(value, digits=6):
    value = number(value)
    return None if value is None else round(value, digits)


def median(values):
    values = sorted([number(value) for value in values if number(value) is not None])
    if not values:
        return 0.0
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return (values[middle - 1] + values[middle]) / 2.0


def time_seconds(text):
    try:
        hour, minute, second = [int(part) for part in text.split(':')[:3]]
        return hour * 3600 + minute * 60 + second
    except (AttributeError, TypeError, ValueError):
        return None


def timestamp_text(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')


def day_key(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')


def default_config(sensitivity='standard'):
    key = sensitivity if sensitivity in SENSITIVITY_PRESETS else 'standard'
    config = {
        'strategy_version': 'V4.0',
        'rule_name': u'分时顶底策略 V4 候选/确认双层',
        'sensitivity': key,
        'warmup_bars': 6,
        'opening_guard_minutes': 5,
        'cooldown_seconds': 120,
        'notifications_enabled': True,
        'swing_strategy_enabled': True,
        'macd_strategy_enabled': True,
        'opening_fast_enabled': True,
        'opening_fast_window_minutes': 5,
        'opening_fast_min_bars': 2,
        'opening_fast_gap_pct': 1.00,
        'opening_fast_min_swing_pct': 0.80,
        'opening_fast_swing_range_mult': 1.80,
        'opening_fast_reversal_pct': 0.35,
        'opening_fast_reversal_range_mult': 0.70,
        'opening_fast_min_confidence': 85,
        'candidate_alerts_enabled': True,
        'candidate_notifications_enabled': True,
        'candidate_min_confidence': 55,
        'candidate_strengthening_confidence': 70,
        'candidate_reversal_fraction': 0.35,
        'candidate_strengthening_reversal_fraction': 0.55,
        'candidate_ttl_bars': 15,
        'opening_candidate_min_bars': 1,
        'early_confirm_enabled': True,
        'early_confirm_reversal_fraction': 0.60,
        'early_confirm_min_evidence': 3,
    }
    config.update(SENSITIVITY_PRESETS[key])
    return config


def as_bool(value, default=True):
    if isinstance(value, string_types):
        lowered = value.strip().lower()
        if lowered in ('false', '0', 'off', 'no'):
            return False
        if lowered in ('true', '1', 'on', 'yes'):
            return True
    return default if value is None else bool(value)


def normalize_config(payload):
    payload = payload if isinstance(payload, dict) else {}
    sensitivity = payload.get('sensitivity', 'standard')
    config = default_config(sensitivity)

    def bounded(key, low, high, integer=False):
        value = number(payload.get(key), config[key])
        value = min(high, max(low, value))
        return int(value) if integer else round(value, 3)

    config['min_swing_pct'] = bounded('min_swing_pct', 0.05, 5.0)
    config['min_swing_range_mult'] = bounded('min_swing_range_mult', 0.1, 5.0)
    config['reversal_pct'] = bounded('reversal_pct', 0.05, 3.0)
    config['reversal_range_mult'] = bounded('reversal_range_mult', 0.1, 3.0)
    config['min_leg_bars'] = bounded('min_leg_bars', 2, 20, True)
    config['min_confidence'] = bounded('min_confidence', 50, 100, True)
    config['warmup_bars'] = bounded('warmup_bars', 4, 30, True)
    config['opening_guard_minutes'] = bounded('opening_guard_minutes', 0, 30, True)
    config['cooldown_seconds'] = bounded('cooldown_seconds', 0, 3600, True)
    config['notifications_enabled'] = as_bool(payload.get('notifications_enabled'), True)
    config['swing_strategy_enabled'] = as_bool(
        payload.get('swing_strategy_enabled'), True)
    config['macd_strategy_enabled'] = as_bool(
        payload.get('macd_strategy_enabled'), True)
    config['opening_fast_enabled'] = as_bool(payload.get('opening_fast_enabled'), True)
    config['opening_fast_window_minutes'] = bounded('opening_fast_window_minutes', 1, 15, True)
    config['opening_fast_min_bars'] = bounded('opening_fast_min_bars', 2, 10, True)
    config['opening_fast_gap_pct'] = bounded('opening_fast_gap_pct', 0.1, 10.0)
    config['opening_fast_min_swing_pct'] = bounded('opening_fast_min_swing_pct', 0.1, 10.0)
    config['opening_fast_swing_range_mult'] = bounded('opening_fast_swing_range_mult', 0.1, 10.0)
    config['opening_fast_reversal_pct'] = bounded('opening_fast_reversal_pct', 0.05, 5.0)
    config['opening_fast_reversal_range_mult'] = bounded('opening_fast_reversal_range_mult', 0.1, 5.0)
    config['opening_fast_min_confidence'] = bounded('opening_fast_min_confidence', 85, 100, True)
    config['candidate_alerts_enabled'] = as_bool(payload.get('candidate_alerts_enabled'), True)
    config['candidate_notifications_enabled'] = as_bool(payload.get('candidate_notifications_enabled'), True)
    config['candidate_min_confidence'] = bounded('candidate_min_confidence', 50, 90, True)
    config['candidate_strengthening_confidence'] = bounded('candidate_strengthening_confidence', 55, 95, True)
    config['candidate_strengthening_confidence'] = max(
        config['candidate_min_confidence'], config['candidate_strengthening_confidence'])
    config['candidate_reversal_fraction'] = bounded('candidate_reversal_fraction', 0.10, 0.90)
    config['candidate_strengthening_reversal_fraction'] = bounded(
        'candidate_strengthening_reversal_fraction', 0.20, 1.00)
    config['candidate_strengthening_reversal_fraction'] = max(
        config['candidate_reversal_fraction'], config['candidate_strengthening_reversal_fraction'])
    config['candidate_ttl_bars'] = bounded('candidate_ttl_bars', 3, 60, True)
    config['opening_candidate_min_bars'] = bounded('opening_candidate_min_bars', 1, 5, True)
    config['early_confirm_enabled'] = as_bool(payload.get('early_confirm_enabled'), True)
    config['early_confirm_reversal_fraction'] = bounded(
        'early_confirm_reversal_fraction', 0.50, 1.00)
    config['early_confirm_min_evidence'] = bounded(
        'early_confirm_min_evidence', 2, 6, True)
    return config


def true_range(bar, previous_close=None):
    high, low = number(bar.get('high')), number(bar.get('low'))
    if high is None or low is None:
        return 0.0
    if previous_close is None:
        return max(0.0, high - low)
    return max(0.0, high - low, abs(high - previous_close), abs(low - previous_close))


class DecisionBarAggregator(object):
    """Causally combines completed 30-second bars into completed 60-second bars."""

    def __init__(self):
        self.current = {}
        self.last_seen = {}

    def reset(self, code=None):
        if code is None:
            self.current, self.last_seen = {}, {}
        else:
            self.current.pop(code, None)
            self.last_seen.pop(code, None)

    def consume(self, code, completed_micro_bars):
        produced = []
        for source in sorted(list(completed_micro_bars or []), key=lambda item: item.get('timestamp', 0)):
            timestamp = number(source.get('timestamp'))
            if timestamp is None or timestamp <= self.last_seen.get(code, -1):
                continue
            previous_seen = self.last_seen.get(code)
            if previous_seen is not None and (
                    day_key(previous_seen) != day_key(timestamp) or timestamp - previous_seen > 120):
                # Never finalize a half-built minute across an overnight or
                # session/data gap; the swing engine will reset on the next
                # completed decision bar.
                self.current.pop(code, None)
            self.last_seen[code] = timestamp
            bucket = int(timestamp // 60) * 60
            current = self.current.get(code)
            if current is not None and current['_bucket'] != bucket:
                if current['_parts'] >= 2 and 0 in current['_offsets'] and 30 in current['_offsets']:
                    produced.append(self.public(current))
                current = None
            if current is None:
                current = {
                    '_bucket': bucket, '_parts': 0, '_offsets': set(),
                    '_micro_bars': [],
                    'timestamp': float(bucket), 'time': timestamp_text(bucket),
                    'open': source.get('open'), 'high': source.get('high'),
                    'low': source.get('low'), 'close': source.get('close'),
                    'vwap': source.get('vwap'), 'volume': 0.0, 'amount': 0.0,
                    'pct_change': source.get('pct_change'),
                    'pre_close': source.get('pre_close'),
                    'first_open': source.get('first_open'),
                    'opening_gap_pct': source.get('opening_gap_pct'),
                }
                self.current[code] = current
            current['_micro_bars'].append({
                'timestamp': timestamp,
                'time': source.get('time') or timestamp_text(timestamp),
                'open': clean(source.get('open')),
                'high': clean(source.get('high')),
                'low': clean(source.get('low')),
                'close': clean(source.get('close')),
                'volume': clean(source.get('volume'), 3),
            })
            current['_parts'] += 1
            current['_offsets'].add(int(timestamp) % 60)
            current['high'] = max(number(current.get('high'), -float('inf')), number(source.get('high'), -float('inf')))
            current['low'] = min(number(current.get('low'), float('inf')), number(source.get('low'), float('inf')))
            current['close'] = source.get('close')
            current['vwap'] = source.get('vwap') if source.get('vwap') is not None else current.get('vwap')
            if source.get('pre_close') is not None:
                current['pre_close'] = source.get('pre_close')
            if source.get('first_open') is not None:
                current['first_open'] = source.get('first_open')
            if source.get('opening_gap_pct') is not None:
                current['opening_gap_pct'] = source.get('opening_gap_pct')
            current['volume'] += number(source.get('volume'), 0.0)
            current['amount'] += number(source.get('amount'), 0.0)
            current['pct_change'] = source.get('pct_change')
            # A :30 micro bar completes the physical minute at its end.
            if int(timestamp) % 60 >= 30:
                if current['_parts'] >= 2 and 0 in current['_offsets'] and 30 in current['_offsets']:
                    produced.append(self.public(current))
                self.current.pop(code, None)
        return produced

    def public(self, bar):
        timestamp = number(bar.get('timestamp'), 0.0)
        return {
            'timestamp': timestamp,
            'time': bar.get('time') or timestamp_text(timestamp),
            'confirm_timestamp': timestamp + 60.0,
            'confirm_time': timestamp_text(timestamp + 60.0),
            'open': clean(bar.get('open')), 'high': clean(bar.get('high')),
            'low': clean(bar.get('low')), 'close': clean(bar.get('close')),
            'vwap': clean(bar.get('vwap')), 'volume': clean(bar.get('volume'), 3),
            'amount': clean(bar.get('amount'), 3),
            'pct_change': clean(bar.get('pct_change')), 'parts': bar.get('_parts', 0),
            'pre_close': clean(bar.get('pre_close'), 4),
            'first_open': clean(bar.get('first_open'), 4),
            'opening_gap_pct': clean(bar.get('opening_gap_pct'), 4),
            'micro_bars': copy.deepcopy(bar.get('_micro_bars') or []),
        }


class SwingV3Engine(object):
    def __init__(self):
        self.states = {}
        self.next_id = int(time.time() * 1000)
        self.next_event_id = int(time.time() * 1000)
        self.event_updates = {}
        self.max_event_updates = 200

    def reset_code(self, code):
        self.states.pop(code, None)
        self.event_updates.pop(code, None)

    def drain_event_updates(self, code):
        updates = list(self.event_updates.get(code, []))
        self.event_updates[code] = []
        return updates

    def discard_event_state(self, code):
        state = self.states.get(code)
        self.event_updates.pop(code, None)
        if state is None:
            return
        state['active_turn_events'] = {'SELL': None, 'BUY': None}
        state['active_turn_event'] = None
        state['last_turn_event'] = None
        state['turn_event_extreme_indices'] = {}
        state['invalidated_extremes'] = {}

    def _new_event_id(self):
        self.next_event_id += 1
        return 'EVT-%d' % self.next_event_id

    def _queue_event(self, event):
        updates = self.event_updates.setdefault(event.get('code'), [])
        updates.append(copy.deepcopy(event))
        if len(updates) > self.max_event_updates:
            del updates[:-self.max_event_updates]

    def _new_state(self):
        return {
            'phase': 'BOOTSTRAP', 'bars': [], 'day': None,
            'anchor_low': None, 'anchor_low_time': None, 'anchor_low_timestamp': None, 'anchor_low_index': None,
            'anchor_high': None, 'anchor_high_time': None, 'anchor_high_timestamp': None, 'anchor_high_index': None,
            'leg_start_price': None, 'leg_start_time': None, 'leg_start_timestamp': None,
            'leg_start_index': None,
            'candidate_price': None, 'candidate_time': None, 'candidate_timestamp': None,
            'candidate_close': None, 'candidate_bar': None, 'candidate_index': None,
            'last_signal_side': None, 'last_signal_at': None,
            'last_signal_channel': None, 'last_signal_pattern': None,
            'first_open': None, 'pre_close': None, 'opening_gap_pct': None,
            'opening_bars': [], 'opening_fast_signal_emitted': False,
            'opening_fast_signal_at': None, 'backfill_status': 'not_run',
            'backfill_reason': None,
            'active_turn_events': {'SELL': None, 'BUY': None},
            'active_turn_event': None, 'last_turn_event': None,
            'turn_event_extreme_indices': {}, 'invalidated_extremes': {},
        }

    def _reset_market_structure(self, state, keep_last_signal=True):
        last_signal = dict((key, state.get(key)) for key in (
            'last_signal_side', 'last_signal_at',
            'last_signal_channel', 'last_signal_pattern'))
        last_turn_event = copy.deepcopy(state.get('last_turn_event'))
        fresh = self._new_state()
        if keep_last_signal:
            fresh.update(last_signal)
        fresh['last_turn_event'] = last_turn_event
        state.clear()
        state.update(fresh)

    def _prepare_bar(self, bar):
        prepared = dict(bar or {})
        for key in ('open', 'high', 'low', 'close', 'vwap', 'volume', 'amount', 'pct_change',
                    'timestamp', 'confirm_timestamp', 'pre_close', 'first_open',
                    'opening_gap_pct'):
            if key in prepared:
                prepared[key] = number(prepared.get(key))
        timestamp = prepared.get('timestamp')
        if timestamp is None:
            raise ValueError('decision bar timestamp is required')
        prepared['time'] = prepared.get('time') or timestamp_text(timestamp)
        prepared['confirm_timestamp'] = prepared.get('confirm_timestamp') or timestamp + 60.0
        prepared['confirm_time'] = prepared.get('confirm_time') or timestamp_text(prepared['confirm_timestamp'])
        micro_bars = []
        for raw_micro in prepared.get('micro_bars') or []:
            micro = dict(raw_micro or {})
            for key in ('timestamp', 'open', 'high', 'low', 'close', 'volume'):
                if key in micro:
                    micro[key] = number(micro.get(key))
            if None in (micro.get('timestamp'), micro.get('open'), micro.get('high'),
                        micro.get('low'), micro.get('close')):
                continue
            micro['time'] = micro.get('time') or timestamp_text(micro['timestamp'])
            micro_bars.append(micro)
        prepared['micro_bars'] = sorted(
            micro_bars, key=lambda item: item.get('timestamp', 0))[-2:]
        if prepared.get('opening_gap_pct') is None and prepared.get('first_open') is not None and prepared.get('pre_close'):
            prepared['opening_gap_pct'] = (prepared['first_open'] - prepared['pre_close']) / prepared['pre_close'] * 100.0
        if None in (prepared.get('open'), prepared.get('high'), prepared.get('low'), prepared.get('close')):
            raise ValueError('decision bar OHLC is required')
        return prepared

    def _robust_range(self, bars):
        ranges, previous = [], None
        for item in bars[-10:]:
            ranges.append(true_range(item, previous))
            previous = item.get('close')
        return median([value for value in ranges if value > 0])

    def _thresholds(self, reference_price, robust_range, config):
        min_swing = max(reference_price * config['min_swing_pct'] / 100.0,
                        robust_range * config['min_swing_range_mult'])
        reversal = max(reference_price * config['reversal_pct'] / 100.0,
                       robust_range * config['reversal_range_mult'])
        return min_swing, reversal

    def _session_reason(self, bar, config):
        seconds = time_seconds(bar.get('time'))
        if seconds is None:
            return None
        if 41400 <= seconds < 46800:
            return u'午间休市，波段状态已重置'
        if seconds < 34200 or seconds >= 54000:
            return u'当前不在可提醒交易时段'
        if seconds < 34200 + config['opening_guard_minutes'] * 60:
            return u'开盘保护期内，仅积累分时结构'
        return None

    def _update_bootstrap_extremes(self, state, bar, index):
        if state['anchor_low'] is None or bar['low'] <= state['anchor_low']:
            state['anchor_low'] = bar['low']
            state['anchor_low_time'] = bar['time']
            state['anchor_low_timestamp'] = bar['timestamp']
            state['anchor_low_index'] = index
        if state['anchor_high'] is None or bar['high'] >= state['anchor_high']:
            state['anchor_high'] = bar['high']
            state['anchor_high_time'] = bar['time']
            state['anchor_high_timestamp'] = bar['timestamp']
            state['anchor_high_index'] = index

    def _start_leg_if_ready(self, state, bar, index, robust_range, config):
        upward = state['anchor_high'] - state['anchor_low']
        down_start = state['anchor_high']
        up_start = state['anchor_low']
        up_bars = index - state['anchor_low_index'] + 1
        down_bars = index - state['anchor_high_index'] + 1
        up_threshold, _ = self._thresholds(up_start, robust_range, config)
        down_threshold, _ = self._thresholds(down_start, robust_range, config)
        if upward >= up_threshold and up_bars >= config['min_leg_bars'] and state['anchor_high_index'] >= state['anchor_low_index']:
            state['phase'] = 'TRACKING_UP'
            state['leg_start_price'], state['leg_start_time'], state['leg_start_timestamp'] = (
                state['anchor_low'], state['anchor_low_time'], state['anchor_low_timestamp'])
            state['leg_start_index'] = state['anchor_low_index']
            state['candidate_price'], state['candidate_time'], state['candidate_timestamp'] = (
                state['anchor_high'], state['anchor_high_time'], state['anchor_high_timestamp'])
            state['candidate_index'] = state['anchor_high_index']
            candidate_bar = state['bars'][state['candidate_index']]
            state['candidate_close'], state['candidate_bar'] = candidate_bar['close'], dict(candidate_bar)
            return
        if upward >= down_threshold and down_bars >= config['min_leg_bars'] and state['anchor_low_index'] >= state['anchor_high_index']:
            state['phase'] = 'TRACKING_DOWN'
            state['leg_start_price'], state['leg_start_time'], state['leg_start_timestamp'] = (
                state['anchor_high'], state['anchor_high_time'], state['anchor_high_timestamp'])
            state['leg_start_index'] = state['anchor_high_index']
            state['candidate_price'], state['candidate_time'], state['candidate_timestamp'] = (
                state['anchor_low'], state['anchor_low_time'], state['anchor_low_timestamp'])
            state['candidate_index'] = state['anchor_low_index']
            candidate_bar = state['bars'][state['candidate_index']]
            state['candidate_close'], state['candidate_bar'] = candidate_bar['close'], dict(candidate_bar)

    def _volume_ratio(self, state, bar):
        baseline = median([item.get('volume') for item in state['bars'][-11:-1] if number(item.get('volume'), 0) > 0])
        return number(bar.get('volume'), 0.0) / baseline if baseline > 0 else 0.0

    def _top_score(self, state, bar, min_swing, reversal, robust_range):
        candidate = state['candidate_bar'] or bar
        full_range = max(candidate['high'] - candidate['low'], 0.000001)
        upper_wick = candidate['high'] - max(candidate['open'], candidate['close'])
        rejection = candidate['close'] <= candidate['low'] + full_range * 0.35 or upper_wick >= full_range * 0.25
        previous = state['bars'][-2] if len(state['bars']) >= 2 else None
        structure = previous is not None and bar['close'] < previous['low']
        momentum = previous is not None and bar['close'] < previous['close']
        volume_ratio = max(self._volume_ratio(state, candidate), self._volume_ratio(state, bar))
        confirmations = [u'上涨波段幅度达到自适应门槛', u'从候选峰值回撤达到确认阈值']
        score = 55
        if rejection:
            score += 15; confirmations.append(u'峰值K线出现冲高回落')
        if structure:
            score += 15; confirmations.append(u'收盘跌破前一根分时低点')
        if momentum:
            score += 10; confirmations.append(u'短线动量由强转弱')
        if volume_ratio >= 1.2:
            score += 5; confirmations.append(u'峰值或反转量能放大 %.2fx' % volume_ratio)
        return min(100, score), confirmations, rejection, structure, momentum, volume_ratio

    def _bottom_score(self, state, bar, min_swing, reversal, robust_range):
        candidate = state['candidate_bar'] or bar
        full_range = max(candidate['high'] - candidate['low'], 0.000001)
        lower_wick = min(candidate['open'], candidate['close']) - candidate['low']
        rejection = candidate['close'] >= candidate['high'] - full_range * 0.35 or lower_wick >= full_range * 0.25
        previous = state['bars'][-2] if len(state['bars']) >= 2 else None
        structure = previous is not None and bar['close'] > previous['high']
        momentum = previous is not None and bar['close'] > previous['close']
        volume_ratio = max(self._volume_ratio(state, candidate), self._volume_ratio(state, bar))
        confirmations = [u'下跌波段幅度达到自适应门槛', u'从候选谷值反弹达到确认阈值']
        score = 55
        if rejection:
            score += 15; confirmations.append(u'谷值K线出现杀跌回收')
        if structure:
            score += 15; confirmations.append(u'收盘突破前一根分时高点')
        if momentum:
            score += 10; confirmations.append(u'短线动量由弱转强')
        if volume_ratio >= 1.2:
            score += 5; confirmations.append(u'谷值或反转量能放大 %.2fx' % volume_ratio)
        return min(100, score), confirmations, rejection, structure, momentum, volume_ratio

    def _candidate_rejection(self, side, candidate_bar):
        full_range = max(candidate_bar['high'] - candidate_bar['low'], 0.000001)
        if side == 'SELL':
            wick = candidate_bar['high'] - max(candidate_bar['open'], candidate_bar['close'])
            return (candidate_bar['close'] <= candidate_bar['low'] + full_range * 0.35 or
                    (wick >= full_range * 0.25 and candidate_bar['close'] <= candidate_bar['open']))
        wick = min(candidate_bar['open'], candidate_bar['close']) - candidate_bar['low']
        return (candidate_bar['close'] >= candidate_bar['high'] - full_range * 0.35 or
                (wick >= full_range * 0.25 and candidate_bar['close'] >= candidate_bar['open']))

    def _candidate_metrics(self, state, bar, side, min_swing, reversal, index,
                           config, swing_abs=None, swing_credit=None):
        candidate = state['candidate_bar'] or bar
        previous = state['bars'][-2] if len(state['bars']) >= 2 else None
        top = side == 'SELL'
        if swing_abs is None:
            swing_abs = ((state['candidate_price'] - state['leg_start_price']) if top else
                         (state['leg_start_price'] - state['candidate_price']))
        leg_bars = index - state['leg_start_index'] + 1
        reversal_abs = ((state['candidate_price'] - bar['close']) if top else
                        (bar['close'] - state['candidate_price']))
        reversal_progress = (reversal_abs / reversal) if reversal else 0.0
        rejection = self._candidate_rejection(side, candidate)
        momentum = (previous is not None and
                    ((top and bar['close'] < previous['close']) or
                     ((not top) and bar['close'] > previous['close'])))
        structure = (previous is not None and
                     ((top and bar['close'] < previous['low']) or
                      ((not top) and bar['close'] > previous['high'])))
        volume_ratio = max(self._volume_ratio(state, candidate), self._volume_ratio(state, bar))
        # The fractional reversal gate is deliberately measured against the
        # existing full confirmation threshold, not against a future bar.
        reversal_evidence = (reversal_progress >= config['candidate_reversal_fraction'] and
                             state.get('candidate_index') is not None and
                             index > state.get('candidate_index'))
        swing_ok = (leg_bars >= config['min_leg_bars'] and
                    swing_abs >= min_swing)
        if swing_credit is not None:
            swing_ok = bool(swing_credit)
        score = 40
        confirmations = []
        if swing_ok:
            score += 10
            confirmations.append(u'波段幅度和完整K根数达到候选门槛')
        if rejection:
            score += 15
            confirmations.append(u'极值K线出现拒绝形态')
        if momentum:
            score += 10
            confirmations.append(u'当前收盘反向于上一分钟收盘')
        if reversal_evidence:
            score += 10
            confirmations.append(u'反转进度达到候选比例 %.0f%%' % (
                config['candidate_reversal_fraction'] * 100.0))
        if structure:
            score += 10
            confirmations.append(u'收盘突破上一分钟结构高低点')
        if volume_ratio >= 1.2:
            score += 5
            confirmations.append(u'极值或当前量比达到 %.2fx' % volume_ratio)
        evidence_count = sum(1 for item in (rejection, momentum, reversal_evidence,
                                            structure, volume_ratio >= 1.2) if item)
        return {
            'score': min(100, score), 'confirmations': confirmations,
            'rejection': rejection, 'momentum': momentum,
            'reversal_evidence': reversal_evidence, 'structure': structure,
            'volume_ratio': volume_ratio, 'evidence_count': evidence_count,
            'reversal_progress': reversal_progress, 'reversal_abs': reversal_abs,
            'swing_abs': swing_abs, 'leg_bars': leg_bars, 'swing_ok': swing_ok,
            'early_ok': bool(rejection or momentum or reversal_evidence),
        }

    def _micro_reversal_evidence(self, bar, side, reversal, candidate_price):
        parts = list(bar.get('micro_bars') or [])
        if len(parts) < 2:
            return None
        first, second = parts[-2], parts[-1]
        first_close = number(first.get('close'))
        second_close = number(second.get('close'))
        if first_close is None or second_close is None:
            return None
        top = side == 'SELL'
        directional = second_close < first_close if top else second_close > first_close
        move = first_close - second_close if top else second_close - first_close
        meaningful = move >= max(number(reversal, 0.0) * 0.20, 0.000001)
        if directional and meaningful:
            return {
                'kind': 'SEQUENCE',
                'move': move,
                'first_time': first.get('time'),
                'second_time': second.get('time'),
            }

        final_high = number(second.get('high'))
        final_low = number(second.get('low'))
        final_range = max(number(final_high, 0.0) - number(final_low, 0.0), 0.000001)
        candidate_price = number(candidate_price)
        if candidate_price is None or final_high is None or final_low is None:
            return None
        tolerance = max(abs(candidate_price) * 0.000001, 0.000001)
        contains_extreme = (
            abs(final_high - candidate_price) <= tolerance if top
            else abs(final_low - candidate_price) <= tolerance)
        reclaimed = candidate_price - second_close if top else second_close - candidate_price
        closes_away = (
            second_close <= final_low + final_range * 0.20 if top
            else second_close >= final_high - final_range * 0.20)
        if (contains_extreme and closes_away and
                reclaimed >= max(number(reversal, 0.0) * 0.20, 0.000001)):
            return {
                'kind': 'EXTREME_RECLAIM',
                'move': reclaimed,
                'first_time': first.get('time'),
                'second_time': second.get('time'),
            }
        return None

    def _accelerated_confirmation(self, state, bar, side, metrics, min_swing,
                                  reversal, swing_abs, leg_bars, config,
                                  cooldown_ok):
        if not config.get('early_confirm_enabled', True) or not cooldown_ok:
            return None
        progress = max(0.0, number(metrics.get('reversal_progress'), 0.0))
        fraction = config['early_confirm_reversal_fraction']
        if progress < fraction:
            return None
        micro = self._micro_reversal_evidence(
            bar, side, reversal, state.get('candidate_price'))
        if micro is None:
            return None
        rapid_reclaim = micro['kind'] == 'EXTREME_RECLAIM' and leg_bars <= 2
        early_min_bars = 2 if rapid_reclaim else max(2, int(config['min_leg_bars']) - 1)
        if leg_bars < early_min_bars or swing_abs < min_swing:
            return None
        volume_ok = number(metrics.get('volume_ratio'), 0.0) >= 1.2
        evidence_flags = (
            bool(metrics.get('rejection')),
            bool(metrics.get('momentum')),
            bool(metrics.get('structure')),
            volume_ok,
            True,  # completed 30-second evidence shows sequence reversal or strict reclaim
            True,  # the partial reversal reached the accelerated threshold
            rapid_reclaim,
        )
        evidence_count = sum(1 for matched in evidence_flags if matched)
        if evidence_count < config['early_confirm_min_evidence']:
            return None

        top = side == 'SELL'
        confirmations = [
            u'%s波段幅度达到自适应门槛' % (u'上涨' if top else u'下跌'),
            (u'最后一根30秒子K在极值处形成严格%s'
             if micro['kind'] == 'EXTREME_RECLAIM'
             else u'连续两根30秒子K形成%s收盘') % (
                 u'冲高回落' if top else u'杀跌回收'),
            u'反转达到完整确认阈值的 %.0f%%，触发加速确认' % (progress * 100.0),
        ]
        # Full swing maturity contributes 55 points, while the two causal
        # acceleration gates (fractional reversal + two micro-bar sequence)
        # contribute 10 points each. A third independent evidence item is
        # still required below, so the gates alone can never confirm a turn.
        score = 75
        if leg_bars < config['min_leg_bars']:
            confirmations.append(u'强反转证据允许少等待1根完整分钟K')
        if metrics.get('rejection'):
            score += 10
            confirmations.append(u'极值K线出现拒绝形态')
        if metrics.get('structure'):
            score += 10
            confirmations.append(u'收盘突破上一分钟结构高低点')
        if metrics.get('momentum'):
            score += 5
            confirmations.append(u'短线动量已经反向')
        if volume_ok:
            score += 5
            confirmations.append(u'极值或反转量能放大 %.2fx' % metrics['volume_ratio'])
        if rapid_reclaim:
            score += 5
            confirmations.append(u'快速波段在2根分钟K内完成极值回收')
        if progress >= 0.80:
            score += 5
        score = min(100, score)
        if score < config['min_confidence']:
            return None
        return {
            'score': score,
            'confirmations': confirmations,
            'evidence_count': evidence_count,
            'reversal_progress': progress,
            'micro_move': micro['move'],
        }

    def _active_candidate_event(self, state, side):
        event = (state.get('active_turn_events') or {}).get(side)
        if event and event.get('event_state') in ('CANDIDATE', 'STRENGTHENING'):
            return event
        return None

    def _event_rationale(self, event, state):
        top = event.get('side') == 'SELL'
        state_label = event.get('event_state')
        evidence = event.get('confirmations') or []
        evidence_text = u'、'.join(evidence) if evidence else u'等待更多反转证据'
        return (u'%s%s %.2f，事件状态 %s，置信度 %d；%s。'
                u'仅作分时提醒，请结合人工判断。') % (
                    u'峰值' if top else u'谷值',
                    u'候选' if state_label != 'CONFIRMED' else u'确认',
                    event.get('extreme_price') or event.get('observed_price') or 0.0,
                    state_label, int(event.get('confidence') or 0), evidence_text)

    def _set_event_observation(self, event, bar):
        event['updated_time'] = bar.get('confirm_time') or bar.get('time')
        event['updated_timestamp'] = bar.get('confirm_timestamp') or bar.get('timestamp')
        event['timestamp'] = event['updated_timestamp']
        event['time'] = event['updated_time']
        event['observed_price'] = clean(bar.get('close'), 4)
        event['observed_time'] = bar.get('confirm_time') or bar.get('time')
        event['observed_timestamp'] = bar.get('confirm_timestamp') or bar.get('timestamp')

    def _clear_confirmed_active_event(self, state, side):
        active_events = state.setdefault('active_turn_events', {'SELL': None, 'BUY': None})
        active_events[side] = None
        other_side = 'BUY' if side == 'SELL' else 'SELL'
        state['active_turn_event'] = self._active_candidate_event(state, other_side)

    def _new_turn_event(self, code, state, bar, config, side, score,
                        confirmations, channel, pattern, index, extreme_bar=None,
                        confirmed=False, notification_kind='NONE'):
        extreme_bar = extreme_bar or (state.get('candidate_bar') or bar)
        top = side == 'SELL'
        observation_time = bar.get('confirm_time') or bar.get('time')
        observation_timestamp = bar.get('confirm_timestamp') or bar.get('timestamp')
        event = {
            'event_id': self._new_event_id(), 'code': code, 'revision': 1,
            'event_state': 'CONFIRMED' if confirmed else 'CANDIDATE',
            'signal_level': 'CONFIRMED' if confirmed else 'CANDIDATE',
            'side': side, 'turning_point': 'TOP' if top else 'BOTTOM',
            'created_time': observation_time, 'created_timestamp': observation_timestamp,
            'updated_time': bar.get('confirm_time') or bar.get('time'),
            'updated_timestamp': bar.get('confirm_timestamp') or bar.get('timestamp'),
            'extreme_price': clean(extreme_bar.get('high' if top else 'low'), 4),
            'extreme_time': extreme_bar.get('time'),
            'extreme_timestamp': extreme_bar.get('timestamp'),
            'observed_price': clean(bar.get('close'), 4),
            'observed_time': observation_time, 'observed_timestamp': observation_timestamp,
            'confirm_price': clean(bar.get('close'), 4) if confirmed else None,
            'confirm_time': bar.get('confirm_time') if confirmed else None,
            'confirm_timestamp': bar.get('confirm_timestamp') if confirmed else None,
            'confidence': int(score), 'confirmations': list(confirmations or []),
            'rationale': None, 'channel': channel,
            'channel_label': u'开盘强信号' if channel == 'OPENING_FAST' else u'常规波段',
            'pattern': pattern if confirmed else 'EARLY_REVERSAL_WATCH',
            'notification_kind': notification_kind,
            'strategy_version': config['strategy_version'],
            'timestamp': bar.get('confirm_timestamp') or bar.get('timestamp'),
            'time': bar.get('confirm_time') or bar.get('time'),
            'reason': None,
        }
        event['rationale'] = self._event_rationale(event, state)
        if confirmed:
            state['last_turn_event'] = copy.deepcopy(event)
            state.setdefault('turn_event_extreme_indices', {}).pop(side, None)
            self._clear_confirmed_active_event(state, side)
        else:
            state.setdefault('active_turn_events', {'SELL': None, 'BUY': None})[side] = event
            state['active_turn_event'] = event
            state.setdefault('turn_event_extreme_indices', {})[side] = index
        self._queue_event(event)
        return event

    def _touch_turn_event(self, state, event, bar, config, score, confirmations,
                          index, event_state=None, pattern=None,
                          notification_kind='NONE', extreme_bar=None,
                          confirmed=False, reason=None):
        event['revision'] = int(event.get('revision') or 0) + 1
        if event_state is not None:
            event['event_state'] = event_state
        event['signal_level'] = 'CONFIRMED' if confirmed else 'CANDIDATE'
        if pattern is not None:
            event['pattern'] = pattern
        event['confidence'] = int(score)
        event['confirmations'] = list(confirmations or [])
        event['notification_kind'] = notification_kind
        event['reason'] = reason
        self._set_event_observation(event, bar)
        if extreme_bar is not None:
            top = event.get('side') == 'SELL'
            event['extreme_price'] = clean(extreme_bar.get('high' if top else 'low'), 4)
            event['extreme_time'] = extreme_bar.get('time')
            event['extreme_timestamp'] = extreme_bar.get('timestamp')
            state.setdefault('turn_event_extreme_indices', {})[event['side']] = index
        if confirmed:
            event['confirm_price'] = clean(bar.get('close'), 4)
            event['confirm_time'] = bar.get('confirm_time')
            event['confirm_timestamp'] = bar.get('confirm_timestamp')
        else:
            event['confirm_price'] = None
            event['confirm_time'] = None
            event['confirm_timestamp'] = None
        event['rationale'] = self._event_rationale(event, state)
        if confirmed:
            state['last_turn_event'] = copy.deepcopy(event)
            state.setdefault('turn_event_extreme_indices', {}).pop(event['side'], None)
            self._clear_confirmed_active_event(state, event['side'])
        else:
            state.setdefault('active_turn_events', {'SELL': None, 'BUY': None})[event['side']] = event
            state['active_turn_event'] = event
        self._queue_event(event)
        return event

    def _invalidate_turn_event(self, state, side, bar, reason):
        event = self._active_candidate_event(state, side)
        if event is None:
            return None
        event['revision'] = int(event.get('revision') or 0) + 1
        event['event_state'] = 'INVALIDATED'
        event['signal_level'] = 'CANDIDATE'
        event['notification_kind'] = 'NONE'
        event['reason'] = reason
        self._set_event_observation(event, bar)
        event['confirm_price'] = None
        event['confirm_time'] = None
        event['confirm_timestamp'] = None
        event['rationale'] = self._event_rationale(event, state)
        state.setdefault('invalidated_extremes', {})[side] = event.get('extreme_price')
        state.setdefault('active_turn_events', {'SELL': None, 'BUY': None})[side] = None
        state.setdefault('turn_event_extreme_indices', {}).pop(side, None)
        self._clear_confirmed_active_event(state, side)
        state['last_turn_event'] = copy.deepcopy(event)
        self._queue_event(event)
        return event

    def _invalidate_active_turn_events(self, state, bar, reason):
        invalidated = []
        for side in ('SELL', 'BUY'):
            event = self._invalidate_turn_event(state, side, bar, reason)
            if event is not None:
                invalidated.append(event)
        return invalidated

    def _can_build_after_invalidation(self, state, side, current_price=None):
        blocked = (state.get('invalidated_extremes') or {}).get(side)
        current = state.get('candidate_price') if current_price is None else current_price
        if blocked is None or current is None:
            return True
        return current > blocked if side == 'SELL' else current < blocked

    def _maybe_update_candidate_event(self, code, state, bar, config, side,
                                      metrics, channel, index, extreme_updated=False,
                                      extreme_bar=None, extreme_index=None):
        if not config.get('candidate_alerts_enabled', True):
            return None
        event_index = index if extreme_index is None else extreme_index
        event_extreme_bar = extreme_bar or state.get('candidate_bar') or bar
        event = self._active_candidate_event(state, side)
        if event is not None:
            strengthening = (metrics['score'] >= config['candidate_strengthening_confidence'] and
                             metrics['reversal_progress'] >= config['candidate_strengthening_reversal_fraction'] and
                             metrics['evidence_count'] >= 2)
            next_state = 'CANDIDATE' if extreme_updated else ('STRENGTHENING' if strengthening else 'CANDIDATE')
            return self._touch_turn_event(
                state, event, bar, config, metrics['score'], metrics['confirmations'], event_index,
                event_state=next_state, notification_kind='NONE',
                extreme_bar=event_extreme_bar if extreme_updated else None)
        if (not metrics['swing_ok'] or not metrics['early_ok'] or
                metrics['score'] < config['candidate_min_confidence'] or
                not self._can_build_after_invalidation(
                    state, side,
                    event_extreme_bar.get('high' if side == 'SELL' else 'low'))):
            return None
        return self._new_turn_event(
            code, state, bar, config, side, metrics['score'], metrics['confirmations'],
            channel, 'EARLY_REVERSAL_WATCH', event_index,
            extreme_bar=event_extreme_bar,
            confirmed=False, notification_kind='CANDIDATE')

    def _expire_candidate_if_needed(self, state, side, index, bar, config):
        event = self._active_candidate_event(state, side)
        if event is None:
            return None
        extreme_index = (state.get('turn_event_extreme_indices') or {}).get(side)
        if extreme_index is None or index - extreme_index < config['candidate_ttl_bars']:
            return None
        return self._invalidate_turn_event(
            state, side, bar,
            u'候选自最近极值起已超过 %d 根完整 60 秒K，未完成确认' % config['candidate_ttl_bars'])

    def _update_tracking_extreme(self, state, bar, index, side):
        top = side == 'SELL'
        price_key = 'high' if top else 'low'
        value = bar[price_key]
        current = state.get('candidate_price')
        if current is not None and (value < current if top else value > current):
            return False
        extreme_updated = current is None or (value > current if top else value < current)
        state['candidate_price'] = value
        state['candidate_time'] = bar['time']
        state['candidate_timestamp'] = bar['timestamp']
        state['candidate_index'] = index
        state['candidate_close'] = bar['close']
        state['candidate_bar'] = dict(bar)
        return extreme_updated

    def _opening_candidate_metrics(self, state, bar, opening, candidate_bar,
                                   candidate_position, side, fast_swing, config):
        top = side == 'SELL'
        prior_bars = opening[:candidate_position]
        context_prices = [number(state.get('first_open'))]
        if top:
            context_prices.extend(number(item.get('low')) for item in prior_bars)
        else:
            context_prices.extend(number(item.get('high')) for item in prior_bars)
        context_prices = [value for value in context_prices if value is not None]
        if top:
            prior_impulse = (candidate_bar['high'] - min(context_prices)
                             if context_prices and prior_bars else 0.0)
            reversal_abs = candidate_bar['high'] - bar['close']
            gap_context = (number(state.get('opening_gap_pct')) is not None and
                           state['opening_gap_pct'] >= config['opening_fast_gap_pct'])
        else:
            prior_impulse = (max(context_prices) - candidate_bar['low']
                             if context_prices and prior_bars else 0.0)
            reversal_abs = bar['close'] - candidate_bar['low']
            gap_context = (number(state.get('opening_gap_pct')) is not None and
                           state['opening_gap_pct'] <= -config['opening_fast_gap_pct'])
        context_ok = bool(gap_context or prior_impulse >= fast_swing * 0.65)
        min_bars = config['opening_candidate_min_bars']
        if number(state.get('pre_close')) is None and not gap_context:
            min_bars = max(2, min_bars)
        enough_bars = len(opening) >= min_bars
        full_range = max(candidate_bar['high'] - candidate_bar['low'], 0.000001)
        if top:
            wick = candidate_bar['high'] - max(candidate_bar['open'], candidate_bar['close'])
            rejection = (candidate_bar['close'] <= candidate_bar['low'] + full_range * 0.35 or
                         (wick >= full_range * 0.25 and candidate_bar['close'] <= candidate_bar['open']))
            momentum = (len(opening) >= 2 and bar['close'] < opening[-2]['close'])
            structure = (len(opening) >= 2 and bar['close'] < opening[-2]['low'])
        else:
            wick = min(candidate_bar['open'], candidate_bar['close']) - candidate_bar['low']
            rejection = (candidate_bar['close'] >= candidate_bar['high'] - full_range * 0.35 or
                         (wick >= full_range * 0.25 and candidate_bar['close'] >= candidate_bar['open']))
            momentum = (len(opening) >= 2 and bar['close'] > opening[-2]['close'])
            structure = (len(opening) >= 2 and bar['close'] > opening[-2]['high'])
        reversal_threshold = max(
            candidate_bar['high' if top else 'low'] * config['opening_fast_reversal_pct'] / 100.0,
            self._robust_range(state['bars']) * config['opening_fast_reversal_range_mult'])
        reversal_evidence = (reversal_abs >= reversal_threshold * config['candidate_reversal_fraction'] and
                             candidate_position < len(opening) - 1)
        volume_ratio = max(self._volume_ratio(state, candidate_bar), self._volume_ratio(state, bar))
        score = 40
        confirmations = []
        if context_ok:
            score += 10
            confirmations.append(u'开盘跳空或先行脉冲达到候选上下文')
        if rejection:
            score += 15
            confirmations.append(u'开盘极值K线出现拒绝形态')
        if momentum:
            score += 10
            confirmations.append(u'开盘当前收盘出现反向动量')
        if reversal_evidence:
            score += 10
            confirmations.append(u'开盘极值反转达到 %.0f%% 快速反转阈值' % (
                config['candidate_reversal_fraction'] * 100.0))
        if structure:
            score += 10
            confirmations.append(u'开盘结构突破上一根K线')
        if volume_ratio >= 1.2:
            score += 5
            confirmations.append(u'开盘极值或当前量比达到 %.2fx' % volume_ratio)
        evidence_count = sum(1 for item in (rejection, momentum, reversal_evidence,
                                            structure, volume_ratio >= 1.2) if item)
        return {
            'score': min(100, score), 'confirmations': confirmations,
            'swing_ok': context_ok, 'early_ok': bool(rejection or momentum or reversal_evidence),
            'evidence_count': evidence_count,
            'reversal_progress': (reversal_abs / reversal_threshold if reversal_threshold else 0.0),
            'enough_bars': enough_bars, 'context_ok': context_ok,
            'rejection': rejection, 'momentum': momentum,
            'reversal_evidence': reversal_evidence, 'structure': structure,
            'volume_ratio': volume_ratio, 'swing_abs': prior_impulse,
            'reversal_abs': reversal_abs, 'leg_bars': len(opening),
        }

    def _process_opening_candidate(self, code, state, bar, index, config, robust_range):
        seconds = time_seconds(bar.get('time'))
        window_end = 34200 + config['opening_fast_window_minutes'] * 60
        if (not config.get('opening_fast_enabled', True) or seconds is None or
                seconds < 34200 or seconds >= window_end):
            return
        opening = state.get('opening_bars') or []
        fast_swing, reference = self._opening_fast_thresholds(state, config, robust_range)
        if fast_swing is None:
            return
        candidates = [
            ('SELL', max(opening, key=lambda item: item['high'])) if opening else None,
            ('BUY', min(opening, key=lambda item: item['low'])) if opening else None,
        ]
        for item in candidates:
            if item is None:
                continue
            side, candidate_bar = item
            candidate_position = opening.index(candidate_bar)
            metrics = self._opening_candidate_metrics(
                state, bar, opening, candidate_bar, candidate_position, side,
                fast_swing, config)
            if not metrics['enough_bars'] or not metrics['context_ok'] or not metrics['early_ok']:
                continue
            old_event = self._active_candidate_event(state, side)
            old_extreme = old_event.get('extreme_price') if old_event else None
            candidate_index = max(0, index - len(opening) + candidate_position)
            current_extreme = candidate_bar['high' if side == 'SELL' else 'low']
            extreme_updated = (old_extreme is None or
                               (current_extreme > old_extreme if side == 'SELL' else
                                current_extreme < old_extreme))
            self._maybe_update_candidate_event(
                code, state, bar, config, side, metrics, 'OPENING_FAST',
                candidate_index, extreme_updated,
                extreme_bar=candidate_bar, extreme_index=candidate_index)

    def _opening_fast_thresholds(self, state, config, robust_range):
        reference = number(state.get('pre_close')) or number(state.get('first_open'))
        if reference is None or reference <= 0:
            return None, None
        swing_abs = max(reference * config['opening_fast_min_swing_pct'] / 100.0,
                        robust_range * config['opening_fast_swing_range_mult'])
        return swing_abs, reference

    def _opening_fast_score(self, state, bar, candidate_bar, candidate_index,
                            current_index, swing_abs, reversal_abs,
                            reversal_threshold, side, gap_context):
        top = side == 'SELL'
        full_range = max(candidate_bar['high'] - candidate_bar['low'], 0.000001)
        if top:
            wick = candidate_bar['high'] - max(candidate_bar['open'], candidate_bar['close'])
            rejection = (wick >= full_range * 0.25 or
                         candidate_bar['close'] <= candidate_bar['low'] + full_range * 0.35)
        else:
            wick = min(candidate_bar['open'], candidate_bar['close']) - candidate_bar['low']
            rejection = (wick >= full_range * 0.25 or
                         candidate_bar['close'] >= candidate_bar['high'] - full_range * 0.35)
        score = 65
        confirmations = [
            u'开盘强波段达到自适应门槛',
            u'候选%s回撤达到开盘反转门槛' % (u'峰值' if top else u'谷值'),
        ]
        if gap_context:
            score += 10
            confirmations.append(u'开盘跳空方向与反转方向一致')
        if rejection:
            score += 10
            confirmations.append(u'候选极值K线出现明显拒绝形态')
        if reversal_abs >= reversal_threshold * 1.35:
            score += 5
            confirmations.append(u'实际反转达到阈值 1.35 倍')
        if swing_abs >= max(0.000001, state.get('_fast_swing_threshold', swing_abs)) * 1.25:
            score += 5
            confirmations.append(u'实际波段达到阈值 1.25 倍')
        reverse_closes = 0
        previous = None
        for item in state.get('opening_bars', []):
            if item.get('timestamp') <= candidate_bar.get('timestamp'):
                previous = item
                continue
            if previous is not None:
                if (top and item['close'] < previous['close']) or ((not top) and item['close'] > previous['close']):
                    reverse_closes += 1
                else:
                    reverse_closes = 0
            previous = item
        stronger_break = (candidate_index < current_index and
                          ((top and bar['close'] < candidate_bar['low']) or
                           ((not top) and bar['close'] > candidate_bar['high'])))
        if reverse_closes >= 2 or stronger_break:
            score += 5
            confirmations.append(u'极值后连续反向收盘或更强结构破位')
        return min(100, score), confirmations, rejection

    def _set_fast_tracking_state(self, state, bar, index, side, candidate_bar, candidate_index):
        candidate_price = candidate_bar['high'] if side == 'SELL' else candidate_bar['low']
        state['phase'] = 'TRACKING_UP' if side == 'SELL' else 'TRACKING_DOWN'
        state['leg_start_price'] = state.get('first_open') or candidate_bar['open']
        state['leg_start_time'] = state['opening_bars'][0].get('time') if state.get('opening_bars') else bar['time']
        state['leg_start_timestamp'] = state['opening_bars'][0].get('timestamp') if state.get('opening_bars') else bar['timestamp']
        state['leg_start_index'] = max(0, index - len(state.get('opening_bars') or []) + 1)
        state['candidate_price'] = candidate_price
        state['candidate_time'] = candidate_bar['time']
        state['candidate_timestamp'] = candidate_bar['timestamp']
        state['candidate_index'] = candidate_index
        state['candidate_close'] = candidate_bar['close']
        state['candidate_bar'] = dict(candidate_bar)

    def _confirm_turn_event(self, code, state, bar, config, side, score,
                            confirmations, channel, pattern, index,
                            extreme_bar=None):
        event = self._active_candidate_event(state, side)
        if event is not None:
            return self._touch_turn_event(
                state, event, bar, config, score, confirmations, index,
                event_state='CONFIRMED', pattern=pattern,
                notification_kind='CONFIRMED', extreme_bar=extreme_bar,
                confirmed=True)
        return self._new_turn_event(
            code, state, bar, config, side, score, confirmations, channel,
            pattern, index, extreme_bar=extreme_bar or state.get('candidate_bar') or bar,
            confirmed=True, notification_kind='CONFIRMED')

    def _process_opening_fast(self, code, state, bar, index, config, robust_range):
        seconds = time_seconds(bar.get('time'))
        window_end = 34200 + config['opening_fast_window_minutes'] * 60
        if not config.get('opening_fast_enabled', True) or seconds is None:
            return None
        if seconds < 34200 or seconds >= window_end:
            return None
        if len(state.get('opening_bars') or []) < config['opening_fast_min_bars']:
            return None
        if state.get('opening_fast_signal_emitted'):
            return None
        if state.get('last_signal_at') is not None:
            if bar['confirm_timestamp'] - state['last_signal_at'] < config['cooldown_seconds']:
                return None
        opening = state['opening_bars']
        fast_swing, reference = self._opening_fast_thresholds(state, config, robust_range)
        if fast_swing is None:
            return None
        state['_fast_swing_threshold'] = fast_swing
        candidates = [
            ('SELL', max(opening, key=lambda item: item['high'])),
            ('BUY', min(opening, key=lambda item: item['low'])),
        ]
        for side, candidate_bar in candidates:
            candidate_price = candidate_bar['high'] if side == 'SELL' else candidate_bar['low']
            candidate_position = opening.index(candidate_bar)
            prior_bars = opening[:candidate_position]
            if side == 'SELL':
                context_prices = [number(state.get('first_open'))]
                context_prices.extend(number(item.get('low')) for item in prior_bars)
                context_prices = [value for value in context_prices if value is not None]
                swing_abs = max(0.0, candidate_price - min(context_prices)) if context_prices else 0.0
                reversal_abs = candidate_price - bar['close']
                gap_context = (number(state.get('opening_gap_pct')) is not None and
                               state['opening_gap_pct'] >= config['opening_fast_gap_pct'])
                structure = bar['close'] < opening[-2]['low']
            else:
                context_prices = [number(state.get('first_open'))]
                context_prices.extend(number(item.get('high')) for item in prior_bars)
                context_prices = [value for value in context_prices if value is not None]
                swing_abs = max(0.0, max(context_prices) - candidate_price) if context_prices else 0.0
                reversal_abs = bar['close'] - candidate_price
                gap_context = (number(state.get('opening_gap_pct')) is not None and
                               state['opening_gap_pct'] <= -config['opening_fast_gap_pct'])
                structure = bar['close'] > opening[-2]['high']
            if not (gap_context or swing_abs >= fast_swing):
                continue
            reversal_threshold = max(candidate_price * config['opening_fast_reversal_pct'] / 100.0,
                                     robust_range * config['opening_fast_reversal_range_mult'])
            if reversal_abs < reversal_threshold or not structure:
                continue
            candidate_index = max(0, index - len(opening) + candidate_position)
            score, confirmations, _ = self._opening_fast_score(
                state, bar, candidate_bar, candidate_index, index, swing_abs,
                reversal_abs, reversal_threshold, side, gap_context)
            if score < config['opening_fast_min_confidence'] or state.get('last_signal_side') == side:
                continue
            self._set_fast_tracking_state(state, bar, index, side, candidate_bar, candidate_index)
            pattern = 'GAP_REJECTION' if gap_context else 'IMPULSE_REVERSAL'
            swing_pct = swing_abs / state['leg_start_price'] * 100.0 if state['leg_start_price'] else 0.0
            reversal_pct_actual = reversal_abs / candidate_price * 100.0 if candidate_price else 0.0
            state['_pending_signal_channel'] = 'OPENING_FAST'
            state['_pending_signal_pattern'] = pattern
            event = self._confirm_turn_event(
                code, state, bar, config, side, score, confirmations,
                'OPENING_FAST', pattern, candidate_index,
                extreme_bar=candidate_bar)
            signal = self._signal(code, state, bar, config, side, score, confirmations,
                                  swing_pct, reversal_pct_actual,
                                  reversal_threshold / candidate_price * 100.0 if candidate_price else 0.0,
                                  channel='OPENING_FAST', pattern=pattern, event=event)
            state['opening_fast_signal_emitted'] = True
            state['opening_fast_signal_at'] = bar['confirm_timestamp']
            self._switch_after_signal(state, bar, side)
            state.pop('_pending_signal_channel', None)
            state.pop('_pending_signal_pattern', None)
            state.pop('_fast_swing_threshold', None)
            return signal
        state.pop('_fast_swing_threshold', None)
        return None

    def _signal(self, code, state, bar, config, side, confidence, confirmations,
                swing_pct, reversal_pct_actual, reversal_threshold_pct,
                channel='REGULAR', pattern='DIRECTIONAL_CHANGE', event=None):
        self.next_id += 1
        top = side == 'SELL'
        turning_point = 'TOP' if top else 'BOTTOM'
        label = u'分时顶' if top else u'分时底'
        lag_bars = max(1, len(state['bars']) - 1 - state['candidate_index'] + 1)
        rationale = (u'%s %.2f（%s），于 %s 确认；确认价 %.2f，反向幅度 %.2f%%，波段幅度 %.2f%%。'
                     u'仅作分时提醒，请结合人工判断。') % (
                         u'峰值' if top else u'谷值', state['candidate_price'],
                         state['candidate_time'], bar['confirm_time'], bar['close'],
                         reversal_pct_actual, swing_pct)
        signal = {
            'id': self.next_id, 'code': code, 'strategy_version': config['strategy_version'],
            'strategy': config['rule_name'], 'turning_point': turning_point,
            'side': side, 'module': 'swing_top' if top else 'swing_bottom',
            'module_label': label, 'regime': state['phase'],
            'regime_label': PHASE_LABELS[state['phase']],
            'extreme_price': clean(state['candidate_price'], 4),
            'extreme_time': state['candidate_time'],
            'extreme_timestamp': state['candidate_timestamp'],
            'confirm_price': clean(bar['close'], 4), 'confirm_time': bar['confirm_time'],
            'confirm_timestamp': bar['confirm_timestamp'],
            'timestamp': bar['confirm_timestamp'], 'bar_timestamp': bar['timestamp'],
            'time': bar['confirm_time'], 'price': clean(bar['close'], 4),
            'change': '%.2f%%' % number(bar.get('pct_change'), 0.0),
            'lag_bars': lag_bars, 'swing_pct': clean(swing_pct, 3),
            'reversal_pct_actual': clean(reversal_pct_actual, 3),
            'reversal_threshold_pct': clean(reversal_threshold_pct, 3),
            'confidence': confidence, 'confirmations': confirmations,
            'rationale': rationale, 'metrics': {}, 'source': 'WindPy',
            'channel': channel,
            'channel_label': u'开盘强信号' if channel == 'OPENING_FAST' else u'常规波段',
            'pattern': pattern,
            'first_open': clean(state.get('first_open'), 4),
            'pre_close': clean(state.get('pre_close'), 4),
            'opening_gap_pct': clean(state.get('opening_gap_pct'), 4),
        }
        if event is not None:
            signal.update(copy.deepcopy(event))
            signal['id'] = self.next_id
            signal['code'] = code
            signal['strategy_version'] = config['strategy_version']
            signal['strategy'] = config['rule_name']
            signal['turning_point'] = turning_point
            signal['side'] = side
            signal['module'] = 'swing_top' if top else 'swing_bottom'
            signal['module_label'] = label
            signal['regime'] = state['phase']
            signal['regime_label'] = PHASE_LABELS[state['phase']]
            signal['extreme_price'] = clean(state['candidate_price'], 4)
            signal['extreme_time'] = state['candidate_time']
            signal['extreme_timestamp'] = state['candidate_timestamp']
            signal['confirm_price'] = clean(bar['close'], 4)
            signal['confirm_time'] = bar['confirm_time']
            signal['confirm_timestamp'] = bar['confirm_timestamp']
            signal['timestamp'] = bar['confirm_timestamp']
            signal['bar_timestamp'] = bar['timestamp']
            signal['time'] = bar['confirm_time']
            signal['price'] = clean(bar['close'], 4)
            signal['change'] = '%.2f%%' % number(bar.get('pct_change'), 0.0)
            signal['lag_bars'] = lag_bars
            signal['swing_pct'] = clean(swing_pct, 3)
            signal['reversal_pct_actual'] = clean(reversal_pct_actual, 3)
            signal['reversal_threshold_pct'] = clean(reversal_threshold_pct, 3)
            signal['confidence'] = confidence
            signal['confirmations'] = list(confirmations or [])
            signal['channel'] = channel
            signal['channel_label'] = u'开盘强信号' if channel == 'OPENING_FAST' else u'常规波段'
            signal['pattern'] = pattern
            signal['first_open'] = clean(state.get('first_open'), 4)
            signal['pre_close'] = clean(state.get('pre_close'), 4)
            signal['opening_gap_pct'] = clean(state.get('opening_gap_pct'), 4)
        return signal

    def _switch_after_signal(self, state, bar, side):
        previous_candidate_index = state['candidate_index']
        state['last_signal_side'] = side
        state['last_signal_at'] = bar['confirm_timestamp']
        state['last_signal_channel'] = state.get('_pending_signal_channel') or 'REGULAR'
        state['last_signal_pattern'] = state.get('_pending_signal_pattern') or 'DIRECTIONAL_CHANGE'
        if side == 'SELL':
            state['phase'] = 'TRACKING_DOWN'
            state['leg_start_price'] = state['candidate_price']
            state['leg_start_time'] = state['candidate_time']
            state['leg_start_timestamp'] = state['candidate_timestamp']
            state['leg_start_index'] = previous_candidate_index
            state['candidate_price'] = bar['low']
        else:
            state['phase'] = 'TRACKING_UP'
            state['leg_start_price'] = state['candidate_price']
            state['leg_start_time'] = state['candidate_time']
            state['leg_start_timestamp'] = state['candidate_timestamp']
            state['leg_start_index'] = previous_candidate_index
            state['candidate_price'] = bar['high']
        state['candidate_time'] = bar['time']
        state['candidate_timestamp'] = bar['timestamp']
        state['candidate_index'] = len(state['bars']) - 1
        state['candidate_close'] = bar['close']
        state['candidate_bar'] = dict(bar)

    def _analytics(self, state, config, robust_range, blocked_reasons=None):
        phase = state['phase']
        price = state.get('candidate_price')
        start = state.get('leg_start_price')
        amplitude = abs(price - start) / start * 100.0 if price and start else 0.0
        reversal_threshold_pct = 0.0
        reversal_progress = 0
        if price and robust_range:
            _, reversal = self._thresholds(price, robust_range, config)
            reversal_threshold_pct = reversal / price * 100.0
            if state['bars']:
                close = state['bars'][-1]['close']
                actual = (price - close) if phase == 'TRACKING_UP' else (close - price)
                reversal_progress = min(100, max(0, int(round(actual / reversal * 100.0)))) if reversal else 0
        bars = len(state['bars'])
        reasons = list(blocked_reasons or [])
        if bars < config['warmup_bars']:
            reasons.append(u'正在预热：已完成 %d/%d 根 60 秒决策K' % (bars, config['warmup_bars']))
        if phase == 'BOOTSTRAP' and bars >= config['warmup_bars']:
            reasons.append(u'等待形成达到门槛的分时波段')
        latest_time = state['bars'][-1].get('time') if state['bars'] else None
        latest_seconds = time_seconds(latest_time)
        fast_window_end = 34200 + config['opening_fast_window_minutes'] * 60
        fast_enabled = config.get('opening_fast_enabled', True)
        fast_active = bool(fast_enabled and latest_seconds is not None and
                           34200 <= latest_seconds < fast_window_end)
        if not fast_enabled:
            fast_status = u'开盘强信号已关闭'
        elif latest_seconds is None or latest_seconds < 34200:
            fast_status = u'等待开盘'
        elif latest_seconds >= fast_window_end:
            fast_status = u'开盘强信号窗口已结束'
        elif state.get('opening_fast_signal_emitted'):
            fast_status = u'开盘强信号已触发，今日不再重复'
        elif len(state.get('opening_bars') or []) < config.get('opening_fast_min_bars', 2):
            fast_status = u'开盘强信号观察（%d/%d）' % (
                len(state.get('opening_bars') or []), config.get('opening_fast_min_bars', 2))
        else:
            fast_status = u'开盘强信号观察中'
        regular_progress = min(100, int(round(bars * 100.0 / config['warmup_bars'])))
        active_channel = 'OPENING_FAST' if fast_active else 'REGULAR'
        active_channel_label = u'开盘强信号观察' if fast_active else u'常规波段追踪'
        active_turn_event = state.get('active_turn_event')
        if active_turn_event is not None:
            active_turn_event = copy.deepcopy(active_turn_event)
        return {
            'ready': bars >= config['warmup_bars'] and not blocked_reasons,
            'decision_bars': bars, 'warmup_bars': bars,
            'warmup_target': config['warmup_bars'],
            'warmup_progress': min(100, int(round(bars * 100.0 / config['warmup_bars']))),
            'phase': phase, 'phase_label': PHASE_LABELS[phase],
            'regime': phase, 'regime_label': PHASE_LABELS[phase],
            'candidate_type': 'TOP' if phase == 'TRACKING_UP' else 'BOTTOM' if phase == 'TRACKING_DOWN' else None,
            'candidate_price': clean(price, 4), 'candidate_time': state.get('candidate_time'),
            'candidate_timestamp': state.get('candidate_timestamp'),
            'leg_start_price': clean(start, 4), 'leg_amplitude_pct': clean(amplitude, 3),
            'reversal_threshold_pct': clean(reversal_threshold_pct, 3),
            'reversal_progress': reversal_progress, 'robust_range': clean(robust_range, 4),
            'blocked_reasons': reasons, 'last_updated': state['bars'][-1]['confirm_time'] if state['bars'] else None,
            'last_bar_time': state['bars'][-1]['time'] if state['bars'] else None,
            'metrics': {},
            'active_channel': active_channel,
            'active_channel_label': active_channel_label,
            'opening_fast_enabled': fast_enabled,
            'opening_fast_active': fast_active,
            'opening_fast_bars': len(state.get('opening_bars') or []),
            'opening_fast_min_bars': config.get('opening_fast_min_bars', 2),
            'opening_fast_status': fast_status,
            'regular_ready': bars >= config['warmup_bars'] and not blocked_reasons,
            'regular_warmup_progress': regular_progress,
            'backfill_status': state.get('backfill_status', 'not_run'),
            'backfill_reason': state.get('backfill_reason'),
            'first_open': clean(state.get('first_open'), 4),
            'pre_close': clean(state.get('pre_close'), 4),
            'opening_gap_pct': clean(state.get('opening_gap_pct'), 4),
            'last_signal_side': state.get('last_signal_side'),
            'last_signal_channel': state.get('last_signal_channel'),
            'active_turn_event': active_turn_event,
            'candidate_alerts_enabled': config.get('candidate_alerts_enabled', True),
        }

    def mark_stale(self, analytics, config):
        analytics = dict(analytics or {})
        reasons = list(analytics.get('blocked_reasons') or [])
        if u'报价长时间未更新' not in reasons:
            reasons.append(u'报价长时间未更新')
        analytics['ready'] = False
        analytics['blocked_reasons'] = reasons
        analytics['last_updated'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return analytics

    def process(self, code, raw_bar, config=None):
        config = normalize_config(config or {})
        bar = self._prepare_bar(raw_bar)
        state = self.states.setdefault(code, self._new_state())
        current_day = day_key(bar['timestamp'])
        blocked = []

        if state['day'] is not None and state['day'] != current_day:
            self._invalidate_active_turn_events(state, bar, u'跨自然日，活动候选已失效')
            self._reset_market_structure(state, keep_last_signal=False)
            state['first_open'] = None
            state['pre_close'] = None
            state['opening_gap_pct'] = None
            state['opening_bars'] = []
            blocked.append(u'跨自然日，波段状态已重置')
        if state['bars'] and bar['timestamp'] - state['bars'][-1]['timestamp'] > 120:
            self._invalidate_active_turn_events(state, bar, u'行情断档超过 120 秒，活动候选已失效')
            session_meta = dict((key, state.get(key)) for key in (
                'first_open', 'pre_close', 'opening_gap_pct', 'backfill_status', 'backfill_reason'))
            self._reset_market_structure(state, keep_last_signal=True)
            state.update(session_meta)
            blocked.append(u'行情断档超过 120 秒，波段状态已重置')
        state['day'] = current_day

        seconds = time_seconds(bar.get('time'))
        if bar.get('pre_close') is not None:
            state['pre_close'] = bar.get('pre_close')
        if seconds is not None and 34200 <= seconds < 34200 + config['opening_fast_window_minutes'] * 60:
            if state.get('first_open') is None:
                state['first_open'] = bar.get('first_open') or bar.get('open')
            if bar.get('opening_gap_pct') is not None:
                state['opening_gap_pct'] = bar.get('opening_gap_pct')
            elif state.get('pre_close') and state.get('first_open'):
                state['opening_gap_pct'] = (state['first_open'] - state['pre_close']) / state['pre_close'] * 100.0

        session_reason = self._session_reason(bar, config)
        if session_reason and u'午间休市' in session_reason:
            self._invalidate_active_turn_events(state, bar, u'午间休市，活动候选已失效')
            session_meta = dict((key, state.get(key)) for key in (
                'first_open', 'pre_close', 'opening_gap_pct', 'backfill_status', 'backfill_reason'))
            self._reset_market_structure(state, keep_last_signal=True)
            state['day'] = current_day
            state.update(session_meta)
            return self._analytics(state, config, 0.0, [session_reason]), None
        if session_reason and seconds is not None and (seconds < 34200 or seconds >= 54000):
            return self._analytics(state, config, self._robust_range(state['bars']), [session_reason]), None

        state['bars'].append(bar)
        if seconds is not None and 34200 <= seconds < 34200 + config['opening_fast_window_minutes'] * 60:
            if not any(item.get('timestamp') == bar.get('timestamp') for item in state['opening_bars']):
                state['opening_bars'].append(dict(bar))
                state['opening_bars'] = state['opening_bars'][-30:]
        # A-share cash sessions contain at most 240 decision bars per day.
        # Keeping 360 avoids shifting the stored leg/candidate indices intraday.
        state['bars'] = state['bars'][-360:]
        index = len(state['bars']) - 1
        robust_range = self._robust_range(state['bars'])
        signal = None

        if state['phase'] == 'BOOTSTRAP':
            self._update_bootstrap_extremes(state, bar, index)
            if len(state['bars']) >= config['warmup_bars']:
                self._start_leg_if_ready(state, bar, index, robust_range, config)
        self._process_opening_candidate(code, state, bar, index, config, robust_range)
        signal = self._process_opening_fast(code, state, bar, index, config, robust_range)
        regular_start = 34200 + 5 * 60
        regular_allowed = (seconds is None or seconds >= regular_start)
        regular_ready = len(state['bars']) >= config['warmup_bars'] and regular_allowed
        if signal is None and regular_ready and state['phase'] == 'TRACKING_UP':
            extreme_updated = self._update_tracking_extreme(state, bar, index, 'SELL')
            min_swing, reversal = self._thresholds(state['leg_start_price'], robust_range, config)
            swing_abs = state['candidate_price'] - state['leg_start_price']
            reversal_abs = state['candidate_price'] - bar['close']
            leg_bars = index - state['leg_start_index'] + 1
            metrics = self._candidate_metrics(
                state, bar, 'SELL', min_swing, reversal, index, config,
                swing_abs=swing_abs)
            if not session_reason:
                self._maybe_update_candidate_event(
                    code, state, bar, config, 'SELL', metrics, 'REGULAR', index,
                    extreme_updated)
            cooldown_ok = (state.get('last_signal_at') is None or
                           bar['confirm_timestamp'] - state['last_signal_at'] >= config['cooldown_seconds'])
            hard = (leg_bars >= config['min_leg_bars'] and swing_abs >= min_swing and reversal_abs >= reversal and
                    bar['close'] < state['candidate_price'] and
                    len(state['bars']) >= 2 and bar['close'] < state['bars'][-2]['close'] and cooldown_ok)
            accelerated = None
            if not hard and not session_reason:
                accelerated = self._accelerated_confirmation(
                    state, bar, 'SELL', metrics, min_swing, reversal,
                    swing_abs, leg_bars, config, cooldown_ok)
            if (hard or accelerated is not None) and not session_reason:
                if accelerated is not None:
                    score = accelerated['score']
                    confirmations = accelerated['confirmations']
                else:
                    score, confirmations, _, _, _, _ = self._top_score(
                        state, bar, min_swing, reversal, robust_range)
                if score >= config['min_confidence'] and state.get('last_signal_side') != 'SELL':
                    swing_pct = swing_abs / state['leg_start_price'] * 100.0
                    reversal_pct_actual = reversal_abs / state['candidate_price'] * 100.0
                    state['_pending_signal_channel'] = 'REGULAR'
                    state['_pending_signal_pattern'] = 'DIRECTIONAL_CHANGE'
                    event = self._confirm_turn_event(
                        code, state, bar, config, 'SELL', score, confirmations,
                        'REGULAR', 'DIRECTIONAL_CHANGE', index,
                        extreme_bar=state.get('candidate_bar') or bar)
                    signal = self._signal(code, state, bar, config, 'SELL', score, confirmations,
                                          swing_pct, reversal_pct_actual, reversal / state['candidate_price'] * 100.0,
                                          channel='REGULAR', pattern='DIRECTIONAL_CHANGE', event=event)
                    if accelerated is not None:
                        signal['confirmation_mode'] = 'ACCELERATED'
                        signal.setdefault('metrics', {})['confirmation_mode'] = 'ACCELERATED'
                    self._switch_after_signal(state, bar, 'SELL')
                    state.pop('_pending_signal_channel', None)
                    state.pop('_pending_signal_pattern', None)
        elif signal is None and regular_ready and state['phase'] == 'TRACKING_DOWN':
            extreme_updated = self._update_tracking_extreme(state, bar, index, 'BUY')
            min_swing, reversal = self._thresholds(state['leg_start_price'], robust_range, config)
            swing_abs = state['leg_start_price'] - state['candidate_price']
            reversal_abs = bar['close'] - state['candidate_price']
            leg_bars = index - state['leg_start_index'] + 1
            metrics = self._candidate_metrics(
                state, bar, 'BUY', min_swing, reversal, index, config,
                swing_abs=swing_abs)
            if not session_reason:
                self._maybe_update_candidate_event(
                    code, state, bar, config, 'BUY', metrics, 'REGULAR', index,
                    extreme_updated)
            cooldown_ok = (state.get('last_signal_at') is None or
                           bar['confirm_timestamp'] - state['last_signal_at'] >= config['cooldown_seconds'])
            hard = (leg_bars >= config['min_leg_bars'] and swing_abs >= min_swing and reversal_abs >= reversal and
                    bar['close'] > state['candidate_price'] and
                    len(state['bars']) >= 2 and bar['close'] > state['bars'][-2]['close'] and cooldown_ok)
            accelerated = None
            if not hard and not session_reason:
                accelerated = self._accelerated_confirmation(
                    state, bar, 'BUY', metrics, min_swing, reversal,
                    swing_abs, leg_bars, config, cooldown_ok)
            if (hard or accelerated is not None) and not session_reason:
                if accelerated is not None:
                    score = accelerated['score']
                    confirmations = accelerated['confirmations']
                else:
                    score, confirmations, _, _, _, _ = self._bottom_score(
                        state, bar, min_swing, reversal, robust_range)
                if score >= config['min_confidence'] and state.get('last_signal_side') != 'BUY':
                    swing_pct = swing_abs / state['leg_start_price'] * 100.0
                    reversal_pct_actual = reversal_abs / state['candidate_price'] * 100.0
                    state['_pending_signal_channel'] = 'REGULAR'
                    state['_pending_signal_pattern'] = 'DIRECTIONAL_CHANGE'
                    event = self._confirm_turn_event(
                        code, state, bar, config, 'BUY', score, confirmations,
                        'REGULAR', 'DIRECTIONAL_CHANGE', index,
                        extreme_bar=state.get('candidate_bar') or bar)
                    signal = self._signal(code, state, bar, config, 'BUY', score, confirmations,
                                          swing_pct, reversal_pct_actual, reversal / state['candidate_price'] * 100.0,
                                          channel='REGULAR', pattern='DIRECTIONAL_CHANGE', event=event)
                    if accelerated is not None:
                        signal['confirmation_mode'] = 'ACCELERATED'
                        signal.setdefault('metrics', {})['confirmation_mode'] = 'ACCELERATED'
                    self._switch_after_signal(state, bar, 'BUY')
                    state.pop('_pending_signal_channel', None)
                    state.pop('_pending_signal_pattern', None)

        # Candidate TTL is an event-layer rule.  It must also run for opening
        # candidates that deliberately leave the legacy phase untouched.
        for turn_side in ('SELL', 'BUY'):
            self._expire_candidate_if_needed(state, turn_side, index, bar, config)

        if session_reason:
            blocked.append(session_reason)
            if not signal or signal.get('channel') != 'OPENING_FAST':
                signal = None
        return self._analytics(state, config, robust_range, blocked), signal
