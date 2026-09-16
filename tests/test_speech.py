import io
import wave
import numpy as np
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile

from speech.vocabulary import build_initial_prompt, get_dataset_entities, BASE_DOMAINS
from speech.normalizer import (
    normalize_acoustic_terms,
    normalize_branch_numbers,
    normalize_entity_names,
    normalize_speech_transcript,
)
from speech.transcriber import WhisperTranscriber, get_transcriber
from query_engine.multi_stats import extract_requested_statistics, detect_entity_level_and_name
from query_engine.router import route_question


def create_test_wav_bytes(duration_sec: float = 0.5, freq: float = 440.0, sample_rate: int = 16000) -> bytes:
    """Generates a small valid mono 16-bit PCM WAV in memory."""
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), False)
    audio = (np.sin(2 * np.pi * freq * t) * 16384).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()


class TestSpeechVocabulary(TestCase):
    def test_vocabulary_and_prompt(self):
        prompt = build_initial_prompt()
        self.assertIn("Dropout", prompt)
        self.assertIn("Fee Due", prompt)
        self.assertIn("Revenue vs Salary", prompt)
        self.assertIn("Student Teacher Ratio", prompt)
        entities = get_dataset_entities()
        self.assertTrue(len(entities) > 0)

        self.assertIn("Anitha", prompt)


class TestSpeechNormalizer(TestCase):
    def test_acoustic_term_normalization(self):
        # Fee due variations
        self.assertEqual(normalize_acoustic_terms("RI Anitha feedue statistics"), "RI Anitha fee due statistics")
        self.assertEqual(normalize_acoustic_terms("fee dues analysis"), "fee due analysis")
        self.assertEqual(normalize_acoustic_terms("fee-do report"), "fee due report")
        self.assertEqual(normalize_acoustic_terms("fee do report"), "fee due report")
        self.assertEqual(normalize_acoustic_terms("due fee statistics"), "fee due statistics")

        # Dropout variations
        self.assertEqual(normalize_acoustic_terms("drop outs report"), "dropout report")
        self.assertEqual(normalize_acoustic_terms("drop-outs summary"), "dropout summary")
        self.assertEqual(normalize_acoustic_terms("drop out percentage"), "dropout percentage")

        # Revenue vs Salary variations
        self.assertEqual(normalize_acoustic_terms("revenue verse salary"), "revenue vs salary")
        self.assertEqual(normalize_acoustic_terms("revenue versus salary"), "revenue vs salary")
        self.assertEqual(normalize_acoustic_terms("sal vs rev statistics"), "revenue vs salary statistics")

        # Student Teacher Ratio variations
        self.assertEqual(normalize_acoustic_terms("teacher student ratio"), "student teacher ratio")
        self.assertEqual(normalize_acoustic_terms("teacher to student ratio"), "student teacher ratio")

    def test_branch_numbers_normalization(self):
        self.assertEqual(normalize_branch_numbers("Kakinada one"), "Kakinada 1")
        self.assertEqual(normalize_branch_numbers("Kakinada two"), "Kakinada 2")
        self.assertEqual(normalize_branch_numbers("Amalapuram two"), "Amalapuram 2")
        self.assertEqual(normalize_branch_numbers("Bobbili two"), "Bobbili 2")
        self.assertEqual(normalize_branch_numbers("Give Kakinada one statistics"), "Give Kakinada 1 statistics")
        self.assertEqual(normalize_branch_numbers("Show Kakinada one dropout statistics"), "Show Kakinada 1 dropout statistics")

        # Plain numbers in queries must not be mangled
        self.assertEqual(normalize_branch_numbers("top five branches"), "top five branches")

    def test_entity_names_and_casing(self):
        self.assertEqual(normalize_entity_names("ri anitha"), "RI Anitha")
        self.assertEqual(normalize_entity_names("agm suresh"), "AGM Suresh")
        self.assertEqual(normalize_entity_names("kakinada 1"), "Kakinada 1")
        self.assertEqual(normalize_entity_names("amalapuram"), "Amalapuram")

    def test_end_to_end_normalization(self):
        # 1. Multi-stat request with speech variations
        raw, norm = normalize_speech_transcript("ri anitha drop outs feedue statistics")
        self.assertEqual(raw, "ri anitha drop outs feedue statistics")
        self.assertEqual(norm, "RI Anitha dropout fee due statistics")

        # 2. Numbered branch request
        raw, norm = normalize_speech_transcript("give kakinada one statistics")
        self.assertEqual(norm, "give Kakinada 1 statistics")

        # 3. Base branch entity safety: Amalapuram should stay Amalapuram
        raw, norm = normalize_speech_transcript("branch amalapuram statistics")
        self.assertEqual(norm, "branch Amalapuram statistics")

        # 4. Numbered branch entity: Amalapuram 2
        raw, norm = normalize_speech_transcript("branch amalapuram two statistics")
        self.assertEqual(norm, "branch Amalapuram 2 statistics")

        # 5. Three-domain multi-stat
        raw, norm = normalize_speech_transcript("ri anitha drop outs feedue revenue verse salary statistics")
        self.assertEqual(norm, "RI Anitha dropout fee due revenue vs salary statistics")

        # 6. Whisper contraction: RIONita and FIDU
        raw, norm = normalize_speech_transcript("RIONita dropout FIDU statistics")
        self.assertEqual(norm, "RI Anitha dropout fee due statistics")

        # 7. Acoustic variants: feed you, A GM Suresh, cocky nada 1
        _, norm = normalize_speech_transcript("A GM Suresh dropout feed you statistics")
        self.assertEqual(norm, "AGM Suresh dropout fee due statistics")

        _, norm = normalize_speech_transcript("Show cocky nada 1 dropout statistics")
        self.assertEqual(norm, "Show Kakinada 1 dropout statistics")

        _, norm = normalize_speech_transcript("Branch bobby lee two statistics")
        self.assertEqual(norm, "Branch Bobbili 2 statistics")

    def test_integration_with_multi_statistics_orchestrator(self):
        """Verify that normalized transcript feeds cleanly into existing multi-statistics routing."""
        _, norm = normalize_speech_transcript("RI anitha drop outs feedue statistics")
        stats = extract_requested_statistics(norm)
        self.assertEqual(stats, ['dropout', 'fee_due'])

        level, name = detect_entity_level_and_name(norm)
        self.assertEqual(level, 'RI')
        self.assertIn('ANITHA', name.upper())

        handler = route_question(norm)
        self.assertIsNotNone(handler)

        # Contraction integration: RIONita FIDU
        _, norm2 = normalize_speech_transcript("RIONita dropout FIDU statistics")
        stats2 = extract_requested_statistics(norm2)
        self.assertEqual(stats2, ['dropout', 'fee_due'])
        level2, name2 = detect_entity_level_and_name(norm2)
        self.assertEqual(level2, 'RI')
        self.assertIn('ANITHA', name2.upper())


class TestTranscriptionEndpoint(TestCase):
    def setUp(self):
        self.client = Client()

    def test_transcribe_missing_file(self):
        resp = self.client.post('/api/transcribe/')
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertIn("No audio file provided", data['error'])

    def test_transcribe_empty_file(self):
        empty_file = SimpleUploadedFile("empty.wav", b"", content_type="audio/wav")
        resp = self.client.post('/api/transcribe/', {'audio': empty_file})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertIn("empty", data['error'])

    def test_transcribe_valid_audio(self):
        wav_bytes = create_test_wav_bytes(duration_sec=0.5)
        audio_file = SimpleUploadedFile("test_audio.wav", wav_bytes, content_type="audio/wav")
        resp = self.client.post('/api/transcribe/', {'audio': audio_file})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('success', data)
        # Even with pure sine wave, endpoint should complete without error
        if data['success']:
            self.assertIn('text', data)
            self.assertIn('raw_text', data)
            self.assertIn('duration', data)
        else:
            self.assertIn("Could not understand", data['error'])


class TestWhisperTranscriberSingleton(TestCase):
    def test_singleton_instance(self):
        t1 = get_transcriber()
        t2 = get_transcriber()
        self.assertIs(t1, t2)
        self.assertEqual(t1.device, 'cpu')
        self.assertIn(t1.compute_type, ['int8', 'float32', 'default'])
