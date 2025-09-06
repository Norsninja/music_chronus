"""
Effects modules for Music Chronus
Global reverb and delay buses with parameter smoothing
"""

from pyo import *

class ReverbBus:
    """
    Global reverb bus using Freeverb
    Receives sends from all voices
    """
    
    def __init__(self, server=None):
        """
        Initialize reverb with smoothed parameters
        
        Args:
            server: Pyo server instance (uses default if None)
        """
        self.server = server or Server.get_server()
        
        # Parameter smoothing time
        self.smooth_time = 0.02
        
        # Input mixer for voice sends
        self.input = Sig(0)
        
        # Reverb parameters with smoothing
        self.mix_sig = Sig(0.3)  # Wet/dry mix (0-1)
        self.mix = SigTo(self.mix_sig, time=self.smooth_time)
        
        self.room_sig = Sig(0.5)  # Room size (0-1)
        self.room = SigTo(self.room_sig, time=self.smooth_time)
        
        self.damp_sig = Sig(0.5)  # Damping (0-1)
        self.damp = SigTo(self.damp_sig, time=self.smooth_time)
        
        # Freeverb processor
        # size: room size, damp: damping, bal: stereo spread (1=mono)
        self.reverb = Freeverb(
            self.input,
            size=self.room,
            damp=self.damp,
            bal=1  # Mono for now
        )
        
        # Mix control (dry/wet)
        self.dry = self.input * (1 - self.mix)
        self.wet = self.reverb * self.mix
        self.output = self.dry + self.wet
    
    def set_input(self, signal):
        """Set the input signal (sum of voice sends)"""
        self.input.value = signal
    
    def set_mix(self, mix):
        """Set wet/dry mix (0-1)"""
        mix = max(0.0, min(1.0, float(mix)))
        self.mix_sig.value = mix
    
    def set_room(self, room):
        """Set room size (0-1)"""
        room = max(0.0, min(1.0, float(room)))
        self.room_sig.value = room
    
    def set_damp(self, damp):
        """Set damping (0-1)"""
        damp = max(0.0, min(1.0, float(damp)))
        self.damp_sig.value = damp
    
    def get_output(self):
        """Get the reverb output signal"""
        return self.output
    
    def get_status(self):
        """Get current reverb status"""
        return {
            'mix': self.mix_sig.value,
            'room': self.room_sig.value,
            'damp': self.damp_sig.value
        }


class DelayBus:
    """
    Global delay bus with feedback
    Receives sends from all voices
    """
    
    def __init__(self, server=None):
        """
        Initialize delay with smoothed parameters and safe feedback limits
        
        Args:
            server: Pyo server instance (uses default if None)
        """
        self.server = server or Server.get_server()
        
        # Parameter smoothing time
        self.smooth_time = 0.02
        
        # Input mixer for voice sends
        self.input = Sig(0)
        
        # Delay parameters with smoothing
        self.time_sig = Sig(0.25)  # Delay time in seconds (0.1-0.6)
        self.time = SigTo(self.time_sig, time=self.smooth_time)
        
        self.feedback_sig = Sig(0.4)  # Feedback amount (0-0.7 for safety)
        self.feedback = SigTo(self.feedback_sig, time=self.smooth_time)
        
        self.mix_sig = Sig(0.3)  # Wet/dry mix (0-1)
        self.mix = SigTo(self.mix_sig, time=self.smooth_time)
        
        # Optional filter parameters for delay color
        self.lowcut_sig = Sig(100.0)  # High-pass in feedback loop
        self.lowcut = SigTo(self.lowcut_sig, time=self.smooth_time)
        
        self.highcut_sig = Sig(5000.0)  # Low-pass in feedback loop
        self.highcut = SigTo(self.highcut_sig, time=self.smooth_time)
        
        # Delay line with feedback
        # Using SmoothDelay for click-free time changes
        self.delay = SmoothDelay(
            self.input,
            delay=self.time,
            feedback=self.feedback,
            maxdelay=1.0  # Maximum 1 second delay
        )
        
        # Optional filtering in feedback path for "analog" character
        self.delay_filtered = Biquad(
            self.delay,
            freq=self.highcut,
            q=0.7,
            type=0  # Lowpass
        )
        
        # High-pass to prevent low frequency buildup
        self.delay_filtered = Biquad(
            self.delay_filtered,
            freq=self.lowcut,
            q=0.7,
            type=1  # Highpass
        )
        
        # Mix control (dry/wet)
        self.dry = self.input * (1 - self.mix)
        self.wet = self.delay_filtered * self.mix
        self.output = self.dry + self.wet
    
    def set_input(self, signal):
        """Set the input signal (sum of voice sends)"""
        self.input.value = signal
    
    def set_time(self, time):
        """Set delay time in seconds (0.1-0.6)"""
        time = max(0.1, min(0.6, float(time)))
        self.time_sig.value = time
    
    def set_feedback(self, feedback):
        """Set feedback amount (0-0.7 for safety)"""
        feedback = max(0.0, min(0.7, float(feedback)))
        self.feedback_sig.value = feedback
    
    def set_mix(self, mix):
        """Set wet/dry mix (0-1)"""
        mix = max(0.0, min(1.0, float(mix)))
        self.mix_sig.value = mix
    
    def set_lowcut(self, freq):
        """Set high-pass filter frequency in feedback (20-1000 Hz)"""
        freq = max(20.0, min(1000.0, float(freq)))
        self.lowcut_sig.value = freq
    
    def set_highcut(self, freq):
        """Set low-pass filter frequency in feedback (1000-10000 Hz)"""
        freq = max(1000.0, min(10000.0, float(freq)))
        self.highcut_sig.value = freq
    
    def get_output(self):
        """Get the delay output signal"""
        return self.output
    
    def get_status(self):
        """Get current delay status"""
        return {
            'time': self.time_sig.value,
            'feedback': self.feedback_sig.value,
            'mix': self.mix_sig.value,
            'lowcut': self.lowcut_sig.value,
            'highcut': self.highcut_sig.value
        }