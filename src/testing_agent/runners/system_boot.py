"""SystemRunner: boot the app, poll a healthcheck, run endpoint smoke checks, teardown."""

from __future__ import annotations

import os
import shlex
import subprocess
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx

from pydantic import BaseModel

from testing_agent.config import EndpointCheck, ProjectConfig, SystemConfig
from testing_agent.detect.models import ProjectManifest
from testing_agent.runners.base import (
    FailureInfo,
    RunResult,
    Runner,
    TestType,
    log_path,
    npm_exec_command,
)


class SystemCheckOutcome(BaseModel):
    """Outcome of one HTTP check (healthcheck or endpoint)."""

    path: str
    ok: bool
    detail: str


def split_boot_command(boot_command: str) -> list[str]:
    """Split a boot command string into argv, wrapping npm-family shims on Windows.

    Uses posix=False on Windows to preserve backslash paths, then strips one
    surrounding quote pair per token (shlex keeps the quote characters in
    non-posix mode).
    """
    posix = os.name != "nt"
    argv = shlex.split(boot_command, posix=posix)
    if not posix:
        argv = [
            token[1:-1]
            if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"')
            else token
            for token in argv
        ]
    return npm_exec_command(argv)


def check_url(
    base_url: str,
    path: str,
    expected_status: int,
    timeout_seconds: float = 5.0,
) -> SystemCheckOutcome:
    """Perform one HTTP GET check and report ok/detail."""
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    try:
        response = httpx.get(url, timeout=timeout_seconds, follow_redirects=True)
    except httpx.HTTPError as exc:
        return SystemCheckOutcome(path=path, ok=False, detail=f"request failed: {exc}")

    if response.status_code == expected_status:
        return SystemCheckOutcome(path=path, ok=True, detail=f"status {response.status_code}")
    return SystemCheckOutcome(
        path=path,
        ok=False,
        detail=f"expected {expected_status}, got {response.status_code}",
    )


def wait_for_healthcheck(
    system: SystemConfig,
    timeout_seconds: int,
) -> SystemCheckOutcome:
    """Poll the healthcheck endpoint until it responds as expected or time runs out."""
    deadline = time.monotonic() + timeout_seconds
    last = SystemCheckOutcome(path=system.healthcheck_path, ok=False, detail="never attempted")
    while time.monotonic() < deadline:
        last = check_url(
            system.target_url,
            system.healthcheck_path,
            system.healthcheck_expected_status,
            timeout_seconds=2.0,
        )
        if last.ok:
            return last
        time.sleep(1.0)
    return SystemCheckOutcome(
        path=system.healthcheck_path,
        ok=False,
        detail=f"healthcheck not reachable within {timeout_seconds}s — last: {last.detail}",
    )


def terminate_tree(process: subprocess.Popen[bytes]) -> None:
    """Terminate a booted process and (on Windows) its whole process tree."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


class SystemRunner(Runner):
    """Boots the application and smoke-checks configured endpoints."""

    id = "system-boot"

    def applies(self, manifest: ProjectManifest) -> bool:
        return manifest.stack.value in ("python", "node")

    def run(
        self,
        manifest: ProjectManifest,
        root: Path,
        test_type: TestType,
        timeout_seconds: int = 300,
        config: ProjectConfig | None = None,
    ) -> RunResult:
        manifest_dir = (Path(root) / manifest.directory) if manifest.directory else Path(root)
        system = config.system if config else SystemConfig()
        if not system.boot_command:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                no_tests=True,
                note="skipped: no system.boot_command configured",
            )

        argv = split_boot_command(system.boot_command)
        log_file = log_path(manifest_dir, self.id, test_type)
        started = time.perf_counter()

        try:
            with open(log_file, "ab") as boot_log:
                process = subprocess.Popen(
                    argv,
                    cwd=str(manifest_dir),
                    stdout=boot_log,
                    stderr=boot_log,
                    stdin=subprocess.DEVNULL,
                )
        except OSError as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                passed=0,
                failed=1,
                duration_ms=duration_ms,
                success=False,
                note=f"boot failed: {argv[0]} — {exc}",
                command=" ".join(argv),
                failures=[FailureInfo(name="boot", message=str(exc))],
            )

        try:
            time.sleep(0.5)
            if process.poll() is not None:
                duration_ms = int((time.perf_counter() - started) * 1000)
                code = process.returncode
                return RunResult(
                    runner=self.id,
                    test_type=test_type,
                    manifest_directory=manifest.directory,
                    passed=0,
                    failed=1,
                    duration_ms=duration_ms,
                    exit_code=code,
                    success=False,
                    command=" ".join(argv),
                    note=f"boot command exited immediately with code {code}",
                    failures=[FailureInfo(name="boot", message=f"exited code {code}")],
                )

            health = wait_for_healthcheck(system, system.boot_timeout_seconds)
            failures: list[FailureInfo] = []
            checks_passed = 0
            if health.ok:
                endpoints: list[EndpointCheck] = list(system.endpoints)
                if not any(e.path == system.healthcheck_path for e in endpoints):
                    endpoints.append(
                        EndpointCheck(
                            path=system.healthcheck_path,
                            expected_status=system.healthcheck_expected_status,
                        )
                    )
                for endpoint in endpoints:
                    outcome = check_url(system.target_url, endpoint.path, endpoint.expected_status)
                    if outcome.ok:
                        checks_passed += 1
                    else:
                        failures.append(
                            FailureInfo(
                                name=f"GET {endpoint.path}",
                                message=outcome.detail,
                            )
                        )
                ok = not failures
                detail = f"health={health.detail}; endpoints {checks_passed}/{len(endpoints)} ok"
            else:
                ok = False
                detail = health.detail
                failures.append(FailureInfo(name="healthcheck", message=health.detail))

            duration_ms = int((time.perf_counter() - started) * 1000)
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                passed=checks_passed,
                failed=len(failures),
                duration_ms=duration_ms,
                exit_code=0 if process.poll() is None else (process.poll() or 0),
                command=" ".join(argv),
                success=ok,
                note=detail,
                failures=failures,
            )
        finally:
            terminate_tree(process)
