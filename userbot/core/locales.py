import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import aiohttp

logger: logging.Logger = logging.getLogger(__name__)

# This is the base URL for official language packs.
# The user needs to create this repository.
OFFICIAL_LOCALES_REPO_URL: str = "https://raw.githubusercontent.com/DeBotCommunity/locales/main/{lang_code}.json"

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
        self.core_locales_path.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Dict[str, Any]] = {}

    async def load_language_pack(self, identifier: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Downloads and saves a language pack from a URL or an official repository.

        Args:
            identifier (str): A 2-letter language code or a full URL to a raw JSON file.

        Returns:
            A tuple containing (lang_code, error_message).
            `lang_code` is the determined language code if successful, otherwise None.
            `error_message` is a string describing the error if failed, otherwise None.
        """
        url: str
        lang_code: str

        if identifier.startswith("http"):
            url = identifier
            try:
                # Extract file name from URL, e.g., ".../neko-lang.json" -> "neko-lang"
                lang_code = Path(url.split('/')[-1]).stem
            except Exception:
                return None, "Invalid URL format."
        else:
            lang_code = identifier.lower()
            if not (2 <= len(lang_code) <= 10 and lang_code.isalnum()):
                 return None, "Invalid language code format."
            url = OFFICIAL_LOCALES_REPO_URL.format(lang_code=lang_code)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return None, f"Could not fetch language file (Status: {response.status})."
                    
                    content: str = await response.text()
                    # Validate that it's valid JSON
                    json.loads(content) 

            file_path: Path = self.core_locales_path / f"{lang_code}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Clear cache for this file if it exists
            self._cache.pop(str(file_path), None)

            return lang_code, None
        except aiohttp.ClientError:
            return None, "Network error while downloading language pack."
        except json.JSONDecodeError:
            return None, "Downloaded file is not valid JSON."
        except Exception as e:
            logger.error(f"Unexpected error loading language pack '{identifier}': {e}", exc_info=True)
            return None, "An unexpected error occurred."

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
        
        if module_name:
            module_locales_path: Path = Path(f"userbot/modules/{module_name}/locales")
            for lang in (lang_code, 'ru', 'en'):
                locale_data = self._load_locale_file(module_locales_path / f"{lang}.json")
                if locale_data and key in locale_data:
                    string_val = locale_data[key]
                    break
            if string_val:
                return string_val.format(**kwargs) if kwargs else string_val

        for lang in (lang_code, 'ru', 'en'):
            core_locale_data = self._load_locale_file(self.core_locales_path / f"{lang}.json")
            if core_locale_data and key in core_locale_data:
                string_val = core_locale_data[key]
                break
        
        if string_val:
            return string_val.format(**kwargs) if kwargs else string_val

        logger.warning(f"Translation key '{key}' not found for lang '{lang_code}' (module: {module_name}).")
        return key

# Global instance
translator = TranslationManager()
