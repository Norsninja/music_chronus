#!/usr/bin/env python3
"""
Music Chronus - Pyo Audio Engine
Polyphonic synthesizer with 4 voices and global effects
Maintains backward compatibility with existing OSC control schema
"""

import os
import sys
import time
import threading
from typing import Dict, Any
from pyo import *
from pythonosc import dispatcher, osc_server

# Import our pyo modules
from pyo_modules import Voice, ReverbBus, DelayBus

class PyoEngine:
    """
    Headless modular synthesizer using pyo's C backend
    Compatible with existing OSC control patterns
    """
    
    def __init__(self, sample_rate=None, buffer_size=None, device_id=None):
        """Initialize pyo server with environment-aware configuration"""
        
        # Get configuration from environment or use defaults
        sample_rate = sample_rate or int(os.environ.get('CHRONUS_SAMPLE_RATE', 48000))
        buffer_size = buffer_size or int(os.environ.get('CHRONUS_BUFFER_SIZE', 256))
        device_id = device_id if device_id is not None else int(os.environ.get('CHRONUS_DEVICE_ID', -1))
        self.verbose = os.environ.get('CHRONUS_VERBOSE', '').lower() in ('1', 'true', 'yes')
        
        # Configure pyo server for Windows
        self.server = Server(
            sr=sample_rate,
            nchnls=1,  # Mono for now
            buffersize=buffer_size,
            duplex=0,  # Output only
            audio='portaudio',  # Use PortAudio backend
            winhost='wasapi'  # Windows WASAPI
        )
        
        # Set output device (AB13X USB Audio)
        if device_id >= 0:
            self.server.setOutputDevice(device_id)
        
        # Boot server but don't start yet
        self.server.boot()
        
        if self.verbose:
            print("[PYO] Available audio devices:")
            pa_list_devices()
        
        # Create voices and effects
        self.setup_voices_and_effects()
        
        # OSC server setup
        self.setup_osc_server()
        
        print(f"[PYO] Engine initialized")
        print(f"[PYO] Sample rate: {sample_rate}Hz")
        print(f"[PYO] Buffer size: {buffer_size} samples")
        print(f"[PYO] Latency: {buffer_size/sample_rate*1000:.1f}ms")
    
    def setup_voices_and_effects(self):
        """Create 4 voices and global effects buses"""
        
        # Create 4 voices
        self.voices = {}
        for i in range(1, 5):
            voice_id = f"voice{i}"
            self.voices[voice_id] = Voice(voice_id, self.server)
            print(f"[PYO] Created {voice_id}")
        
        # Create routing and effects with proper audio signal passing
        self.setup_routing()
        
        print("[PYO] Created 4 voices + reverb + delay")
    
    def setup_routing(self):
        """Setup signal routing: voices -> effects -> output"""
        
        # Sum all voice dry signals
        dry_signals = [voice.get_dry_signal() for voice in self.voices.values()]
        self.dry_mix = Mix(dry_signals, voices=1)  # Mix to mono
        
        # Sum all reverb sends
        reverb_sends = [voice.get_reverb_send() for voice in self.voices.values()]
        self.reverb_input = Mix(reverb_sends, voices=1)
        
        # Sum all delay sends
        delay_sends = [voice.get_delay_send() for voice in self.voices.values()]
        self.delay_input = Mix(delay_sends, voices=1)
        
        # Create effects with proper audio signal inputs (not Sig(0)!)
        self.reverb = ReverbBus(self.reverb_input, self.server)
        self.delay = DelayBus(self.delay_input, self.server)
        
        # Master output: dry + reverb + delay
        self.master = Mix([
            self.dry_mix,
            self.reverb.get_output(),
            self.delay.get_output()
        ], voices=1)
        
        # Send to output
        self.master.out()
    
    def setup_osc_server(self):
        """Setup OSC server for control messages"""
        
        # Create dispatcher for OSC routing
        self.dispatcher = dispatcher.Dispatcher()
        
        # Module parameter control: /mod/<module_id>/<param>
        self.dispatcher.map("/mod/*/*", self.handle_mod_param)
        
        # Gate control: /gate/<module_id>
        self.dispatcher.map("/gate/*", self.handle_gate)
        
        # Engine control
        self.dispatcher.map("/engine/start", lambda addr, *args: self.start())
        self.dispatcher.map("/engine/stop", lambda addr, *args: self.stop())
        self.dispatcher.map("/engine/status", lambda addr, *args: self.print_status())
        self.dispatcher.map("/engine/list", lambda addr, *args: self.list_modules())
        
        # Catch-all for debugging
        self.dispatcher.set_default_handler(self.handle_unknown)
        
        # Create OSC server on port 5005
        self.osc_server = osc_server.ThreadingOSCUDPServer(
            ("127.0.0.1", 5005),
            self.dispatcher
        )
        
        # Start OSC server in background thread
        self.osc_thread = threading.Thread(
            target=self.osc_server.serve_forever,
            daemon=True
        )
        self.osc_thread.start()
        
        print("[OSC] Server listening on 127.0.0.1:5005")
    
    def handle_mod_param(self, addr, *args):
        """Handle /mod/<module_id>/<param> value"""
        
        parts = addr.split('/')
        if len(parts) < 4 or len(args) < 1:
            return
        
        module_id = parts[2]
        param = parts[3]
        value = args[0]
        
        # Handle sub-parameters like /mod/voice1/adsr/attack
        if len(parts) > 4:
            param = '/'.join(parts[3:])
        
        if self.verbose:
            print(f"[OSC] Set {module_id}.{param} = {value}")
        
        # Route voice parameters
        if module_id.startswith('voice'):
            if module_id in self.voices:
                voice = self.voices[module_id]
                
                if param == 'freq':
                    voice.set_freq(value)
                elif param == 'amp':
                    voice.set_amp(value)
                elif param == 'filter/freq':
                    voice.set_filter_freq(value)
                elif param == 'filter/q':
                    voice.set_filter_q(value)
                elif param.startswith('adsr/'):
                    adsr_param = param.split('/')[1]
                    voice.set_adsr(adsr_param, value)
                elif param == 'send/reverb':
                    voice.set_reverb_send(value)
                elif param == 'send/delay':
                    voice.set_delay_send(value)
        
        # Backward compatibility: map old names to voice1
        elif module_id == 'sine1' and param == 'freq':
            self.voices['voice1'].set_freq(value)
        elif module_id == 'filter1':
            if param == 'freq':
                self.voices['voice1'].set_filter_freq(value)
            elif param == 'q':
                self.voices['voice1'].set_filter_q(value)
        elif module_id == 'adsr1':
            if param in ['attack', 'decay', 'sustain', 'release']:
                self.voices['voice1'].set_adsr(param, value)
        
        # Route effect parameters
        elif module_id == 'reverb1':
            if param == 'mix':
                self.reverb.set_mix(value)
            elif param == 'room':
                self.reverb.set_room(value)
            elif param == 'damp':
                self.reverb.set_damp(value)
        
        elif module_id == 'delay1':
            if param == 'time':
                self.delay.set_time(value)
            elif param == 'feedback':
                self.delay.set_feedback(value)
            elif param == 'mix':
                self.delay.set_mix(value)
            elif param == 'lowcut':
                self.delay.set_lowcut(value)
            elif param == 'highcut':
                self.delay.set_highcut(value)
    
    def handle_gate(self, addr, *args):
        """Handle /gate/<module_id> value"""
        
        parts = addr.split('/')
        if len(parts) < 3 or len(args) < 1:
            return
        
        module_id = parts[2]
        gate = args[0]
        
        if self.verbose:
            print(f"[OSC] Gate {module_id} = {gate}")
        
        # Route to voices
        if module_id.startswith('voice'):
            if module_id in self.voices:
                self.voices[module_id].gate(gate)
        
        # Backward compatibility: map old names to voice1
        elif module_id == 'adsr1' or module_id == '1':
            self.voices['voice1'].gate(gate)
    
    def handle_unknown(self, addr, *args):
        """Debug handler for unmatched OSC messages"""
        print(f"[OSC] Unknown: {addr} {args}")
    
    def start(self):
        """Start audio processing"""
        self.server.start()
        print("[PYO] Audio started")
    
    def stop(self):
        """Stop audio processing"""
        self.server.stop()
        print("[PYO] Audio stopped")
    
    def print_status(self):
        """Print current engine status"""
        print("\n" + "="*50)
        print("PYO ENGINE STATUS")
        print("="*50)
        print(f"Server running: {self.server.getIsStarted()}")
        print(f"Sample rate: {self.server.getSamplingRate()}Hz")
        print(f"Buffer size: {self.server.getBufferSize()}")
        print(f"Output latency: {self.server.getBufferSize()/self.server.getSamplingRate()*1000:.1f}ms")
        print("\nVoices (4):")
        for voice_id in self.voices:
            print(f"  {voice_id}: ready")
        print("\nEffects:")
        print(f"  reverb1: mix={self.reverb.get_status()['mix']:.2f}")
        print(f"  delay1: time={self.delay.get_status()['time']:.2f}s")
        print("="*50 + "\n")
    
    def list_modules(self):
        """List available modules and parameters"""
        print("\n" + "="*50)
        print("AVAILABLE MODULES")
        print("="*50)
        
        print("\nVoices (voice1-4):") 
        print("  /mod/voiceN/freq <20-5000>")
        print("  /mod/voiceN/amp <0-1>")
        print("  /mod/voiceN/filter/freq <50-8000>")
        print("  /mod/voiceN/filter/q <0.5-10>")
        print("  /mod/voiceN/adsr/attack <0.001-2>")
        print("  /mod/voiceN/adsr/decay <0-2>")
        print("  /mod/voiceN/adsr/sustain <0-1>")
        print("  /mod/voiceN/adsr/release <0.01-3>")
        print("  /mod/voiceN/send/reverb <0-1>")
        print("  /mod/voiceN/send/delay <0-1>")
        print("  /gate/voiceN <0|1>")
        
        print("\nEffects:")
        print("  /mod/reverb1/mix <0-1>")
        print("  /mod/reverb1/room <0-1>")
        print("  /mod/reverb1/damp <0-1>")
        print("  /mod/delay1/time <0.1-0.6>")
        print("  /mod/delay1/feedback <0-0.7>")
        print("  /mod/delay1/mix <0-1>")
        
        print("\nBackward Compatibility (mapped to voice1):")
        print("  /mod/sine1/freq")
        print("  /mod/filter1/freq|q")
        print("  /mod/adsr1/*")
        print("  /gate/adsr1")
        
        print("="*50 + "\n")
    
    def run_forever(self):
        """Keep engine running (for headless operation)"""
        print("\n[PYO] Engine ready for OSC control")
        print("Commands:")
        print("  /mod/<module>/<param> value - Set parameter")
        print("  /gate/<module> 0/1 - Gate control")
        print("  /engine/start - Start audio")
        print("  /engine/stop - Stop audio")
        print("  /engine/status - Show status")
        print("  /engine/list - List all modules")
        print("\nPress Ctrl+C to exit\n")
        
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n[PYO] Shutting down...")
            self.stop()
            self.server.shutdown()
            self.osc_server.shutdown()


def main():
    """Main entry point"""
    
    # Create engine with environment-aware config
    engine = PyoEngine()
    
    # Auto-start audio
    engine.start()
    
    # Run forever (headless mode)
    engine.run_forever()


if __name__ == "__main__":
    main()