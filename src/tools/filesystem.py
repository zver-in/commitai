import os
import fnmatch
from typing import Any, Dict, List, Callable, Optional

from langchain.tools import tool


# =========================
# Helpers (local to filesystem tools)
# =========================

def _abspath(path: str) -> str:
    return os.path.abspath(os.path.normpath(path))


def _ensure_within(base: str, candidate: str) -> bool:
    """Return True if candidate path is within base directory."""
    try:
        base_cp = os.path.commonpath([base])
        cand_cp = os.path.commonpath([base, candidate])
        return base_cp == cand_cp
    except Exception:
        return False


def _is_denied(rel_path: str, deny_patterns: List[str]) -> bool:
    # Check against both the full relative path and its basename
    base = os.path.basename(rel_path)
    for pattern in deny_patterns:
        if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(base, pattern):
            return True
    return False


# =========================
# Filesystem tool builders
# =========================

def build_list_directory(config: Dict[str, Any]):
    """Create a parameterized list_directory tool bound to config.

    Config supported keys:
    - workdir: str (required)
    - deny: list[str] (optional)
    """
    workdir = _abspath(config.get("workdir", "."))
    deny: List[str] = list(config.get("deny", []) or [])

    @tool("list_directory", return_direct=False)
    def list_directory(path: str = ".") -> str:
        """List directory contents within the configured workdir.

        Parameters:
        - path: relative path inside workdir (default '.')

        Security policies:
        - leaving the workdir is forbidden
        - deny-pattern filtering is applied
        """
        target = _abspath(os.path.join(workdir, path))
        if not _ensure_within(workdir, target):
            return f"Access denied: path is outside the working directory ({path})"
        if not os.path.exists(target):
            return f"Directory not found: {path}"
        if not os.path.isdir(target):
            return f"Not a directory: {path}"
        try:
            entries = sorted(os.listdir(target))
        except PermissionError:
            return f"Permission denied for directory: {path}"
        lines: List[str] = [f"Contents of {path}:"]
        count = 0
        for name in entries:
            rel = os.path.relpath(os.path.join(target, name), workdir)
            if _is_denied(rel, deny):
                continue
            if count >= 500:
                lines.append("... (output truncated)")
                break
            full = os.path.join(target, name)
            if os.path.isdir(full):
                lines.append(f"[DIR]  {name}")
            else:
                try:
                    size = os.path.getsize(full)
                except Exception:
                    size = -1
                size_info = f"{size} B" if size >= 0 else "? B"
                lines.append(f"[FILE] {name}  ({size_info})")
            count += 1
        return "\n".join(lines)

    return list_directory


def build_read_file(config: Dict[str, Any]):
    """Create a parameterized read_file tool bound to config.

    Config supported keys:
    - workdir: str (required)
    - deny: list[str] (optional)
    - max_bytes: int (optional, default 200_000)
    """
    workdir = _abspath(config.get("workdir", "."))
    deny: List[str] = list(config.get("deny", []) or [])
    default_max = int(config.get("max_bytes", 200_000))

    @tool("read_file", return_direct=False)
    def read_file(path: str, max_bytes: Optional[int] = None) -> str:
        """Read a file within the workdir with size limit and deny-pattern checks.

        Parameters:
        - path: relative path to a file inside workdir
        - max_bytes: override read size limit (defaults to config)

        Security policies:
        - leaving the workdir is forbidden
        - deny-pattern filtering is applied
        """
        limit = default_max if max_bytes is None else int(max_bytes)
        target = _abspath(os.path.join(workdir, path))
        if not _ensure_within(workdir, target):
            return f"Access denied: path is outside the working directory ({path})"
        if not os.path.exists(target):
            return f"File not found: {path}"
        if os.path.isdir(target):
            return f"The path points to a directory, not a file: {path}"
        rel = os.path.relpath(target, workdir)
        if _is_denied(rel, deny):
            return f"Access denied by deny policy for: {path}"
        try:
            size = os.path.getsize(target)
            if size > limit:
                return f"File is too large ({size} bytes), limit {limit} bytes: {path}"
        except PermissionError as e:
            return f"Permission denied when checking file size for {path}: {e}"
        except FileNotFoundError:
            return f"File not found while checking size: {path}"
        except OSError as e:
            # If stat fails for other OS reasons, continue to attempt reading with limit
            size = -1
        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(limit)
            return content
        except UnicodeDecodeError:
            return f"Unable to decode file as UTF-8: {path}"
        except FileNotFoundError:
            return f"File not found while opening: {path}"
        except PermissionError as e:
            return f"Permission denied when reading file {path}: {e}"
        except IsADirectoryError:
            return f"Expected a file but found a directory: {path}"
        except OSError as e:
            return f"OS error while reading file {path}: {e}"

    return read_file
