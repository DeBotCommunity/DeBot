# MODULE METADATA STANDARD:
# Modules should define an instance of the 'ModuleInfo' class from 'userbot.src.module_info'.
# This instance should be assigned to a variable named 'info' at the module level.
# Example in a module (e.g., my_module.py):
# from userbot.src.module_info import ModuleInfo
# info = ModuleInfo(
#     name="my_module", # Typically the module's file name without .py
#     category="tools", # e.g., "tools", "fun", "chat"
#     patterns=[".command1", ".command2"], # List of command patterns
#     descriptions=["Description for command1", "Description for command2"], # Corresponding descriptions
#     authors=["Your Name"], # Optional: list of author names
#     version="1.0" # Optional: module version string
# )
# # Your module's functions and handlers would follow
# async def command1_handler(event): ...

from typing import List, Optional

class ModuleInfo:
    def __init__(self,
                 name: str,
                 category: str,
                 patterns: List[str],
                 descriptions: List[str],
                 authors: Optional[List[str]] = None,
                 version: Optional[str] = None):
        if len(patterns) != len(descriptions):
            raise ValueError("The number of patterns must match the number of descriptions.")

        self.name: str = name
        self.category: str = category
        self.patterns: List[str] = patterns
        self.descriptions: List[str] = descriptions
        self.authors: Optional[List[str]] = authors
        self.version: Optional[str] = version

    def __repr__(self) -> str:
        return (f"ModuleInfo(name='{self.name}', category='{self.category}', "
                f"patterns={self.patterns}, descriptions={self.descriptions}, "
                f"authors={self.authors}, version='{self.version}')")
