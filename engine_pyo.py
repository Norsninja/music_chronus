#!/usr/bin/env python3
"""
Music Chronus - Pyo Audio Engine
Proof of concept using pyo's C DSP engine instead of custom Python DSP
Maintains compatibility with existing OSC control schema
"""

import sys
import time
import threading
from typing import Dict, Any
from pyo import *
from pythonosc import dispatcher, osc_server

class PyoEngine:
    """
    Headless modular synthesizer using pyo's C backend
    Compatible with existing OSC control patterns
    """
    
    def __init__(self, sample_rate=48000, buffer_size=256, device_id=17):
        """Initialize pyo server with Windows WASAPI"""
        
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
        
        # Module storage - using dict for dynamic access
        self.modules = {}
        
        # Create initial module chain: sine -> adsr -> filter
        self.build_initial_chain()
        
        # OSC server setup
        self.setup_osc_server()
        
        print(f"[PYO] Engine initialized")
        print(f"[PYO] Sample rate: {sample_rate}Hz")
        print(f"[PYO] Buffer size: {buffer_size} samples")
        print(f"[PYO] Latency: {buffer_size/sample_rate*1000:.1f}ms")
    
    def build_initial_chain(self):
        """Build the initial sine->adsr->filter chain"""
        
        # ADSR envelope with reasonable defaults
        self.modules['adsr1'] = Adsr(
            attack=0.01,   # 10ms attack
            decay=0.1,     # 100ms decay
            sustain=0.7,   # 70% sustain level
            release=0.5,   # 500ms release
            dur=0,         # Infinite duration (gate controlled)
            mul=0.3        # Overall amplitude
        )
        
        # Make envelope exponential for more natural sound
        self.modules['adsr1'].setExp(0.75)
        
        # Sine oscillator modulated by envelope
        self.modules['sine1'] = Sine(
            freq=440,  # A4
            mul=self.modules['adsr1']
        )
        
        # Biquad lowpass filter
        # Type 0 = lowpass, 1 = highpass, 2 = bandpass
        self.modules['filter1'] = Biquad(
            self.modules['sine1'],
            freq=1000,  # Cutoff frequency
            q=2,        # Resonance
            type=0      # Lowpass
        )
        
        # Connect filter output to audio out
        self.modules['filter1'].out()
        
        print("[PYO] Module chain created: sine1 -> adsr1 -> filter1")
    
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
        
        print(f"[OSC] Set {module_id}.{param} = {value}")
        
        # Route to appropriate module
        if module_id == 'sine1' and param == 'freq':
            self.modules['sine1'].freq = float(value)
            
        elif module_id == 'adsr1':
            if param == 'attack':
                self.modules['adsr1'].attack = float(value)
            elif param == 'decay':
                self.modules['adsr1'].decay = float(value)
            elif param == 'sustain':
                self.modules['adsr1'].sustain = float(value)
            elif param == 'release':
                self.modules['adsr1'].release = float(value)
                
        elif module_id == 'filter1':
            if param == 'freq':
                self.modules['filter1'].freq = float(value)
            elif param == 'q':
                self.modules['filter1'].q = float(value)
    
    def handle_gate(self, addr, *args):
        """Handle /gate/<module_id> value"""
        
        parts = addr.split('/')
        if len(parts) < 3 or len(args) < 1:
            return
        
        module_id = parts[2]
        gate = args[0]
        
        print(f"[OSC] Gate {module_id} = {gate}")
        
        # For now, gate controls ADSR
        if module_id == 'adsr1' or module_id == '1':
            if gate > 0:
                self.modules['adsr1'].play()  # Trigger envelope
            else:
                self.modules['adsr1'].stop()  # Release envelope
    
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
        print(f"CPU usage: Not available in pyo")
        print("\nModules:")
        for name, module in self.modules.items():
            print(f"  {name}: {type(module).__name__}")
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
    
    # Create engine with Windows config
    engine = PyoEngine(
        sample_rate=48000,
        buffer_size=256,  # 5.3ms latency
        device_id=17  # AB13X USB Audio
    )
    
    # Auto-start audio
    engine.start()
    
    # Run forever (headless mode)
    engine.run_forever()


if __name__ == "__main__":
    main()