![feels-quanty](./docs/assets/readme-hero.svg)

# feels-quanty

> **Local-first · Explainable · Signal only**

[![WindPy](https://img.shields.io/badge/WindPy-realtime-171A18?style=flat-square)](#数据与架构)
[![Python](https://img.shields.io/badge/Python-2.7-3776AB?style=flat-square&logo=python&logoColor=white)](#运行环境)
[![Node.js](https://img.shields.io/badge/Node.js-22.13+-5B5CF0?style=flat-square&logo=nodedotjs&logoColor=white)](#运行环境)
[![React](https://img.shields.io/badge/React-19-149ECA?style=flat-square&logo=react&logoColor=white)](#项目结构)
[![Mode](https://img.shields.io/badge/Mode-signal_only-15986A?style=flat-s~�ۭ��G����ƭy�9192\u901a\u9053\u8c03\u7528\u5931\u8d25'})
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
