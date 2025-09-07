"""
DEBUG VERSION - Acid Filter that just passes through
Testing if the problem is in acid processing or the connection itself
"""

from pyo import *

class AcidFilter:
    """
    DEBUG: Simplest possible acid - just pass through the input
    """
    
    def __init__(self, input_signal, voice_id="acid1", server=None):
        """
        Initialize debug acid - just store and pass input
        """
        self.voice_id = voice_id
        self.server = server or Server.get_server()
        self.input_signal = input_signal
        
        # DEBUG: Just pass through the input directly
        self.output = self.input_signal
        
        print(f"[DEBUG ACID] Created - passing through input signal directly")
        print(f"[DEBUG ACID] Input type: {type(input_signal)}")
        
    def gate(self, state):
        """Gate does nothing in debug mode"""
        pass
    
    def set_cutoff(self, freq):
        """Stub"""
        pass
    
    def set_res(self, res):
        """Stub"""
        pass
    
    def set_env_amount(self, amount):
        """Stub"""
        pass
    
    def set_decay(self, decay):
        """Stub"""
        pass
    
    def set_accent(self, accent):
        """Stub"""
        pass
    
    def set_cutoff_offset(self, offset):
        """Stub"""
        pass
    
    def set_res_accent_boost(self, boost):
        """Stub"""
        pass
    
    def set_accent_decay(self, decay):
        """Stub"""
        pass
    
    def set_drive(self, drive):
        """Stub"""
        pass
    
    def set_mix(self, mix):
        """Stub - always pass through"""
        pass
    
    def set_vol_comp(self, comp):
        """Stub"""
        pass
    
    def get_output(self):
        """Get the output signal - just the input"""
        return self.output
    
    def get_status(self):
        """Get status"""
        return {
            'voice_id': self.voice_id,
            'debug_mode': True
        }