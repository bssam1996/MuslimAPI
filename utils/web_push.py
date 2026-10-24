"""Persistent Web Push subscriptions and dated jobs, driven by authenticated cron."""
import asyncio
import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import psycopg
from psycopg.rows import dict_row
from pywebpush import webpush, WebPushException

PRAYERS = ('Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha')
ARABIC = dict(zip(PRAYERS, ('الفجر', 'الظهر', 'العصر', 'المغرب', 'العشاء')))
UTC = timezone.utc
MAX_LATENESS = 90
log = logging.getLogger('prayer_push')


@dataclass
class Settings:
    database: str
    public_key: str
    private_key: str
    subject: str
    origins: list[str]
    cron_secret: str = ''

    @classmethod
    def from_env(cls):
        settings = cls(
            os.getenv('DATABASE_URL') or (os.getenv('PUSH_DATABASE', '') if not os.getenv('VERCEL') else ''),
            os.environ['VAPID_PUBLIC_KEY'], os.environ['VAPID_PRIVATE_KEY'],
            os.environ['VAPID_SUBJECT'],
            [s.strip() for s in os.environ['APP_ORIGINS'].split(',') if s.strip()],
            os.environ['CRON_SECRET'],
        )
        if not settings.origins or '*' in settings.origins:
            raise ValueError('APP_ORIGINS must list exact web app origins')
        if not settings.database or len(settings.cron_secret) < 32:
            raise ValueError('Durable database and a CRON_SECRET of at least 32 characters are required')
        if os.getenv('VERCEL') and not settings.database.startswith(('postgres://', 'postgresql://')):
            raise ValueError('Vercel requires durable PostgreSQL storage')
        if not settings.subject.startswith(('mailto:', 'https://')):
            raise ValueError('VAPID_SUBJECT must be a contact mailto: or HTTPS URL')
        return settings


class Database:
    """PostgreSQL in production, SQLite only for local development and tests."""
    def __init__(self, address):
        self.postgres = address.startswith(('postgres://', 'postgresql://'))
        if self.postgres:
            self.connection = psycopg.connect(address, autocommit=True, row_factory=dict_row, connect_timeout=10)
        else:
            Path(address).parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(address, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute('PRAGMA foreign_keys=ON')
            self.connection.execute('PRAGMA journal_mode=WAL')

    def execute(self, sql, params=()):
        return self.connection.execute(sql.replace('?', '%s') if self.postgres else sql, params)

    def executescript(self, sql):
        with self:
            if self.postgres:
                self.execute('SELECT pg_advisory_xact_lock(761284302)')
            for statement in sql.split(';'):
                if statement.strip():
                    self.execute(statement)

    def __enter__(self):
        self.transaction = self.connection.transaction() if self.postgres else self.connection
        self.transaction.__enter__()
        return self

    def __exit__(self, *args):
        return self.transaction.__exit__(*args)

    def close(self):
        self.connection.close()


class SchedulerLock:
    """Transaction-scoped lock also works through pooled PostgreSQL URLs."""
    def __init__(self, db):
        self.db = db
        self.local = asyncio.Lock()

    async def __aenter__(self):
        await self.local.acquire()
        if self.db.postgres:
            self.transaction = self.db.connection.transaction()
            self.transaction.__enter__()
            locked = self.db.execute('SELECT pg_try_advisory_xact_lock(761284301) AS locked').fetchone()['locked']
            if not locked:
                self.transaction.__exit__(None, None, None)
                self.local.release()
                raise HTTPException(503, 'Scheduler busy; retry shortly')

    async def __aexit__(self, *args):
        try:
            if self.db.postgres:
                self.transaction.__exit__(*args)
        finally:
            self.local.release()


def credential(request):
    header = request.headers.get('Authorization', '')
    if not re.fullmatch(r'Bearer [A-Za-z0-9_-]{43}', header):
        raise HTTPException(401, 'Subscription credential required')
    return hashlib.sha256(header[7:].encode()).hexdigest()


def decode_key(value, size):
    if not isinstance(value, str) or len(value) > 128:
        raise ValueError('Invalid subscription key')
    raw = base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))
    if len(raw) != size:
        raise ValueError('Invalid subscription key size')
    return raw


def validate_subscription(raw):
    if not isinstance(raw, dict):
        raise ValueError('Subscription required')
    endpoint = raw.get('endpoint', '')
    if not isinstance(endpoint, str) or len(endpoint) > 4096:
        raise ValueError('Invalid endpoint')
    url = urlparse(endpoint)
    host = url.hostname or ''
    # Never send arbitrary user-controlled URLs from the backend (SSRF).
    allowed = host == 'fcm.googleapis.com' or host.endswith('.push.services.mozilla.com') or host.endswith('.push.apple.com') or host.endswith('.notify.windows.com')
    if url.scheme != 'https' or url.port not in (None, 443) or url.username or url.password or url.fragment or not allowed:
        raise ValueError('Unsupported push endpoint')
    keys = raw.get('keys', {})
    ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), decode_key(keys.get('p256dh'), 65))
    decode_key(keys.get('auth'), 16)
    return {'endpoint': endpoint, 'keys': {k: keys[k] for k in ('p256dh', 'auth')}}


def validate_configuration(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get('query'), dict):
        raise ValueError('Prayer configuration required')
    query = raw['query']
    allowed = {'latitude', 'longitude', 'method', 'school', 'tune', 'calendarMethod', 'adjustment'}
    if set(query) - allowed or any(not isinstance(v, str) or len(v) > 200 for v in query.values()):
        raise ValueError('Unsupported calculation settings')
    for name, limit in (('latitude', 90), ('longitude', 180)):
        number = float(query[name])
        if not math.isfinite(number) or not -limit <= number <= limit:
            raise ValueError('Invalid coordinates')
    if 'method' in query and int(query['method']) not in {0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 22, 23}:
        raise ValueError('Invalid method')
    if query.get('school', '0') not in ('0', '1'):
        raise ValueError('Invalid school')
    tune = query.get('tune', '0,0,0,0,0,0,0,0,0').split(',')
    if len(tune) != 9 or any(not -1440 <= int(v) <= 1440 for v in tune):
        raise ValueError('Invalid prayer adjustments')
    if query.get('calendarMethod', 'HJCoSA') not in ('HJCoSA', 'UAQ', 'DIYANET', 'MATHEMATICAL'):
        raise ValueError('Invalid calendar method')
    if not -30 <= int(query.get('adjustment', '0')) <= 30:
        raise ValueError('Invalid calendar adjustment')
    prayers = raw.get('prayers')
    if not isinstance(prayers, list) or any(p not in PRAYERS for p in prayers) or len(set(prayers)) != len(prayers):
        raise ValueError('Invalid enabled prayers')
    if raw.get('locale') not in ('en', 'ar'):
        raise ValueError('Invalid language')
    return {'query': query, 'prayers': prayers, 'locale': raw['locale']}


def dated_jobs(data, date, zone, prayers):
    """Use the API's location zone for each date, including DST transitions."""
    if data['date']['gregorian']['date'] != date.strftime('%d-%m-%Y'):
        raise ValueError('Prayer API returned the wrong date')
    jobs = []
    for prayer in prayers:
        match = re.fullmatch(r'(\d{2}):(\d{2})(?:\s+\([^)]*\))?', data['timings'][prayer])
        if not match:
            raise ValueError('Invalid prayer time')
        hour, minute = map(int, match.groups())
        when = datetime(date.year, date.month, date.day, hour, minute, tzinfo=zone)
        jobs.append((date.isoformat(), prayer, when.timestamp()))
    return jobs


class PushEngine:
    def __init__(self, settings, fetch_day=None, sender=None, clock=time.time):
        self.settings, self.clock = settings, clock
        self.fetch_day = fetch_day or self._fetch_day
        self.sender = sender or self._send
        self.db = Database(settings.database)
        self.lock = SchedulerLock(self.db)
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS web_push_subscriptions (
            token TEXT PRIMARY KEY, endpoint TEXT UNIQUE NOT NULL,
            subscription TEXT NOT NULL, configuration TEXT NOT NULL,
            zone TEXT, refresh_after DOUBLE PRECISION NOT NULL DEFAULT 0,
            schedule_pending INTEGER NOT NULL DEFAULT 1,
            last_test DOUBLE PRECISION NOT NULL DEFAULT 0
          );
          CREATE TABLE IF NOT EXISTS web_push_jobs (
            token TEXT NOT NULL REFERENCES web_push_subscriptions(token) ON DELETE CASCADE,
            date TEXT NOT NULL, prayer TEXT NOT NULL, run_at DOUBLE PRECISION NOT NULL,
            state TEXT NOT NULL DEFAULT 'pending', retry_at DOUBLE PRECISION NOT NULL DEFAULT 0,
            attempts INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (token, date, prayer)
          );
          CREATE INDEX IF NOT EXISTS web_push_jobs_due ON web_push_jobs(state, run_at, retry_at);
        ''')

    async def _fetch_day(self, date, query):
        # Reuse exactly the same validation, authority selection, astronomical
        # calculation and timezone resolution as the public Flutter API.
        from routes.prayer_times import get_timings
        result = await get_timings(
            date.strftime('%d-%m-%Y'), latitude=query['latitude'],
            longitude=query['longitude'], method=query.get('method'),
            school=query.get('school'), tune=query.get('tune'),
        )
        payload = json.loads(result.body)
        if payload.get('code') != 200:
            raise ValueError('Prayer calculation failed')
        return payload['data']

    async def _send(self, subscription, payload, ttl):
        await asyncio.to_thread(
            webpush, subscription_info=subscription,
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=self.settings.private_key,
            vapid_claims={'sub': self.settings.subject},
            ttl=ttl, headers={'Urgency': 'high'}, timeout=10,
        )

    def get(self, token):
        row = self.db.execute('SELECT * FROM web_push_subscriptions WHERE token=?', (token,)).fetchone()
        if row is None:
            raise HTTPException(404, 'Subscription not found')
        return row

    def status(self, token):
        row = self.get(token)
        job = self.db.execute(
            "SELECT * FROM web_push_jobs WHERE token=? AND state='pending' AND run_at>? ORDER BY run_at LIMIT 1",
            (token, self.clock()),
        ).fetchone()
        return {
            'enabled': True, 'timeZone': row['zone'],
            'schedulePending': bool(row['schedule_pending']),
            'nextPrayer': job['prayer'] if job else None,
            'nextAt': datetime.fromtimestamp(job['run_at'], UTC).isoformat() if job else None,
        }

    def delete(self, token):
        with self.db:
            self.db.execute('DELETE FROM web_push_subscriptions WHERE token=?', (token,))

    async def put(self, token, subscription, config):
        encoded = json.dumps(config, sort_keys=True)
        previous = self.db.execute('SELECT * FROM web_push_subscriptions WHERE token=?', (token,)).fetchone()
        changed = previous is None or previous['configuration'] != encoded
        try:
            with self.db:
                self.db.execute('''
                  INSERT INTO web_push_subscriptions(token, endpoint, subscription, configuration)
                  VALUES(?,?,?,?) ON CONFLICT(token) DO UPDATE SET
                    endpoint=excluded.endpoint, subscription=excluded.subscription,
                    configuration=excluded.configuration
                ''', (token, subscription['endpoint'], json.dumps(subscription), encoded))
                if changed:
                    # Old pending alarms must stop immediately on a location or
                    # settings change, even if the replacement API request fails.
                    self.db.execute("DELETE FROM web_push_jobs WHERE token=? AND state!='sent'", (token,))
                    self.db.execute('UPDATE web_push_subscriptions SET zone=NULL, refresh_after=0, schedule_pending=1 WHERE token=?', (token,))
        except (sqlite3.IntegrityError, psycopg.IntegrityError) as error:
            raise HTTPException(409, 'Endpoint already subscribed with another credential') from error
        if changed or self.get(token)['refresh_after'] <= self.clock():
            await self.refresh(token)
        return self.status(token)

    async def refresh(self, token):
        row = self.get(token)
        config = json.loads(row['configuration'])
        now = self.clock()
        if not config['prayers']:
            with self.db:
                self.db.execute('UPDATE web_push_subscriptions SET refresh_after=?, schedule_pending=0 WHERE token=?', (now + 21600, token))
            return
        try:
            # Discover the location zone from API metadata, never the server's
            # or browser's timezone. Re-fetch if UTC's date differs there.
            first_date = datetime.fromtimestamp(now, ZoneInfo(row['zone'] or 'UTC')).date()
            first = await self.fetch_day(first_date, config['query'])
            zone_name = first['meta']['timezone']
            zone = ZoneInfo(zone_name)
            local_date = datetime.fromtimestamp(now, zone).date()
            if local_date != first_date:
                first = await self.fetch_day(local_date, config['query'])
            jobs = []
            for offset in range(3):
                date = local_date + timedelta(days=offset)
                data = first if offset == 0 else await self.fetch_day(date, config['query'])
                if data['meta']['timezone'] != zone_name:
                    raise ValueError('Inconsistent prayer timezone')
                jobs.extend(dated_jobs(data, date, zone, config['prayers']))
            # Only replace after all dates validate. Keep sent date/prayer keys
            # so tuning settings never sends the same prayer twice that day.
            with self.db:
                for date, prayer, when in jobs:
                    if when <= now:
                        continue
                    self.db.execute('''
                      INSERT INTO web_push_jobs(token,date,prayer,run_at) VALUES(?,?,?,?)
                      ON CONFLICT(token,date,prayer) DO UPDATE SET run_at=excluded.run_at
                      WHERE web_push_jobs.state='pending'
                    ''', (token, date, prayer, when))
                self.db.execute('UPDATE web_push_subscriptions SET zone=?, refresh_after=?, schedule_pending=0 WHERE token=?', (zone_name, now + 21600, token))
        except Exception:
            # Leave good existing jobs in place and retry without opening a tab.
            with self.db:
                self.db.execute('UPDATE web_push_subscriptions SET refresh_after=?, schedule_pending=1 WHERE token=?', (now + 60, token))
            log.warning('Prayer schedule refresh failed; retrying in one minute')

    async def dispatch(self):
        deadline = time.monotonic() + 35
        now = self.clock()
        with self.db:
            self.db.execute("UPDATE web_push_jobs SET state='expired' WHERE state IN ('pending','sending') AND run_at<?", (now - MAX_LATENESS,))
            self.db.execute("UPDATE web_push_jobs SET state='pending' WHERE state='sending' AND retry_at<=?", (now,))
        due = self.db.execute("SELECT * FROM web_push_jobs WHERE state='pending' AND run_at<=? AND retry_at<=? ORDER BY run_at LIMIT 100", (now, now)).fetchall()
        for job in due:
            if time.monotonic() >= deadline:
                break
            # Re-check time after network waits; never flood old reminders.
            remaining = int(job['run_at'] + MAX_LATENESS - self.clock())
            if remaining <= 0:
                continue
            row = self.db.execute('SELECT * FROM web_push_subscriptions WHERE token=?', (job['token'],)).fetchone()
            if row is None:
                continue
            config = json.loads(row['configuration'])
            if job['prayer'] not in config['prayers']:
                continue
            identity = (job['token'], job['date'], job['prayer'])
            with self.db:
                self.db.execute("UPDATE web_push_jobs SET state='sending', retry_at=?, attempts=attempts+1 WHERE token=? AND date=? AND prayer=?", (self.clock() + 30, *identity))
            ar = config['locale'] == 'ar'
            name = ARABIC[job['prayer']] if ar else job['prayer']
            payload = {
                'title': f"حان وقت صلاة {name}" if ar else f"Time for {name}",
                'body': f"لا تنسَ صلاة {name}" if ar else f"Don't forget to pray {name}.",
                'expiredBody': 'افتح تطبيق مسلم لمعرفة مواقيت الصلاة الحالية.' if ar else 'Open Muslim to see current prayer times.',
                'tag': f"prayer-{job['date']}-{job['prayer']}",
                'expiresAt': int((job['run_at'] + MAX_LATENESS) * 1000),
            }
            try:
                await self.sender(json.loads(row['subscription']), payload, remaining)
            except Exception as error:
                response = getattr(error, 'response', None)
                if isinstance(error, WebPushException) and response is not None and response.status_code in (404, 410):
                    self.delete(job['token'])
                else:
                    with self.db:
                        self.db.execute("UPDATE web_push_jobs SET state='pending', retry_at=? WHERE token=? AND date=? AND prayer=?", (self.clock() + min(15 * 2 ** min(job['attempts'], 3), 60), *identity))
                    log.warning('Push delivery failed; retrying within the reminder window')
            else:
                with self.db:
                    self.db.execute("UPDATE web_push_jobs SET state='sent' WHERE token=? AND date=? AND prayer=?", identity)

    async def tick(self):
        deadline = time.monotonic() + 45
        async with self.lock:
            await self.dispatch()
        # Release the lock between subscriptions so interactive changes can run.
        rows = self.db.execute('SELECT token FROM web_push_subscriptions WHERE refresh_after<=? ORDER BY refresh_after LIMIT 20', (self.clock(),)).fetchall()
        for row in rows:
            if time.monotonic() >= deadline:
                break
            async with self.lock:
                if self.db.execute('SELECT 1 FROM web_push_subscriptions WHERE token=?', (row['token'],)).fetchone():
                    await self.refresh(row['token'])
                    await self.dispatch()
        with self.db:
            self.db.execute('DELETE FROM web_push_jobs WHERE run_at<?', (self.clock() - 7 * 86400,))

def create_app(settings=None, engine=None):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    try:
        settings = settings or Settings.from_env()
    except (KeyError, ValueError):
        # Keep every existing API route usable until push has been configured.
        @app.api_route('/{path:path}', methods=['GET', 'PUT', 'DELETE', 'POST'])
        async def unavailable(path: str):
            return JSONResponse({'detail': 'Web push is not configured'}, status_code=503, headers={'Cache-Control': 'no-store'})
        app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_headers=['Authorization', 'Content-Type'])
        return app

    app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_methods=['GET', 'PUT', 'POST', 'DELETE'], allow_headers=['Authorization', 'Content-Type'])

    @app.middleware('http')
    async def guard(request, call_next):
        if '/subscriptions/' in request.url.path and request.method != 'OPTIONS':
            if request.headers.get('origin') not in settings.origins:
                return JSONResponse({'detail': 'App origin required'}, status_code=403)
            try:
                credential(request)
            except HTTPException:
                return JSONResponse({'detail': 'Subscription credential required'}, status_code=401)
        if request.url.path.endswith('/cron') and not secrets.compare_digest(request.headers.get('authorization', ''), 'Bearer ' + settings.cron_secret):
            return JSONResponse({'detail': 'Invalid scheduler credential'}, status_code=401)
        size = request.headers.get('content-length')
        if size and (not size.isdigit() or int(size) > 16384):
            return JSONResponse({'detail': 'Request too large'}, status_code=413)
        # Never rely on an in-memory subscription list or a background task:
        # Vercel may discard the process immediately after returning a response.
        request.state.push_engine = None
        needs_database = request.method != 'OPTIONS' and request.url.path.endswith(('/me', '/test', '/cron'))
        if needs_database:
            try:
                request.state.push_engine = engine or PushEngine(settings)
            except Exception:
                log.warning('Web push database unavailable')
                return JSONResponse({'detail': 'Push storage unavailable'}, status_code=503)
        try:
            response = await call_next(request)
        finally:
            if needs_database and engine is None and request.state.push_engine:
                request.state.push_engine.db.close()
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/health')
    async def health():
        return {'ok': True}

    @app.get('/config')
    async def config():
        return {'publicKey': settings.public_key}

    @app.get('/subscriptions/me')
    async def status(request: Request):
        return request.state.push_engine.status(credential(request))

    @app.put('/subscriptions/me')
    async def subscribe(request: Request):
        engine = request.state.push_engine
        key = credential(request)
        try:
            raw = await request.body()
            if len(raw) > 16384:
                raise HTTPException(413, 'Request too large')
            body = json.loads(raw)
            subscription = validate_subscription(body['subscription'])
            configuration = validate_configuration(body['configuration'])
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise HTTPException(422, 'Invalid subscription or prayer settings') from error
        async with engine.lock:
            return await engine.put(key, subscription, configuration)

    @app.delete('/subscriptions/me', status_code=204)
    async def unsubscribe(request: Request):
        engine = request.state.push_engine
        async with engine.lock:
            engine.delete(credential(request))

    @app.post('/subscriptions/me/test')
    async def test(request: Request):
        engine = request.state.push_engine
        key = credential(request)
        async with engine.lock:
            row = engine.get(key)
            if engine.clock() - row['last_test'] < 30:
                raise HTTPException(429, 'Wait before testing again')
            with engine.db:
                engine.db.execute('UPDATE web_push_subscriptions SET last_test=? WHERE token=?', (engine.clock(), key))
            ar = json.loads(row['configuration'])['locale'] == 'ar'
            try:
                await engine.sender(json.loads(row['subscription']), {
                    'title': 'مسلم' if ar else 'Muslim',
                    'body': 'تم تفعيل إشعارات الصلاة.' if ar else 'Prayer notifications are enabled.',
                    'tag': 'muslim-test',
                }, 60)
            except Exception as error:
                raise HTTPException(502, 'Push service could not accept the notification') from error
        return {'sent': True}

    @app.get('/cron')
    async def cron(request: Request):
        if not secrets.compare_digest(request.headers.get('authorization', ''), 'Bearer ' + settings.cron_secret):
            raise HTTPException(401, 'Invalid scheduler credential')
        await request.state.push_engine.tick()
        return {'ok': True}

    return app
