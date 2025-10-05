from typing import Any, Dict, Callable
from .filesystem import build_list_directory, build_read_file, build_search_in_files
from .git import (
    build_git_changed_files,
    build_git_diff,
    build_git_pr_diff,
    build_git_pr_changed_files,
    build_post_review_comment,
    build_list_review_comments,
)


# =========================
# ToolFactory
# =========================

class ToolFactory:
    """Factory to instantiate tools from YAML specs.

    YAML tool spec format:
    - name: list_directory
      type: filesystem
      config: { workdir: ./agents, deny: ["*.pyc"] }
    """

    def __init__(self):
        # Map type -> name -> builder
        self._registry: Dict[str, Dict[str, Callable[[Dict[str, Any]], Any]]] = {
            "filesystem": {
                "list_directory": build_list_directory,
                "read_file": build_read_file,
                "search_in_files": build_search_in_files,
            },
            "git": {
                "git_changed_files": build_git_changed_files,
                "git_diff": build_git_diff,
                "git_pr_diff": build_git_pr_diff,
                "git_pr_changed_files": build_git_pr_changed_files,
                "post_review_comment": build_post_review_comment,
                "list_review_comments": build_list_review_comments,
            },
        }

    def create(self, tool_spec: Dict[str, Any]):
        t_name = str(tool_spec.get("name", "")).strip()
        t_type = str(tool_spec.get("type", "")).strip()
        config = tool_spec.get("config") or {}
        if not t_name or not t_type:
            raise ValueError("Invalid tool specification: 'name' and 'type' fields are required")
        type_bucket = self._registry.get(t_type)
        if not type_bucket or t_name not in type_bucket:
            raise ValueError(f"Unknown tool '{t_name}' for type '{t_type}'")
        builder = type_bucket[t_name]
        return builder(config)

    def register(self, t_type: str, t_name: str, builder: Callable[[Dict[str, Any]], Any]) -> None:
        bucket = self._registry.setdefault(t_type, {})
        bucket[t_name] = builder
