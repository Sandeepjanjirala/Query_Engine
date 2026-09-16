import os
import sys
import time
import wave
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from speech.transcriber import get_transcriber
from query_engine.multi_stats import extract_requested_statistics, detect_entity_level_and_name
from query_engine.router import route_question


def get_wav_duration(path: str) -> float:
    with wave.open(path, 'rb') as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate)


def run_cpu_performance_benchmark():
    print("=" * 80)
    print("PART 1: CPU PERFORMANCE BENCHMARK (10s, 20s, 30s Recordings)")
    print("=" * 80)

    # 1. Measure model loading time
    transcriber = get_transcriber()
    t0 = time.time()
    transcriber._ensure_model_loaded()
    load_time = time.time() - t0
    print(f"Model Name        : {transcriber.model_name}")
    print(f"Device            : {transcriber.device}")
    print(f"Compute Type      : {transcriber.compute_type}")
    print(f"Initial Load Time : {load_time:.2f}s (cached in-memory for all subsequent queries)")
    print("-" * 80)

    audio_dir = Path("scratch/audio")
    bench_files = ["bench_10s.wav", "bench_20s.wav", "bench_30s.wav"]

    print(f"{'Recording':<15} | {'Audio Dur':<12} | {'Transcribe Time':<18} | {'RTF (Trans/Dur)':<18} | {'Status'}")
    print("-" * 80)

    for bf in bench_files:
        path = str(audio_dir / bf)
        if not os.path.exists(path):
            print(f"Warning: {path} not found")
            continue
        dur = get_wav_duration(path)
        t_start = time.time()
        raw, norm, proc_time = transcriber.transcribe(path, file_extension='.wav', language='en')
        wall_time = time.time() - t_start
        rtf = proc_time / dur if dur > 0 else 0
        speedup = f"{1/rtf:.2f}x real-time" if rtf > 0 else "N/A"
        print(f"{bf:<15} | {dur:>9.2f}s  | {proc_time:>14.2f}s    | {rtf:>10.2f} ({speedup}) | PASS")

    print("=" * 80)
    print()


def run_10_spoken_queries_evaluation():
    print("=" * 80)
    print("PART 2: 10 REAL SPOKEN QUERIES THROUGH /api/transcribe/ AND QUERY ENGINE")
    print("=" * 80)

    client = Client()
    audio_dir = Path("scratch/audio")

    queries = [
        ("q1.wav", "RI Anitha dropout statistics"),
        ("q2.wav", "RI Anitha fee due statistics"),
        ("q3.wav", "RI Anitha dropout fee due statistics"),
        ("q4.wav", "RI Anitha dropout fee due revenue versus salary statistics"),
        ("q5.wav", "Give Kakinada one statistics"),
        ("q6.wav", "Show Kakinada one dropout statistics"),
        ("q7.wav", "Branch Amalapuram statistics"),
        ("q8.wav", "Branch Amalapuram two statistics"),
        ("q9.wav", "Show top five branches by dropout percentage"),
        ("q10.wav", "Show revenue versus salary for RI Anitha"),
    ]

    for idx, (filename, intent) in enumerate(queries, 1):
        path = audio_dir / filename
        if not path.exists():
            print(f"[{idx}] Missing audio file: {path}")
            continue

        with open(path, 'rb') as f:
            wav_bytes = f.read()

        audio_file = SimpleUploadedFile(filename, wav_bytes, content_type="audio/wav")

        # 1. Test POST to local Django endpoint /api/transcribe/
        resp = client.post('/api/transcribe/', {'audio': audio_file})
        if resp.status_code != 200:
            print(f"[{idx}] /api/transcribe/ FAILED: status {resp.status_code}")
            continue

        data = resp.json()
        raw_text = data.get('raw_text', '')
        norm_text = data.get('text', '')
        duration = data.get('duration', 0.0)

        # 2. Extract analytical domains
        detected_domains = extract_requested_statistics(norm_text)

        # 3. Detect entity
        level, entity_name = detect_entity_level_and_name(norm_text)

        # 4. Route query
        handler = route_question(norm_text)
        fn_name = handler.__name__ if handler else "None"

        # 5. Execute query through Query Engine API
        exec_resp = client.post(
            '/api/query/',
            data={'question': norm_text, 'filters': {'agm': 'All', 'ri': 'All', 'zone': 'All', 'branches': ['All']}},
            content_type='application/json'
        )
        exec_data = exec_resp.json()
        answer = exec_data.get('answer', '')
        first_line = answer.split('\n')[0] if answer else "No answer"

        print(f"--- [Query {idx}/10] ---")
        print(f"  Spoken Intent     : {intent}")
        print(f"  Raw Whisper Output: \"{raw_text}\"")
        print(f"  Normalized Text   : \"{norm_text}\"")
        print(f"  Transcribe Time   : {duration:.2f}s")
        print(f"  Detected Domains  : {detected_domains}")
        print(f"  Detected Entity   : Level={level}, Name={entity_name}")
        print(f"  Routed Function   : {fn_name}")
        print(f"  Engine Response   : {first_line[:90]}...")
        print()

    print("=" * 80)


if __name__ == '__main__':
    run_cpu_performance_benchmark()
    run_10_spoken_queries_evaluation()
