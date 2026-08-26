<p align="center">
  <img src="images/craybee_large.png" alt="craybee">
</p>

## Run it

Requires Python (via [uv](https://docs.astral.sh/uv/getting-started/installation/)) — no Node needed, the compiled frontend ships inside the package.

```bash
uvx craybee serve
```

This starts the webserver (binds `127.0.0.1:8000` by default) and opens a browser tab automatically.

## Develop

Requires [`uv`](https://docs.astral.sh/uv/getting-started/installation/) and Node 20+.

```bash
git clone <repo> && cd craybee
./setup.sh
uv run craybee dev
```

`uv run craybee dev` runs the FastAPI backend and the Vite dev server together with hot reload: the browser opens on `:5173` (Vite, with hot module reload for the frontend) which proxies `/api` and `/ws` to the backend on `:8000` (auto-reloads on backend source changes).

`./setup.sh` only needs to be run once (and after pulling changes) — it installs both the Python and frontend dependency sets and does an initial frontend build.
