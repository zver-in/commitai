import os
import subprocess
from typing import Any, Tuple

import json
import re
from github import Github, GithubException

from langchain.tools import tool


class GitRepositoryError(Exception):
    """Raised when the given path is not a valid Git repository."""
    pass


def _abspath(path: str) -> str:
    """Convert a path to an absolute path with normalized slashes.
    
    Args:
        path: Relative or absolute path to normalize
        
    Returns:
        str: Absolute and normalized path
    """
    return os.path.abspath(os.path.normpath(path))


def _validate_git_repository(workdir: str) -> None:
    """Validate if the given directory is a valid Git repository.
    
    Args:
        workdir: Path to the working directory
        
    Raises:
        GitRepositoryError: If the directory is not a valid Git repository
    """
    if not os.path.exists(workdir):
        raise GitRepositoryError(f"Working directory does not exist: {workdir}")
    if not os.path.isdir(workdir):
        raise GitRepositoryError(f"Path is not a directory: {workdir}")
        
    git_dir = os.path.join(workdir, ".git")
    if not os.path.exists(git_dir):
        raise GitRepositoryError(
            (
                f"Not a Git repository (missing .git directory): {workdir}\n"
                "Please ensure you're running this command from within a Git repository "
                "or initialize one with 'git init'."
            )
        )
    if not os.path.isdir(git_dir):
        raise GitRepositoryError(f".git is not a directory: {git_dir}")


def _run_git_command(workdir: str, command: list[str], timeout: int = 30) -> Tuple[bool, str, str]:
    """Run a git command and return its result.
    
    Args:
        workdir: Working directory for the command
        command: Git command to run (without 'git' prefix)
        timeout: Command timeout in seconds
        
    Returns:
        Tuple[bool, str, str]: (success, stdout, stderr)
        
    Security:
        - Executes git commands in a subprocess
        - Implements timeout to prevent hanging
        - Validates file system access
    """
    try:
        proc = subprocess.run(
            ["git"] + command,
            cwd=workdir,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return (proc.returncode == 0, proc.stdout.strip(), proc.stderr.strip())
    except FileNotFoundError:
        return (False, "", "Git command not found. Please ensure Git is installed and in your PATH.")
    except subprocess.TimeoutExpired:
        return (False, "", "Git command timed out. The repository might be too large or there might be network issues.")
    except PermissionError:
        return (False, "", f"Permission denied when trying to access {workdir}. Check your read permissions.")
    except Exception as e:
        return (False, "", f"Unexpected error while running Git command: {str(e)}")


# =========================
# Git tool builders
# =========================

def build_git_changed_files(config: dict[str, Any]):
    """Create a tool that returns list of changed files via `git diff --name-only`.

    Config supported keys:
    - workdir: str (required)
    """
    workdir = _abspath(config.get("workdir", "."))

    @tool("git_changed_files", return_direct=False)
    def git_changed_files(query: str = "") -> str:
        """
        Returns a list of changed files in the Git repository (git diff --name-only).
        
        Note: The 'query' parameter is part of the tool's interface but is not used.
              It can be safely omitted when calling this function.
        
        Returns:
            str: List of changed files (one per line) or an error message.
            
        Security:
            - Only runs `git diff --name-only`
            - Execution is restricted to the specified workdir
            - The query parameter is completely ignored and not used in command construction
            
        Example:
            git_changed_files()  # Returns list of changed files
        """
        # Validate Git repository
        try:
            _validate_git_repository(workdir)
        except GitRepositoryError as e:
            return f"Error: {e}"
            
        # Execute git command
        success, output, error_msg = _run_git_command(workdir, ["diff", "--name-only"])
        
        if not success:
            return (
                f"Error: {error_msg}\n\n"
                "Troubleshooting tips:\n"
                "1. Make sure you have the necessary Git permissions\n"
                "2. Run 'git status' in the repository to check its state\n"
                "3. If this is a new repository, try making an initial commit"
            )
            
        return output if output else ""

    return git_changed_files


def _check_git_initial_commit(workdir: str) -> Tuple[bool, str]:
    """Check if the Git repository has at least one commit.
    
    Args:
        workdir: Path to the working directory
        
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    success, _, error_msg = _run_git_command(workdir, ["rev-parse", "--is-inside-work-tree"])
    if not success:
        return (False, "Not a valid Git repository or no commits yet.\n"
                     "Make sure you have made at least one commit in this repository.")
    return (True, "")


def build_git_diff(config: dict[str, Any]):
    """Create a tool that returns the full uncommitted diff via `git diff HEAD`.

    Config supported keys:
    - workdir: str (required)
    """
    workdir = _abspath(config.get("workdir", "."))

    @tool("git_diff", return_direct=False)
    def git_diff(query: str = "") -> str:
        """
        Returns the full uncommitted diff in the Git repository (git diff HEAD).
        
        Note: The 'query' parameter is part of the tool's interface but is not used.
              It can be safely omitted when calling this function.
        
        Returns:
            str: The git diff output or an error message.
            
        Security:
            - Only runs `git diff HEAD`
            - Execution is restricted to the specified workdir
            - No user input is used in command construction
            
        Example:
            git_diff()  # Returns the full git diff
        """
        # Validate Git repository
        try:
            _validate_git_repository(workdir)
        except GitRepositoryError as e:
            return f"Error: {e}"
            
        # Check for initial commit
        try:
            is_valid, error_msg = _check_git_initial_commit(workdir)
            if not is_valid:
                return f"Error: {error_msg}"

            # Execute git diff command
            success, output, error_msg = _run_git_command(workdir, ["diff", "HEAD"])
            if not success:
                return f"Error: {error_msg}"
                
            return output if output else "No changes to show"
        except FileNotFoundError:
            return (
                "Error: Git command not found. "
                "Please ensure Git is installed and available in your PATH.\n"
                "You can install Git from https://git-scm.com/downloads"
            )
        except subprocess.TimeoutExpired:
            return "Error: Git command timed out after 30 seconds. The repository might be too large or there might be network issues."
        except PermissionError:
            return f"Error: Permission denied when trying to access {workdir}. Check your read permissions."
        except Exception as e:
            return (
                f"Unexpected error while running Git command: {str(e)}\n"
                f"Type: {type(e).__name__}"
            )

    return git_diff


def build_git_pr_diff(config: dict[str, Any]):
    """Create a tool that returns PR diff against a base branch: `git diff <base_branch>...HEAD`.

    This tool is designed to show the differences between the current branch and a specified
    base branch (typically 'main' or 'master'). It's particularly useful for code reviews
    to see what changes are being introduced in a pull request.

    Config supported keys:
        workdir (str): The working directory of the Git repository (required).
        base_branch (str): The base branch to compare against (default: 'origin/main').

    Security:
        - Only executes `git fetch origin` and `git diff <base_branch>...HEAD`
        - Execution is strictly limited to the specified workdir
        - No user input is used in command construction
        - All operations are read-only and don't modify the repository
    """
    workdir = _abspath(config.get("workdir", "."))
    base_branch = str(config.get("base_branch", "origin/main"))

    @tool("git_pr_diff", return_direct=False)
    def git_pr_diff(query: str = "") -> str:
        """
        Returns the diff between the current branch and the specified base branch.
        
        This function first validates the repository state, checks if the base branch exists,
        fetches the latest changes from the remote repository, and then shows the differences
        between the base branch and the current HEAD.
        
        Args:
            query: Unused parameter, can be left empty.
            
        Returns:
            str: The git diff output or a detailed error message if something goes wrong.
            
        Security:
            - Only runs `git fetch origin` and `git diff <base_branch>...HEAD`
            - Execution is strictly limited to the specified workdir
            - No user input is used in command construction
            - All operations are read-only and don't modify the repository
            
        Example:
            git_pr_diff()  # Shows diff between origin/main and current branch
        """
        # Validate working directory and repository
        try:
            _validate_git_repository(workdir)
        except GitRepositoryError as e:
            return f"Error: {e}"

        # 1) Check if the base branch exists
        try:
            check_branch = subprocess.run(
                ["git", "show-ref", "--verify", f"refs/remotes/{base_branch}"],
                cwd=workdir,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if check_branch.returncode != 0:
                # Try to list available remote branches for better error message
                try:
                    branches_proc = subprocess.run(
                        ["git", "branch", "-r"],
                        cwd=workdir,
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=5,
                    )
                    available_branches = branches_proc.stdout.strip()
                    branch_list = "\n  " + "\n  ".join(available_branches.splitlines()) if available_branches else "  (no remote branches found)"
                    branch_hint = f"\n\nAvailable remote branches:{branch_list}"
                except Exception:
                    branch_hint = ""
                
                return (
                    f"Error: Base branch '{base_branch}' not found in remote repository.{branch_hint}\n"
                    f"Please check the branch name or fetch the latest changes with 'git fetch --all'"
                )
        except subprocess.TimeoutExpired:
            return "Error: Timed out while checking for base branch. The repository might be too large or there might be network issues."
        except Exception as e:
            return f"Error checking for base branch: {str(e)}"

        # 2) Fetch origin
        try:
            fetch_proc = subprocess.run(
                ["git", "fetch", "origin"],
                cwd=workdir,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,  # Longer timeout for fetch operation
            )
        except FileNotFoundError:
            return (
                "Error: Git command not found. "
                "Please ensure Git is installed and available in your PATH.\n"
                "You can install Git from https://git-scm.com/downloads"
            )
        except subprocess.TimeoutExpired:
            return "Error: Git fetch operation timed out after 60 seconds. The repository might be too large or there might be network issues."
        except PermissionError:
            return f"Error: Permission denied when trying to access {workdir}. Check your read/write permissions."
        except Exception as e:
            return (
                f"Unexpected error while running Git fetch: {str(e)}\n"
                f"Type: {type(e).__name__}"
            )

        if fetch_proc.returncode != 0:
            error_msg = (fetch_proc.stderr or "No error details available").strip()
            return (
                f"Git fetch failed with exit code {fetch_proc.returncode}.\n"
                f"Command: git fetch origin\n"
                f"Error: {error_msg}\n\n"
                "Troubleshooting tips:\n"
                "1. Check your network connection\n"
                "2. Verify you have permission to access the remote repository\n"
                "3. Run 'git remote -v' to check your remote configuration"
            )

        # 3) Diff against base_branch
        success, output, error = _run_git_command(
            workdir,
            ["diff", f"{base_branch}...HEAD"],
            timeout=30  # Reasonable timeout for diff operation
        )
        
        if not success:
            return (
                f"Git diff failed. {error}\n\n"
                "Troubleshooting tips:\n"
                f"1. Verify that branch '{base_branch}' exists in the remote\n"
                "2. Check if you have any uncommitted changes with 'git status'\n"
                "3. Try running 'git fetch --all' to update all remote branches"
            )
            
        return output if output else "No changes to show"

    return git_pr_diff


def build_git_pr_changed_files(config: dict[str, Any]):
    """Create a tool that returns list of files changed in PR: `git diff --name-only <base_branch>...HEAD`.

    This tool is designed to list all files that have been changed in the current branch
    compared to the specified base branch. It's particularly useful for code reviews
    to quickly see which files have been modified in a pull request.

    Config supported keys:
        workdir (str): The working directory of the Git repository (required).
        base_branch (str): The base branch to compare against (default: 'origin/main').

    Security:
        - Only executes `git fetch origin` and `git diff --name-only <base_branch>...HEAD`
        - Execution is strictly limited to the specified workdir
        - No user input is used in command construction
        - All operations are read-only and don't modify the repository
    """
    workdir = _abspath(config.get("workdir", "."))
    base_branch = str(config.get("base_branch", "origin/main"))

    @tool("git_pr_changed_files", return_direct=False)
    def git_pr_changed_files(query: str = "") -> str:
        """
        Returns a list of files changed in the current branch compared to the base branch.
        
        This function first validates the repository state, checks if the base branch exists,
        fetches the latest changes from the remote repository, and then lists all files
        that have been modified between the base branch and the current HEAD.
        
        Args:
            query: Unused parameter, can be left empty.
            
        Returns:
            str: List of changed files (one per line) or a detailed error message.
            
        Security:
            - Only runs `git fetch origin` and `git diff --name-only <base_branch>...HEAD`
            - Execution is strictly limited to the specified workdir
            - No user input is used in command construction
            - All operations are read-only and don't modify the repository
            
        Example:
            git_pr_changed_files()  # Lists files changed compared to origin/main
        """
        # Validate working directory and repository
        try:
            _validate_git_repository(workdir)
        except GitRepositoryError as e:
            return f"Error: {e}"

        # 1) Check if the base branch exists
        try:
            check_branch = subprocess.run(
                ["git", "show-ref", "--verify", f"refs/remotes/{base_branch}"],
                cwd=workdir,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if check_branch.returncode != 0:
                # Try to list available remote branches for better error message
                try:
                    branches_proc = subprocess.run(
                        ["git", "branch", "-r"],
                        cwd=workdir,
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=5,
                    )
                    available_branches = branches_proc.stdout.strip()
                    branch_list = "\n  " + "\n  ".join(available_branches.splitlines()) if available_branches else "  (no remote branches found)"
                    branch_hint = f"\n\nAvailable remote branches:{branch_list}"
                except Exception:
                    branch_hint = ""
                
                return (
                    f"Error: Base branch '{base_branch}' not found in remote repository.{branch_hint}\n"
                    f"Please check the branch name or fetch the latest changes with 'git fetch --all'"
                )
        except subprocess.TimeoutExpired:
            return "Error: Timed out while checking for base branch. The repository might be too large or there might be network issues."
        except Exception as e:
            return f"Error checking for base branch: {str(e)}"

        # 2) Fetch origin
        try:
            fetch_proc = subprocess.run(
                ["git", "fetch", "origin"],
                cwd=workdir,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,  # Longer timeout for fetch operation
            )
        except FileNotFoundError:
            return (
                "Error: Git command not found. "
                "Please ensure Git is installed and available in your PATH.\n"
                "You can install Git from https://git-scm.com/downloads"
            )
        except subprocess.TimeoutExpired:
            return "Error: Git fetch operation timed out after 60 seconds. The repository might be too large or there might be network issues."
        except PermissionError:
            return f"Error: Permission denied when trying to access {workdir}. Check your read/write permissions."
        except Exception as e:
            return (
                f"Unexpected error while running Git fetch: {str(e)}\n"
                f"Type: {type(e).__name__}"
            )

        if fetch_proc.returncode != 0:
            error_msg = (fetch_proc.stderr or "No error details available").strip()
            return (
                f"Git fetch failed with exit code {fetch_proc.returncode}.\n"
                f"Command: git fetch origin\n"
                f"Error: {error_msg}\n\n"
                "Troubleshooting tips:\n"
                "1. Check your network connection\n"
                "2. Verify you have permission to access the remote repository\n"
                "3. Run 'git remote -v' to check your remote configuration"
            )

        # 3) Get changed files
        success, output, error = _run_git_command(
            workdir,
            ["diff", "--name-only", f"{base_branch}...HEAD"],
            timeout=30  # Reasonable timeout for diff operation
        )

def build_post_review_comment(config: dict[str, Any]):
    """Create a tool that posts a code review comment to a GitHub Pull Request.

    The tool reads GitHub Actions environment variables:
    - GITHUB_TOKEN: auth token
    - GITHUB_REPOSITORY: "owner/repo"
    - GITHUB_EVENT_PATH: path to the event JSON with pull_request.number and pull_request.head.sha

    Input JSON format:
    {
      "file": "src/app.py",
      "line": 42,
      "comment": "Add error handling here."
    }

    Security and scope:
    - Only uses provided env to access the current repository and PR.
    - Does not perform arbitrary API calls beyond creating a PR review comment.
    """
    @tool("post_review_comment", return_direct=False)
    def post_review_comment(comment_data: str = "") -> str:
        """
        Posts a code review comment to a GitHub Pull Request.
        
        Args:
            comment_data: JSON string containing the comment details.
                Example: {"file": "src/app.py", "line": 42, "comment": "Add error handling"}
                
        Returns:
            str: Success message or error details.
            
        Security:
            - Only posts to the current repository and PR
            - Requires GITHUB_TOKEN with appropriate permissions
            - Limited to the scope of the current PR
        """
        # 1) Validate environment
        token = os.environ.get("GITHUB_TOKEN")
        repo_full = os.environ.get("GITHUB_REPOSITORY")
        event_path = os.environ.get("GITHUB_EVENT_PATH")

        missing = []
        if not token:
            missing.append("GITHUB_TOKEN")
        if not repo_full:
            missing.append("GITHUB_REPOSITORY")
        if not event_path:
            missing.append("GITHUB_EVENT_PATH")
        if missing:
            return (
                "Missing environment variables: " + ", ".join(missing) +
                ". The tool must be run inside GitHub Actions with a properly configured environment."
            )

        if not os.path.isfile(event_path):
            return f"GitHub Actions event file not found: {event_path}"

        # 2) Parse input JSON
        try:
            payload = json.loads(comment_data or "{}")
        except json.JSONDecodeError as e:
            return (
                "Invalid input JSON. Expected a JSON string with fields: file, line, comment. "
                f"Parse error: {e}"
            )

        if not isinstance(payload, dict):
            return "Invalid input: expected a JSON object with fields: file, line, comment."

        file_path = payload.get("file")
        line = payload.get("line")
        comment = payload.get("comment")

        if not isinstance(file_path, str) or not file_path:
            return "The 'file' field is required and must be a string with a relative file path."
        if not isinstance(line, int) or line <= 0:
            return "The 'line' field is required and must be a positive integer."
        if not isinstance(comment, str) or not comment.strip():
            return "The 'comment' field is required and must be a non-empty string."

        # 3) Read event to get PR number and head SHA
        try:
            with open(event_path, "r", encoding="utf-8") as f:
                event = json.load(f)
            pr_number = (
                event.get("pull_request", {}).get("number")
                or event.get("number")
            )
            head_sha = (
                event.get("pull_request", {}).get("head", {}).get("sha")
            )
        except FileNotFoundError:
            return f"GitHub Actions event file not found: {event_path}"
        except PermissionError as e:
            return f"Permission denied when reading GitHub event file {event_path}: {e}"
        except json.JSONDecodeError as e:
            return f"Invalid JSON in GitHub event file {event_path}: {e}"
        except OSError as e:
            return f"OS error while reading GitHub event file {event_path}: {e}"

        if not isinstance(pr_number, int):
            return "Failed to determine the PR number from GITHUB_EVENT_PATH (pull_request.number)."
        if not isinstance(head_sha, str) or not head_sha:
            # Not strictly required by newer APIs when using line/side, but helpful for compatibility
            head_sha = None

        # 4) Connect to GitHub and create the review comment
        try:
            gh = Github(login_or_token=token)
            repo = gh.get_repo(repo_full)
            pr = repo.get_pull(pr_number)
        except GithubException as e:
            status = getattr(e, 'status', None)
            data = getattr(e, 'data', None)
            msg = f"GitHub API error while fetching repository/PR: status={status}, details={data or str(e)}"
            return msg
        except Exception as e:
            return f"Failed to initialize GitHub client or access PR: {e}"

        # 5) Compute diff position for the target file/line using PR file patches
        def _compute_review_position() -> int | None:
            """
            Map absolute line in the new file to a patch position for GitHub review comments.

            Algorithm per task requirements:
            - Iterate PR files, find the matching file by path
            - Parse its unified diff patch (f.patch)
            - For each hunk @@ -a,b +c,d @@, track current new-file line starting at c
            - Count ONLY context (' ') and added ('+') lines toward position
            - When current new-file line equals the requested 'line', return the current position
            """
            try:
                files = list(pr.get_files())
            except Exception:
                return None

            target_file = None
            for f in files:
                try:
                    if getattr(f, "filename", None) == file_path:
                        target_file = f
                        break
                except Exception:
                    continue

            if target_file is None:
                return None

            patch = getattr(target_file, "patch", None)
            if not patch:
                # Binary or too large diffs may have no patch available
                return None

            pos = 0  # position within this file's patch (counting only ' ' and '+')
            new_line_cur = None  # current line number in the new file

            hunk_re = re.compile(r"^@@\s-\d+(?:,\d+)?\s\+(\d+)(?:,(\d+))?\s@@")

            for raw in patch.splitlines():
                if raw.startswith("@@"):
                    m = hunk_re.match(raw)
                    if not m:
                        new_line_cur = None
                        continue
                    try:
                        new_start = int(m.group(1))
                    except Exception:
                        new_start = None
                    new_line_cur = new_start
                    continue

                # Only count context and added lines toward position
                if raw.startswith(" "):
                    # context line exists in the new file
                    if new_line_cur is not None:
                        pos += 1
                        if new_line_cur == line:
                            return pos
                        new_line_cur += 1
                    continue
                if raw.startswith("+"):
                    # added line exists in the new file
                    if new_line_cur is not None:
                        pos += 1
                        if new_line_cur == line:
                            return pos
                        new_line_cur += 1
                    continue
                if raw.startswith("-"):
                    # removed line (does not exist in new file); do not count position, do not advance new_line_cur
                    continue
                # Any other line types are unexpected in patch; ignore

            return None

        review_position = _compute_review_position()

        # 6) Create review with inline comment using 'position' when possible; fallback to general PR comment
        if review_position is not None:
            try:
                # Create a single comment using the review comment endpoint
                pr.create_comment(
                    body=comment,
                    path=file_path,
                    position=int(review_position),
                    commit=pr.head.sha,
                )
                return (
                    f"Comment added to PR #{pr_number}, file {file_path}, line {line} (position {review_position})"
                )
            except Exception as e:
                # Fallback to general PR comment
                fallback_msg = f"File: {file_path}, line {line}\n\n{comment}\n\n(Failed to create inline comment: {str(e)})"
                pr.create_issue_comment(fallback_msg)
                return "Failed to create an inline comment. Added a general comment to the PR."
        else:
            # Fallback to general PR comment if position not found
            fallback_msg = f"File: {file_path}, line {line}\n\n{comment}\n\n(Diff position not found)"
            pr.create_issue_comment(fallback_msg)
            return "Could not determine a position for the inline comment. Added a general comment to the PR."

    return post_review_comment


def build_list_review_comments(config: dict[str, Any]):
    """Create a tool that lists all review comments for the current GitHub Pull Request.

    The tool reads GitHub Actions environment variables:
    - GITHUB_TOKEN: auth token
    - GITHUB_REPOSITORY: "owner/repo"
    - GITHUB_EVENT_PATH: path to the event JSON with pull_request.number

    Output JSON array format (one object per comment):
    [
      {
        "id": 123456,
        "file": "src/utils/helpers.js",
        "line": 42,
        "body": "...",
        "author": "octocat",
        "created_at": "2025-09-20T12:34:56Z"
      }
    ]
    """
    @tool("list_review_comments", return_direct=False)
    def list_review_comments(query: str = "") -> str:
        """
        Returns all review comments for the current PR as a JSON array.

        Args:
            query: Unused parameter, can be left empty.

        Returns:
            str: JSON array with fields id, file, line, body, author, created_at

        Security:
            - Only reads from the current repository and PR using GitHub Actions env
            - Requires GITHUB_TOKEN with appropriate permissions
        """
        # 1) Validate environment
        token = os.environ.get("GITHUB_TOKEN")
        repo_full = os.environ.get("GITHUB_REPOSITORY")
        event_path = os.environ.get("GITHUB_EVENT_PATH")

        missing = []
        if not token:
            missing.append("GITHUB_TOKEN")
        if not repo_full:
            missing.append("GITHUB_REPOSITORY")
        if not event_path:
            missing.append("GITHUB_EVENT_PATH")
        if missing:
            return (
                "Missing environment variables: " + ", ".join(missing) +
                ". The tool must be run inside GitHub Actions with a properly configured environment."
            )

        if not os.path.isfile(event_path):
            return f"GitHub Actions event file not found: {event_path}"

        # 2) Read event to get PR number
        try:
            with open(event_path, "r", encoding="utf-8") as f:
                event = json.load(f)
            pr_number = (
                event.get("pull_request", {}).get("number")
                or event.get("number")
            )
        except Exception as e:
            return f"Failed to read or parse GITHUB_EVENT_PATH: {e}"

        if not isinstance(pr_number, int):
            return "Failed to determine the PR number from GITHUB_EVENT_PATH (pull_request.number)."

        # 3) Connect to GitHub and list review comments
        try:
            gh = Github(login_or_token=token)
            repo = gh.get_repo(repo_full)
            pr = repo.get_pull(pr_number)
        except GithubException as e:
            return f"GitHub API error while fetching the repository or PR: {getattr(e, 'data', None) or str(e)}"
        except Exception as e:
            return f"Failed to initialize GitHub client: {e}"

        results = []
        try:
            # PyGithub returns a PaginatedList; iterate to handle pagination
            for c in pr.get_review_comments():
                # Prefer 'line', then 'original_line'. Fall back to position fields if not present.
                line = None
                # getattr with default None to avoid AttributeError across versions
                line = getattr(c, "line", None)
                if line is None:
                    line = getattr(c, "original_line", None)
                if line is None:
                    line = getattr(c, "position", None)
                if line is None:
                    line = getattr(c, "original_position", None)

                created = getattr(c, "created_at", None)
                created_iso = None
                if created is not None:
                    try:
                        # Ensure Zulu timezone if naive
                        created_iso = created.isoformat() + ("Z" if created.tzinfo is None else "")
                    except Exception:
                        created_iso = str(created)

                results.append({
                    "id": getattr(c, "id", None),
                    "file": getattr(c, "path", None),
                    "line": line,
                    "body": getattr(c, "body", None),
                    "author": getattr(getattr(c, "user", None), "login", None),
                    "created_at": created_iso,
                })
        except GithubException as e:
            return f"GitHub API error while fetching comments: {getattr(e, 'data', None) or str(e)}"
        except Exception as e:
            return f"Unknown error while fetching comments: {e}"

        try:
            return json.dumps(results, ensure_ascii=False)
        except Exception as e:
            return f"Failed to serialize result to JSON: {e}"

    return list_review_comments
