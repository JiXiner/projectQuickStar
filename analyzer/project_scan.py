"""Fast, cancellable project discovery and metadata scanning."""

from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .code_parser import analyze_source_file
from .language_detector import detect_languages, matches_language

ProgressCallback = Callable[[int, int, str], None]

DEFAULT_EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git", ".idea", ".vscode", ".svn", "__pycache__", ".pytest_cache",
        ".mypy_cache", ".tox", ".venv", "venv", "env", "node_modules",
        "vendor", "dist", "build", "target", "coverage", ".next",
    }
)


class ScanCancelled(RuntimeError):
    """Raised when the current scan was cancelled by the user."""


@dataclass
class FileRecord:
    path: str
    extension: str
    size: int
    modified_at: float
    analysis: dict | None = None


@dataclass
class ScanResult:
    project_name: str
    root_path: str
    source_path: str
    selected_language: str
    detected_languages: dict[str, int]
    total_files: int
    total_bytes: int
    duration_seconds: float
    files: list[FileRecord] = field(default_factory=list)
    skipped_files: int = 0
    warnings: list[str] = field(default_factory=list)
    report_paths: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class ProjectScanner:
    """Scan a directory or archive without blocking its caller."""

    def __init__(
        self,
        max_workers: int | None = None,
        excluded_directories: Iterable[str] = DEFAULT_EXCLUDED_DIRECTORIES,
    ) -> None:
        self.max_workers = max_workers or min(32, (os.cpu_count() or 4) + 4)
        self.excluded_directories = frozenset(excluded_directories)
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()

    @property
    def is_paused(self) -> bool:
        return self._pause_event.is_set()

    def pause(self) -> None:
        self._pause_event.set()

    def resume(self) -> None:
        self._pause_event.clear()

    def cancel(self) -> None:
        self._cancel_event.set()
        self._pause_event.clear()

    def scan(
        self,
        source: str | Path,
        selected_language: str = "自动检测",
        progress: ProgressCallback | None = None,
    ) -> ScanResult:
        self._cancel_event.clear()
        self._pause_event.clear()
        started = time.perf_counter()
        source_path = Path(source).expanduser().resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"项目路径不存在：{source_path}")

        temporary_directory: tempfile.TemporaryDirectory[str] | None = None
        try:
            root, temporary_directory = self._prepare_root(source_path)
            paths = list(self._discover_files(root))
            total_discovered = len(paths)
            if progress:
                progress(0, total_discovered, "已建立文件清单")

            records: list[FileRecord] = []
            warnings: list[str] = []
            skipped = 0
            with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="scan") as pool:
                futures = {pool.submit(self._read_metadata, path, root): path for path in paths}
                for completed, future in enumerate(as_completed(futures), start=1):
                    self._wait_if_paused()
                    if self._cancel_event.is_set():
                        for pending in futures:
                            pending.cancel()
                        raise ScanCancelled("扫描已取消")
                    try:
                        record = future.result()
                        if matches_language(record.path, selected_language):
                            records.append(record)
                        else:
                            skipped += 1
                    except OSError as exc:
                        skipped += 1
                        if len(warnings) < 100:
                            warnings.append(f"无法读取 {futures[future]}：{exc}")
                    if progress and (completed == total_discovered or completed % 25 == 0):
                        progress(completed, total_discovered, f"正在扫描：{futures[future].name}")

            records.sort(key=lambda item: item.path.lower())
            language_counts = detect_languages(record.path for record in records)
            return ScanResult(
                project_name=root.name,
                root_path=str(root),
                source_path=str(source_path),
                selected_language=selected_language,
                detected_languages=language_counts,
                total_files=len(records),
                total_bytes=sum(record.size for record in records),
                duration_seconds=round(time.perf_counter() - started, 3),
                files=records,
                skipped_files=skipped,
                warnings=warnings,
            )
        finally:
            if temporary_directory is not None:
                temporary_directory.cleanup()

    def _discover_files(self, root: Path):
        for current_root, directories, filenames in os.walk(root, followlinks=False):
            self._wait_if_paused()
            if self._cancel_event.is_set():
                raise ScanCancelled("扫描已取消")
            directories[:] = sorted(
                directory
                for directory in directories
                if directory not in self.excluded_directories
                and not Path(current_root, directory).is_symlink()
            )
            for filename in sorted(filenames):
                path = Path(current_root, filename)
                if not path.is_symlink():
                    yield path

    def _wait_if_paused(self) -> None:
        while self._pause_event.is_set() and not self._cancel_event.wait(0.1):
            pass

    @staticmethod
    def _read_metadata(path: Path, root: Path) -> FileRecord:
        stat = path.stat()
        return FileRecord(
            path=path.relative_to(root).as_posix(),
            extension=path.suffix.lower(),
            size=stat.st_size,
            modified_at=stat.st_mtime,
            analysis=analyze_source_file(path),
        )

    def _prepare_root(
        self, source: Path
    ) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
        if source.is_dir():
            return source, None
        temporary_directory = tempfile.TemporaryDirectory(prefix="project_quick_star_")
        destination = Path(temporary_directory.name)
        try:
            lower_name = source.name.lower()
            if lower_name.endswith(".zip"):
                with zipfile.ZipFile(source) as archive:
                    self._safe_extract_zip(archive, destination)
            elif lower_name.endswith((".tar.gz", ".tgz", ".tar")):
                with tarfile.open(source) as archive:
                    self._safe_extract_tar(archive, destination)
            elif lower_name.endswith(".rar"):
                self._extract_rar(source, destination)
            else:
                raise ValueError("仅支持目录、zip、rar、tar、tar.gz 和 tgz 项目")
            children = [child for child in destination.iterdir()]
            root = children[0] if len(children) == 1 and children[0].is_dir() else destination
            return root, temporary_directory
        except Exception:
            temporary_directory.cleanup()
            raise

    @staticmethod
    def _inside_destination(destination: Path, member_name: str) -> bool:
        target = (destination / member_name).resolve()
        try:
            target.relative_to(destination.resolve())
            return True
        except ValueError:
            return False

    def _safe_extract_zip(self, archive: zipfile.ZipFile, destination: Path) -> None:
        for member in archive.infolist():
            if not self._inside_destination(destination, member.filename):
                raise ValueError(f"压缩包包含不安全路径：{member.filename}")
        archive.extractall(destination)

    def _safe_extract_tar(self, archive: tarfile.TarFile, destination: Path) -> None:
        members = archive.getmembers()
        for member in members:
            if member.issym() or member.islnk():
                raise ValueError(f"压缩包包含不允许的链接：{member.name}")
            if not self._inside_destination(destination, member.name):
                raise ValueError(f"压缩包包含不安全路径：{member.name}")
        # Python 3.12 adds the safer ``filter`` argument. Every member has
        # already been validated above, so older supported interpreters can
        # use extractall without it.
        if "filter" in tarfile.TarFile.extractall.__code__.co_varnames:
            archive.extractall(destination, members=members, filter="data")
        else:
            archive.extractall(destination, members=members)

    def _extract_rar(self, source: Path, destination: Path) -> None:
        try:
            import rarfile
        except ImportError as exc:
            raise RuntimeError("RAR 支持需要安装 rarfile，并配置可用的解压程序") from exc
        with rarfile.RarFile(source) as archive:
            for member in archive.infolist():
                if not self._inside_destination(destination, member.filename):
                    raise ValueError(f"压缩包包含不安全路径：{member.filename}")
            archive.extractall(destination)
