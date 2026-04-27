import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

_transcriber = None


def _get_transcriber():
    """Lazily load Whisper pipeline from the local Bangla model directory."""
    global _transcriber
    if _transcriber is not None:
        return _transcriber

    model_path = Path(getattr(settings, 'WHISPER_BN_MODEL_PATH', ''))
    if not model_path.exists():
        raise FileNotFoundError(f"Whisper model directory not found: {model_path}")

    try:
        from transformers import pipeline
    except Exception as exc:
        raise RuntimeError(
            "transformers is required for Whisper STT. Install backend dependencies."
        ) from exc

    _transcriber = pipeline(
        task='automatic-speech-recognition',
        model=str(model_path),
        tokenizer=str(model_path),
        feature_extractor=str(model_path),
        device=-1,
    )
    return _transcriber


def transcribe_bangla_audio(audio_file) -> str:
    """Transcribe an uploaded audio file with the local Whisper-BN model."""
    transcriber = _get_transcriber()

    suffix = Path(audio_file.name or 'voice.webm').suffix or '.webm'
    temp_path = Path('/tmp') / f"sk_voice_{audio_file.size}_{id(audio_file)}{suffix}"

    with open(temp_path, 'wb') as handle:
        for chunk in audio_file.chunks():
            handle.write(chunk)

    try:
        result = transcriber(str(temp_path))
        text = (result or {}).get('text', '')
        return text.strip()
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Failed to cleanup temp audio file: %s", exc)
