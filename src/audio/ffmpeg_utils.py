import shutil
import tempfile
import subprocess
from typing import Optional

from src import config


def process_with_preset(input_path: str, preset_name: str) -> Optional[str]:
    """Process input_path with the named preset and return path to processed file.

    Returns None if ffmpeg is not available or processing fails.
    """
    if preset_name not in config.VOICE_PRESETS:
        return None
    if not shutil.which("ffmpeg"):
        return None

    ff_filter = config.VOICE_PRESETS[preset_name]
    if not ff_filter or (isinstance(ff_filter, str) and ff_filter.strip() == ""):
        # Explicitly no processing; callers should play the raw TTS file.
        return None
    processed = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    processed_name = processed.name
    processed.close()

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-af",
        ff_filter,
        processed_name,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return processed_name
    except subprocess.CalledProcessError:
        try:
            processed.close()
        except Exception:
            pass
        try:
            import os

            os.remove(processed_name)
        except Exception:
            pass
        return None
