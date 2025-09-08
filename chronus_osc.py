#!/usr/bin/env python3
"""
ChronusOSC - Clean, consistent OSC interface for Music Chronus
Handles all the type conversion and format requirements automatically
"""

from pythonosc import udp_client
from typing import Union, List, Optional

class ChronusOSC:
    """
    Wrapper for OSC communication with Music Chronus engine.
    Provides consistent, type-safe methods for all commands.
    
    Rules this class handles for you:
    1. Single numeric values can be sent with or without list
    2. Multiple values MUST be in a list
    3. Commands with no args need empty list []
    4. All values are properly typed (float, int, str)
    """
    
    def __init__(self, host="127.0.0.1", port=5005):
        self.client = udp_client.SimpleUDPClient(host, port)
        
    # ============= VOICE CONTROLS =============
    
    def set_voice_freq(self, voice: int, freq: float):
        """Set voice frequency (20-5000 Hz)"""
        self.client.send_message(f'/mod/voice{voice}/freq', float(freq))
    
    def set_voice_amp(self, voice: int, amp: float):
        """Set voice amplitude (0-1)"""
        self.client.send_message(f'/mod/voice{voice}/amp', float(amp))
    
    def set_voice_filter(self, voice: int, freq: float, q: float = None):
        """Set voice filter parameters"""
        self.client.send_message(f'/mod/voice{voice}/filter/freq', float(freq))
        if q is not None:
            self.client.send_message(f'/mod/voice{voice}/filter/q', float(q))
    
    def set_voice_adsr(self, voice: int, attack: float = None, decay: float = None, 
                       sustain: float = None, release: float = None):
        """Set voice ADSR envelope"""
        if attack is not None:
            self.client.send_message(f'/mod/voice{voice}/adsr/attack', float(attack))
        if decay is not None:
            self.client.send_message(f'/mod/voice{voice}/adsr/decay', float(decay))
        if sustain is not None:
            self.client.send_message(f'/mod/voice{voice}/adsr/sustain', float(sustain))
        if release is not None:
            self.client.send_message(f'/mod/voice{voice}/adsr/release', float(release))
    
    def set_voice_sends(self, voice: int, reverb: float = None, delay: float = None):
        """Set voice effect sends (0-1)"""
        if reverb is not None:
            self.client.send_message(f'/mod/voice{voice}/send/reverb', float(reverb))
        if delay is not None:
            self.client.send_message(f'/mod/voice{voice}/send/delay', float(delay))
    
    def gate_voice(self, voice: int, state: bool):
        """Gate voice on/off"""
        self.client.send_message(f'/gate/voice{voice}', 1 if state else 0)
    
    # ============= ACID FILTER =============
    
    def set_acid_cutoff(self, cutoff: float):
        """Set acid filter cutoff (80-5000 Hz)"""
        self.client.send_message('/mod/acid1/cutoff', float(cutoff))
    
    def set_acid_res(self, res: float):
        """Set acid filter resonance (0-0.98)"""
        self.client.send_message('/mod/acid1/res', float(res))
    
    def set_acid_env(self, amount: float, decay: float = None):
        """Set acid filter envelope"""
        self.client.send_message('/mod/acid1/env_amount', float(amount))
        if decay is not None:
            self.client.send_message('/mod/acid1/decay', float(decay))
    
    def set_acid_drive(self, drive: float, mix: float = None):
        """Set acid filter drive/distortion"""
        self.client.send_message('/mod/acid1/drive', float(drive))
        if mix is not None:
            self.client.send_message('/mod/acid1/mix', float(mix))
    
    # ============= EFFECTS =============
    
    def set_reverb(self, mix: float, room: float = None, damp: float = None):
        """Set reverb parameters"""
        self.client.send_message('/mod/reverb1/mix', float(mix))
        if room is not None:
            self.client.send_message('/mod/reverb1/room', float(room))
        if damp is not None:
            self.client.send_message('/mod/reverb1/damp', float(damp))
    
    def set_delay(self, mix: float, time: float = None, feedback: float = None):
        """Set delay parameters"""
        self.client.send_message('/mod/delay1/mix', float(mix))
        if time is not None:
            self.client.send_message('/mod/delay1/time', float(time))
        if feedback is not None:
            self.client.send_message('/mod/delay1/feedback', float(feedback))
    
    def set_distortion(self, drive: float, mix: float = None, tone: float = None):
        """Set distortion parameters"""
        self.client.send_message('/mod/dist1/drive', float(drive))
        if mix is not None:
            self.client.send_message('/mod/dist1/mix', float(mix))
        if tone is not None:
            self.client.send_message('/mod/dist1/tone', float(tone))
    
    # ============= LFOs =============
    
    def set_lfo(self, lfo: int, rate: float, depth: float = None):
        """Set LFO parameters (lfo: 1 or 2)"""
        self.client.send_message(f'/mod/lfo{lfo}/rate', float(rate))
        if depth is not None:
            self.client.send_message(f'/mod/lfo{lfo}/depth', float(depth))
    
    # ============= SEQUENCER =============
    
    def seq_add_track(self, track_id: str, voice_id: str, pattern: str, 
                      base_freq: float = None, filter_freq: float = None, notes: str = None):
        """Add a sequencer track with pattern"""
        # Build args list - only include provided values
        args = [track_id, voice_id, pattern]
        if base_freq is not None:
            args.append(float(base_freq))
        if filter_freq is not None:
            args.append(float(filter_freq))
        if notes is not None:
            args.append(notes)
        
        self.client.send_message('/seq/add', args)
    
    def seq_remove_track(self, track_id: str):
        """Remove a sequencer track"""
        self.client.send_message('/seq/remove', [track_id])
    
    def seq_update_pattern(self, track_id: str, pattern: str):
        """Update track pattern"""
        self.client.send_message('/seq/update/pattern', [track_id, pattern])
    
    def seq_update_notes(self, track_id: str, notes: str):
        """Update track notes"""
        self.client.send_message('/seq/update/notes', [track_id, notes])
    
    def seq_start(self):
        """Start sequencer"""
        self.client.send_message('/seq/start', [])
    
    def seq_stop(self):
        """Stop sequencer"""
        self.client.send_message('/seq/stop', [])
    
    def seq_clear(self):
        """Clear all sequencer tracks"""
        self.client.send_message('/seq/clear', [])
    
    def seq_bpm(self, bpm: float):
        """Set sequencer BPM (30-300)"""
        self.client.send_message('/seq/bpm', float(bpm))
    
    def seq_swing(self, swing: float):
        """Set sequencer swing (0-0.6)"""
        self.client.send_message('/seq/swing', float(swing))
    
    def seq_status(self):
        """Get sequencer status"""
        self.client.send_message('/seq/status', [])
    
    # ============= ENGINE CONTROL =============
    
    def engine_start(self):
        """Start engine"""
        self.client.send_message('/engine/start', [])
    
    def engine_stop(self):
        """Stop engine"""
        self.client.send_message('/engine/stop', [])
    
    def engine_status(self):
        """Get engine status"""
        self.client.send_message('/engine/status', [])
    
    def engine_schema(self):
        """Get engine schema"""
        self.client.send_message('/engine/schema', [])
    
    # ============= PATTERN MANAGEMENT =============
    
    def pattern_save(self, slot: int, name: str = None):
        """Save current state to pattern slot (0-127)"""
        args = [int(slot)]
        if name is not None:
            args.append(name)
        self.client.send_message('/pattern/save', args)
    
    def pattern_load(self, slot: int):
        """Load pattern from slot (0-127)"""
        self.client.send_message('/pattern/load', int(slot))
    
    def pattern_list(self):
        """List all saved patterns"""
        self.client.send_message('/pattern/list', [])
    
    # ============= RAW COMMANDS =============
    
    def send_raw(self, path: str, value = None):
        """
        Send raw OSC message for any custom commands.
        
        Rules:
        - Single value: can be sent as-is or in list
        - Multiple values: MUST be in list
        - No args: use empty list []
        """
        if value is None:
            value = []
        self.client.send_message(path, value)


# ============= USAGE EXAMPLES =============

if __name__ == "__main__":
    import time
    
    print("ChronusOSC Demo")
    print("=" * 40)
    
    # Create instance
    osc = ChronusOSC()
    
    print("\n1. Simple voice control:")
    osc.set_voice_freq(1, 440.0)
    osc.set_voice_filter(1, 1000, q=2.0)
    osc.gate_voice(1, True)
    time.sleep(1)
    osc.gate_voice(1, False)
    
    print("\n2. Sequencer pattern:")
    osc.seq_add_track('kick', 'voice1', 'X...X...X...X...', base_freq=60)
    osc.seq_add_track('hats', 'voice3', 'x.x.x.x.', base_freq=4000)
    osc.seq_bpm(120)
    osc.seq_start()
    time.sleep(4)
    osc.seq_stop()
    osc.seq_clear()
    
    print("\n3. Effects:")
    osc.set_reverb(mix=0.3, room=0.5)
    osc.set_delay(mix=0.2, time=0.375, feedback=0.4)
    
    print("\nDemo complete!")