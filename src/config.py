import os
import sys
import yaml


def load_system_prompt(path: str) -> str:
    """Load system prompt from the given agent YAML file (field: description).

    System prompt is mandatory. If file is missing, unreadable, or description
    is empty, an exception is raised.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        desc = data.get("description")
        if isinstance(desc, str) and desc.strip():
            return desc.strip()
        raise ValueError(
            f"The file {path} is missing a non-empty 'description' field."
        )
    except FileNotFoundError:
        raise FileNotFoundError(
            f"System prompt file not found: {path}. Please ensure it exists."
        )
    except PermissionError as e:
        raise PermissionError(
            f"Permission denied when reading system prompt file: {path}"
        ) from e
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in system prompt file: {path}") from e
    except OSError as e:
        # Includes IO-related issues like too long path, I/O errors, etc.
        raise OSError(f"Failed to read system prompt file {path}: {e}") from e


def load_enabled_tools(path: str) -> list[str]:
    """Load enabled tools from the given agent YAML (field: tools).

    Returns a list of tool names (strings). If field is missing or not a list,
    returns an empty list.

    Backward compatibility: if 'tools' is a list of objects, we will extract
    their 'name' field and return it.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        tools = data.get("tools")
        if isinstance(tools, list):
            names: list[str] = []
            for t in tools:
                if isinstance(t, (str, int, float)):
                    val = str(t).strip()
                    if val:
                        names.append(val)
                elif isinstance(t, dict):
                    name = str(t.get("name", "")).strip()
                    if name:
                        names.append(name)
            return names
        return []
    except FileNotFoundError:
        # Missing config means no tools enabled
        return []
    except PermissionError as e:
        print(
            f"Warning: permission denied while reading tools from {path}: {e}",
            file=sys.stderr,
        )
        return []
    except yaml.YAMLError as e:
        print(
            f"Warning: invalid YAML while reading tools from {path}: {e}",
            file=sys.stderr,
        )
        return []
    except OSError as e:
        print(
            f"Warning: OS error while reading tools from {path}: {e}",
            file=sys.stderr,
        )
        return []


def _load_yaml(path: str) -> dict:
    """Internal: load agent YAML as dict from explicit path."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def load_tools_specs(path: str) -> list[dict]:
    """Load structured tool specifications from YAML.

    Expected format under key 'tools':
      - name: list_directory
        type: filesystem
        config:
          workdir: ./agents
          deny: ["*.pyc", "__pycache__"]

    Returns a list of dicts with keys: name, type, config (dict).
    If tools is a simple list of strings, it is converted into specs with
    empty type/config for backward compatibility, but consumers should prefer
    structured specs.
    """
    try:
        data = _load_yaml(path)
    except FileNotFoundError:
        return []
    except PermissionError as e:
        print(
            f"Warning: permission denied while reading agent YAML {path}: {e}",
            file=sys.stderr,
        )
        return []
    except yaml.YAMLError as e:
        print(
            f"Warning: invalid YAML in agent file {path}: {e}",
            file=sys.stderr,
        )
        return []
    except OSError as e:
        print(
            f"Warning: OS error while reading agent YAML {path}: {e}",
            file=sys.stderr,
        )
        return []

    specs_raw = data.get("tools")
    specs: list[dict] = []
    if isinstance(specs_raw, list):
        for item in specs_raw:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
                ttype = str(item.get("type", "")).strip()
                cfg = item.get("config") or {}
                if not isinstance(cfg, dict):
                    cfg = {}
                if name:
                    specs.append({"name": name, "type": ttype, "config": cfg})
            elif isinstance(item, (str, int, float)):
                name = str(item).strip()
                if name:
                    specs.append({"name": name, "type": "", "config": {}})
    return specs


def load_agent_config(path: str) -> dict:
    """Return a normalized agent config dict with keys: id, description, tools.

    - id: str or "agent"
    - description: str (may be empty)
    - tools: list of structured tool specs (see load_tools_specs)
    """
    try:
        data = _load_yaml(path)
    except FileNotFoundError:
        data = {}
    except (PermissionError, yaml.YAMLError, OSError) as e:
        print(f"Warning: failed to load agent config from {path}: {e}", file=sys.stderr)
        data = {}
    return {
        "id": (str(data.get("id")) if data.get("id") else "agent"),
        "description": str(data.get("description") or ""),
        "tools": load_tools_specs(path),
    }
