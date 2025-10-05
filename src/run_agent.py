#!/usr/bin/env python3
"""
A simple CLI that sends your request to an OpenAI model and lets the AI call tools
(e.g., to list files in a directory) configured via an agent YAML file.

Examples:
  python -m src.run_agent --agent "$PWD/agents/assistant.yaml" "Hello, how are you?"
  python -m src.run_agent --agent "$PWD/agents/code_reviewer.yaml" --verbose "Debug this code"

Requires the OPENAI_API_KEY environment variable.

Options:
  --verbose  Enable detailed logging of the agent's execution process.
             Useful for debugging and understanding the agent's decision-making.
             Outputs additional information about the agent's thought process.
"""
import os
import sys
import yaml
import argparse
from typing import Optional, Tuple

from .agent import run_agent, AgentConfig
from .config import load_system_prompt


DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def read_input_text(arg_text: Optional[str]) -> str:
    if arg_text is not None and arg_text.strip():
        return arg_text
    if not sys.stdin.isatty():
        data = sys.stdin.read()
        if data.strip():
            return data.strip()
    print("Error: provide input text as an argument or via stdin.", file=sys.stderr)
    sys.exit(2)


## main only keeps CLI and delegates to agent


def validate_agent_yaml(agent_yaml: str) -> tuple[bool, str]:
    """Validate the agent YAML file exists and is properly formatted."""
    if not os.path.isfile(agent_yaml):
        return False, f"Agent file not found: {agent_yaml}"
    
    try:
        # Check if the file is a valid YAML and contains required fields
        with open(agent_yaml, 'r') as f:
            config = yaml.safe_load(f)
            
        if not isinstance(config, dict):
            return False, f"Agent configuration must be a YAML dictionary, got {type(config).__name__}"
            
        # Check for required top-level fields
        required_fields = ['description', 'tools']
        for field in required_fields:
            if field not in config:
                return False, f"Missing required field in agent config: {field}"
                
        # Basic validation of tools list
        if not isinstance(config.get('tools'), list):
            return False, "'tools' field must be a list of tool configurations"
            
        return True, ""
        
    except yaml.YAMLError as e:
        return False, f"Invalid YAML in agent configuration: {str(e)}"
    except Exception as e:
        return False, f"Error validating agent configuration: {str(e)}"

def validate_model(model_name: str) -> tuple[bool, str]:
    """Validate that the model name is in the expected format."""
    # This is a basic check - adjust according to your model naming conventions
    if not isinstance(model_name, str) or not model_name.strip():
        return False, "Model name must be a non-empty string"
    
    # Add any specific model name validation here
    return True, ""

def main() -> int:
    # Validate environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not api_key.strip():
        print("Error: Environment variable OPENAI_API_KEY is not set or empty.", file=sys.stderr)
        return 2

    # Set up argument parser with more detailed help
    parser = argparse.ArgumentParser(
        description="Send text to an OpenAI model with tool support.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "text", 
        nargs="?", 
        help="Input text to process. If omitted, reads from stdin."
    )
    
    parser.add_argument(
        "--model", 
        default=DEFAULT_MODEL, 
        help=f"OpenAI model to use (default: {DEFAULT_MODEL})"
    )
    
    parser.add_argument(
        "--agent", 
        required=True, 
        help="Full, explicit path (not just a name) to the agent YAML file (e.g., $PWD/agents/assistant.yaml or an absolute path). The file must exist."
    )
    
    parser.add_argument(
        "--temperature", 
        type=float, 
        default=None,
        help="Controls randomness (0.0 to 2.0). Lower is more deterministic. If not set, uses model defaults."
    )
    
    parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Enable detailed logging for debugging"
    )
    
    args = parser.parse_args()

    # Validate model name
    is_valid, error_msg = validate_model(args.model)
    if not is_valid:
        print(f"Error: {error_msg}", file=sys.stderr)
        return 2
    
    # Validate temperature if provided
    if args.temperature is not None and not (0.0 <= args.temperature <= 2.0):
        print(f"Error: Temperature must be between 0.0 and 2.0, got {args.temperature}", file=sys.stderr)
        return 2

    # Read and validate input text
    prompt = read_input_text(args.text)
    if not prompt.strip():
        print("Error: Input text cannot be empty", file=sys.stderr)
        return 2

    # Resolve agent configuration path (must be an explicit existing file)
    agent_yaml = args.agent.strip()

    # Validate agent configuration
    is_valid, error_msg = validate_agent_yaml(agent_yaml)
    if not is_valid:
        print(f"Agent configuration error: {error_msg}", file=sys.stderr)
        return 2

    # Preflight check: ensure system prompt exists and is non-empty
    try:
        system_prompt = load_system_prompt(agent_yaml)
        if not system_prompt or not system_prompt.strip():
            print("Error: System prompt in agent configuration is empty", file=sys.stderr)
            return 2
    except Exception as e:
        print(f"Error loading agent configuration: {str(e)}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2

    # Create agent configuration
    agent_config = AgentConfig(
        model=args.model,
        prompt_text=prompt,
        agent_config_path=agent_yaml,
        verbose=args.verbose,
        temperature=args.temperature,
    )
    
    # Run the agent with the provided configuration
    try:
        return run_agent(agent_config)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 12


if __name__ == "__main__":
    raise SystemExit(main())
