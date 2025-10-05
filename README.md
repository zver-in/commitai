# CommitAI - Customizable AI Agent Framework

CommitAI is an open-source framework for creating and managing AI agents through simple YAML configurations. It allows you to build custom AI assistants with various tools for tasks like code reviews, issue triaging, documentation updates, and more.

## Key Features

- 🛠️ **Extensible Tool System**: Easily add new tools and capabilities to your agents
- ⚙️ **YAML-based Configuration**: Define complex agent behaviors without writing code
- 🤖 **Multiple Agent Types**: Create specialized agents for different tasks
- 🔄 **Git Integration**: Built-in tools for working with Git repositories
- 🐳 **Docker Support**: Run agents in containers for easy deployment
- 🔌 **OpenAI Integration**: Leverage powerful language models for intelligent task execution

## Quick Start

### Prerequisites
- Python 3.9+
- [Git](https://git-scm.com/)
- [Docker](https://www.docker.com/) (optional, for containerized execution)
- `OPENAI_API_KEY` environment variable with a valid OpenAI API key

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/commitai-v2.git
   cd commitai-v2
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set your OpenAI API key:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

## Installation
1) Install dependencies:
 
    ```bash
    pip install -r requirements.txt
    ```
 
2) Set your API key (macOS / Linux):
 
    ```bash
    export OPENAI_API_KEY="<your_api_key>"
    ```
 
   For Windows (PowerShell):
 
    ```powershell
    setx OPENAI_API_KEY "<your_api_key>"
    ```
 
   Optionally set a default model via `OPENAI_MODEL`.

## Docker

You can also run this project using Docker, which is especially useful for consistent environments across different systems.

### Prerequisites
- Docker installed on your system

### Building the Docker image

```bash
docker build -t commitai-v2 .
```

### Running the container

Basic usage:
```bash
docker run -it --rm \
  -e OPENAI_API_KEY=your_api_key_here \
  -v $(pwd)/agents:/app/agents \
  commitai-v2 --agent "/app/agents/assistant.yaml" "Your request here"
```

### Development with Docker

For development with live code changes:
```bash
docker run -it --rm \
  -e OPENAI_API_KEY=your_api_key_here \
  -v $(pwd):/app \
  -v /app/__pycache__ \
  commitai-v2 --agent "/app/agents/assistant.yaml" "Your request here"
```

### Environment Variables
- Mount your local `agents` directory to `/app/agents` to use your agent configurations
- Set `OPENAI_API_KEY` environment variable for API authentication
- Optionally set `OPENAI_MODEL` to specify a different model

## Creating Your First Agent

1. Create a new YAML file in the `agents/` directory, for example `my_agent.yaml`:

```yaml
id: my_agent
description: |
  A helpful AI assistant that can interact with files and Git repositories.

tools:
  - name: list_directory
    type: filesystem
    config:
      workdir: .
  - name: read_file
    type: filesystem
    config:
      workdir: .
  - name: git_diff
    type: git
    config:
      workdir: .
```

2. Run your agent:

```bash
python -m src.run_agent --agent "agents/my_agent.yaml" "Your request here"
```

## Example Use Cases

### Code Review Agent
Review pull requests and suggest improvements:
```bash
python -m src.run_agent --agent "agents/code_reviewer.yaml" "Review the latest changes in the pull request"
```

### Documentation Assistant
Help keep documentation up to date:
```bash
python -m src.run_agent --agent "agents/documentation_assistant.yaml" "Update README with latest features"
```

### Issue Triage Assistant
Help manage and prioritize GitHub issues:
```bash
python -m src.run_agent --agent "agents/issue_triage.yaml" "Categorize and prioritize new issues"
```
 
## Environment Variables
- `OPENAI_API_KEY` — required
- `OPENAI_MODEL` — optional (default: `gpt-4o-mini`)

Note: The `--agent` must point to a YAML file that exists at the specified path. Prefer an absolute path or `$PWD/agents/<file>.yaml` so CI and scripts resolve the file correctly.

## Troubleshooting
- If you see an error that `openai` is not installed, ensure you ran `pip install -r requirements.txt`.
- If you get an authorization error, verify `OPENAI_API_KEY` is set in your current terminal session.

## Project Structure

```
.
├── agents/                  # YAML configuration files for different agents
├── src/
│   ├── tools/              # Tool implementations
│   │   ├── factory.py      # Tool factory for creating tool instances
│   │   ├── filesystem.py   # Filesystem operations
│   │   └── git.py          # Git operations
│   ├── agent.py            # Core agent implementation
│   ├── config.py           # Configuration loading and helpers
│   └── run_agent.py        # CLI entry point
├── .github/workflows/      # GitHub Actions workflows
├── Dockerfile              # Container configuration
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## Available Tools

### Filesystem Tools
- `list_directory` - List contents of a directory
- `read_file` - Read file contents with support for line ranges and size limits
- `write_file` - Write to a file
- `view_file` - View file contents with syntax highlighting
- `search_in_files` - Search for text within files under a given directory

### Git Tools

#### Basic Git Operations
- `git_changed_files` - List files with uncommitted changes in the working directory
- `git_diff` - Show uncommitted changes in the working directory
- `git_pr_diff` - Show changes between the current branch and a base branch (typically 'main' or 'master')
- `git_pr_changed_files` - List files changed in a pull request compared to the base branch

#### GitHub Code Review Tools
- `post_review_comment` - Post a code review comment to a GitHub Pull Request
- `list_review_comments` - List all review comments for the current Pull Request

#### Planned Features
We're actively working on expanding our Git toolset. Here are some of the features we plan to add:
- Branch management (create, switch, delete)
- Commit operations (commit, amend, revert)
- Remote repository interactions (push, pull, fetch)
- Tag management
- Stash operations

Stay tuned for updates as we continue to enhance our Git integration!

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details on how to get started.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with ❤️ by the CommitAI team
- Special thanks to all our contributors

## Support

For support, please open an issue in the GitHub repository.

## Agent capabilities
The script runs a LangChain agent using tools defined in the selected YAML file (e.g., `./agents/code_reviewer.yaml`). The agent configuration is loaded from the YAML file at the path you pass via `--agent`, so the path must be correct and the file must exist.

Examples:

```bash
python -m src.run_agent --agent "$PWD/agents/code_reviewer.yaml" "List files in the prompts/ directory"
```

```bash
python -m src.run_agent --agent "$PWD/agents/code_reviewer.yaml" "List files in the src directory"
```

Dependencies for the agent mode (`langchain`, `langchain-openai`) are in `requirements.txt`. If you installed dependencies earlier, re-run installation to ensure everything is up to date:

```bash
pip install -r requirements.txt