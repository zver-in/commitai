from dataclasses import dataclass
from typing import List, Optional, Type, TypeVar, Callable, Any
import sys
import yaml
from functools import wraps

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from .config import load_system_prompt, load_tools_specs
from .tools.factory import ToolFactory

T = TypeVar('T')

def handle_error(
    error_message: str,
    error_type: Type[Exception] = Exception,
    exit_code: int = 1,
    print_traceback: bool = False,
    verbose: bool = False
) -> Callable:
    """Decorator to handle errors in a consistent way.
    
    Args:
        error_message: The error message to display
        error_type: The type of exception to catch
        exit_code: The exit code to return
        print_traceback: Whether to print the full traceback
        verbose: Whether to print additional debug information
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except error_type as e:
                print(f"Error: {error_message}: {str(e)}", file=sys.stderr)
                if print_traceback or verbose:
                    import traceback
                    traceback.print_exc()
                sys.exit(exit_code)
            except Exception as e:
                print(f"Unexpected error: {str(e)}", file=sys.stderr)
                if verbose:
                    import traceback
                    traceback.print_exc()
                sys.exit(exit_code)
        return wrapper
    return decorator

def validate_condition(
    condition: bool,
    error_message: str,
    exit_code: int = 1,
    verbose: bool = False
) -> None:
    """Validate a condition and exit with an error message if not met.
    
    Args:
        condition: The condition to check
        error_message: The error message to display if condition is False
        exit_code: The exit code to return if condition is False
        verbose: Whether to print additional debug information
    """
    if not condition:
        print(f"Error: {error_message}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_stack()
        sys.exit(exit_code)

def create_tool_safely(
    factory: ToolFactory,
    spec: dict,
    verbose: bool = False
) -> Optional[Any]:
    """Safely create a tool from a specification.
    
    Args:
        factory: The ToolFactory instance to use
        spec: The tool specification dictionary
        verbose: Whether to print additional debug information
        
    Returns:
        The created tool or None if creation failed
    """
    try:
        return factory.create(spec)
    except ValueError as ve:
        print(f"Validation error creating tool {spec.get('type', 'unknown')}: {str(ve)}", file=sys.stderr)
    except ImportError as ie:
        print(f"Dependency error creating tool {spec.get('type', 'unknown')}: {str(ie)}", file=sys.stderr)
    except Exception as e:
        print(f"Unexpected error creating tool {spec.get('type', 'unknown')}: {str(e)}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc()
    return None


@dataclass
class AgentConfig:
    """Configuration for running an agent.
    
    Attributes:
        model: The name of the OpenAI model to use (e.g., 'gpt-4o-mini')
        prompt_text: The input text prompt for the agent
        agent_config_path: Path to the YAML configuration file for the agent's tools
        verbose: If True, enables detailed logging of the agent's execution process.
        temperature: Controls randomness in the model's output (0.0 to 2.0).
                   Lower values make output more deterministic.
                   If None, uses default values (1.0 for gpt-5 models, 0.7 for others).
    """
    model: str
    prompt_text: str
    agent_config_path: str
    verbose: bool = False
    temperature: Optional[float] = None


@dataclass
class RunAgentParams:
    """Parameters for running an agent instance.
    
    Attributes:
        config: The agent configuration
        llm: The language model instance
        tools: List of tools available to the agent
        agent_prompt: The prompt template for the agent
    """
    config: AgentConfig
    llm: Any  # Using Any to avoid importing specific LLM types
    tools: List[Any]  # Using Any to avoid importing specific tool types
    agent_prompt: Any  # Using Any to avoid importing specific prompt types


def run_agent(config: AgentConfig) -> int:
    """Run a LangChain agent with tools defined via YAML specs (ToolFactory).
    
    Args:
        config: AgentConfig instance containing all configuration parameters.
    
    Returns:
        int: Exit code (0 for success, non-zero for errors)
    """
    # Set default temperature if not provided
    temperature = config.temperature or (1.0 if 'gpt-5' in config.model else 0.7)
    
    # Validate temperature range
    validate_condition(
        0.0 <= temperature <= 2.0,
        f"Temperature must be between 0.0 and 2.0, got {temperature}",
        verbose=config.verbose
    )
    
    # Initialize LLM with error handling
    try:
        llm = ChatOpenAI(model=config.model, temperature=temperature, streaming=False)
    except Exception as e:
        print(f"Error initializing ChatOpenAI: {str(e)}", file=sys.stderr)
        if config.verbose:
            import traceback
            traceback.print_exc()
        return 1
    
    # Build tools from structured YAML specs
    try:
        factory = ToolFactory()
        specs = load_tools_specs(config.agent_config_path)
        
        validate_condition(
            isinstance(specs, list),
            f"Expected a list of tool specifications, got {type(specs).__name__}",
            verbose=config.verbose
        )
        
        tools: List = []
        for spec in specs:
            if not isinstance(spec, dict):
                print(f"Warning: Tool specification must be a dictionary, got {type(spec).__name__}", file=sys.stderr)
                continue
                
            if not spec.get("type"):
                print(f"Warning: Tool specification missing required 'type' field: {spec}", file=sys.stderr)
                continue
                
            tool = create_tool_safely(factory, spec, config.verbose)
            if tool is not None:
                tools.append(tool)
            else:
                print(f"Warning: Failed to create tool from spec: {spec}", file=sys.stderr)
        
        validate_condition(
            bool(tools),
            "No valid tools were created from the configuration",
            verbose=config.verbose
        )
        
    except (FileNotFoundError, yaml.YAMLError) as e:
        error_type = "Configuration file not found" if isinstance(e, FileNotFoundError) else "Error parsing YAML"
        print(f"{error_type}: {str(e)}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error loading tool specifications: {str(e)}", file=sys.stderr)
        if config.verbose:
            import traceback
            traceback.print_exc()
        return 1

    system_prompt = load_system_prompt(config.agent_config_path)
    agent_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    params = RunAgentParams(config=config, llm=llm, tools=tools, agent_prompt=agent_prompt)
    return _run_agent(params)


def _run_agent(params: RunAgentParams) -> int:
    agent = create_openai_tools_agent(params.llm, params.tools, params.agent_prompt)
    
    # Configure executor with max iterations and better error handling
    executor = AgentExecutor(
        agent=agent, 
        tools=params.tools, 
        verbose=params.config.verbose,  # Default to False to avoid noisy callbacks
        max_iterations=10,  # Limit to prevent infinite loops
    )

    try:
        # Execute the agent with the provided prompt
        result = executor.invoke({"input": params.config.prompt_text})
        
        # Print the final output
        if result and "output" in result:
            print(result["output"])
            return 0
        else:
            print("Error: No output from agent", file=sys.stderr)
            return 1
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        print(f"Error executing agent: {str(e)}", file=sys.stderr)
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"API Response: {e.response.text}", file=sys.stderr)
        return 1
