from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from deep_translator import GoogleTranslator

CACHE_SIZE = 50

# Normalize language codes to what deep-translator expects
_LANG_NORMALIZE = {
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
}


def _normalize(lang: str) -> str:
    return _LANG_NORMALIZE.get(lang.lower(), lang)


class Translator:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._cache: OrderedDict = OrderedDict()

    def translate(self, text: str, source_lang: str = "auto", target_lang: str = "vi") -> str:
        if not text.strip():
            return ""

        src = _normalize(source_lang)
        tgt = _normalize(target_lang)

        # No-op if source == target
        if src != "auto" and src == tgt:
            return text

        cache_key = (text, src, tgt)
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        try:
            result = GoogleTranslator(source=src, target=tgt).translate(text)
            self._cache[cache_key] = result
            if len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
            return result
        except Exception:
            return f"{text} (translation unavailable)"

    def translate_async(self, text: str, source_lang: str, target_lang: str, callback):
        """Submit translation to thread pool; calls callback(result) when done."""
        future = self._executor.submit(self.translate, text, source_lang, target_lang)
        future.add_done_callback(lambda f: callback(f.result()))

    def shutdown(self):
        self._executor.shutdown(wait=False)
