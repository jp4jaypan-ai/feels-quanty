# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import datetime
import ctypes
import io
import json
import os
import subprocess
import sys
import threading
import time

from macd_divergence import (
    MacdDivergenceEngine,
    STRATEGY_VERSION as MACD_STRATEGY_VERSION,
)
from swing_v3 import (
    DecisionBarAggregator,
    PHASE_LABELS,
    SwingV3Engine,
    default_config as swing_default_config,
    normalize_config as swing_normalize_config,
)

try:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    from SocketServer import ThreadingMixIn
    from urlparse import urlparse
except ImportError:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from socketserver import ThreadingMixIn
    from urllib.parse import urlparse

try:
    from WindPy import w
    WINDPY_AVAILABLE, WINDPY_IMPORT_ERROR = True, None
except Exception as exc:
    w, WINDPY_AVAILABLE, WINDPY_IMPORT_ERROR = None, False, repr(exc)

try:
    unicode
except NameError:
    unicode = str

HOST = os.environ.get('QUANT_HOST', '127.0.0.1')
PORT = int(os.environ.get('QUANT_PORT', '8765'))
POLL_SECONDS = max(0.25, float(os.environ.get('QUANT_POLL_SECONDS', '1.0')))
# 30-second bars for a full A-share session are roughly 480 points. Keep
# headroom for clock irregularities and short pauses so the chart can replay
# the whole day instead of rolling off the morning session after two hours.
BUCKET_SECONDS, MAX_BARS, MAX_SIGNALS, STALE_SECONDS = 30, 600, 500, 15
CACHE_VERSION, MAX_DECISION_BARS = 1, 360
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not isinstance(PROJECT_ROOT, unicode):
    PROJECT_ROOT = PROJECT_ROOT.decode(sys.getfilesystemencoding() or 'mbcs', 'replace')
CACHE_PATH = os.environ.get(
    'QUANT_CACHE_PATH', os.path.join(PROJECT_ROOT, 'work', 'intraday_cache.json'))
QUOTE_FIELDS = ['rt_last', 'rt_pct_chg', 'rt_vol', 'rt_amt', 'rt_high', 'rt_low',
                'rt_pre_close', 'rt_vwap', 'rt_bid1', 'rt_ask1', 'rt_time']
QUOTE_FIELD_STRING = ','.join(QUOTE_FIELDS)
def now_text():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def number(value, default=None):
    try:
        value = float(value)
        return default if value != value or value in (float('inf'), float('-inf')) else value
    except (TypeError, ValueError):
        return default


def clean(value, digits=6):
    value = number(value)
    return None if value is None else round(value, digits)


def trading_day_text(value=None):
    value = value or datetime.date.today()
    if isinstance(value, datetime.datetime):
        value = value.date()
    return value.strftime('%Y-%m-%d') if isinstance(value, datetime.date) else unicode(value)


def _unicode_path(path):
    if isinstance(path, unicode):
        return path
    return path.decode(sys.getfilesystemencoding() or 'utf-8', 'replace')


def _atomic_replace_file(source, target):
    replace = getattr(os, 'replace', None)
    if replace is not None:
        replace(source, target)
        return
    if os.name == 'nt':
        move_file = ctypes.windll.kernel32.MoveFileExW
        move_file.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
        move_file.restype = ctypes.c_int
        if not move_file(_unicode_path(source), _unicode_path(target), 0x1 | 0x8):
            raise ctypes.WinError()
        return
    os.rename(source, target)


def merge_timestamped(existing, incoming, limit):
    merged = {}
    for item in list(existing or []) + list(incoming or []):
        if not isinstance(item, dict):
            continue
        timestamp = number(item.get('timestamp'))
        if timestamp is None:
            continue
        merged[timestamp] = dict(item)
    return [merged[key] for key in sorted(merged.keys())][-int(limit):]


class IntradayCache(object):
    """Versioned, current-trading-day cache for causally replayable market data."""

    def __init__(self, path, today_provider=None):
        self.path = path
        self.today_provider = today_provider or datetime.date.today
        self.lock = threading.RLock()
        self.status, self.last_error, self.updated_at = 'not_loaded', None, None

    def _today(self):
        return trading_day_text(self.today_provider())

    def _empty(self, codes=None, config=None):
        return {
            'version': CACHE_VERSION,
            'trading_day': self._today(),
            'updated_at': None,
            'codes': list(codes) if isinstance(codes, list) else [],
            'config': dict(config) if isinstance(config, dict) else {},
            'micro_bars': {},
            'decision_bars': {},
            'signals': [],
            'turning_events': [],
            'macd_alerts': [],
        }

    def _sanitize(self, payload, keep_market=True):
        payload = payload if isinstance(payload, dict) else {}
        clean_payload = self._empty(payload.get('codes'), payload.get('config'))
        clean_payload['updated_at'] = payload.get('updated_at')
        if not keep_market:
            return clean_payload
        for key, limit in (('micro_bars', MAX_BARS),
                           ('decision_bars', MAX_DECISION_BARS)):
            raw = payload.get(key)
            if not isinstance(raw, dict):
                continue
            for code, bars in raw.items():
                if isinstance(bars, list):
                    clean_payload[key][unicode(code)] = merge_timestamped([], bars, limit)
        if isinstance(payload.get('signals'), list):
            clean_payload['signals'] = [
                dict(item) for item in payload['signals'] if isinstance(item, dict)
            ][:MAX_SIGNALS]
        if isinstance(payload.get('turning_events'), list):
            clean_payload['turning_events'] = [
                dict(item) for item in payload['turning_events'] if isinstance(item, dict)
            ][:MAX_SIGNALS]
        if isinstance(payload.get('macd_alerts'), list):
            clean_payload['macd_alerts'] = [
                dict(item) for item in payload['macd_alerts'] if isinstance(item, dict)
            ][:MAX_SIGNALS]
        return clean_payload

    def load(self):
        with self.lock:
            if not os.path.exists(self.path):
                self.status, self.last_error, self.updated_at = 'missing', None, None
                return self._empty()
            try:
                with io.open(self.path, 'r', encoding='utf-8-sig') as handle:
                    raw = json.load(handle)
                if not isinstance(raw, dict):
                    raise ValueError('cache root must be a JSON object')
                if int(raw.get('version') or 0) != CACHE_VERSION:
                    raise ValueError('unsupported cache version: %s' % raw.get('version'))
                same_day = raw.get('trading_day') == self._today()
                payload = self._sanitize(raw, keep_market=same_day)
                self.status = 'loaded' if same_day else 'new_day'
                self.last_error = None
                self.updated_at = payload.get('updated_at') if same_day else None
                return payload
            except Exception as exc:
                self.status, self.last_error, self.updated_at = 'corrupt', unicode(exc), None
                return self._empty()

    def save(self, payload):
        temporary = None
        with self.lock:
            try:
                prepared = self._sanitize(payload, keep_market=True)
                prepared['version'] = CACHE_VERSION
                prepared['trading_day'] = self._today()
                prepared['updated_at'] = now_text()
                directory = os.path.dirname(self.path)
                if directory and not os.path.isdir(directory):
                    try:
                        os.makedirs(directory)
                    except OSError:
                        if not os.path.isdir(directory):
                            raise
                temporary = '%s.tmp-%s-%s' % (
                    self.path, os.getpid(), int(time.time() * 1000000))
                content = json.dumps(
                    prepared, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
                if not isinstance(content, unicode):
                    content = content.decode('utf-8')
                with io.open(temporary, 'w', encoding='utf-8', newline='') as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                _atomic_replace_file(temporary, self.path)
                self.status, self.last_error = 'saved', None
                self.updated_at = prepared['updated_at']
                return True
            except Exception as exc:
                self.status, self.last_error = 'write_failed', unicode(exc)
                if temporary and os.path.exists(temporary):
                    try:
                        os.remove(temporary)
                    except OSError:
                        pass
                return False


def quote_time(value):
    if isinstance(value, (datetime.datetime, datetime.time)):
        return value.strftime('%H:%M:%S')
    if isinstance(value, (str, unicode)) and ':' in value:
        try:
            h, m, s = [int(float(x)) for x in value.strip().split(':')[:3]]
            if h <= 23 and m <= 59 and s <= 59:
                return '%02d:%02d:%02d' % (h, m, s)
        except (TypeError, ValueError):
            pass
    value = number(value)
    if value is not None:
        raw = int(value)
        h, m, s = raw // 10000, (raw // 100) % 100, raw % 100
        if h <= 23 and m <= 59 and s <= 59:
            return '%02d:%02d:%02d' % (h, m, s)
    return datetime.datetime.now().strftime('%H:%M:%S')


def time_seconds(text):
    try:
        h, m, s = [int(x) for x in text.split(':')[:3]]
        return h * 3600 + m * 60 + s
    except (AttributeError, TypeError, ValueError):
        return None


def latest_completed_minute(now=None):
    current = now or datetime.datetime.now()
    return current.replace(second=0, microsecond=0) - datetime.timedelta(minutes=1)


def wsi_epoch(value, fallback_day=None):
    fallback_day = fallback_day or datetime.datetime.now().date()
    if isinstance(value, datetime.datetime):
        return time.mktime(value.timetuple())
    if isinstance(value, datetime.date):
        return time.mktime(datetime.datetime.combine(value, datetime.time()).timetuple())
    if isinstance(value, datetime.time):
        return time.mktime(datetime.datetime.combine(fallback_day, value).timetuple())
    if isinstance(value, (str, unicode)):
        text = value.strip()
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S', '%H:%M:%S'):
            try:
                parsed = datetime.datetime.strptime(text[:19], fmt)
                if fmt == '%H:%M:%S':
                    parsed = datetime.datetime.combine(fallback_day, parsed.time())
                return time.mktime(parsed.timetuple())
            except (TypeError, ValueError):
                continue
    numeric = number(value)
    if numeric is not None:
        raw = int(numeric)
        if raw < 1000000:
            raw = '%06d' % raw
            try:
                parsed = datetime.time(int(raw[:2]), int(raw[2:4]), int(raw[4:6]))
                return time.mktime(datetime.datetime.combine(fallback_day, parsed).timetuple())
            except (TypeError, ValueError):
                return None
        if raw > 1000000000:
            return numeric
    return None


def _wsi_field_key(value):
    try:
        text = value.decode('ascii', 'ignore') if not isinstance(value, unicode) else value
    except AttributeError:
        text = value
    return str(text).lower().replace('_', '').replace('-', '')


def parse_wsi_bars(result, pre_close=None, end_time=None):
    error_code = getattr(result, 'ErrorCode', 0)
    if error_code not in (None, 0):
        raise RuntimeError('WindPy wsi error %s' % error_code)
    fields = list(getattr(result, 'Fields', []) or [])
    data = list(getattr(result, 'Data', []) or [])
    times = list(getattr(result, 'Times', []) or [])
    requested = ['open', 'high', 'low', 'close', 'volume', 'amount']
    if not fields:
        fields = requested[:len(data)]
    rows = {}
    for index, field in enumerate(fields):
        if index < len(data):
            rows[_wsi_field_key(field)] = list(data[index] or [])
    aliases = {
        'open': ('open',), 'high': ('high',), 'low': ('low',), 'close': ('close',),
        'volume': ('volume', 'vol'), 'amount': ('amount', 'amt'),
    }
    end_stamp = wsi_epoch(end_time) if end_time is not None else None
    day = datetime.datetime.fromtimestamp(end_stamp).date() if end_stamp else datetime.datetime.now().date()
    start_stamp = time.mktime(datetime.datetime.combine(day, datetime.time(9, 30)).timetuple())
    parsed = []
    seen = set()
    for index, item_time in enumerate(times):
        timestamp = wsi_epoch(item_time, day)
        if timestamp is None or timestamp < start_stamp or (end_stamp is not None and timestamp > end_stamp):
            continue
        if timestamp in seen:
            continue
        values = {}
        for name, candidates in aliases.items():
            for candidate in candidates:
                row = rows.get(candidate, [])
                values[name] = row[index] if index < len(row) else None
                if values[name] is not None:
                    break
        if any(number(values.get(name)) is None for name in ('open', 'high', 'low', 'close')):
            continue
        seen.add(timestamp)
        parsed.append({
            'timestamp': timestamp,
            'time': datetime.datetime.fromtimestamp(timestamp).strftime('%H:%M:%S'),
            'confirm_timestamp': timestamp + 60.0,
            'confirm_time': datetime.datetime.fromtimestamp(timestamp + 60.0).strftime('%H:%M:%S'),
            'open': number(values.get('open')), 'high': number(values.get('high')),
            'low': number(values.get('low')), 'close': number(values.get('close')),
            'volume': number(values.get('volume'), 0.0), 'amount': number(values.get('amount'), 0.0),
            'vwap': None, 'pct_change': 0.0,
            'pre_close': number(pre_close), 'first_open': None, 'opening_gap_pct': None,
        })
    parsed.sort(key=lambda item: item['timestamp'])
    first_open = None
    if parsed and time_seconds(parsed[0]['time']) == 34200:
        first_open = parsed[0]['open']
    opening_gap = ((first_open - number(pre_close)) / number(pre_close) * 100.0
                   if first_open is not None and number(pre_close) else None)
    for item in parsed:
        item['first_open'] = first_open
        item['opening_gap_pct'] = opening_gap
    return parsed


def quote_epoch(text):
    seconds = time_seconds(text)
    if seconds is None:
        return time.time()
    stamp = datetime.datetime.combine(datetime.datetime.now().date(), datetime.time())
    return time.mktime(stamp.timetuple()) + seconds


def normalize_codes(codes):
    result = []
    for item in codes if isinstance(codes, list) else []:
        try:
            code = str(item).strip().upper()
        except UnicodeEncodeError:
            code = item.encode('ascii', 'ignore').decode('ascii').strip().upper()
        if code and code not in result:
            result.append(code)
    return result[:50]


def default_config():
    return swing_default_config()


def as_bool(value, default=True):
    if isinstance(value, (str, unicode)):
        value = value.strip().lower()
        if value in ('false', '0', 'off', 'no'):
            return False
        if value in ('true', '1', 'on', 'yes'):
            return True
    return default if value is None else bool(value)


def normalize_config(payload):
    return swing_normalize_config(payload)


def empty_analytics(config=None):
    target = (config or default_config())['warmup_bars']
    return {
        'ready': False, 'decision_bars': 0, 'warmup_bars': 0,
        'warmup_target': target, 'warmup_progress': 0,
        'phase': 'BOOTSTRAP', 'phase_label': PHASE_LABELS['BOOTSTRAP'],
        'regime': 'BOOTSTRAP', 'regime_label': PHASE_LABELS['BOOTSTRAP'],
        'candidate_type': None, 'candidate_price': None,
        'candidate_time': None, 'candidate_timestamp': None,
        'leg_start_price': None, 'leg_amplitude_pct': 0.0,
        'reversal_threshold_pct': 0.0, 'reversal_progress': 0,
        'robust_range': 0.0, 'metrics': {},
        'blocked_reasons': [u'\u7b49\u5f85 60 \u79d2\u51b3\u7b56 K \u7ebf\u9884\u70ed'],
        'last_updated': None, 'last_bar_time': None,
        'active_channel': 'OPENING_FAST',
        'active_channel_label': u'\u5f00\u76d8\u5f3a\u4fe1\u53f7\u89c2\u5bdf',
        'opening_fast_enabled': (config or default_config()).get('opening_fast_enabled', True),
        'opening_fast_active': False,
        'opening_fast_bars': 0,
        'opening_fast_min_bars': (config or default_config()).get('opening_fast_min_bars', 2),
        'opening_fast_status': u'\u7b49\u5f85\u5f00\u76d8',
        'regular_ready': False,
        'regular_warmup_progress': 0,
        'backfill_status': 'not_run',
        'backfill_reason': None,
        'first_open': None, 'pre_close': None, 'opening_gap_pct': None,
        'last_signal_side': None, 'last_signal_channel': None,
        'active_turn_event': None,
        'candidate_alerts_enabled': (config or default_config()).get('candidate_alerts_enabled', True),
    }


class SharedState(object):
    def __init__(self):
        self.lock = threading.RLock()
        self.codes, self.config = [], default_config()
        self.monitoring, self.connected = False, False
        self.last_error, self.last_update = WINDPY_IMPORT_ERROR, None
        self.cache_status, self.cache_updated_at, self.cache_error = 'disabled', None, None
        self.quotes, self.bars, self.analytics, self.signals = {}, {}, {}, []
        self.turning_events = []
        self.macd_alerts = []

    def snapshot(self):
        with self.lock:
            return {
                'ok': True, 'windpy_available': WINDPY_AVAILABLE,
                'connected': self.connected, 'monitoring': self.monitoring,
                'codes': list(self.codes), 'config': dict(self.config),
                'last_error': self.last_error, 'last_update': self.last_update,
                'cache_status': self.cache_status,
                'cache_updated_at': self.cache_updated_at,
                'cache_error': self.cache_error,
                'quotes': dict(self.quotes), 'bars': dict(self.bars),
                'analytics': dict(self.analytics), 'signals': list(self.signals),
                'turning_events': list(self.turning_events),
                'macd_alerts': list(self.macd_alerts),
                'server_time': now_text(),
            }


class QuoteDeduper(object):
    def __init__(self):
        self.last_keys = {}

    def reset(self, code=None):
        self.last_keys = {} if code is None else dict((k, v) for k, v in self.last_keys.items() if k != code)

    def is_duplicate(self, code, quote):
        key = (quote.get('rt_time'), quote.get('price'),
               quote.get('volume_total'), quote.get('amount_total'))
        if self.last_keys.get(code) == key:
            return True
        self.last_keys[code] = key
        return False


def cumulative_delta(value, previous):
    current, before = number(value), number(previous)
    if current is None:
        return 0.0, u'\u7d2f\u8ba1\u91cf\u7f3a\u5931'
    if before is None:
        return 0.0, None
    if current < before:
        return 0.0, u'\u7d2f\u8ba1\u91cf\u56de\u9000\uff0c\u5df2\u5ffd\u7565\u672c\u6b21\u589e\u91cf'
    return current - before, None


class MicroBarAggregator(object):
    def __init__(self):
        self.current, self.completed, self.cumulative, self.last_unique_at = {}, {}, {}, {}
        self.days, self.session_meta = {}, {}

    def reset(self, code=None):
        if code is None:
            self.current, self.completed, self.cumulative, self.last_unique_at = {}, {}, {}, {}
            self.days, self.session_meta = {}, {}
        else:
            for store in (self.current, self.completed, self.cumulative, self.last_unique_at, self.days, self.session_meta):
                store.pop(code, None)

    def update(self, code, quote):
        epoch = quote.get('epoch') or time.time()
        day = datetime.datetime.fromtimestamp(epoch).date()
        if self.days.get(code) != day:
            for store in (self.current, self.completed, self.cumulative):
                store.pop(code, None)
            self.days[code] = day
            self.session_meta.pop(code, None)
        meta = self.session_meta.setdefault(code, {
            'pre_close': None, 'first_open': None, 'opening_gap_pct': None,
        })
        if quote.get('pre_close') is not None:
            meta['pre_close'] = quote.get('pre_close')
        quote_seconds = time_seconds(quote.get('time'))
        if quote_seconds is None and quote.get('epoch') is not None:
            quote_seconds = (datetime.datetime.fromtimestamp(quote.get('epoch')).hour * 3600 +
                             datetime.datetime.fromtimestamp(quote.get('epoch')).minute * 60 +
                             datetime.datetime.fromtimestamp(quote.get('epoch')).second)
        if quote_seconds is not None and 34200 <= quote_seconds < 34200 + 5 * 60 and meta.get('first_open') is None:
            meta['first_open'] = quote.get('price')
        if meta.get('opening_gap_pct') is None and meta.get('first_open') is not None and meta.get('pre_close'):
            meta['opening_gap_pct'] = (meta['first_open'] - meta['pre_close']) / meta['pre_close'] * 100.0
        bucket = int(epoch // BUCKET_SECONDS) * BUCKET_SECONDS
        previous = self.cumulative.get(code, {})
        volume, vi = cumulative_delta(quote.get('volume_total'), previous.get('volume'))
        amount, ai = cumulative_delta(quote.get('amount_total'), previous.get('amount'))
        self.cumulative[code] = {'volume': quote.get('volume_total'), 'amount': quote.get('amount_total')}
        current, completed = self.current.get(code), self.completed.setdefault(code, [])
        if current is None or current['_bucket'] != bucket:
            if current is not None:
                completed.append(self.public(current))
                self.completed[code] = completed[-MAX_BARS:]
            current = {
                '_bucket': bucket, 'timestamp': float(bucket),
                'time': datetime.datetime.fromtimestamp(bucket).strftime('%H:%M:%S'),
                'open': quote['price'], 'high': quote['price'], 'low': quote['price'],
                'close': quote['price'], 'pct_change': quote.get('pct_change'),
                'vwap': quote.get('vwap'),
                'micro_vwap': quote['price'], 'volume': 0.0, 'amount': 0.0,
                '_pv': 0.0, '_volume_sum': 0.0, '_issues': [],
                'pre_close': meta.get('pre_close'),
                'first_open': meta.get('first_open'),
                'opening_gap_pct': meta.get('opening_gap_pct'),
            }
            self.current[code] = current
        current['high'] = max(current['high'], quote['price'])
        current['low'] = min(current['low'], quote['price'])
        current['close'] = quote['price']
        current['pct_change'] = quote.get('pct_change')
        current['volume'] += volume
        current['amount'] += amount
        current['_issues'].extend([x for x in (vi, ai) if x])
        if volume > 0:
            current['_pv'] += quote['price'] * volume
            current['_volume_sum'] += volume
            current['micro_vwap'] = current['_pv'] / current['_volume_sum']
        if quote.get('vwap') is not None:
            current['vwap'] = quote['vwap']
        current['pre_close'] = meta.get('pre_close')
        current['first_open'] = meta.get('first_open')
        current['opening_gap_pct'] = meta.get('opening_gap_pct')
        self.last_unique_at[code] = time.time()
        return {
            'bars': self.public_bars(code), 'completed': list(self.completed.get(code, [])),
            'current': self.public(current), 'issues': list(set(current['_issues'])),
        }

    def public(self, bar):
        vwap = bar.get('vwap') if bar.get('vwap') is not None else bar.get('micro_vwap')
        return {
            'open': clean(bar.get('open')), 'high': clean(bar.get('high')),
            'low': clean(bar.get('low')), 'close': clean(bar.get('close')),
            'pct_change': clean(bar.get('pct_change')),
            'vwap': clean(vwap), 'micro_vwap': clean(bar.get('micro_vwap')),
            'volume': clean(bar.get('volume'), 3), 'amount': clean(bar.get('amount'), 3),
            'timestamp': bar.get('timestamp'), 'time': bar.get('time'),
            'pre_close': clean(bar.get('pre_close'), 4),
            'first_open': clean(bar.get('first_open'), 4),
            'opening_gap_pct': clean(bar.get('opening_gap_pct'), 4),
        }

    def public_bars(self, code):
        bars = list(self.completed.get(code, []))
        if code in self.current:
            bars.append(self.public(self.current[code]))
        return bars[-MAX_BARS:]


class WindMonitor(object):
    def __init__(self, state, cache=None):
        self.state, self.engine = state, SwingV3Engine()
        self.macd_engine = MacdDivergenceEngine()
        self.deduper, self.aggregator = QuoteDeduper(), MicroBarAggregator()
        self.decision_aggregator = DecisionBarAggregator()
        self.cache = cache
        self.micro_history, self.decision_history = {}, {}
        self.history_days = {}
        self.backfill_days = {}
        self.thread, self.stop_event, self.lock = None, threading.Event(), threading.RLock()

    def _sync_cache_state(self):
        if self.cache is None:
            self.state.cache_status = 'disabled'
            self.state.cache_updated_at = None
            self.state.cache_error = None
            return
        self.state.cache_status = self.cache.status
        self.state.cache_updated_at = self.cache.updated_at
        self.state.cache_error = self.cache.last_error

    def _cache_payload(self):
        with self.state.lock:
            codes = list(self.state.codes)
            return {
                'version': CACHE_VERSION,
                'trading_day': trading_day_text(),
                'codes': codes,
                'config': dict(self.state.config),
                'micro_bars': dict(
                    (code, list(self.micro_history.get(code, [])))
                    for code in codes if self.micro_history.get(code)),
                'decision_bars': dict(
                    (code, list(self.decision_history.get(code, [])))
                    for code in codes if self.decision_history.get(code)),
                'signals': list(self.state.signals),
                'turning_events': list(self.state.turning_events),
                'macd_alerts': list(self.state.macd_alerts),
            }

    def _persist_cache(self):
        if self.cache is None:
            return False
        saved = self.cache.save(self._cache_payload())
        with self.state.lock:
            self._sync_cache_state()
        return saved

    def restore_cache(self, payload):
        payload = payload if isinstance(payload, dict) else {}
        config = normalize_config(payload.get('config') or {})
        codes = normalize_codes(payload.get('codes') or [])
        raw_micro = payload.get('micro_bars') if isinstance(payload.get('micro_bars'), dict) else {}
        raw_decisions = (
            payload.get('decision_bars')
            if isinstance(payload.get('decision_bars'), dict) else {})
        raw_signals = payload.get('signals') if isinstance(payload.get('signals'), list) else []
        raw_events = (
            payload.get('turning_events')
            if isinstance(payload.get('turning_events'), list) else [])
        raw_macd_alerts = (
            payload.get('macd_alerts')
            if isinstance(payload.get('macd_alerts'), list) else [])
        self.micro_history = dict(
            (code, merge_timestamped([], raw_micro.get(code), MAX_BARS))
            for code in codes if raw_micro.get(code))
        self.decision_history = dict(
            (code, merge_timestamped([], raw_decisions.get(code), MAX_DECISION_BARS))
            for code in codes if raw_decisions.get(code))
        self.history_days = dict(
            (code, trading_day_text()) for code in codes
            if self.micro_history.get(code) or self.decision_history.get(code))
        with self.state.lock:
            self.state.codes = codes
            self.state.config = config
            self.state.quotes = {}
            self.state.bars = dict(
                (code, list(self.micro_history.get(code, [])))
                for code in codes if self.micro_history.get(code))
            self.state.analytics = {}
            self.state.signals = [
                dict(item) for item in raw_signals
                if isinstance(item, dict) and item.get('code') in codes
            ][:MAX_SIGNALS]
            self.state.turning_events = [
                dict(item) for item in raw_events
                if (isinstance(item, dict) and item.get('code') in codes and
                     item.get('event_state') not in ('CANDIDATE', 'STRENGTHENING'))
            ][:MAX_SIGNALS]
            self.state.macd_alerts = [
                dict(item) for item in raw_macd_alerts
                if (isinstance(item, dict) and item.get('code') in codes and
                    item.get('strategy_version') == MACD_STRATEGY_VERSION)
            ][:MAX_SIGNALS]
            self.state.last_update = payload.get('updated_at')
            self._sync_cache_state()
        for code in codes:
            analytics = None
            decisions = self.decision_history.get(code, [])
            for item in decisions:
                analytics, ignored_signal = self.engine.process(code, item, config)
                self.engine.drain_event_updates(code)
                macd_alert = self.macd_engine.process(code, item)
                if (macd_alert is not None and
                        config.get('macd_strategy_enabled', True)):
                    self._upsert_macd_alert(macd_alert)
            self.engine.drain_event_updates(code)
            self.engine.discard_event_state(code)
            if analytics is not None:
                reason = (
                    u'\u5df2\u4ece\u5f53\u65e5\u7f13\u5b58\u6062\u590d %d '
                    u'\u6839\u5b8c\u6574\u5206\u949f K\uff0c\u65e0\u9700\u9884\u70ed'
                ) % len(decisions)
                self._record_backfill(code, 'cache', reason, analytics)
            else:
                self.state.analytics[code] = empty_analytics(config)
        return codes

    def _last_engine_timestamp(self, code):
        state = self.engine.states.get(code) or {}
        timestamps = [
            number(item.get('timestamp')) for item in state.get('bars', [])
            if number(item.get('timestamp')) is not None
        ]
        return max(timestamps) if timestamps else None

    def _prepare_history_day(self, code, quote, config):
        epoch = number(quote.get('epoch'))
        if epoch is None:
            return False
        day = trading_day_text(datetime.datetime.fromtimestamp(epoch))
        previous = self.history_days.get(code)
        self.history_days[code] = day
        if previous is None or previous == day:
            return False
        self.micro_history.pop(code, None)
        self.decision_history.pop(code, None)
        self.backfill_days.pop(code, None)
        with self.state.lock:
            self.state.bars.pop(code, None)
            self.state.analytics[code] = empty_analytics(config)
            self.state.signals = [
                item for item in self.state.signals if item.get('code') != code]
            self.state.turning_events = [
                item for item in self.state.turning_events if item.get('code') != code]
            self.state.macd_alerts = [
                item for item in self.state.macd_alerts if item.get('code') != code]
        return True

    def set_codes(self, codes):
        normalized = normalize_codes(codes)
        with self.state.lock:
            old, self.state.codes = list(self.state.codes), normalized
            for code in [x for x in old if x not in normalized]:
                for store in (self.state.quotes, self.state.bars, self.state.analytics):
                    store.pop(code, None)
                self.state.turning_events = [
                    item for item in self.state.turning_events if item.get('code') != code]
                self.state.signals = [
                    item for item in self.state.signals if item.get('code') != code]
                self.state.macd_alerts = [
                    item for item in self.state.macd_alerts if item.get('code') != code]
                self.engine.reset_code(code); self.macd_engine.reset_code(code)
                self.deduper.reset(code); self.aggregator.reset(code)
                self.decision_aggregator.reset(code)
                self.micro_history.pop(code, None)
                self.decision_history.pop(code, None)
                self.history_days.pop(code, None)
                self.backfill_days.pop(code, None)
            for code in [x for x in normalized if x not in old]:
                self.state.analytics[code] = empty_analytics(self.state.config)
        self._persist_cache()
        return normalized

    def set_config(self, payload):
        config = normalize_config(payload)
        with self.state.lock:
            self.state.config = config
            for code in self.state.codes:
                self.state.analytics.setdefault(code, empty_analytics(config))
                self.state.analytics[code]['warmup_target'] = config['warmup_bars']
                self.state.analytics[code]['candidate_alerts_enabled'] = config.get('candidate_alerts_enabled', True)
        self._persist_cache()
        return config

    def _upsert_turning_event(self, event):
        event_id = event.get('event_id')
        if not event_id:
            return
        with self.state.lock:
            previous = [item for item in self.state.turning_events
                        if item.get('event_id') == event_id]
            if previous:
                previous_revision = number(previous[0].get('revision'), 0)
                incoming_revision = number(event.get('revision'), 0)
                if incoming_revision < previous_revision:
                    return
            self.state.turning_events = [
                item for item in self.state.turning_events if item.get('event_id') != event_id]
            self.state.turning_events.insert(0, dict(event))
            self.state.turning_events = self.state.turning_events[:MAX_SIGNALS]

    def _upsert_macd_alert(self, event):
        event_id = event.get('event_id') or event.get('id')
        if not event_id:
            return
        with self.state.lock:
            previous = [
                item for item in self.state.macd_alerts
                if (item.get('event_id') or item.get('id')) == event_id]
            if previous:
                previous_revision = number(previous[0].get('revision'), 0)
                incoming_revision = number(event.get('revision'), 0)
                if incoming_revision < previous_revision:
                    return
            self.state.macd_alerts = [
                item for item in self.state.macd_alerts
                if (item.get('event_id') or item.get('id')) != event_id]
            self.state.macd_alerts.insert(0, dict(event))
            self.state.macd_alerts = self.state.macd_alerts[:MAX_SIGNALS]

    def start(self):
        with self.lock:
            if self.thread is not None and self.thread.is_alive():
                self.state.monitoring = True
                return
            self.stop_event.clear(); self.state.monitoring = True; self.state.last_error = None
            self.thread = threading.Thread(target=self.run, name='windpy-monitor')
            self.thread.daemon = True; self.thread.start()

    def stop(self):
        self.stop_event.set()
        with self.state.lock:
            self.state.monitoring, self.state.connected = False, False
        if self.thread is not None and self.thread.is_alive() and self.thread is not threading.current_thread():
            self.thread.join(3.0)
        self.thread = None
        self._persist_cache()

    def connect(self):
        if not WINDPY_AVAILABLE:
            raise RuntimeError(u'\u5f53\u524d Python \u89e3\u91ca\u5668\u672a\u627e\u5230 WindPy\uff0c\u8bf7\u4f7f\u7528 Wind \u5b89\u88c5\u7684 Python 2.7 \u73af\u5883')
        result = w.start()
        code = getattr(result, 'ErrorCode', 0)
        if code not in (None, 0) or not w.isconnected():
            raise RuntimeError(u'WindPy \u672a\u8fde\u63a5\u5230 Wind \u7ec8\u7aef: %s' % code)
        self.state.connected, self.state.last_error = True, None

    def disconnect(self):
        try:
            if WINDPY_AVAILABLE and w.isconnected():
                w.stop()
        except Exception:
            pass
        self.state.connected = False

    def run(self):
        try:
            self.connect()
            while not self.stop_event.is_set():
                with self.state.lock:
                    codes, config = list(self.state.codes), dict(self.state.config)
                if codes:
                    try:
                        self.poll(codes, config)
                    except Exception as exc:
                        self.state.last_error, self.state.connected = u'\u884c\u60c5\u8bfb\u53d6\u5931\u8d25: %s' % exc, False
                        if self.stop_event.wait(3.0):
                            break
                        try:
                            self.connect()
                        except Exception as reconnect:
                            self.state.last_error = u'WindPy \u91cd\u8fde\u5931\u8d25: %s' % reconnect
                    else:
                        self.stop_event.wait(POLL_SECONDS)
                else:
                    self.stop_event.wait(POLL_SECONDS)
        except Exception as exc:
            self.state.last_error, self.state.connected, self.state.monitoring = str(exc), False, False
        finally:
            self.disconnect(); self.state.monitoring = False

    def _record_backfill(self, code, status, reason=None, analytics=None):
        state = self.engine.states.get(code)
        if state is not None:
            state['backfill_status'] = status
            state['backfill_reason'] = reason
        current = dict(analytics or self.state.analytics.get(code) or empty_analytics(self.state.config))
        current['backfill_status'] = status
        current['backfill_reason'] = reason
        current['active_turn_event'] = None
        self.state.analytics[code] = current

    def _backfill_code(self, code, pre_close, config):
        today = datetime.datetime.now().date()
        if self.backfill_days.get(code) == today:
            return
        self.backfill_days[code] = today
        try:
            latest = latest_completed_minute()
            if latest.time() < datetime.time(9, 30):
                self._record_backfill(code, 'skipped', u'当前尚无完整历史分钟K')
                return
            previous_tail = self._last_engine_timestamp(code)
            latest_timestamp = wsi_epoch(latest)
            if (previous_tail is not None and latest_timestamp is not None and
                    previous_tail >= latest_timestamp):
                analytics = self.state.analytics.get(code)
                restored = len(self.decision_history.get(code, []))
                reason = (
                    u'\u5f53\u65e5\u7f13\u5b58\u5df2\u6062\u590d %d '
                    u'\u6839\u5b8c\u6574\u5206\u949f K\uff0c\u65e0\u9700 WSI \u8865\u9f50'
                ) % restored
                self._record_backfill(code, 'cache', reason, analytics)
                return
            begin = latest.replace(hour=9, minute=30, second=0, microsecond=0)
            if previous_tail is not None:
                cached_next = datetime.datetime.fromtimestamp(previous_tail + 60.0)
                if cached_next.date() == latest.date() and cached_next > begin:
                    begin = cached_next
            begin_time = begin.strftime('%Y-%m-%d %H:%M:%S')
            latest_completed = latest.strftime('%Y-%m-%d %H:%M:%S')
            result = w.wsi(code, 'open,high,low,close,volume,amt', begin_time,
                           latest_completed, 'BarSize=1')
            all_bars = parse_wsi_bars(result, pre_close, latest)
            if not all_bars:
                self._record_backfill(code, 'skipped', u'WSI未返回完整历史分钟K')
                return
            bars = [
                item for item in all_bars
                if previous_tail is None or item.get('timestamp') > previous_tail
            ]
            if not bars:
                analytics = self.state.analytics.get(code)
                restored = len(self.decision_history.get(code, []))
                reason = (
                    u'\u5f53\u65e5\u7f13\u5b58\u5df2\u6062\u590d %d '
                    u'\u6839\u5b8c\u6574\u5206\u949f K\uff0cWSI \u65e0\u65ad\u6863\u9700\u8865'
                ) % restored
                self._record_backfill(code, 'cache', reason, analytics)
                self._persist_cache()
                return
            analytics = None
            for item in bars:
                analytics, ignored_signal = self.engine.process(code, item, config)
                self.engine.drain_event_updates(code)
                self.macd_engine.process(code, item)
            restored = len(self.decision_history.get(code, []))
            self.decision_history[code] = merge_timestamped(
                self.decision_history.get(code), bars, MAX_DECISION_BARS)
            self.engine.drain_event_updates(code)
            self.engine.discard_event_state(code)
            if previous_tail is None:
                reason = u'已回填 %d 根完整分钟K，仅用于预热' % len(bars)
            else:
                reason = (
                    u'\u5df2\u4ece\u7f13\u5b58\u6062\u590d %d \u6839\uff0c'
                    u'WSI \u4ec5\u8865\u9f50 %d \u6839\u65ad\u6863\u5206\u949f K'
                ) % (restored, len(bars))
            self._record_backfill(code, 'ok', reason, analytics)
            self._persist_cache()
        except Exception as exc:
            self.engine.drain_event_updates(code)
            self.engine.discard_event_state(code)
            self._record_backfill(code, 'failed', unicode(exc))

    def _backfill_before_realtime(self, code, quote, config):
        self._backfill_code(code, quote.get('pre_close'), config)

    def _reset_on_quote_clock_regression(self, code, quote, config):
        previous = self.state.quotes.get(code) or {}
        previous_epoch = number(previous.get('epoch'))
        current_epoch = number(quote.get('epoch'))
        if previous_epoch is None or current_epoch is None:
            return False
        previous_day = datetime.datetime.fromtimestamp(previous_epoch).date()
        current_day = datetime.datetime.fromtimestamp(current_epoch).date()
        if previous_day != current_day or current_epoch + 300 >= previous_epoch:
            return False
        self.engine.reset_code(code)
        self.macd_engine.reset_code(code)
        self.deduper.reset(code)
        self.aggregator.reset(code)
        self.decision_aggregator.reset(code)
        self.backfill_days.pop(code, None)
        self.micro_history.pop(code, None)
        self.decision_history.pop(code, None)
        self.history_days[code] = trading_day_text(
            datetime.datetime.fromtimestamp(current_epoch))
        self.state.bars.pop(code, None)
        self.state.analytics[code] = empty_analytics(config)
        self.state.signals = [
            item for item in self.state.signals if item.get('code') != code]
        self.state.turning_events = [
            item for item in self.state.turning_events if item.get('code') != code]
        self.state.macd_alerts = [
            item for item in self.state.macd_alerts if item.get('code') != code]
        return True

    def poll(self, codes, config):
        result = w.wsq(','.join(codes), QUOTE_FIELD_STRING)
        if getattr(result, 'ErrorCode', 0) not in (None, 0):
            raise RuntimeError('WindPy wsq error %s' % result.ErrorCode)
        data, response_codes = getattr(result, 'Data', []), list(getattr(result, 'Codes', codes) or codes)
        notification_events = {}
        cache_dirty = False
        for index, code in enumerate(response_codes):
            values = {}
            for field_index, field in enumerate(QUOTE_FIELDS):
                row = data[field_index] if field_index < len(data) else []
                values[field] = row[index] if index < len(row) else None
            price, text = number(values.get('rt_last')), quote_time(values.get('rt_time'))
            if price is None or price <= 0:
                self.state.analytics[code] = dict(self.state.analytics.get(code) or empty_analytics(config), ready=False, blocked_reasons=[u'\u4ef7\u683c\u65e0\u6548'])
                continue
            pct, vwap = number(values.get('rt_pct_chg'), 0.0), number(values.get('rt_vwap'))
            if vwap is not None and (vwap <= price * 0.5 or vwap >= price * 1.5):
                vwap = None
            quote = {'code': code, 'price': price, 'pct_change': pct, 'change': '%.2f%%' % pct, 'volume_total': number(values.get('rt_vol')), 'amount_total': number(values.get('rt_amt')), 'high': number(values.get('rt_high')), 'low': number(values.get('rt_low')), 'pre_close': number(values.get('rt_pre_close')), 'vwap': vwap, 'bid1': number(values.get('rt_bid1')), 'ask1': number(values.get('rt_ask1')), 'rt_time': values.get('rt_time'), 'time': text, 'epoch': quote_epoch(text), 'updated_at': now_text()}
            cache_dirty = self._prepare_history_day(code, quote, config) or cache_dirty
            cache_dirty = self._reset_on_quote_clock_regression(
                code, quote, config) or cache_dirty
            self.state.quotes[code], self.state.last_update = quote, now_text()
            self._backfill_before_realtime(code, quote, config)
            if self.deduper.is_duplicate(code, quote):
                continue
            event = self.aggregator.update(code, quote)
            self.micro_history[code] = merge_timestamped(
                self.micro_history.get(code), event['completed'], MAX_BARS)
            self.state.bars[code] = merge_timestamped(
                self.micro_history.get(code), event['bars'], MAX_BARS)
            analytics = self.state.analytics.get(code) or empty_analytics(config)
            decision_bars = self.decision_aggregator.consume(code, event['completed'])
            if decision_bars:
                self.decision_history[code] = merge_timestamped(
                    self.decision_history.get(code), decision_bars, MAX_DECISION_BARS)
                cache_dirty = True
            for decision_bar in decision_bars:
                analytics, signal = self.engine.process(code, decision_bar, config)
                macd_alert = self.macd_engine.process(code, decision_bar)
                swing_enabled = config.get('swing_strategy_enabled', True)
                macd_enabled = config.get('macd_strategy_enabled', True)
                if macd_alert is not None and macd_enabled:
                    self._upsert_macd_alert(macd_alert)
                    if (config.get('notifications_enabled', True) and
                            macd_alert.get('notification_kind') == 'CONFIRMED'):
                        notification_events[
                            ('MACD', macd_alert.get('event_id') or macd_alert.get('id'))
                        ] = ('MACD', macd_alert)
                if signal is not None and swing_enabled:
                    self.state.signals.insert(0, signal)
                    self.state.signals = self.state.signals[:MAX_SIGNALS]
                updates = self.engine.drain_event_updates(code)
                confirmed_update_seen = False
                for update in updates if swing_enabled else []:
                    self._upsert_turning_event(update)
                    event_id = update.get('event_id')
                    notification_key = (event_id, update.get('observed_timestamp') or
                                        update.get('updated_timestamp'))
                    if update.get('notification_kind') == 'CONFIRMED':
                        confirmed_update_seen = True
                        if config.get('notifications_enabled', True):
                            notification_events[notification_key] = ('Confirmed', update)
                    elif (update.get('notification_kind') == 'CANDIDATE' and
                          config.get('notifications_enabled', True) and
                          config.get('candidate_alerts_enabled', True) and
                          config.get('candidate_notifications_enabled', True) and
                          notification_key not in notification_events):
                        notification_events[notification_key] = ('Candidate', update)
                if (signal is not None and swing_enabled and not confirmed_update_seen and
                        config.get('notifications_enabled', True)):
                    signal_key = (signal.get('event_id', signal.get('id')),
                                  signal.get('bar_timestamp') or signal.get('timestamp'))
                    notification_events[signal_key] = ('Confirmed', signal)
            if event['issues']:
                analytics = dict(analytics)
                reasons = list(analytics.get('blocked_reasons') or [])
                reasons.extend([issue for issue in event['issues'] if issue not in reasons])
                analytics['blocked_reasons'] = reasons
            self.state.analytics[code] = analytics
        for code in codes:
            last = self.aggregator.last_unique_at.get(code)
            if last is not None and time.time() - last >= STALE_SECONDS:
                self.state.analytics[code] = self.engine.mark_stale(self.state.analytics.get(code), config)
        if cache_dirty:
            self._persist_cache()
        for level, signal in notification_events.values():
            if level == 'MACD':
                sell = signal['side'] == 'SELL'
                title_label = u'%s · %s' % (
                    signal.get('module_label') or (
                        u'多尺度顶部确认' if sell else u'多尺度底部确认'),
                    signal.get('action_label') or (
                        u'卖出建议' if sell else u'买入建议'))
                message = (
                    u'%s %.2f（%s）；%s阈值 %.3f%%，'
                    u'波段 %.3f%% / %s 根 K，多尺度一致度 %.0f%%；'
                    u'MACD-V %.1f（%s），%s确认价 %.2f，置信度 %s。'
                ) % (
                    u'高点' if sell else u'低点',
                    signal['extreme_price'], signal['extreme_time'],
                    signal.get('scale_label', u'自适应'),
                    number(signal.get('scale_threshold_pct'), 0.0),
                    number(signal.get('leg_amplitude_pct'), 0.0),
                    signal.get('leg_bars', 0),
                    number(signal.get('consensus_pct'), 0.0),
                    number(signal.get('macdv'), 0.0),
                    signal.get('momentum_stage_label', u'动能转向'),
                    signal['confirm_time'], signal['confirm_price'],
                    signal.get('confidence'))
                send_notification(
                    u'%s  %s' % (signal['code'], title_label),
                    message, 'Confirmed')
                continue
            is_candidate = level == 'Candidate'
            if is_candidate:
                title_label = u'\u5019\u9009\u5206\u65f6\u5e95 \u00b7 \u89c2\u5bdf\u4e70\u70b9' if signal['side'] == 'BUY' else u'\u5019\u9009\u5206\u65f6\u9876 \u00b7 \u89c2\u5bdf\u5356\u70b9'
                message = u'%s %.2f\uff08%s\uff09\uff0c\u5019\u9009\u89c2\u5bdf\uff0c\u975e\u4ea4\u6613\u6307\u4ee4\uff1b\u5f53\u524d\u4ef7 %.2f\uff0c\u7f6e\u4fe1\u5ea6 %s\u3002' % (
                    u'\u8c37\u503c' if signal['side'] == 'BUY' else u'\u5cf0\u503c',
                    signal['extreme_price'], signal['extreme_time'],
                    signal.get('observed_price'), signal.get('confidence'))
            else:
                title_label = u'\u5206\u65f6\u5e95\u4e70\u5165\u63d0\u9192' if signal['side'] == 'BUY' else u'\u5206\u65f6\u9876\u5356\u51fa\u63d0\u9192'
                message = u'%s %.2f\uff08%s\uff09\uff0c%s\u786e\u8ba4\u4ef7 %.2f\uff0c\u7f6e\u4fe1\u5ea6 %s\u3002' % (
                    u'\u8c37\u503c' if signal['side'] == 'BUY' else u'\u5cf0\u503c',
                    signal['extreme_price'], signal['extreme_time'],
                    signal['confirm_time'], signal['confirm_price'], signal.get('confidence'))
            send_notification(u'%s  %s' % (signal['code'], title_label), message, level)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads, allow_reuse_address = True, True


STATE, MONITOR = SharedState(), None


def windows_arg(value):
    return value.encode('mbcs', 'replace') if isinstance(value, unicode) else str(value)


def notification_path():
    path = os.path.abspath(__file__)
    if not isinstance(path, unicode):
        path = path.decode('mbcs', 'replace')
    return os.path.join(os.path.dirname(path), u'notify_toast.ps1')


def send_notification(title, message, level='Confirmed'):
    if os.name != 'nt':
        return False
    try:
        script, flags = notification_path(), getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
        if not os.path.exists(script):
            return False
        subprocess.Popen([windows_arg('powershell.exe'), windows_arg('-NoProfile'), windows_arg('-ExecutionPolicy'), windows_arg('Bypass'), windows_arg('-WindowStyle'), windows_arg('Hidden'), windows_arg('-File'), windows_arg(script), windows_arg('-Title'), windows_arg(title), windows_arg('-Message'), windows_arg(message), windows_arg('-Level'), windows_arg(level)], creationflags=flags)
        return True
    except Exception:
        return False


class ApiHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, format_string, *args):
        return
    def headers_for(self, length=None):
        self.send_header('Access-Control-Allow-Origin', '*'); self.send_header('Access-Control-Allow-Headers', 'Content-Type'); self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'); self.send_header('Cache-Control', 'no-store'); self.send_header('Content-Type', 'application/json; charset=utf-8')
        if length is not None:
            self.send_header('Content-Length', str(length))
    def send_json(self, status, payload):
        body = json_bytes(payload); self.send_response(status); self.headers_for(len(body)); self.end_headers(); self.wfile.write(body)
    def read_json(self):
        try:
            length = self.headers.getheader('Content-Length')
        except AttributeError:
            length = self.headers.get('Content-Length')
        raw = self.rfile.read(int(length or 0))
        return json.loads(raw.decode('utf-8')) if raw else {}
    def do_OPTIONS(self):
        self.send_response(204); self.headers_for(0); self.end_headers()
    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/health':
            state = STATE.snapshot(); self.send_json(200, {
                'ok': True,
                'windpy_available': state['windpy_available'],
                'connected': state['connected'],
                'monitoring': state['monitoring'],
                'last_error': state['last_error'],
                'cache_status': state['cache_status'],
                'cache_updated_at': state['cache_updated_at'],
                'cache_error': state['cache_error'],
            })
        elif path == '/api/state':
            self.send_json(200, STATE.snapshot())
        else:
            self.send_json(404, {'ok': False, 'error': 'not found'})
    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self.read_json()
            if path == '/api/watchlist':
                self.send_json(200, {'ok': True, 'codes': MONITOR.set_codes(payload.get('codes', [])), 'state': STATE.snapshot()})
            elif path == '/api/config':
                self.send_json(200, {'ok': True, 'config': MONITOR.set_config(payload), 'state': STATE.snapshot()})
            elif path == '/api/monitor':
                if 'codes' in payload:
                    MONITOR.set_codes(payload.get('codes', []))
                if 'config' in payload:
                    MONITOR.set_config(payload.get('config'))
                if as_bool(payload.get('running'), False):
                    MONITOR.start()
                else:
                    MONITOR.stop()
                self.send_json(200, {'ok': True, 'state': STATE.snapshot()})
            elif path == '/api/notify/test':
                ok = send_notification(u'\u91cf\u5316\u52a9\u624b\u63d0\u9192\u6d4b\u8bd5', u'Windows \u63d0\u9192\u901a\u9053\u5df2\u89e6\u53d1\u3002')
                self.send_json(200, {'ok': bool(ok), 'message': u'\u5df2\u89e6\u53d1\u63d0\u9192' if ok else u'\u63d0\u9192\u901a\u9053\u8c03\u7528\u5931\u8d25'})
            else:
                self.send_json(404, {'ok': False, 'error': 'not found'})
        except Exception as exc:
            self.send_json(400, {'ok': False, 'error': str(exc)})


MONITOR = WindMonitor(STATE)


def main():
    global STATE, MONITOR
    cache = IntradayCache(CACHE_PATH)
    cached_payload = cache.load()
    STATE = SharedState()
    MONITOR = WindMonitor(STATE, cache)
    MONITOR.restore_cache(cached_payload)
    server = ThreadedHTTPServer((HOST, PORT), ApiHandler)
    print('feels-quanty backend listening on http://%s:%s' % (HOST, PORT))
    # Python 2.7 stdout can be ASCII when redirected by the launcher. Do not
    # interpolate the Chinese absolute project path into startup logs.
    print('Intraday cache status: %s' % STATE.cache_status)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        MONITOR.stop(); server.server_close()


if __name__ == '__main__':
    main()
