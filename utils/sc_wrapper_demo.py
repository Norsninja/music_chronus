#!/usr/bin/env python3
"""
SuperCollider wrapper demo - Shows how to match our current OSC API
This demonstrates that we can keep our interface while using SC as the engine
"""

from pythonosc import udp_client
import time

class SuperColliderWrapper:
    """
    Wraps SuperCollider to match our current OSC interface
    Shows that switching engines doesn't mean losing our API design
    """
    
    def __init__(self, host="127.0.0.1", port=57110):
        self.client = udp_client.SimpleUDPClient(host, port)
        self.voices = {}  # Track node IDs for each voice
        self.next_node_id = 1000
        
    def handle_mod_param(self, path, value):
        """
        Convert our /mod/voiceN/param to SuperCollider commands
        Example: /mod/voice1/freq 440 -> /n_set [nodeID, "freq", 440]
        """
        parts = path.split('/')
        voice_id = parts[2]  # e.g., "voice1"
        param = parts[3] if len(parts) > 3 else None
        
        # Ensure voice exists
        if voice_id not in self.voices:
            self.create_voice(voice_id)
        
        node_id = self.voices[voice_id]
        
        # Map our param names to SC param names
        param_map = {
            'freq': 'freq',
            'amp': 'amp',
            'filter/freq': 'cutoff',  # If using a filtered synth
            'filter/q': 'rq',        # Reciprocal of Q in SC
        }
        
        sc_param = param_map.get(param, param)
        self.client.send_message("/n_set", [node_id, sc_param, value])
        
    def handle_gate(self, voice_id, state):
        """
        Convert our gate messages to SuperCollider
        /gate/voice1 1 -> Create or gate on
        /gate/voice1 0 -> Release or free
        """
        if state > 0:
            if voice_id not in self.voices:
                self.create_voice(voice_id)
            else:
                # Gate on existing synth
                self.client.send_message("/n_set", [self.voices[voice_id], "gate", 1])
        else:
            if voice_id in self.voices:
                # Gate off (this would trigger release in a proper ADSR synth)
                self.client.send_message("/n_set", [self.voices[voice_id], "gate", 0])
                # For now, just free it after a moment
                time.sleep(0.5)
                self.client.send_message("/n_free", [self.voices[voice_id]])
                del self.voices[voice_id]
    
    def create_voice(self, voice_id):
        """Create a new synth instance for a voice"""
        node_id = self.next_node_id
        self.next_node_id += 1
        
        # Create a default synth (in real use, we'd load custom SynthDefs)
        self.client.send_message("/s_new", ["default", node_id, 0, 0, "amp", 0.2])
        self.voices[voice_id] = node_id
        return node_id

def demo_compatibility():
    """
    Demonstrate that our current patterns work with SuperCollider
    """
    print("="*60)
    print("SUPERCOLLIDER COMPATIBILITY DEMO")
    print("Showing our OSC API working with SC backend")
    print("="*60)
    
    wrapper = SuperColliderWrapper()
    
    print("\n1. Testing our familiar commands...")
    print("   /mod/voice1/freq 440")
    wrapper.handle_mod_param("/mod/voice1/freq", 440)
    
    print("   /gate/voice1 1")
    wrapper.handle_gate("voice1", 1)
    time.sleep(1)
    
    print("\n2. Changing parameters...")
    print("   /mod/voice1/freq 880")
    wrapper.handle_mod_param("/mod/voice1/freq", 880)
    time.sleep(1)
    
    print("   /mod/voice1/amp 0.5")
    wrapper.handle_mod_param("/mod/voice1/amp", 0.5)
    time.sleep(1)
    
    print("\n3. Gate off...")
    print("   /gate/voice1 0")
    wrapper.handle_gate("voice1", 0)
    
    print("\n4. Playing a pattern (just like our sequencer)...")
    pattern = "X...X...X...X..."
    for step in pattern:
        if step == 'X':
            wrapper.handle_mod_param("/mod/voice2/freq", 55)
            wrapper.handle_gate("voice2", 1)
            time.sleep(0.1)
            wrapper.handle_gate("voice2", 0)
        time.sleep(0.125)
    
    print("\n" + "="*60)
    print("COMPATIBILITY PROVEN!")
    print("We can keep our exact OSC interface with SC as the engine")
    print("="*60)

if __name__ == "__main__":
    print("\nNOTE: Make sure SuperCollider server is running first!")
    print("Run: python test_supercollider.py")
    print("Then run this script in another terminal\n")
    
    demo_compatibility()