import tempfile
import os
import time
from typing import Optional

from gtts import gTTS


def save_tts_with_retries(tts_obj: gTTS, filename: str, attempts: int = 3, backoff: float = 1.0) -> None:
    last_exc = None
    for i in range(attempts):
        try:
            tts_obj.save(filename)
            return
        except Exception as e:
            last_exc = e
            time.sleep(backoff * (2 ** i))
    raise last_exc


def generate_tts(text: str, lang: str = "es") -> str:
    """Generate TTS audio for the given text and return the path to a temporary mp3 file.

    Caller is responsible for removing the file when done.
    """
    tts = gTTS(text, lang=lang)
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_name = tmp.name
    tmp.close()
    save_tts_with_retries(tts, tmp_name)
    return tmp_name
