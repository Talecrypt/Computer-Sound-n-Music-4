import sys
import queue
import argparse
import numpy as np
import sounddevice as sd
import mido

class SynthState:
    def __init__(self, sample_rate, waveform='sawtooth'):
        self.sample_rate = sample_rate
        self.waveform = waveform
        self.phase = 0.0
        self.freq = 0.0
        
        # Envelope State
        self.env_val = 0.0
        self.env_state = 'IDLE' 
        self.active_note = None

        # 10ms attack and release rates
        self.attack_rate = 1.0 / (0.010 * self.sample_rate)
        self.release_rate = 1.0 / (0.010 * self.sample_rate)
        
        # -3dBFS Volume Target
        self.target_amp = 10 ** (-3.0 / 20.0) 

def process_midi(msg, state):
    """Update synthesizer state based on MIDI messages."""
    print(f"Received MIDI: {msg}")
    # Handle KEY ON
    if msg.type == 'note_on' and msg.velocity > 0:
        # Calculate frequency: f = 440 * 2^((d-69)/12)
        state.freq = 440.0 * (2.0 ** ((msg.note - 69) / 12.0))
        state.active_note = msg.note
        state.env_state = 'ATTACK'
        state.phase = 0.0 # Reset phase to avoid clicks on new notes
        
    # Handle KEY OFF or KEY ON
    elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
        if msg.note == state.active_note:
            state.env_state = 'RELEASE'

def audio_callback(outdata, frames, time, status, state, midi_queue):
    """Audio processing callback. Runs continuously in a separate thread."""
    if status:
        print(status, file=sys.stderr)

    # Process pending MIDI events between audio blocks
    while not midi_queue.empty():
        msg = midi_queue.get_nowait()
        process_midi(msg, state)

    # If nothing is playing, output silence and return early to save CPU
    if state.env_state == 'IDLE' and state.env_val <= 0.0:
        outdata[:] = 0.0
        return

    # 1. Calculate Phase Array
    phase_increments = np.full(frames, state.freq / state.sample_rate)
    phases = state.phase + np.cumsum(phase_increments)
    state.phase = phases[-1] % 1.0 # Store ending phase for the next block
    phases = phases % 1.0 # Wrap between 0.0 and 1.0

    # 2. Generate Base Waveform
    if state.waveform == 'sawtooth':
        samples = 2.0 * phases - 1.0
    elif state.waveform == 'sine':
        samples = np.sin(2.0 * np.pi * phases)
    elif state.waveform == 'square':
        samples = np.where(phases < 0.5, 1.0, -1.0)
    elif state.waveform == 'noise':
        samples = np.random.uniform(-1.0, 1.0, frames)
    else:
        samples = np.zeros(frames)

    # 3. Process Linear AR Envelope
    env = np.zeros(frames)
    for i in range(frames):
        if state.env_state == 'ATTACK':
            state.env_val += state.attack_rate
            if state.env_val >= 1.0:
                state.env_val = 1.0
                state.env_state = 'SUSTAIN'
        elif state.env_state == 'RELEASE':
            state.env_val -= state.release_rate
            if state.env_val <= 0.0:
                state.env_val = 0.0
                state.env_state = 'IDLE'
        env[i] = state.env_val

    # 4. Apply Envelope & Volume, then write to output buffer
    outdata[:, 0] = samples * env * state.target_amp

def main():
    parser = argparse.ArgumentParser(description="Monophonic MIDI Synthesizer")
    parser.add_argument('--midi-device', type=str, default=None, help="Name of the MIDI controller to connect to")
    parser.add_argument('--waveform', choices=['sawtooth', 'sine', 'square', 'noise'], default='sawtooth', help="Waveform type (Bonus)")
    args = parser.parse_args()

    sample_rate = 44100
    state = SynthState(sample_rate, waveform=args.waveform)
    midi_queue = queue.Queue()

    def midi_callback(msg):
        # Push relevant MIDI messages to the queue for the audio thread to process
        if msg.type in ['note_on', 'note_off']:
            midi_queue.put(msg)

    # Initialize MIDI Input
    try:
        if args.midi_device:
            port = mido.open_input(args.midi_device, callback=midi_callback)
        else:
            port = mido.open_input(callback=midi_callback)
        print(f"Connected to MIDI Input: {port.name}")
    except Exception as e:
        print("Error: Could not open MIDI port.")
        print("Available ports:", mido.get_input_names())
        sys.exit(1)

    # Initialize Audio Output
    # Blocksize of 256 at 44.1kHz ensures an ultra-low latency of ~5.8ms per block.
    try:
        with sd.OutputStream(channels=1,
                             callback=lambda *args_cb: audio_callback(*args_cb, state, midi_queue),
                             samplerate=sample_rate,
                             blocksize=256,
                             latency='low'):
            print(f"Synthesizer running! Waveform: {args.waveform}. Press Ctrl+C to stop.")
            while True:
                sd.sleep(1000)
    except KeyboardInterrupt:
        print("\nExiting...")
        port.close()

if __name__ == "__main__":
    main()