import ast
import logging
from typing import Dict, List, Any, Optional, Tuple

logger: logging.Logger = logging.getLogger(__name__)

class ModuleParser(ast.NodeVisitor):
    """
    An AST visitor to parse metadata from a Python module's source code.
    """
    def __init__(self) -> None:
        """Initializes the parser's result storage."""
        self.metadata: Dict[str, Any] = {
            "requires": [],
            "trusted": False,
            "config": {},
            "info": None,
        }

    def visit_Assign(self, node: ast.Assign) -> None:
        """
        Visits an assignment node to extract metadata variables.

        Args:
            node (ast.Assign): The AST assignment node.
        """
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name: str = node.targets[0].id
            if name in ["__requires__", "__trusted__", "__config__", "info"]:
                try:
                    value: Any = ast.literal_eval(node.value)
                    self.metadata[name.strip('_')] = value
                except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                    logger.warning(f"Could not evaluate value for '{name}' in module. Skipping.")
        self.generic_visit(node)


def parse_module_metadata(source_code: str) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Parses a module's source code to extract metadata.

    Args:
        source_code (str): The Python source code of the module.

    Returns:
        Tuple[Dict[str, Any], Optional[str]]: A tuple containing the extracted
            metadata dictionary and an error message string if validation fails,
            otherwise None for the error.
    """
    try:
        tree: ast.AST = ast.parse(source_code)
        parser: ModuleParser = ModuleParser()
        parser.visit(tree)
        metadata: Dict[str, Any] = parser.metadata

        # --- Validation ---
        # Validate __config__ and info relationship
        config: Optional[Dict] = metadata.get("config")
        info: Optional[Dict] = metadata.get("info") # from literal_eval
        
        if isinstance(config, dict) and config:
            if not isinstance(info, dict) or 'descriptions' not in info or not isinstance(info['descriptions'], list):
                return metadata, "Module has '__config__' but 'info' with 'descriptions' list is missing or invalid."
            
            all_descriptions_text: str = " ".join(map(str, info['descriptions']))
            for key in config.keys():
                if key not in all_descriptions_text:
                    return metadata, f"Configuration key '{key}' from '__config__' is not described in info.descriptions."
        
        return metadata, None

    except SyntaxError as e:
        logger.error(f"Failed to parse module due to syntax error: {e}")
        return {}, f"Syntax error in module code: {e}"
    except Exception as e:
        logger.error(f"An unexpected error occurred during module parsing: {e}")
        return {}, f"Unexpected error during parsing: {e}"
