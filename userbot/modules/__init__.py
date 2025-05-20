import glob
import os # Added os for os.path.join and normpath
from os.path import basename, dirname, isfile

# Old filesystem scanning logic is removed.
# ALL_MODULES and __all__ are removed as they are not suitable for DB-driven loading.

def scan_filesystem_for_modules(modules_dir: str = None) -> list:
    """
    Scans the specified directory (or the directory of this file if None) for Python modules.
    It does not import them.

    Args:
        modules_dir (str, optional): The directory to scan. Defaults to the directory
                                     containing this __init__.py file.

    Returns:
        A list of dictionaries, where each dictionary contains:
        - 'name': The module name (filename without .py).
        - 'path': The full, normalized path to the module file.
    """
    if modules_dir is None:
        modules_dir = dirname(__file__)
    
    found_modules = []
    # Scan for .py files in the modules_dir (not recursively for now)
    for filepath in glob.glob(os.path.join(modules_dir, "*.py")):
        if isfile(filepath) and not filepath.endswith("__init__.py"):
            module_name = basename(filepath)[:-3]
            normalized_path = os.path.normpath(filepath) # Normalize path separators
            found_modules.append({"name": module_name, "path": normalized_path})
            
    return found_modules

# Example usage (can be removed or kept for testing this function):
if __name__ == '__main__':
    # This part will only run if you execute this __init__.py file directly
    print("Scanning for modules in the local directory...")
    local_modules = scan_filesystem_for_modules()
    if local_modules:
        for mod_info in local_modules:
            print(f"  Found: {mod_info['name']} at {mod_info['path']}")
    else:
        print("  No modules found.")
