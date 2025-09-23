import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import aiohttp

logger: logging.Logger = logging.getLogger(__name__)

# This is the base URL for official language packs.
OFFICIAL_LOCALES_REPO_URL: str = "https://raw.githubusercontent.com/DeBotCommunity/locales/main/{lang_code}.json"
GITHUB_API_OWNER: str = "DeBotCommunity"
GITHUB_API_REPO: str = "locales"

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
        """Downloads a language pack if the remote version is newer, or loads it.

        Checks the last commit date of the language file in the official GitHub
        repository against the local file's modification time. If the remote
        file is newer or the local file does not exist, it's downloaded.
        If the check fails, it falls back to using the local file if available.
        If a full URL is provided as an identifier, it's downloaded directly.

        Args:
            identifier (str): A 2-letter language code (e.g., 'en') or a full URL
                              to a raw JSON file.

        Returns:
            A tuple containing (lang_code, error_message).
            `lang_code` is the determined language code if successful, otherwise None.
            `error_message` is a string describing the error if failed, otherwise None.
        """
        # --- Direct URL Handling ---
        if identifier.startswith("http"):
            try:
                lang_code: str = Path(identifier.split('/')[-1]).stem
                async with aiohttp.ClientSession() as session:
                    async with session.get(identifier) as response:
                        if response.status != 200:
                            return None, f"Could not fetch from URL (Status: {response.status})."
                        content: str = await response.text()
                        json.loads(content)
                file_path: Path = self.core_locales_path / f"{lang_code}.json"
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self._cache.pop(str(file_path), None)
                return lang_code, None
            except Exception as e:
                logger.error(f"Failed to process URL language pack '{identifier}': {e}", exc_info=True)
                return None, "Invalid URL or content."

        # --- Language Code Handling with Update Check ---
        lang_code = identifier.lower()
        if not (2 <= len(lang_code) <= 10 and lang_code.isalnum()):
            return None, "Invalid language code format."

        local_path: Path = self.core_locales_path / f"{lang_code}.json"
        raw_url: str = OFFICIAL_LOCALES_REPO_URL.format(lang_code=lang_code)
        
        try:
            api_url: str = f"https://api.github.com/repos/{GITHUB_API_OWNER}/{GITHUB_API_REPO}/commits"
            params: Dict[str, str] = {"path": f"{lang_code}.json", "page": "1", "per_page": "1"}

            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, params=params) as response:
                    response_json: Any = await response.json()
                    if response.status != 200 or not isinstance(response_json, list) or not response_json:
                        if local_path.is_file():
                            logger.warning(f"Could not check for '{lang_code}' updates. Using local version.")
                            return lang_code, None
                        return None, f"Language '{lang_code}' not in remote repo and no local copy."
                    
                    commit_date_str: str = response_json[0]['commit']['committer']['date']
                    remote_mtime: datetime = datetime.fromisoformat(commit_date_str.replace('Z', '+00:00'))

                    should_download: bool = False
                    if not local_path.is_file():
                        should_download = True
                        logger.info(f"Local file for '{lang_code}' not found. Downloading.")
                    else:
                        local_mtime_ts: float = local_path.stat().st_mtime
                        local_mtime: datetime = datetime.fromtimestamp(local_mtime_ts, tz=timezone.utc)
                        if remote_mtime > local_mtime:
                            should_download = True
                            logger.info(f"Remote file for '{lang_code}' is newer. Downloading update.")
                        else:
                            logger.info(f"Local file for '{lang_code}' is up-to-date.")

                    if should_download:
                        async with session.get(raw_url) as raw_response:
                            if raw_response.status != 200:
                                raise aiohttp.ClientError(f"Failed to download raw file, status: {raw_response.status}")
                            content = await raw_response.text()
                            json.loads(content)
                            with open(local_path, 'w', encoding='utf-8') as f:
                                f.write(content)
                            os.utime(local_path, (remote_mtime.timestamp(), remote_mtime.timestamp()))
                            self._cache.pop(str(local_path), None)
                            logger.info(f"Successfully downloaded and updated '{lang_code}'.")

        except aiohttp.ClientError as e:
            logger.warning(f"Network error checking for '{lang_code}' updates: {e}. Using local version as fallback.")
            if not local_path.is_file():
                return None, "Network error and no local copy available."
        except Exception as e:
            logger.error(f"Unexpected error updating language pack '{identifier}': {e}", exc_info=True)
            if not local_path.is_file():
                return None, "Unexpected error and no local copy available."
        
        return lang_code, None

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
        language: str,
        key: str,
        module_name: Optional[str] = None,
        **kwargs
    ) -> str:
        """Retrieves a translated string, applying formatting.

        This method implements the fallback logic:
        1. Module-specific string in the requested language.
        2. Module-specific string in Russian (ru).
        3. Module-specific string in English (en).
        4. Core string in the requested language.
        5. Core string in Russian (ru).
        6. Core string in English (en).
        7. The key itself as a fallback.

        Args:
            language (str): The desired language code (e.g., 'ru', 'en') for the lookup.
            key (str): The key of the string to retrieve.
            module_name (Optional[str]): The name of the module requesting the string.
            **kwargs: Keyword arguments for string formatting.

        Returns:
            str: The translated and formatted string.
        """
        string_val: Optional[str] = None
        
        if module_name:
            module_locales_path: Path = Path(f"userbot/modules/{module_name}/locales")
            for lang in (language, 'ru', 'en'):
                locale_data = self._load_locale_file(module_locales_path / f"{lang}.json")
                if locale_data and key in locale_data:
                    string_val = locale_data[key]
                    break
            if string_val:
                return string_val.format(**kwargs) if kwargs else string_val

        for lang in (language, 'ru', 'en'):
            core_locale_data = self._load_locale_file(self.core_locales_path / f"{lang}.json")
            if core_locale_data and key in core_locale_data:
                string_val = core_locale_data[key]
                break
        
        if string_val:
            return string_val.format(**kwargs) if kwargs else string_val

        logger.warning(f"Translation key '{key}' not found for lang '{language}' (module: {module_name}).")
        return key

# Global instance
translator = TranslationManager()
