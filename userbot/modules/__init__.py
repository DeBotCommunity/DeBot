import glob
from os.path import basename, dirname, isfile


def __list_all_modules():
    """
    Return a list of all module names in the current directory.

    Returns:
        A list of strings representing the names of all modules in the current directory.
    """
    mod_paths = glob.glob(f"{dirname(__file__)}/*.py")
    return [
        basename(f)[:-3]
        for f in mod_paths
        if isfile(f) and f.endswith(".py") and not f.endswith("__init__.py")
    ]


ALL_MODULES = sorted(__list_all_modules())
__all__ = ALL_MODULES + ["ALL_MODULES"]
