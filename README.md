# Muslim API

Muslim API is a FastAPI service that provides coordinate-based prayer times,
monthly prayer calendars, calculation-method metadata, a random Hadith/search
interface, and Arabic Islamic quiz content. It is designed for the Muslim
Flutter app, but its HTTP endpoints can be used by any client.

## Features

- Offline, deterministic prayer-time calculation from latitude and longitude.
- Daily and monthly prayer calendars, including Gregorian and Hijri date data.
- 23 published calculation methods plus a custom-angle method.
- Automatic authority selection for configured locations when `method` is not
  supplied; an explicit method always takes precedence.
- Local-time resolution from coordinates, with an optional IANA timezone
  override.
- Hanafi or standard (Shafi) Asr calculation, high-latitude handling, Jafari
  midnight mode, Moonsighting shafaq variants, and per-prayer minute tuning.
- Random Hadith, Hadith search, and random Islamic quiz questions.

## Run locally

Prerequisites: Python 3.11 or later.

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

The service is then available at `http://127.0.0.1:8000`. FastAPI's interactive
OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

## Run with Docker

```sh
docker build -t muslim-api:local .
docker compose up -d
```

Compose reads `.env`; if it does not exist, copy `.env.docker.example` to `.env`
first. Open `http://localhost:8000/docs`.

GitHub Actions tests the image and publishes AMD64/ARM64 images to
`ghcr.io/bssam1996/muslimapi` on pushes to `master` and version tags. See
[DOCKER.md](DOCKER.md) for GHCR setup, hosting on a mini PC, and local builds.

## API overview

| Endpoint | Description |
| --- | --- |
| `GET /` | Service health greeting. |
| `GET /v1/timings/{date}` | Prayer times for one date and location. |
| `GET /v1/calendar/{year}/{month}` | Prayer times for every day in a Gregorian month. |
| `GET /v1/methods` | Supported calculation methods and their parameters. |
| `GET /hadith/` | Hadith service greeting. |
| `GET /hadith/get_random_hadith` | One random Hadith from the bundled collection. |
| `GET /hadith/find_hadith?searchQuery=…` | Search the Hadith collection. |
| `GET /quizes/` | Quiz service greeting. |
| `GET /quizes/get_random_quiz` | One random Arabic Islamic quiz question. |
| `GET /quizes/get_random_question` | Alias for `get_random_quiz`. |

Prayer-time endpoints use an AlAdhan-style envelope:

```json
{
  "code": 200,
  "status": "OK",
  "data": {}
}
```

Invalid prayer-time requests return HTTP `400` with `status: "BAD_REQUEST"`
and an explanatory message at `data.message`.

## Prayer times

### Get timings for one day

```http
GET /v1/timings/30-08-2026?latitude=31.2001&longitude=29.9187
```

`date` must be `DD-MM-YYYY`, or `today`. `today` is evaluated in the
location's resolved timezone (or the supplied `timezonestring`).

Example using an explicit method and timezone:

```http
GET /v1/timings/today?latitude=51.5072&longitude=-0.1276&method=3&timezonestring=Europe/London
```

The response includes `Imsak`, `Fajr`, `Sunrise`, `Dhuhr`, `Asr`, `Sunset`,
`Maghrib`, `Isha`, `Midnight`, `Firstthird`, and `Lastthird` as 24-hour `HH:MM`
values. It also includes Gregorian/Hijri date data and calculation metadata.

### Get a monthly calendar

```http
GET /v1/calendar/2026/8?latitude=31.2001&longitude=29.9187
```

The parameters are the same as the daily endpoint. The response contains one
daily prayer-time payload for every day of the requested Gregorian month.

### Discover methods

```http
GET /v1/methods
```

Use this endpoint when building a method picker: it is the source of truth for
the method IDs and their active calculation parameters.

## Prayer-time parameters

The daily and calendar endpoints accept these query parameters.

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| `latitude` | Yes | — | Decimal latitude, from `-90` to `90`. |
| `longitude` | Yes | — | Decimal longitude, from `-180` to `180`. |
| `method` | No | Location default, then `3` | Calculation method ID. See the methods table. |
| `school` | No | `0` | Asr school: `0` standard/Shafi, `1` Hanafi. |
| `shafaq` | No | `general` | Moonsighting shafaq: `general`, `ahmer`, or `abyad`. |
| `tune` | No | all `0` | Up to nine comma-separated minute offsets. |
| `midnightMode` | No | Method default | `0` standard (sunset to sunrise) or `1` Jafari (sunset to Fajr). |
| `latitudeAdjustmentMethod` | No | `3` | High-latitude method: `1` middle of night, `2` one seventh, `3` angle based. |
| `timezonestring` | No | Coordinate-derived | Valid IANA timezone, such as `Europe/London`. |
| `methodSettings` | With `method=99` | — | Custom Fajr, Maghrib, and Isha settings: `Fajr,Maghrib,Isha`. Use `null` for a default component. |

`tune` follows this exact order:

```text
Imsak,Fajr,Sunrise,Dhuhr,Asr,Maghrib,Sunset,Isha,Midnight
```

For example, `tune=0,-2,0,0,0,1,0,0,0` moves Fajr two minutes earlier and
Maghrib one minute later. Fewer than nine values are accepted and missing
values are treated as zero.

## Calculation methods

| ID | Key | Authority / method |
| ---: | --- | --- |
| 0 | `JAFARI` | Shia Ithna-Ashari, Leva Institute, Qum |
| 1 | `KARACHI` | University of Islamic Sciences, Karachi |
| 2 | `ISNA` | Islamic Society of North America |
| 3 | `MWL` | Muslim World League |
| 4 | `MAKKAH` | Umm Al-Qura University, Makkah |
| 5 | `EGYPT` | Egyptian General Authority of Survey |
| 7 | `TEHRAN` | Institute of Geophysics, University of Tehran |
| 8 | `GULF` | Gulf Region |
| 9 | `KUWAIT` | Kuwait |
| 10 | `QATAR` | Qatar |
| 11 | `SINGAPORE` | Majlis Ugama Islam Singapura |
| 12 | `FRANCE` | Union Organization Islamic de France |
| 13 | `TURKEY` | Diyanet İşleri Başkanlığı, Turkey |
| 14 | `RUSSIA` | Spiritual Administration of Muslims of Russia |
| 15 | `MOONSIGHTING` | Moonsighting Committee Worldwide |
| 16 | `DUBAI` | Dubai (experimental) |
| 17 | `JAKIM` | Jabatan Kemajuan Islam Malaysia |
| 18 | `TUNISIA` | Tunisia |
| 19 | `ALGERIA` | Algeria |
| 20 | `KEMENAG` | Kementerian Agama Republik Indonesia |
| 21 | `MOROCCO` | Morocco |
| 22 | `PORTUGAL` | Comunidade Islamica de Lisboa |
| 23 | `JORDAN` | Ministry of Awqaf, Islamic Affairs and Holy Places, Jordan |
| 99 | `CUSTOM` | Supply `methodSettings` yourself. |

## Automatic location defaults

When `method` is omitted or empty, the API obtains an IANA timezone from the
provided coordinates and checks the maintained mapping in
[`data/prayer_times/location_defaults.json`](data/prayer_times/location_defaults.json).
This selects the locally configured authority where one is available. For
example, Alexandria's coordinates resolve to `Africa/Cairo`, so the API uses
the Egyptian General Authority of Survey (`method=5`).

The mapping currently includes Egypt, Saudi Arabia, Pakistan, Iran, the UAE,
Kuwait, Qatar, Singapore, France, Turkey, Russia, Malaysia, Tunisia, Algeria,
Indonesia, Morocco, Portugal, and Jordan. If no location rule exists, the API
uses Muslim World League (`method=3`).

The response makes the decision visible:

```json
"meta": {
  "method": {"id": 5, "name": "Egyptian General Authority of Survey"},
  "methodSelection": "location_default",
  "methodResolution": {
    "selection": "location_default",
    "timezone": "Africa/Cairo",
    "region": "Egypt"
  }
}
```

An explicitly supplied `method` produces `"methodSelection": "explicit"` and
always overrides this mapping. `timezonestring` changes output-time formatting
and the meaning of `today`; it does not alter location-based method selection.

## How prayer times are calculated

Prayer-time calculation is performed locally; the service does not call an
external prayer-time API at request time.

1. The supplied coordinates determine the local timezone, unless an IANA
   `timezonestring` override is supplied.
2. If no method is specified, the coordinate's geographic timezone selects a
   configured authority; otherwise the requested method is used.
3. Solar transit, sunrise, sunset, and solar-angle events are calculated from
   the date and coordinates using an Adhan-derived astronomical implementation.
4. Fajr and Isha use the selected method's twilight angles or its fixed
   post-sunset interval. Maghrib uses sunset unless the method defines an angle
   or interval. Asr uses the selected school’s shadow factor.
5. At high latitudes, unavailable twilight events are resolved with the
   selected high-latitude policy. The API reports `AqrabBalad` as its polar
   resolution and returns the reference latitude in `meta`.
6. Optional tuning offsets are applied, then values are rounded to the nearest
   minute and returned in local 24-hour time.

The implementation is a Python adaptation of selected logic from
[`batoulapps/adhan-js`](https://github.com/batoulapps/adhan-js). Attribution and
licence details are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Hijri date fields use the bundled `hijridate` Umm al-Qura calendar data and are
formatted in the API's HJCoSA-compatible response shape.

## Caching and CORS

Prayer-time responses are deterministic for a complete request URL. They send
`Cache-Control: public, max-age=300` and
`Vercel-CDN-Cache-Control: public, s-maxage=86400`. CORS is enabled by the
application for browser clients.

## Tests

Run the test suite with:

```bash
python -m pytest -q
```

The prayer-time tests cover deterministic calculations, method selection,
Alexandria's automatic Egyptian authority selection, explicit method overrides,
calendar generation, and invalid request handling.
