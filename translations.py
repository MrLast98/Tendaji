import json
import os
import defaults

TRANSLATION_FOLDER = "translations"


def is_string_valid(string):
    return string and string is not None and string != ""


class TranslationManager:
    def __init__(self, manager):
        self.manager = manager
        self.translations = {}
        self.manager = self.manager.configuration.get("app", {})
        self.default_language = "en"
        if not os.path.exists("translations"):
            os.mkdir("translations")
        self.load_translations()

    def load_translations(self):
        file_list = os.listdir(TRANSLATION_FOLDER)
        if len(file_list) > 0:
            for filename in os.listdir(TRANSLATION_FOLDER):
                if filename.endswith(".json"):
                    language_code = os.path.splitext(filename)[0]
                    with open(os.path.join(TRANSLATION_FOLDER, filename), "r") as file:
                        self.translations[language_code] = json.load(file)
        else:
            self.translations["en"] = defaults.EN_DEFAULTS
            with open(os.path.join(TRANSLATION_FOLDER, "en.json"), "w", encoding="utf-8") as file:
                file.write(json.dumps(self.translations["en"]))

    def get_language(self):
        return self.manager.get("selected_languages") if is_string_valid(
            self.manager.get("selected_languages")) else self.default_language

    def get_translation(self, key, language=None):
        language = language if is_string_valid(language) else self.get_language()
        translation = self.translations.get(language, {})
        return translation.get(key, f"No translation found for key '{key}' in language '{language}'")

    def get_dictionary(self, key, language=None):
        language = language if is_string_valid(language) else self.get_language()
        dictionary = self.translations.get(language, {}).get("dictionary", {})
        return dictionary.get(key, f"No dictionary item found for key '{key}' in language '{language}'")

    def get_errors(self, section, key, language=None):
        language = language if is_string_valid(language) else self.get_language()
        errors = self.translations.get(language, {})["errors"][section]
        return errors.get(key, f"No dictionary item found for key '{key}' in language '{language}'")
