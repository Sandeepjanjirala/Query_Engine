"""
speech/transcriber.py

Provides thread-safe singleton faster-whisper model management and local audio transcription.
Models are loaded once and reused across all requests.
"""

import os
import time
import logging
import tempfile
import threading
from typing import Optional, Tuple, BinaryIO, Union

import ctranslate2
from django.conf import settings

from .vocabulary import build_initial_prompt
from .normalizer import normalize_speech_transcript

logger = logging.getLogger(__name__)


class WhisperTranscriber:
    """
    Singleton transcriber wrapping faster-whisper.
    Thread-safe lazy initialization ensures the model is loaded only once.
    """
    _instance: Optional['WhisperTranscriber'] = None
    _lock = threading.Lock()

    def __init__(self):
        self.model_name = getattr(settings, 'WHISPER_MODEL', 'small')
        self.device = getattr(settings, 'WHISPER_DEVICE', 'auto')
        self.compute_type = getattr(settings, 'WHISPER_COMPUTE_TYPE', 'auto')
        self.download_root = getattr(settings, 'WHISPER_DOWNLOAD_ROOT', None)
        self.cpu_threads = getattr(settings, 'WHISPER_CPU_THREADS', 4)
        self.beam_size = getattr(settings, 'WHISPER_BEAM_SIZE', 1)

        # Resolve device & compute type safely
        if self.device == 'auto':
            try:
                has_cuda = ctranslate2.get_cuda_device_count() > 0
            except Exception:
                has_cuda = False
            self.device = 'cuda' if has_cuda else 'cpu'

        if self.compute_type == 'auto':
            if self.device == 'cuda':
                self.compute_type = 'float16'
            else:
                self.compute_type = 'int8'

        self._model = None
        self._load_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> 'WhisperTranscriber':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _ensure_model_loaded(self):
        if self._model is None:
            with self._load_lock:
                if self._model is None:
                    from faster_whisper import WhisperModel
                    logger.info(
                        f"Loading Whisper model '{self.model_name}' on device='{self.device}', "
                        f"compute_type='{self.compute_type}', cpu_threads={self.cpu_threads}..."
                    )
                    t0 = time.time()
                    try:
                        self._model = WhisperModel(
                            self.model_name,
                            device=self.device,
                            compute_type=self.compute_type,
                            cpu_threads=self.cpu_threads,
                            download_root=self.download_root,
                        )
                    except Exception as exc:
                        # If GPU fails or model fails, try fallback to cpu + int8
                        if self.device != 'cpu':
                            logger.warning(f"Failed to load on {self.device}: {exc}. Falling back to CPU.")
                            self.device = 'cpu'
                            self.compute_type = 'int8'
                            self._model = WhisperModel(
                                self.model_name,
                                device='cpu',
                                compute_type='int8',
                                cpu_threads=self.cpu_threads,
                                download_root=self.download_root,
                            )
                        else:
                            raise
                    load_time = time.time() - t0
                    logger.info(f"Whisper model '{self.model_name}' loaded in {load_time:.2f}s.")

    def transcribe(
        self,
        audio_source: Union[str, BinaryIO, bytes],
        file_extension: str = '.webm',
        language: str = 'en',
    ) -> Tuple[str, str, float]:
        """
        Transcribes the given audio input and returns:
        (raw_transcript, normalized_transcript, duration_seconds)

        Parameters:
        - audio_source: filepath (str), file-like object, or raw bytes.
        - file_extension: container extension (e.g. '.webm', '.wav', '.mp4').
        - language: language hint ('en' for Indian English analytics queries).
        """
        self._ensure_model_loaded()

        temp_path = None
        if isinstance(audio_source, str) and os.path.exists(audio_source):
            target_path = audio_source
        else:
            # Write bytes or file-like object to a temporary file for PyAV
            suffix = file_extension if file_extension.startswith('.') else f'.{file_extension}'
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                temp_path = tmp.name
                if isinstance(audio_source, bytes):
                    tmp.write(audio_source)
                elif hasattr(audio_source, 'read'):
                    audio_source.seek(0)
                    tmp.write(audio_source.read())
            target_path = temp_path

        try:
            initial_prompt = build_initial_prompt()
            t0 = time.time()
            transcribe_kwargs = dict(
                language=language,
                initial_prompt=initial_prompt,
                beam_size=self.beam_size,
                temperature=0.0,
                condition_on_previous_text=False,
                repetition_penalty=1.2,
                no_repeat_ngram_size=3,
            )

            # Pass 1: Try with Silero VAD (with relaxed threshold and generous speech padding)
            segments, info = self._model.transcribe(
                target_path,
                vad_filter=True,
                vad_parameters=dict(threshold=0.2, min_silence_duration_ms=600, speech_pad_ms=400),
                **transcribe_kwargs,
            )

            # Assemble full transcript from segments
            raw_parts = [segment.text.strip() for segment in segments]
            raw_transcript = " ".join(raw_parts).strip()

            # Pass 2 Fallback: If VAD dropped speech as silence, immediately retry without VAD
            if not raw_transcript:
                logger.info("Silero VAD produced empty transcript; falling back to non-VAD transcription.")
                segments, info = self._model.transcribe(
                    target_path,
                    vad_filter=False,
                    **transcribe_kwargs,
                )
                raw_parts = [segment.text.strip() for segment in segments]
                raw_transcript = " ".join(raw_parts).strip()

            transcription_time = time.time() - t0

            logger.info(
                f"Transcribed audio ({info.duration:.2f}s) in {transcription_time:.2f}s "
                f"[Model: {self.model_name}, Device: {self.device}]"
            )

            # Step: Business & Entity Normalization
            raw_cleaned, normalized_transcript = normalize_speech_transcript(raw_transcript)

            return raw_cleaned, normalized_transcript, transcription_time
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass


def get_transcriber() -> WhisperTranscriber:
    """Helper to access the singleton transcriber instance."""
    return WhisperTranscriber.get_instance()


def transcribe_audio(
    audio_file,
    extension: str = '.webm',
    language: str = 'en',
) -> Tuple[str, str, float]:
    """Convenience function to transcribe audio using the singleton engine."""
    transcriber = get_transcriber()
    return transcriber.transcribe(audio_file, file_extension=extension, language=language)
