# Monophonic MIDI Synthesizer

**Author:** Saif Abu Hananah  
**Course/Assignment:** Personal MIDI Synthesizer  

## What I Did
I built a real-time, monophonic software synthesizer in Python. The core audio engine uses `sounddevice` to stream raw audio arrays directly to the system's soundcard, while `mido` listens for incoming MIDI events. 

To meet the sub-10ms latency requirement and ensure events are only processed between sample outputs, I implemented a thread-safe message queue. The MIDI thread pushes `note_on` and `note_off` events to the queue, and the audio callback processes them before rendering the next 256-frame block of audio (achieving roughly ~5.8ms latency at 44.1kHz). The default voice is a sawtooth wave peaking at -3dBFS, shaped by a fixed 10ms linear Attack/Release (AR) envelope.

**Bonus Features Implemented:**
* **Direct MIDI (`--midi-device`):** The program accepts a command-line argument to bind directly to a specific, named MIDI controller or virtual port.
* **Alternate Waveforms (`--waveform`):** Added support for Sine, Square, and White Noise generation.

## How It Went
The core math and DSP logic for the phase accumulation and AR envelope went smoothly. However, I ran into significant challenges with Windows audio and MIDI routing.

Because I use a wireless computer keyboard instead of a physical USB MIDI controller, I discovered that Windows does not natively detect typing keyboards as MIDI devices. To solve this, I installed **loopMIDI** to create a virtual MIDI cable and used **VMPK (Virtual MIDI Piano Keyboard)** to translate my typing into MIDI data. I routed VMPK into the virtual cable, and used my `--midi-device` flag to bind my Python script to the other end.

Additionally, my system defaulted to sending audio to my monitor's silent DisplayPort output. I had to manually query my system's devices using `python -m sounddevice` and explicitly route the output to my headphones during testing.

## What Is Still To Be Done
While the core requirements and several bonuses are complete, there is plenty of room for expansion:
* **Polyphony:** The synth currently tracks a single active note and frequency. Implementing an array of voice objects would allow for chords.
* **ADSR Envelopes:** Expanding the AR envelope to include Decay time and Sustain levels.
* **Velocity Sensitivity:** Mapping the incoming `KEY ON` velocity to the target amplitude, and `KEY OFF` velocity to the release rate.

---

## How To Run the Program

**Prerequisites:**
```bash
pip install numpy sounddevice mido python-rtmidi