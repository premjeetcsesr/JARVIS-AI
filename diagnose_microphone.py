r"""MARK LIV microphone diagnostic.
Run with: venv\Scripts\python.exe diagnose_microphone.py
This does not send audio anywhere; it only lists local input devices and records
a short local RMS test.
"""
import sounddevice as sd
import numpy as np

print("="*60)
print("MARK LIV - MICROPHONE DIAGNOSTIC")
print("="*60)
devices = sd.query_devices()
for i,d in enumerate(devices):
    if d.get("max_input_channels", 0) > 0:
        print(f"[{i}] {d['name']} | inputs={d['max_input_channels']} | default_sr={d.get('default_samplerate')}")
print("\nDefault input:", sd.default.device[0])
print("\nTesting default microphone for 3 seconds...")
try:
    audio = sd.rec(int(3*16000), samplerate=16000, channels=1, dtype="int16", blocking=True)
    rms=float(np.sqrt(np.mean(audio.astype(np.float32)**2)))
    peak=int(np.max(np.abs(audio)))
    print(f"RMS: {rms:.1f}  Peak: {peak}")
    if rms < 60:
        print("WARNING: almost no microphone signal detected.")
    else:
        print("Microphone signal detected.")
except Exception as e:
    print("MICROPHONE TEST FAILED:", repr(e))
