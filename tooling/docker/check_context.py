"""Check Docker's backend context filtering with synthetic local state only.

Requires Git and Docker Buildx. Uses FROM scratch and a local filesystem export:
no backend startup, image pull, dependency install, or provider request.
"""

from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SHIPPED_DATA = {
    "data/ipl_matches.csv",
    "data/merit_score_release_certificate.json",
    "data/sources.json",
}
SENTINELS = (
    ".env",
    ".env.local",
    "app/.env",
    "app/.env.production.local",
    "app/credentials.env",
    "app/__pycache__/main.cpython-314.pyc",
    "app/nested/.env.staging",
    "app/nested/__pycache__/cache.pyc",
    "app/cache.db",
    "app/cache.sqlite3-journal",
    "data/sportabase.db",
    "data/sportabase.db-wal",
    "data/sportabase.db-shm",
    "data/sportabase.db-journal",
    "data/sportabase.db.audit.bak",
    "data/copy.sqlite",
    "data/copy.sqlite3",
    "data/copy.sqlite3-wal",
    "data/account-export.json",
    "data/backups/renamed-snapshot",
    ".pytest_cache/sb009-probe",
    ".pytest-full/sb009-probe/state.db",
    ".venv314/pyvenv.cfg",
    ".vscode/sb009-probe.json",
    "tests/sb009-private-fixture.txt",
)


def export_context(context: Path, output: Path) -> Path:
    subprocess.run(
        [
            "docker", "buildx", "build",
            "--network=none", "--progress=plain",
            "--output", f"type=local,dest={output}",
            "--file", "-", str(context),
        ],
        input="FROM scratch\nCOPY . /context/\n",
        text=True,
        check=True,
        timeout=120,
    )
    return output / "context"


def main() -> None:
    if shutil.which("docker") is None:
        raise SystemExit("Docker is required; this check must not be skipped.")

    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "backend"],
        cwd=ROOT, text=True, capture_output=True, check=True,
    ).stdout.split("\0")

    with tempfile.TemporaryDirectory(prefix="sportabase-docker-context-") as tmp:
        scratch = Path(tmp)
        context = scratch / "backend"
        required = {"requirements.txt", *SHIPPED_DATA}
        for name in filter(None, tracked):
            relative = Path(name).relative_to("backend")
            source = ROOT / name
            if source.is_symlink():
                raise AssertionError(f"Review symlink before packaging: {name}")
            target = context / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if relative.parts[0] == "app" and relative.suffix == ".py":
                required.add(relative.as_posix())

        policy = context / ".dockerignore"
        policy_bytes = policy.read_bytes()
        for name in SENTINELS:
            target = context / name
            if target.exists():
                raise AssertionError(f"Synthetic fixture collides with tracked file: {name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"SYNTHETIC SB-009 FIXTURE: {name}\n", encoding="utf-8")

        # Reproduce the old unfiltered-context exposure using only fake local files.
        policy.unlink()
        unfiltered = export_context(context, scratch / "unfiltered")
        for name in SENTINELS:
            if not (unfiltered / name).is_file():
                raise AssertionError(f"Unfiltered control did not expose fixture: {name}")

        policy.write_bytes(policy_bytes)
        filtered = export_context(context, scratch / "filtered")
        for name in SENTINELS:
            if (filtered / name).exists():
                raise AssertionError(f"Local state leaked into Docker context: {name}")
        for name in sorted(required):
            if (filtered / name).read_bytes() != (context / name).read_bytes():
                raise AssertionError(f"Required build input changed: {name}")

        actual_data = {
            path.relative_to(filtered).as_posix()
            for path in (filtered / "data").rglob("*") if path.is_file()
        }
        if actual_data != SHIPPED_DATA:
            raise AssertionError(f"Unexpected shipped data files: {sorted(actual_data)}")

    print(
        f"PASS: {len(SENTINELS)} local-state sentinels excluded; "
        f"{len(required)} required files preserved byte-for-byte; "
        "unfiltered control reproduced the exposure."
    )


if __name__ == "__main__":
    main()
