# Hosting Muslim API with Docker

The image includes the API, its Python dependencies, Hadith and quiz datasets,
prayer calculation data, and timezone data. It runs as an unprivileged user on
port **8000**, with an HTTP health check. The Compose service restarts after a
reboot when Docker starts and limits log growth.

Use Docker Desktop in **Linux containers** mode on Windows. The mini PC needs
Docker Engine and the Docker Compose plugin. GitHub Actions can publish the
image to GitHub Container Registry (GHCR), ready for the mini PC to pull.

## Publish automatically to GHCR

The workflow in [`.github/workflows/publish-image.yml`](.github/workflows/publish-image.yml)
tests the container before publishing `ghcr.io/bssam1996/muslimapi` for both
Linux AMD64 and ARM64. Docker picks the correct architecture when pulling.

| Trigger | Published tags |
| --- | --- |
| Push to `master` | `latest` and `sha-<short-commit>` |
| Push a version tag, e.g. `v1.0.0` | `1.0.0`, `1.0`, and `sha-<short-commit>` |
| Manual run on the default branch | `latest` and `sha-<short-commit>` |
| Pull request to `master` | Runs checks without publishing |

Version tags do not move `latest`; that tag tracks the default branch.
Manual runs on feature branches run checks without publishing.

1. Commit and push the Docker files and workflow, then merge them into `master`.
   Publishing starts when the changes reach `master`. The workflow must be on
   the default branch before GitHub
   displays its manual **Run workflow** button.
2. Open the repository's **Actions** tab and select **Build and publish MuslimAPI**.
   The workflow uses `GITHUB_TOKEN` with `packages: write`; no registry password
   or additional repository secret is required. Repository/organization policy
   must allow GitHub Actions and package publishing.
3. After the first successful run, find **muslimapi** under your GitHub account's
   **Packages**. New GHCR packages default to private. For anonymous pulls,
   change the package's visibility to **Public** in its package settings.
   To keep it private, authenticate on the mini PC as described below.

If a package with this name already exists and publishing is denied, grant
`bssam1996/MuslimAPI` access under the package's **Manage Actions access** settings.
The workflow applies a source-repository label to associate newly published
images with this repository.

For a versioned release, tag the desired commit and push the tag:

```sh
git tag v1.0.0
git push origin v1.0.0
```

For a private package, run `docker login ghcr.io -u bssam1996` on the mini PC
and paste a GitHub personal access token (classic) with `read:packages` at the
password prompt. Public images can be pulled without logging in. See GitHub's
[Container registry documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

## Build and test on this PC

From the project directory:

```sh
docker build -t muslim-api:local .
docker compose up -d
docker compose ps
docker compose logs --tail=100 api
```

Compose reads runtime settings from `.env`. This repository already has an empty,
ignored `.env`; keep it for the default API, or copy settings from
`.env.docker.example`. If `.env` does not exist, copy that example to `.env` first.
Do not overwrite an existing populated `.env`.

Open `http://localhost:8000/docs`. Example checks:

```sh
curl http://localhost:8000/
curl http://localhost:8000/hadith/get_random_hadith
curl http://localhost:8000/quizes/get_random_quiz
curl "http://localhost:8000/v1/timings/today?latitude=51.5072&longitude=-0.1276"
```

Stop the local service with `docker compose down`.

## Push to Docker Hub

This is an alternative to the automated GHCR workflow. Replace
`YOUR_DOCKERHUB_USER` with your Docker Hub username and create a `muslim-api`
repository there before pushing.

For an Intel/AMD mini PC, build a Linux AMD64 image explicitly:

```sh
docker login
docker buildx build --platform linux/amd64 --load -t YOUR_DOCKERHUB_USER/muslim-api:1.0.0 .
docker push YOUR_DOCKERHUB_USER/muslim-api:1.0.0
```

If the mini PC uses ARM64, use `linux/arm64` instead. To publish one tag supporting
both architectures, use a multi-platform builder:

```sh
docker buildx create --name muslim-api-builder --driver docker-container --use
docker buildx build --platform linux/amd64,linux/arm64 --push -t YOUR_DOCKERHUB_USER/muslim-api:1.0.0 .
```

Create the builder once; on subsequent builds select it with
`docker buildx use muslim-api-builder`. Docker selects the matching architecture
when the mini PC pulls the image. See Docker's
[multi-platform build documentation](https://docs.docker.com/build/building/multi-platform/).
On Linux, `uname -m` reports `x86_64` for AMD64 or `aarch64` for ARM64.

## Run on the mini PC

For just the API, no source checkout is required:

```sh
docker pull ghcr.io/bssam1996/muslimapi:latest
docker run -d --name muslim-api --restart unless-stopped --init --read-only --tmpfs /tmp --security-opt no-new-privileges --cap-drop ALL --log-opt max-size=10m --log-opt max-file=3 -p 8000:8000 ghcr.io/bssam1996/muslimapi:latest
```

Alternatively, copy `compose.yaml` and `.env.docker.example` to a directory on the
mini PC, copy the example to `.env`, then set:

```dotenv
MUSLIM_API_IMAGE=ghcr.io/bssam1996/muslimapi:latest
PORT=8000
BIND_ADDRESS=0.0.0.0
```

Start the service:

```sh
docker compose pull
docker compose up -d
docker compose ps
```

Use either `docker run` or Compose for a given port. The API is available on
your home network at `http://MINI_PC_IP:8000`, with docs at `/docs`.
For public hosting, route a domain through an HTTPS reverse proxy or tunnel to
port 8000. When using a reverse proxy on the same host, set
`BIND_ADDRESS=127.0.0.1` (or use `-p 127.0.0.1:8000:8000` with `docker run`).

For updates, wait for the GitHub Actions publish job, then run
`docker compose pull` followed by `docker compose up -d` on the mini PC.
To pin a release, set `MUSLIM_API_IMAGE=ghcr.io/bssam1996/muslimapi:1.0.0`
after publishing `v1.0.0`. You can also pin a `sha-<short-commit>` tag for
rollback. If you used `docker run`, stop and remove the old container before
recreating it with the pulled image.

Environment files, private keys, virtual environments, and local databases are
excluded from the image build context. Supply secrets at runtime only.
