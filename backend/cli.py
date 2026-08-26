import contextlib
import os
import shutil
import signal
import subprocess
import sys
import webbrowser
from pathlib import Path

import typer
import uvicorn

from backend.config import get_settings

cli = typer.Typer(help="craybee - agent orchestration harness", no_args_is_help=True)

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND = REPO_ROOT / "frontend"


def _in_source_checkout() -> bool:
    return (FRONTEND / "package.json").exists()


@cli.command()
def serve(
    port: int = typer.Option(None, help="Port to listen on."),
    host: str = typer.Option(None, help="Interface to bind. Defaults to loopback."),
    browser: bool = typer.Option(True, help="Open a browser window on start."),
    reload: bool = typer.Option(False, help="Reload the API on source changes."),
) -> None:
    """Run the built app: one process, no Node required."""
    settings = get_settings()
    host = host or settings.host
    port = port or settings.port

    if not (Path(__file__).parent / "static" / "index.html").exists():
        typer.secho(
            "No compiled frontend found. Run `craybee build` (needs Node), "
            "or `craybee dev` for hot reload.",
            fg=typer.colors.YELLOW,
        )

    if browser:
        webbrowser.open(f"http://{host}:{port}")

    uvicorn.run("backend.main:app", host=host, port=port, reload=reload)


@cli.command()
def dev(
    api_port: int = typer.Option(8000, help="Port for the FastAPI backend."),
    web_port: int = typer.Option(5173, help="Port for the Vite dev server."),
    browser: bool = typer.Option(True, help="Open a browser window on start."),
) -> None:
    """Run the backend and Vite together with hot reload (source checkout only)."""
    _require_source_checkout("dev")
    npm = _require_npm()

    # Vite is the one the browser talks to; it proxies /api and /ws to FastAPI.
    # The target has to be passed through: --api-port moves the backend, and a
    # proxy still pointing at the default port fails in a way that looks like a
    # backend outage rather than a misconfiguration.
    vite_env = {**os.environ, "CRAYBEE_API_URL": f"http://127.0.0.1:{api_port}"}
    vite = subprocess.Popen(
        [npm, "run", "dev", "--", "--port", str(web_port), "--strictPort"],
        cwd=FRONTEND,
        env=vite_env,
        **_new_process_group(),
    )
    if browser:
        webbrowser.open(f"http://127.0.0.1:{web_port}")

    try:
        uvicorn.run(
            "backend.main:app",
            host="127.0.0.1",
            port=api_port,
            reload=True,
            reload_dirs=[str(REPO_ROOT / "backend")],
        )
    finally:
        # Without this, Ctrl-C orphans Vite holding the port and the next
        # `craybee dev` fails with a confusing bind error. terminate() alone is
        # not enough: it signals the npm wrapper, leaving the real vite child
        # running, so the whole process group has to go.
        _terminate_group(vite)


@cli.command()
def build() -> None:
    """Compile the frontend into backend/static/ (source checkout only)."""
    _require_source_checkout("build")
    npm = _require_npm()
    subprocess.run([npm, "ci"], cwd=FRONTEND, check=True)
    subprocess.run([npm, "run", "build"], cwd=FRONTEND, check=True)

    static = Path(__file__).parent / "static"
    if static.exists():
        shutil.rmtree(static)
    shutil.copytree(FRONTEND / "dist", static)
    typer.secho(f"Built frontend into {static}", fg=typer.colors.GREEN)


def _new_process_group() -> dict[str, object]:
    """Popen kwargs that put the child in its own group, so it can be killed as one."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _terminate_group(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        process.terminate()

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if sys.platform != "win32":
            with contextlib.suppress(ProcessLookupError, OSError):
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        else:
            process.kill()


def _require_source_checkout(command: str) -> None:
    if _in_source_checkout():
        return
    typer.secho(
        f"`{command}` needs a source checkout, but this is an installed package.\n"
        "  git clone <repo> && cd craybee && ./setup.sh",
        fg=typer.colors.RED,
    )
    raise typer.Exit(1)


def _require_npm() -> str:
    npm = shutil.which("npm")
    if npm is None:
        typer.secho("Node 20+ and npm are required for this command.", fg=typer.colors.RED)
        raise typer.Exit(1)
    return npm


def main() -> None:
    cli()


if __name__ == "__main__":
    sys.exit(main())
