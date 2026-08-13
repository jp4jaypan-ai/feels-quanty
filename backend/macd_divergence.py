# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import datetime


STRATEGY_VERSION = 'MDC-MACDV-2.0'

try:
    unicode
except NameError:
    unicode = str


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
    prepared = []
    for value in values:
        parsed = number(value)
        if parsed is not None:
            prepared.append(parsed)
    prepared.sort()
    if not prepared:
        return 0.0
    middle = len(prepared) // 2
    if len(prepared) % 2:
        return prepared[middle]
    return (prepared[middle - 1] + prepared[middle]) / 2.0


def time_seconds(text):
    try:
        hour, minute, second = [int(part) for part in text.split(':')[:3]]
        return hour * 3600 + minute * 60 + second
    except (AttributeError, TypeError, ValueError):
        return None


def day_key(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')


def session_time(seconds):
    return seconds is not None and (
        34200 <= seconds < 41400 or 46800 <= seconds < 54000)


def default_scale_specs():
    """Directional-change thresholds expressed in current ATR percentage.

    The floor protects quiet stocks from producing economically tiny formal
    signals. The ATR multiplier lets volatile stocks expand their own scale.
    A threshold is frozen for the lifetime of a directional-change leg.
    """
    return [
        {'code': 'MICRO', 'label': u'微级', 'rank': 1, 'weight': 1,
         'atr_mult': 0.75, 'floor_pct': 0.10},
        {'code': 'SMALL', 'label': u'小级', 'rank': 2, 'weight': 2,
         'atr_mult': 1.20, 'floor_pct': 0.18},
        {'code': 'MEDIUM', 'label': u'中级', 'rank': 3, 'weight': 3,
         'atr_mult': 1.80, 'floor_pct': 0.32},
        {'code': 'LARGE', 'label': u'大级', 'rank': 4, 'weight': 4,
         'atr_mult': 2.60, 'floor_pct': 0.55},
    ]


def default_macd_config():
    return {
        'enabled': True,
        'fast_period': 12,
        'slow_period': 26,
        'signal_period': 9,
        'atr_period': 26,
        'warmup_bars': 35,
        'records_limit': 480,
        'volume_lookback': 20,
        'volume_expansion_ratio': 1.20,
        'candidate_consensus_pct': 30,
        'confirmed_consensus_pct': 55,
        'candidate_min_confidence': 62,
        'confirmed_min_confidence': 78,
        'medium_min_leg_bars': 4,
        'large_min_leg_bars': 6,
        'medium_leg_threshold_mult': 1.25,
        'large_leg_threshold_mult': 1.40,
        'divergence_min_macdv_delta': 3.0,
        'late_zone': 50.0,
        'extreme_zone': 150.0,
        'scales': default_scale_specs(),
    }


def _normalise_scales(value):
    defaults = default_scale_specs()
    supplied = value if isinstance(value, list) else []
    by_code = dict(
        (unicode(item.get('code')).upper(), item)
        for item in supplied if isinstance(item, dict) and item.get('code'))
    result = []
    previous_floor = 0.0
    previous_mult = 0.0
    for base in defaults:
        raw = by_code.get(base['code'], {})
        item = dict(base)
        item.update(raw)
        item['code'] = base['code']
        item['label'] = unicode(item.get('label') or base['label'])
        item['rank'] = base['rank']
        item['weight'] = base['weight']
        item['atr_mult'] = max(
            previous_mult + 0.05, number(item.get('atr_mult'), base['atr_mult']))
        item['floor_pct'] = max(
            previous_floor + 0.01, number(item.get('floor_pct'), base['floor_pct']))
        previous_mult = item['atr_mult']
        previous_floor = item['floor_pct']
        result.append(item)
    return result


def normalize_macd_config(payload=None):
    config = default_macd_config()
    if isinstance(payload, dict):
        config.update(payload)
    config['fast_period'] = max(2, int(number(config.get('fast_period'), 12)))
    config['slow_period'] = max(
        config['fast_period'] + 1, int(number(config.get('slow_period'), 26)))
    config['signal_period'] = max(2, int(number(config.get('signal_period'), 9)))
    config['atr_period'] = max(5, int(number(config.get('atr_period'), 26)))
    minimum_warmup = max(
        config['slow_period'] + config['signal_period'], config['atr_period'])
    config['warmup_bars'] = max(
        minimum_warmup, int(number(config.get('warmup_bars'), minimum_warmup)))
    config['records_limit'] = max(
        120, int(number(config.get('records_limit'), 480)))
    config['volume_lookback'] = max(
        5, int(number(config.get('volume_lookback'), 20)))
    for key, fallback in (
            ('volume_expansion_ratio', 1.20),
            ('divergence_min_macdv_delta', 3.0),
            ('late_zone', 50.0),
            ('extreme_zone', 150.0)):
        config[key] = max(0.0, number(config.get(key), fallback))
    config['candidate_consensus_pct'] = max(
        10, min(90, int(number(config.get('candidate_consensus_pct'), 30))))
    config['confirmed_consensus_pct'] = max(
        config['candidate_consensus_pct'],
        min(100, int(number(config.get('confirmed_consensus_pct'), 55))))
    config['candidate_min_confidence'] = max(
        50, min(90, int(number(config.get('candidate_min_confidence'), 62))))
    config['confirmed_min_confidence'] = max(
        config['candidate_min_confidence'],
        min(95, int(number(config.get('confirmed_min_confidence'), 78))))
    config['medium_min_leg_bars'] = max(
        2, int(number(config.get('medium_min_leg_bars'), 4)))
    config['large_min_leg_bars'] = max(
        config['medium_min_leg_bars'],
        int(number(config.get('large_min_leg_bars'), 6)))
    config['medium_leg_threshold_mult'] = max(
        1.0, number(config.get('medium_leg_threshold_mult'), 1.25))
    config['large_leg_threshold_mult'] = max(
        config['medium_leg_threshold_mult'],
        number(config.get('large_leg_threshold_mult'), 1.40))
    config['extreme_zone'] = max(config['late_zone'] + 10.0, config['extreme_zone'])
    config['scales'] = _normalise_scales(config.get('scales'))
    config['enabled'] = bool(config.get('enabled', True))
    return config


def _momentum_stage(macdv, signal):
    if macdv > 150.0:
        return 'RISK_UP', u'风险过热'
    if macdv >= 50.0:
        if macdv >= signal:
            return 'RALLYING', u'上行动能扩张'
        return 'RETRACING', u'上行动能回落'
    if macdv > -50.0:
        return 'RANGING', u'动能中性'
    if macdv >= -150.0:
        if macdv >= signal:
            return 'REBOUNDING', u'下行动能修复'
        return 'REVERSING', u'下行动能扩张'
    return 'RISK_DOWN', u'风险超跌'


class MacdDivergenceEngine(object):
    """Causal multi-scale directional-change and MACD-V engine."""

    def __init__(self, config=None):
        self.config = normalize_macd_config(config)
        self.states = {}

    def _new_tracker(self, spec):
        return {
            'spec': dict(spec),
            'mode': None,
            'threshold_pct': None,
            'anchor_high': None,
            'anchor_low': None,
            'leg_start': None,
            'extreme': None,
            'events': {'TOP': [], 'BOTTOM': []},
        }

    def _new_state(self):
        return {
            'day': None,
            'records': [],
            'bar_index': -1,
            'ema_fast': None,
            'ema_slow': None,
            'macdv_signal': None,
            'atr': None,
            'tr_values': [],
            'previous_close': None,
            'last_timestamp': None,
            'scales': dict(
                (item['code'], self._new_tracker(item))
                for item in self.config['scales']),
            'event_revisions': {},
            'emitted_signatures': set(),
            'formal_event_ids': set(),
        }

    def reset_code(self, code):
        self.states.pop(code, None)

    def reset(self):
        self.states = {}

    def _prepare_bar(self, raw):
        timestamp = number(raw.get('timestamp'))
        close = number(raw.get('close'))
        high = number(raw.get('high'), close)
        low = number(raw.get('low'), close)
        open_price = number(raw.get('open'), close)
        if timestamp is None or close is None or close <= 0:
            return None
        if high is None or low is None or high < low:
            return None
        if open_price is None or open_price <= 0:
            open_price = close
        return {
            'timestamp': timestamp,
            'time': raw.get('time') or datetime.datetime.fromtimestamp(
                timestamp).strftime('%H:%M:%S'),
            'confirm_timestamp': number(
                raw.get('confirm_timestamp'), timestamp + 60.0),
            'confirm_time': raw.get('confirm_time') or datetime.datetime.fromtimestamp(
                timestamp + 60.0).strftime('%H:%M:%S'),
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': number(raw.get('volume'), 0.0),
        }

    def _append_indicator(self, state, bar):
        config = self.config
        close = bar['close']
        previous_close = state['previous_close']
        true_range = bar['high'] - bar['low']
        if previous_close is not None:
            true_range = max(
                true_range,
                abs(bar['high'] - previous_close),
                abs(bar['low'] - previous_close))
        state['tr_values'].append(true_range)
        atr_period = config['atr_period']
        if len(state['tr_values']) <= atr_period:
            state['atr'] = sum(state['tr_values']) / float(len(state['tr_values']))
        else:
            state['atr'] = (
                state['atr'] * (atr_period - 1.0) + true_range) / atr_period
        state['previous_close'] = close

        fast_alpha = 2.0 / (config['fast_period'] + 1.0)
        slow_alpha = 2.0 / (config['slow_period'] + 1.0)
        signal_alpha = 2.0 / (config['signal_period'] + 1.0)
        if state['ema_fast'] is None:
            state['ema_fast'] = close
            state['ema_slow'] = close
        else:
            state['ema_fast'] = (
                fast_alpha * close + (1.0 - fast_alpha) * state['ema_fast'])
            state['ema_slow'] = (
                slow_alpha * close + (1.0 - slow_alpha) * state['ema_slow'])
        ema_spread = state['ema_fast'] - state['ema_slow']
        macdv = (
            ema_spread / state['atr'] * 100.0
            if state['atr'] is not None and state['atr'] > 1e-12 else 0.0)
        if state['macdv_signal'] is None:
            state['macdv_signal'] = macdv
        else:
            state['macdv_signal'] = (
                signal_alpha * macdv +
                (1.0 - signal_alpha) * state['macdv_signal'])
        histogram = macdv - state['macdv_signal']
        previous_record = state['records'][-1] if state['records'] else None
        slope = macdv - previous_record['macdv'] if previous_record else 0.0
        stage, stage_label = _momentum_stage(macdv, state['macdv_signal'])
        state['bar_index'] += 1
        record = dict(bar)
        record.update({
            'index': state['bar_index'],
            'atr': state['atr'],
            'atr_pct': state['atr'] / close * 100.0,
            'ema_spread': ema_spread,
            'macdv': macdv,
            'macdv_signal': state['macdv_signal'],
            'macdv_histogram': histogram,
            'macdv_slope': slope,
            'momentum_stage': stage,
            'momentum_stage_label': stage_label,
            'range_pct': (bar['high'] - bar['low']) / close * 100.0,
        })
        state['records'].append(record)
        state['records'] = state['records'][-config['records_limit']:]
        return record

    def _point(self, record, field):
        return {
            'index': record['index'],
            'timestamp': record['timestamp'],
            'time': record['time'],
            'price': record[field],
            'close': record['close'],
            'macdv': record['macdv'],
            'macdv_signal': record['macdv_signal'],
            'macdv_histogram': record['macdv_histogram'],
            'momentum_stage': record['momentum_stage'],
            'momentum_stage_label': record['momentum_stage_label'],
        }

    def _threshold(self, spec, record):
        return max(spec['floor_pct'], record['atr_pct'] * spec['atr_mult'])

    def _directional_change(self, tracker, record):
        spec = tracker['spec']
        current_threshold = self._threshold(spec, record)
        if tracker['mode'] is None:
            high_point = self._point(record, 'high')
            low_point = self._point(record, 'low')
            if (tracker['anchor_high'] is None or
                    high_point['price'] >= tracker['anchor_high']['price']):
                tracker['anchor_high'] = high_point
            if (tracker['anchor_low'] is None or
                    low_point['price'] <= tracker['anchor_low']['price']):
                tracker['anchor_low'] = low_point
            rise = (
                (record['close'] - tracker['anchor_low']['price']) /
                tracker['anchor_low']['price'] * 100.0)
            fall = (
                (tracker['anchor_high']['price'] - record['close']) /
                tracker['anchor_high']['price'] * 100.0)
            if rise >= current_threshold and rise >= fall:
                tracker['mode'] = 'UP'
                tracker['threshold_pct'] = current_threshold
                tracker['leg_start'] = dict(tracker['anchor_low'])
                tracker['extreme'] = self._point(record, 'high')
            elif fall >= current_threshold:
                tracker['mode'] = 'DOWN'
                tracker['threshold_pct'] = current_threshold
                tracker['leg_start'] = dict(tracker['anchor_high'])
                tracker['extreme'] = self._point(record, 'low')
            return None

        threshold = tracker['threshold_pct'] or current_threshold
        if tracker['mode'] == 'UP':
            if record['high'] >= tracker['extreme']['price']:
                tracker['extreme'] = self._point(record, 'high')
            extreme = tracker['extreme']
            reversal = (extreme['price'] - record['close']) / extreme['price'] * 100.0
            if reversal < threshold:
                return None
            event = self._dc_event(tracker, 'TOP', extreme, record, threshold, reversal)
            tracker['events']['TOP'].append(event)
            tracker['events']['TOP'] = tracker['events']['TOP'][-12:]
            tracker['mode'] = 'DOWN'
            tracker['threshold_pct'] = current_threshold
            tracker['leg_start'] = dict(extreme)
            tracker['extreme'] = self._point(record, 'low')
            tracker['anchor_high'] = None
            tracker['anchor_low'] = None
            return event

        if record['low'] <= tracker['extreme']['price']:
            tracker['extreme'] = self._point(record, 'low')
        extreme = tracker['extreme']
        reversal = (record['close'] - extreme['price']) / extreme['price'] * 100.0
        if reversal < threshold:
            return None
        event = self._dc_event(tracker, 'BOTTOM', extreme, record, threshold, reversal)
        tracker['events']['BOTTOM'].append(event)
        tracker['events']['BOTTOM'] = tracker['events']['BOTTOM'][-12:]
        tracker['mode'] = 'UP'
        tracker['threshold_pct'] = current_threshold
        tracker['leg_start'] = dict(extreme)
        tracker['extreme'] = self._point(record, 'high')
        tracker['anchor_high'] = None
        tracker['anchor_low'] = None
        return event

    def _dc_event(self, tracker, kind, extreme, record, threshold, reversal):
        previous_events = tracker['events'][kind]
        previous = previous_events[-1] if previous_events else None
        leg_start = tracker.get('leg_start') or extreme
        if kind == 'TOP':
            leg_amplitude = (
                (extreme['price'] - leg_start['price']) /
                leg_start['price'] * 100.0)
        else:
            leg_amplitude = (
                (leg_start['price'] - extreme['price']) /
                leg_start['price'] * 100.0)
        leg_bars = max(0, extreme['index'] - leg_start['index'])
        divergence = False
        divergence_delta = 0.0
        price_delta = 0.0
        if previous is not None:
            previous_extreme = previous['extreme']
            if kind == 'TOP':
                price_delta = (
                    (extreme['price'] - previous_extreme['price']) /
                    previous_extreme['price'] * 100.0)
                divergence_delta = previous_extreme['macdv'] - extreme['macdv']
                divergence = (
                    price_delta > max(0.02, threshold * 0.10) and
                    divergence_delta >= self.config['divergence_min_macdv_delta'])
            else:
                price_delta = (
                    (previous_extreme['price'] - extreme['price']) /
                    previous_extreme['price'] * 100.0)
                divergence_delta = extreme['macdv'] - previous_extreme['macdv']
                divergence = (
                    price_delta > max(0.02, threshold * 0.10) and
                    divergence_delta >= self.config['divergence_min_macdv_delta'])
        return {
            'kind': kind,
            'side': 'SELL' if kind == 'TOP' else 'BUY',
            'scale': tracker['spec'],
            'threshold_pct': threshold,
            'reversal_pct': reversal,
            'leg_start': dict(leg_start),
            'leg_amplitude_pct': max(0.0, leg_amplitude),
            'leg_bars': leg_bars,
            'extreme': dict(extreme),
            'previous': previous,
            'price_delta_pct': price_delta,
            'divergence': divergence,
            'divergence_delta': divergence_delta,
            'confirm_record': record,
        }

    def _scale_consensus(self, state, side):
        expected = 'DOWN' if side == 'SELL' else 'UP'
        total = float(sum(item['weight'] for item in self.config['scales']))
        aligned = []
        score = 0.0
        for spec in self.config['scales']:
            tracker = state['scales'][spec['code']]
            if tracker['mode'] == expected:
                aligned.append(spec)
                score += spec['weight']
        return score / total * 100.0, aligned

    def _regime(self, state):
        modes = []
        for code in ('MEDIUM', 'LARGE'):
            mode = state['scales'][code]['mode']
            if mode is not None:
                modes.append(mode)
        if modes and all(mode == 'UP' for mode in modes):
            return 'BULLISH', u'高级别上行'
        if modes and all(mode == 'DOWN' for mode in modes):
            return 'BEARISH', u'高级别下行'
        return 'MIXED', u'高级别混合'

    def _higher_scale_conflict(self, state, side, rank):
        if rank >= 3:
            return False
        higher = []
        for code in ('MEDIUM', 'LARGE'):
            mode = state['scales'][code]['mode']
            if mode is not None:
                higher.append(mode)
        if not higher:
            return False
        opposing = 'UP' if side == 'SELL' else 'DOWN'
        return all(mode == opposing for mode in higher)

    def _volume_ratio(self, state, record):
        lookback = self.config['volume_lookback']
        history = [
            item['volume'] for item in state['records'][-lookback - 1:-1]
            if number(item.get('volume'), 0.0) > 0]
        reference = median(history)
        if reference <= 0:
            return 0.0
        return record['volume'] / reference

    def _advice(self, state, side, primary, record, consensus, divergence):
        config = self.config
        rank = primary['scale']['rank']
        histogram = record['macdv_histogram']
        slope = record['macdv_slope']
        previous = state['records'][-2] if len(state['records']) >= 2 else None
        previous_histogram = previous['macdv_histogram'] if previous else histogram
        if side == 'SELL':
            momentum_support = slope < 0 and histogram <= 0
            momentum_cross = previous_histogram >= 0 and histogram < 0
            late = record['macdv'] < -config['late_zone']
            extreme_late = record['macdv'] < -config['extreme_zone']
        else:
            momentum_support = slope > 0 and histogram >= 0
            momentum_cross = previous_histogram <= 0 and histogram > 0
            late = record['macdv'] > config['late_zone']
            extreme_late = record['macdv'] > config['extreme_zone']
        conflict = self._higher_scale_conflict(state, side, rank)
        if rank >= 4:
            structure_ok = (
                primary['leg_bars'] >= config['large_min_leg_bars'] and
                primary['leg_amplitude_pct'] >=
                primary['threshold_pct'] * config['large_leg_threshold_mult'])
        elif rank >= 3:
            structure_ok = (
                primary['leg_bars'] >= config['medium_min_leg_bars'] and
                primary['leg_amplitude_pct'] >=
                primary['threshold_pct'] * config['medium_leg_threshold_mult'])
        else:
            structure_ok = primary['leg_bars'] >= 2
        advice = 'WATCH'
        if (rank >= 3 and structure_ok and momentum_support and
                consensus >= config['confirmed_consensus_pct'] and
                not conflict and not late):
            advice = 'CONFIRMED'
        elif (rank >= 2 and momentum_support and
              consensus >= config['candidate_consensus_pct'] and
              not conflict):
            advice = 'CANDIDATE'
        elif (rank >= 2 and divergence and momentum_support and not conflict):
            advice = 'CANDIDATE'
        if extreme_late or conflict or rank == 1:
            advice = 'WATCH'
        elif late and advice == 'CONFIRMED':
            advice = 'CANDIDATE'
        return advice, momentum_support, momentum_cross, late, conflict, structure_ok

    def _build_alert(self, code, state, events, record):
        sides = {}
        for event in events:
            sides.setdefault(event['side'], []).append(event)
        groups = sorted(
            sides.values(),
            key=lambda group: max(item['scale']['rank'] for item in group),
            reverse=True)
        selected = groups[0]
        primary = max(selected, key=lambda item: item['scale']['rank'])
        side = primary['side']
        extreme = primary['extreme']
        triggered = sorted(
            [item['scale'] for item in selected], key=lambda item: item['rank'])
        consensus, aligned = self._scale_consensus(state, side)
        divergence_events = [item for item in selected if item['divergence']]
        divergence = bool(divergence_events)
        advice, momentum_support, momentum_cross, late, conflict, structure_ok = self._advice(
            state, side, primary, record, consensus, divergence)
        if primary['scale']['rank'] == 1:
            return None
        if primary['scale']['rank'] == 2 and advice == 'WATCH':
            return None
        regime, regime_label = self._regime(state)
        volume_ratio = self._volume_ratio(state, record)
        volume_support = volume_ratio >= self.config['volume_expansion_ratio']

        base_score = {1: 44, 2: 57, 3: 70, 4: 80}[primary['scale']['rank']]
        score = base_score + min(10, int(round(consensus / 10.0)))
        score += 7 if momentum_support else 0
        score += 3 if momentum_cross else 0
        score += 6 if divergence else 0
        score += 3 if volume_support else 0
        if (side == 'BUY' and regime == 'BULLISH') or (
                side == 'SELL' and regime == 'BEARISH'):
            score += 4
        if late:
            score -= 10
        if conflict:
            score -= 15
        confidence = max(35, min(95, int(round(score))))
        if advice == 'CONFIRMED':
            confidence = max(confidence, self.config['confirmed_min_confidence'])
        elif advice == 'CANDIDATE':
            confidence = max(confidence, self.config['candidate_min_confidence'])

        event_state = {
            'WATCH': 'CANDIDATE',
            'CANDIDATE': 'STRENGTHENING',
            'CONFIRMED': 'CONFIRMED',
        }[advice]
        point_text = u'顶部' if side == 'SELL' else u'底部'
        advice_text = {
            'WATCH': u'观察', 'CANDIDATE': u'候选', 'CONFIRMED': u'确认'
        }[advice]
        action_text = {
            'WATCH': u'观察%s' % point_text,
            'CANDIDATE': u'%s候选' % (u'卖出' if side == 'SELL' else u'买入'),
            'CONFIRMED': u'%s建议' % (u'卖出' if side == 'SELL' else u'买入'),
        }[advice]
        confirmations = [
            u'%s方向变化阈值 %.3f%% 已完成' % (
                primary['scale']['label'], primary['threshold_pct']),
            u'多尺度一致度 %.0f%%（%s）' % (
                consensus, u' / '.join(item['label'] for item in aligned) or u'无'),
            u'MACD-V %.1f，%s' % (
                record['macdv'], record['momentum_stage_label']),
        ]
        if momentum_support:
            confirmations.append(u'MACD-V 柱体与斜率已同向转折')
        if divergence:
            confirmations.append(u'同级价格与 MACD-V 出现常规背离')
        if volume_support:
            confirmations.append(u'确认 K 量能为近期中位数 %.2f 倍' % volume_ratio)
        if conflict:
            confirmations.append(u'与高级别趋势冲突，已降级为观察')
        if late:
            confirmations.append(u'动能已进入反向区域，避免追卖或追买，已降级')
        if not structure_ok:
            confirmations.append(u'波段幅度或持续时间不足，未升级为正式建议')

        rationale = (
            u'%s%s%s：波段运行 %.3f%% / %d 根 K，反转阈值 %.3f%%，实际反转 %.3f%%；'
            u'多尺度一致度 %.0f%%；MACD-V %.1f，处于%s。%s'
        ) % (
            primary['scale']['label'], point_text, advice_text,
            primary['leg_amplitude_pct'], primary['leg_bars'],
            primary['threshold_pct'], primary['reversal_pct'], consensus,
            record['macdv'], record['momentum_stage_label'],
            u'正式提醒。' if advice == 'CONFIRMED' else u'仅前端观察，不弹窗。')

        event_id = 'MDC-MACDV-%s-%s-%d' % (
            code, side, int(extreme['timestamp']))
        revision = state['event_revisions'].get(event_id, 0) + 1
        signature = (event_id, primary['scale']['code'], event_state)
        if signature in state['emitted_signatures']:
            return None
        state['emitted_signatures'].add(signature)
        state['event_revisions'][event_id] = revision
        notification_kind = 'NONE'
        if advice == 'CONFIRMED' and event_id not in state['formal_event_ids']:
            notification_kind = 'CONFIRMED'
            state['formal_event_ids'].add(event_id)

        previous_event = primary.get('previous')
        previous_extreme = previous_event.get('extreme') if previous_event else None
        divergence_type = 'NONE'
        if divergence:
            divergence_type = (
                'BEARISH_REGULAR' if side == 'SELL' else 'BULLISH_REGULAR')
        price_slope = 0.0
        macdv_slope_between_extremes = 0.0
        if previous_extreme is not None:
            distance = max(1, extreme['index'] - previous_extreme['index'])
            price_slope = (
                (extreme['price'] - previous_extreme['price']) /
                previous_extreme['price'] * 100.0 / distance)
            macdv_slope_between_extremes = (
                extreme['macdv'] - previous_extreme['macdv']) / distance

        return {
            'id': event_id,
            'event_id': event_id,
            'revision': revision,
            'event_state': event_state,
            'signal_level': 'CONFIRMED' if advice == 'CONFIRMED' else 'CANDIDATE',
            'notification_kind': notification_kind,
            'advice_level': advice,
            'advice_label': advice_text,
            'action_label': action_text,
            'code': code,
            'strategy_version': STRATEGY_VERSION,
            'strategy': u'自适应多尺度动能',
            'module': 'multiscale_macdv',
            'module_label': u'%s%s%s' % (
                primary['scale']['label'], point_text, advice_text),
            'side': side,
            'turning_point': primary['kind'],
            'scale_code': primary['scale']['code'],
            'scale_label': primary['scale']['label'],
            'scale_rank': primary['scale']['rank'],
            'scale_threshold_pct': clean(primary['threshold_pct'], 4),
            'triggered_scales': [item['code'] for item in triggered],
            'triggered_scale_labels': [item['label'] for item in triggered],
            'aligned_scales': [item['code'] for item in aligned],
            'aligned_scale_labels': [item['label'] for item in aligned],
            'consensus_pct': clean(consensus, 1),
            'regime': regime,
            'regime_label': regime_label,
            'momentum_stage': record['momentum_stage'],
            'momentum_stage_label': record['momentum_stage_label'],
            'macdv': clean(record['macdv'], 3),
            'macdv_signal': clean(record['macdv_signal'], 3),
            'macdv_histogram': clean(record['macdv_histogram'], 3),
            'macdv_slope': clean(record['macdv_slope'], 3),
            'divergence': divergence,
            'divergence_type': divergence_type,
            'divergence_label': (
                u'常规顶背离' if divergence and side == 'SELL' else
                u'常规底背离' if divergence else u'未形成同级背离'),
            'previous_extreme_price': clean(
                previous_extreme.get('price'), 4) if previous_extreme else None,
            'previous_extreme_time': (
                previous_extreme.get('time') if previous_extreme else None),
            'previous_extreme_timestamp': (
                previous_extreme.get('timestamp') if previous_extreme else None),
            'extreme_price': clean(extreme['price'], 4),
            'extreme_time': extreme['time'],
            'extreme_timestamp': extreme['timestamp'],
            'created_time': extreme['time'],
            'created_timestamp': extreme['timestamp'],
            'observed_price': clean(record['close'], 4),
            'observed_time': record['time'],
            'observed_timestamp': record['timestamp'],
            'updated_time': record['confirm_time'],
            'updated_timestamp': record['confirm_timestamp'],
            'confirm_price': clean(record['close'], 4),
            'confirm_time': record['confirm_time'],
            'confirm_timestamp': record['confirm_timestamp'],
            'timestamp': record['confirm_timestamp'],
            'price_delta_pct': clean(primary['price_delta_pct'], 4),
            'price_slope_pct_per_bar': clean(price_slope, 5),
            'dif_delta_pct': clean(primary['divergence_delta'], 4),
            'dif_slope_pct_per_bar': clean(macdv_slope_between_extremes, 5),
            'histogram_slope_pct_per_bar': clean(record['macdv_slope'], 5),
            'recent_histogram_slope_pct_per_bar': clean(record['macdv_slope'], 5),
            'reversal_pct': clean(primary['reversal_pct'], 4),
            'leg_start_price': clean(primary['leg_start']['price'], 4),
            'leg_start_time': primary['leg_start']['time'],
            'leg_amplitude_pct': clean(primary['leg_amplitude_pct'], 4),
            'leg_bars': primary['leg_bars'],
            'structure_ok': structure_ok,
            'volume_ratio': clean(volume_ratio, 3),
            'lag_bars': max(0, record['index'] - extreme['index']),
            'confidence': confidence,
            'confirmations': confirmations,
            'rationale': rationale,
            'channel': 'REGULAR',
            'channel_label': 'MDC · MACD-V',
            'pattern': 'MULTISCALE_MACDV',
            'source': 'WindPy',
        }

    def process(self, code, raw_bar):
        if not self.config.get('enabled', True):
            return None
        bar = self._prepare_bar(raw_bar)
        if bar is None or not session_time(time_seconds(bar.get('time'))):
            return None
        state = self.states.setdefault(code, self._new_state())
        current_day = day_key(bar['timestamp'])
        if state['day'] is not None and state['day'] != current_day:
            state = self._new_state()
            self.states[code] = state
        state['day'] = current_day
        if (state['last_timestamp'] is not None and
                bar['timestamp'] <= state['last_timestamp']):
            return None
        state['last_timestamp'] = bar['timestamp']
        record = self._append_indicator(state, bar)
        if len(state['tr_values']) < self.config['atr_period']:
            return None
        events = []
        for spec in self.config['scales']:
            event = self._directional_change(
                state['scales'][spec['code']], record)
            if event is not None:
                events.append(event)
        if len(state['records']) < self.config['warmup_bars'] or not events:
            return None
        return self._build_alert(code, state, events, record)


MultiscaleMacdEngine = MacdDivergenceEngine
