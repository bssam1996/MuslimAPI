# Web prayer reminders

The FastAPI app mounts a separate service at `/web-push`. Existing prayer,
Hadith and quiz routes keep their behavior. Until push settings are configured,
push routes return HTTP 503 while existing routes continue working.

## Production setup

1. Install `requirements.txt`. The additional packages are `pywebpush` and
   `psycopg[binary]`. Use the existing project's Python 3.11+ environment.
2. Run `python scripts/generate_push_keys.py` once from the repository root.
   It creates ignored files `secrets/vapid.pem` and `secrets/vapid.env` without
   printing the private key. Keep these files private and back them up; changing
   the key pair requires browser subscriptions to be recreated.
3. Configure these environment variables in the host dashboard (see
   `.env.web-push.example`):

   | Variable | Purpose |
   | --- | --- |
   | `DATABASE_URL` | Durable PostgreSQL URL, with TLS in production. A pooled URL is supported. |
   | `APP_ORIGINS` | Comma-separated exact app origins, e.g. `https://bssam1996.github.io`. No path or wildcard. |
   | `VAPID_PUBLIC_KEY` | Public key from `secrets/vapid.env`. |
   | `VAPID_PRIVATE_KEY` | Private key from `secrets/vapid.env`. Never add it to Flutter or source control. |
   | `VAPID_SUBJECT` | Contact address, e.g. `mailto:owner@example.com`. |
   | `CRON_SECRET` | Random secret of at least 32 characters. Use a password manager or `secrets.token_urlsafe(32)`. |

4. Deploy the backend. Check `/web-push/config`: it should return the public key.
   The first subscription request creates `web_push_subscriptions` and
   `web_push_jobs` in PostgreSQL. This needs permission to create tables/indexes;
   table creation is serialized with a database advisory lock.
5. Configure an authenticated **GET every minute** to
   `https://muslim-api-mu.vercel.app/web-push/cron`, using the header
   `Authorization: Bearer <CRON_SECRET>`. Use an external minute scheduler or a
   Vercel plan that supports minute cron. The schedule fragment for the latter
   is in `vercel.web-push-cron.example.json`; merge its `crons` field into
   `vercel.json` when supported, then redeploy. Vercel automatically sends
   `CRON_SECRET` as the Bearer credential.
6. Deploy the Flutter web app. Its default URL already points to this backend's
   `/web-push`; override with `--dart-define=WEB_PUSH_API_URL=...` if needed.
7. Enable notifications, send a test, then verify delivery with the app closed
   and at a scheduled prayer time on real devices.

**Vercel Hobby only supports daily cron**, which is insufficient for prayer
delivery. Its daily schedule also has hour-level timing uncertainty. This is
why the repository's existing `vercel.json` is not given a minute cron that
could break Hobby deployments. An external scheduler must send the exact path
above, without a trailing slash or redirects. Allow its requests through any
deployment protection, and rate-limit public subscription writes at the host.
See [Vercel cron accuracy and authentication](https://vercel.com/docs/cron-jobs/manage-cron-jobs).

## How scheduling works

Subscriptions contain coordinates, calculation settings, language and enabled
prayers. Each record is controlled by a random 256-bit browser credential; only
its hash is stored in the database. A credential cannot replace another
subscription's endpoint. Only known browser push hosts are allowed as endpoints.
Subscription requests also require the configured app origin.

The service calls the same `routes.prayer_times.get_timings` calculation used by
the public API directly, without an HTTP round trip. It resolves the location's
IANA timezone from calculation metadata and stores UTC timestamps for each
prayer on each of the next three local dates. Method, school and minute offsets
are preserved. Jobs refresh every six hours; failures retry in one minute.

The cron sends due jobs and uses transaction-level PostgreSQL advisory locks
to avoid concurrent dispatch by overlapping invocations. Sent date/prayer
identities survive settings changes to avoid repeats. Changing location or
settings invalidates old pending jobs immediately, even if calculation fails.
Disabling deletes the subscription and its jobs. Push endpoints returning
404/410 are removed. Delivery retries use short backoff and a maximum 90-second
reminder window. Long server outages do not produce a flood of stale reminders.

Web push remains best effort: minute scheduler timing, network conditions and
browser/OS behavior affect arrival. The push TTL expires relative to the prayer
time. The worker always shows a visible notification; a late delivered payload
uses a message asking the user to check current prayer times. Notification
clicks open/focus the app within its configured base path.

Process memory and local disk are never production storage on Vercel. For local
development only, unset `DATABASE_URL` and set
`PUSH_DATABASE=data/web_push/push.sqlite3`; this is rejected when `VERCEL` is
set. Start with `uvicorn main:app --env-file .env --reload`. Set
`APP_ORIGINS=http://localhost:5000` to match the fixed Flutter development port.
Local scheduling also requires calling `/web-push/cron` every minute; no
background task is assumed to survive a request.

## Operation and testing

```sh
python -m pytest tests/test_web_push.py tests/test_prayer_times.py -q
```

Tests use temporary SQLite storage and mock push delivery. One test compares
scheduled timestamps against the real public prayer engine across the London
DST transition. Configure a test PostgreSQL instance separately for production
storage verification and smoke-test a live subscription/cron before rollout.

Each cron invocation has a bounded batch and runtime budget; monitor scheduler
failures and pending reminders. For larger audiences, move delivery to a queue
or dedicated workers so all subscriptions are served within their reminder
window. This implementation does not add user accounts or location tracking.
