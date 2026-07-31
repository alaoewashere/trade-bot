"""
install_skills.py
-----------------
Clones (or pulls) the claude-trading-skills repository and installs each skill
subdirectory into this project's skills/ folder.

On Windows, directories are copied (symlinks require Developer Mode).

Usage:
    python scripts/install_skills.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


SKILLS_REPO_URL = "https://github.com/tradermonty/claude-trading-skills.git"
SKILLS_CACHE_DIR = Path.home() / ".claude" / "skills"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_SKILLS_DIR = PROJECT_ROOT / "skills"


def _run(cmd: list[str], cwd: Path | None = None) -> int:
    result = subprocess.run(cmd, cwd=cwd)
    return result.returncode


def clone_or_pull_skills_repo() -> Path:
    SKILLS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    repo_dir = SKILLS_CACHE_DIR / "claude-trading-skills"

    if (repo_dir / ".git").exists():
        print("[skills] Repository already exists. Pulling latest...")
        rc = _run(["git", "pull", "--ff-only"], cwd=repo_dir)
        if rc != 0:
            print("[skills] WARNING: git pull failed. Using cached copy.")
    else:
        print(f"[skills] Cloning {SKILLS_REPO_URL} -> {repo_dir}")
        rc = _run(["git", "clone", "--depth=1", SKILLS_REPO_URL, str(repo_dir)])
        if rc != 0:
            print("[skills] ERROR: git clone failed. Check your internet connection.")
            sys.exit(1)

    return repo_dir


def _try_symlink(src: Path, dst: Path) -> bool:
    try:
        dst.symlink_to(src, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        return False


def _copy_skill(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def install_skills(repo_dir: Path) -> None:
    PROJECT_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    skill_sources = [
        p for p in sorted(repo_dir.iterdir())
        if p.is_dir() and not p.name.startswith(".")
    ]

    if not skill_sources:
        print("[skills] No skill subdirectories found.")
        return

    installed = []
    skipped = []
    is_windows = sys.platform == "win32"

    for src in skill_sources:
        dst = PROJECT_SKILLS_DIR / src.name

        if dst.is_symlink() and Path(os.readlink(dst)).resolve() == src.resolve():
            skipped.append(src.name)
            continue

        if dst.exists() or dst.is_symlink():
            if dst.is_symlink():
                dst.unlink()
            else:
                shutil.rmtree(dst)

        if is_windows:
            linked = _try_symlink(src, dst)
            if not linked:
                _copy_skill(src, dst)
                print(f"  [copy]    {src.name}")
            else:
                print(f"  [link]    {src.name}")
        else:
            if _try_symlink(src, dst):
                print(f"  [link]    {src.name}")
            else:
                _copy_skill(src, dst)
                print(f"  [copy]    {src.name}")

        installed.append(src.name)

    print()
    print(f"[skills] Done: {len(installed)} installed, {len(skipped)} already up-to-date.")
    print(f"[skills] Location: {PROJECT_SKILLS_DIR}")


def main() -> None:
    print("=" * 60)
    print("  Hedge Fund AI - Skill Installer")
    print("=" * 60)
    repo_dir = clone_or_pull_skills_repo()
    print()
    install_skills(repo_dir)


if __name__ == "__main__":
    main()
