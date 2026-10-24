import asyncio
import base64
from datetime import date, datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from pywebpush import WebPushException
import httpx

from utils.web_push import PushEngine, Settings, create_app, validate_subscription

UTC = timezone.utc
TOKEN = 'a' * 43
ORIGIN = 'https://example.com'
HEADERS = {'Origin': ORIGIN, 'Authorization': f'Bearer {TOKEN}'}


def subscription(endpoint='https://fcm.googleapis.com/fcm/send/test'):
    key = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    encode = lambda raw: base64.urlsafe_b64encode(raw).decode().rstrip('=')
    return {'endpoint': endpoint, 'keys': {'p256dh': encode(key), 'auth': encode(b'0123456789abcdef')}}


def configuration(prayers=None, locale='en', latitude='51.5074'):
    return {'query': {'latitude': latitude, 'longitude': '-0.1278', 'method': '3', 'school': '1', 'tune': '0,2,0,0,0,0,0,0,0'}, 'prayers': prayers if prayers is not None else ['Fajr', 'Dhuhr'], 'locale': locale}


@pytest.fixture
def setup(tmp_path):
    now = [datetime(2026, 10, 24, tzinfo=UTC).timestamp()]
    calls, sent = [], []

    async def fetch_day(on_date, query):
        calls.append((on_date, dict(query)))
        minute = on_date.day - 24
        return {'meta': {'timezone': 'Europe/London'}, 'date': {'gregorian': {'date': on_date.strftime('%d-%m-%Y')}}, 'timings': {'Fajr': f'06:{minute:02}', 'Dhuhr': '12:30', 'Asr': '15:30', 'Maghrib': '17:30', 'Isha': '19:30'}}

    async def sender(sub, payload, ttl):
        sent.append((sub, payload, ttl))

    settings = Settings(str(tmp_path / 'push.sqlite3'), 'public', 'private', 'mailto:owner@example.com', [ORIGIN], 's' * 32)
    engine = PushEngine(settings, fetch_day, sender, lambda: now[0])
    parent = FastAPI()
    parent.mount('/web-push', create_app(settings, engine))
    with TestClient(parent) as client:
        yield client, engine, now, calls, sent
    engine.db.close()


def enable(client, config=None, sub=None, headers=HEADERS):
    return client.put('/web-push/subscriptions/me', headers=headers, json={'subscription': sub or subscription(), 'configuration': config or configuration()})


def test_each_day_has_its_own_time_and_dst_offset(setup):
    client, engine, now, calls, _ = setup
    response = enable(client)
    assert response.status_code == 200, response.text
    assert response.json()['timeZone'] == 'Europe/London'
    jobs = engine.db.execute("SELECT * FROM web_push_jobs WHERE prayer='Fajr' ORDER BY date").fetchall()
    assert len(jobs) == 3
    assert datetime.fromtimestamp(jobs[0]['run_at'], UTC).isoformat() == '2026-10-24T05:00:00+00:00'
    assert datetime.fromtimestamp(jobs[1]['run_at'], UTC).isoformat() == '2026-10-25T06:01:00+00:00'
    assert [c[0] for c in calls] == [date(2026, 10, 24), date(2026, 10, 25), date(2026, 10, 26)]
    assert all(c[1] == configuration()['query'] for c in calls)


def test_cron_sends_without_a_browser_and_does_not_repeat(setup):
    client, engine, now, _, sent = setup
    enable(client, configuration(locale='ar'))
    first = engine.db.execute('SELECT MIN(run_at) AS time FROM web_push_jobs').fetchone()['time']
    now[0] = first + 20
    cron_headers = {'Authorization': 'Bearer ' + 's' * 32}
    assert client.get('/web-push/cron', headers=cron_headers).status_code == 200
    assert len(sent) == 1
    assert 'الفجر' in sent[0][1]['title']
    assert sent[0][2] == 70
    assert client.get('/web-push/cron', headers=cron_headers).status_code == 200
    assert len(sent) == 1
    # A later settings update must retain today's sent prayer identity.
    cfg = configuration(locale='ar')
    cfg['query']['tune'] = '0,3,0,0,0,0,0,0,0'
    enable(client, cfg)
    assert client.get('/web-push/cron', headers=cron_headers).status_code == 200
    assert len(sent) == 1


def test_disable_removes_subscription_and_all_its_jobs(setup):
    client, engine, _, _, _ = setup
    enable(client)
    assert client.delete('/web-push/subscriptions/me', headers=HEADERS).status_code == 204
    assert engine.db.execute('SELECT COUNT(*) AS count FROM web_push_jobs').fetchone()['count'] == 0
    assert client.get('/web-push/subscriptions/me', headers=HEADERS).status_code == 404


def test_all_prayers_can_be_disabled_without_losing_master_subscription(setup):
    client, engine, _, _, _ = setup
    enable(client)
    result = enable(client, configuration(prayers=[]))
    assert result.status_code == 200
    assert result.json()['enabled']
    assert result.json()['nextPrayer'] is None
    assert engine.db.execute('SELECT COUNT(*) AS count FROM web_push_jobs').fetchone()['count'] == 0


def test_refresh_failure_retries_without_discarding_good_schedule(setup):
    client, engine, now, _, _ = setup
    enable(client)

    async def offline(*args):
        raise OSError('offline')

    engine.fetch_day = offline
    engine.db.execute('UPDATE web_push_subscriptions SET refresh_after=0')
    engine.db.connection.commit()
    asyncio.run(engine.tick())
    assert engine.db.execute('SELECT COUNT(*) AS count FROM web_push_jobs').fetchone()['count'] == 6
    row = engine.db.execute('SELECT * FROM web_push_subscriptions').fetchone()
    assert row['refresh_after'] == now[0] + 60
    assert row['schedule_pending'] == 1
    # A different location must immediately invalidate the old pending jobs.
    result = enable(client, configuration(latitude='30.0'))
    assert result.status_code == 200
    assert result.json()['schedulePending']
    assert engine.db.execute('SELECT COUNT(*) AS count FROM web_push_jobs').fetchone()['count'] == 0


def test_expired_reminders_are_skipped_after_server_downtime(setup):
    client, engine, now, _, sent = setup
    enable(client)
    now[0] = datetime(2026, 10, 24, 18, tzinfo=UTC).timestamp()
    asyncio.run(engine.tick())
    assert sent == []


def test_failed_delivery_is_retried_within_short_ttl(setup):
    client, engine, now, _, sent = setup
    enable(client)
    first = engine.db.execute('SELECT MIN(run_at) AS time FROM web_push_jobs').fetchone()['time']
    original = engine.sender
    attempts = []

    async def flaky(*args):
        attempts.append(True)
        if len(attempts) == 1:
            raise OSError('temporary')
        await original(*args)

    engine.sender = flaky
    now[0] = first
    asyncio.run(engine.tick())
    assert not sent
    now[0] += 15
    asyncio.run(engine.tick())
    assert len(sent) == 1
    assert sent[0][2] == 75


def test_authentication_origin_and_subscription_ownership(setup):
    client, _, _, _, _ = setup
    assert enable(client, headers={'Origin': ORIGIN}).status_code == 401
    assert enable(client, headers={**HEADERS, 'Origin': 'https://evil.example'}).status_code == 403
    assert client.get('/web-push/cron').status_code == 401
    sub = subscription()
    assert enable(client, sub=sub).status_code == 200
    assert enable(client, sub=sub, headers={**HEADERS, 'Authorization': 'Bearer ' + 'b' * 43}).status_code == 409
    assert client.get('/web-push/subscriptions/me', headers={**HEADERS, 'Authorization': 'Bearer ' + 'b' * 43}).status_code == 404


@pytest.mark.parametrize('endpoint', ['http://127.0.0.1/secret', 'https://localhost/push', 'https://example.com/push', 'https://fcm.googleapis.com.evil.example/push', 'https://fcm.googleapis.com:444/push'])
def test_only_known_browser_push_hosts_are_allowed(endpoint):
    with pytest.raises(ValueError):
        validate_subscription(subscription(endpoint))


def test_test_notification_is_sent_and_rate_limited(setup):
    client, _, _, _, sent = setup
    enable(client)
    assert client.post('/web-push/subscriptions/me/test', headers=HEADERS).status_code == 200
    assert len(sent) == 1
    assert client.post('/web-push/subscriptions/me/test', headers=HEADERS).status_code == 429


def test_real_prayer_engine_matches_public_api(setup):
    client, engine, _, _, _ = setup
    engine.fetch_day = engine._fetch_day
    response = enable(client)
    assert response.status_code == 200
    assert not response.json()['schedulePending']
    from routes.prayer_times import get_timings
    for day in (24, 25, 26):
        config = configuration()['query']
        public = asyncio.run(get_timings(f'{day}-10-2026', latitude=config['latitude'], longitude=config['longitude'], method=config['method'], school=config['school'], tune=config['tune']))
        timings = json.loads(public.body)['data']['timings']
        for job in engine.db.execute('SELECT * FROM web_push_jobs WHERE date=?', (f'2026-10-{day}',)).fetchall():
            from zoneinfo import ZoneInfo
            actual = datetime.fromtimestamp(job['run_at'], ZoneInfo('Europe/London')).strftime('%H:%M')
            assert actual == timings[job['prayer']]


def test_disabled_push_does_not_require_database_or_break_other_routes(monkeypatch):
    monkeypatch.delenv('VAPID_PUBLIC_KEY', raising=False)
    app = FastAPI()
    app.mount('/web-push', create_app())
    @app.get('/existing')
    def existing():
        return {'ok': True}
    with TestClient(app) as client:
        assert client.get('/existing').status_code == 200
        assert client.get('/web-push/config').status_code == 503


def test_expired_endpoint_is_deleted_without_blocking_other_recipients(setup):
    client, engine, now, _, sent = setup
    enable(client)
    enable(client, sub=subscription('https://fcm.googleapis.com/fcm/send/second'), headers={**HEADERS, 'Authorization': 'Bearer ' + 'b' * 43})
    now[0] = engine.db.execute('SELECT MIN(run_at) AS time FROM web_push_jobs').fetchone()['time'] + 10
    original = engine.sender
    async def sender(sub, *args):
        if sub['endpoint'].endswith('/test'):
            raise WebPushException('Gone', response=httpx.Response(410))
        await original(sub, *args)
    engine.sender = sender
    asyncio.run(engine.tick())
    assert len(sent) == 1
    assert client.get('/web-push/subscriptions/me', headers=HEADERS).status_code == 404
    assert engine.db.execute('SELECT COUNT(*) AS count FROM web_push_subscriptions').fetchone()['count'] == 1


def test_generated_keys_are_valid_and_script_does_not_overwrite_them(tmp_path):
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'generate_push_keys.py'
    result = subprocess.run([sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True, check=True)
    env = dict(line.split('=', 1) for line in (tmp_path / 'secrets/vapid.env').read_text().splitlines())
    private = env['VAPID_PRIVATE_KEY']
    assert private not in result.stdout
    raw_private = base64.urlsafe_b64decode(private + '=')
    public = ec.derive_private_key(int.from_bytes(raw_private, 'big'), ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    assert base64.urlsafe_b64encode(public).decode().rstrip('=') == env['VAPID_PUBLIC_KEY']
    assert subprocess.run([sys.executable, str(script)], cwd=tmp_path, capture_output=True).returncode != 0
