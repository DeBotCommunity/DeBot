import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger: logging.Logger = logging.getLogger(__name__)

class TranslationManager:
    """
    Manages loading and retrieving translated strings from JSON files.
    """
    def __init__(self, locales_dir: str = "userbot/locales"):
        """
        Initializes the TranslationManager.

        Args:
            locales_dir (str): The base directory where locale files are stored.
        """
        self.locales_path: Path = Path(locales_dir)
        self.core_locales_path: Path = self.locales_path / "core"
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _load_locale_file(self, path: Path) -> Optional[Dict[str, Any]]:
        """
        Loads a specific JSON locale file into the cache if it exists.

        Args:
            path (Path): The full path to the JSON file.

        Returns:
            Optional[Dict[str, Any]]: The loaded locale data, or None if not found.
        """
        if str(path) in self._cache:
            return self._cache[str(path)]
        
        if not path.is_file():
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data: Dict[str, Any] = json.load(f)
                self._cache[str(path)] = data
                return data
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load or parse locale file {path}: {e}")
            return None

    def get_string(
        self,
        lang_code: str,
        key: str,
        module_name: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Retrieves a translated string, applying formatting.

        This method implements the fallback logic:
        1. Module-specific string in the requested language.
        2. Module-specific string in Russian (ru).
        3. Module-specific string in English (en).
        4. Core string in the requested language.
        5. Core string in Russian (ru).
        6. Core string in English (en).
        7. The key itself as a fallback.

        Args:
            lang_code (str): The desired language code (e.g., 'ru', 'en').
            key (str): The key of the string to retrieve.
            module_name (Optional[str]): The name of the module requesting the string.
            **kwargs: Keyword arguments for string formatting.

        Returns:
            str: The translated and formatted string.
        """
        string_val: Optional[str] = None
        
        # 1. Try module-specific locales
        if module_name:
            module_locales_path: Path = Path("userbot/modules") / module_name / "locales"
            # Try requested lang, then ru, then en for the module
            for lang in (lang_code, 'ru', 'en'):
                locale_data = self._load_locale_file(module_locales_path / f"{lang}.json")
                if locale_data and key in locale_data:
                    string_val = locale_data[key]
                    break
            if string_val:
                return string_val.format(**kwargs) if kwargs else string_val

        # 2. Try core locales
        for lang in (lang_code, 'ru', 'en'):
            core_locale_data = self._load_locale_file(self.core_locales_path / f"{lang}.json")
            if core_locale_data and key in core_locale_data:
                string_val = core_locale_data[key]
                break
        
        if string_val:
            return string_val.format(**kwargs) if kwargs else string_val

        # 3. Fallback
        logger.warning(f"Translation key '{key}' not found for lang '{lang_code}' (module: {module_name}).")
        return key

# Global instance
translator = TranslationManager()
