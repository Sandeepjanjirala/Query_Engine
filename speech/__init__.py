"""
speech package
Local, free speech-to-text integration using faster-whisper.
"""

from .transcriber import WhisperTranscriber, get_transcriber, transcribe_audio
from .normalizer import normalize_speech_transcript
from .vocabulary import build_initial_prompt, get_dataset_entities, BASE_DOMAINS

__all__ = [
    'WhisperTranscriber',
    'get_transcriber',
    'transcribe_audio',
    'normalize_speech_transcript',
    'build_initial_prompt',
    'get_dataset_entities',
    'BASE_DOMAINS',
]
