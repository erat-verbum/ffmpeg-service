"""
OCR module for converting bitmap subtitles to SRT format.

Uses subtile-ocr with Tesseract OCR engine.
"""

import asyncio
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

INSTALLED_TESSERACT_LANGUAGES: frozenset[str] = frozenset(
    {
        "eng",
        "fra",
        "spa",
        "ger",
        "ita",
    }
)

ISO_TO_TESSERACT: dict[str, str] = {
    "eng": "eng",
    "fra": "fra",
    "fre": "fra",
    "deu": "ger",
    "spa": "spa",
    "ita": "ita",
    "por": "por",
    "rus": "rus",
    "jpn": "jpn",
    "kor": "kor",
    "chi": "chi_sim",
    "zho": "chi_sim",
    "chi_sim": "chi_sim",
    "chi_tra": "chi_tra",
    "dut": "dut",
    "nld": "dut",
    "dan": "dan",
    "swe": "swe",
    "nor": "nor",
    "fin": "fin",
    "pol": "pol",
    "ces": "ces",
    "cze": "ces",
    "hun": "hun",
    "gre": "gre",
    "ell": "gre",
    "tur": "tur",
    "ara": "ara",
    "heb": "heb",
    "tha": "tha",
    "vie": "vie",
    "hin": "hin",
    "ben": "ben",
    "tam": "tam",
    "tel": "tel",
    "kan": "kan",
    "mal": "mal",
    "mar": "mar",
    "guj": "guj",
}


def get_tesseract_language(iso_code: Optional[str]) -> Optional[str]:
    """
    Convert ISO 639-2 language code to Tesseract language code.

    Args:
        iso_code: ISO 639-2 language code (e.g., 'eng', 'fra', 'deu')

    Returns:
        Tesseract language code, or None if language is not supported or not installed
    """
    if not iso_code:
        return None
    tesseract_code = ISO_TO_TESSERACT.get(iso_code.lower())
    if tesseract_code and tesseract_code in INSTALLED_TESSERACT_LANGUAGES:
        return tesseract_code
    return None


def convert_subtitle_sync(
    subtitle_path: Path,
    output_path: Path,
    language: str,
) -> tuple[bool, str]:
    """
    Synchronously convert bitmap subtitle to SRT using subtile-ocr CLI.

    Args:
        subtitle_path: Path to input .sub or .sup file
        output_path: Path for output .srt file
        language: Tesseract language code

    Returns:
        Tuple of (success: bool, error_message: str)
    """
    try:
        result = subprocess.run(
            ["subtile-ocr", "-l", language, "-o", str(output_path), str(subtitle_path)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0 and output_path.exists():
            if output_path.stat().st_size > 0:
                return (True, "")
            output_path.unlink()
            return (False, "OCR produced empty output")
        return (False, result.stderr or "Unknown error")
    except subprocess.TimeoutExpired:
        return (False, "OCR process timed out")
    except FileNotFoundError:
        return (False, "subtile-ocr not found")
    except Exception as e:
        return (False, str(e))


async def convert_bitmap_subtitle_to_srt(
    subtitle_path: Path,
    output_path: Path,
    language: str,
) -> bool:
    """
    Convert bitmap subtitle to SRT using subtile-ocr.

    Args:
        subtitle_path: Path to input .sub or .sup file
        output_path: Path for output .srt file
        language: Tesseract language code

    Returns:
        True if conversion successful, False otherwise
    """
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        success, error = await loop.run_in_executor(
            executor,
            convert_subtitle_sync,
            subtitle_path,
            output_path,
            language,
        )
    if not success:
        logger.warning(f"OCR failed for {subtitle_path}: {error}")
    return success
