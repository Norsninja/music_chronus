"""
Distortion module for Music Chronus
Master insert distortion with drive, mix, and tone controls
Uses pyo's Disto object for efficient waveshaping
"""

from pyo import *

class DistortionModule:
    """
    Master distortion insert with transparent mix control
    Chain: Input -> Disto -> Tone Control -> Mix
    """
    
    def __init__(self, input_sig, module_id="dist1", server=None):
        """
        Initialize distortion module as master insert
        
        Args:
            input_sig: Input signal (typically from voice mixer)
            module_id: Identifier for this module (default "dist1")
            server: Pyo server instance (uses default if None)
        """
        self.module_id = module_id
        self.server = server  # Server instance not needed for this module
        self.input = input_sig
        
        # Parameter smoothing time (20ms for zipper-free control)
        self.smooth_time = 0.02
        
        # Drive control (0-1, where 0 = clean, 1 = heavily distorted)
        self.drive_sig = Sig(0.0)
        self.drive = SigTo(self.drive_sig, time=self.smooth_time)
        
        # Mix control (0-1, dry/wet mix)
        self.mix_sig = Sig(0.0)
        self.mix = SigTo(self.mix_sig, time=self.smooth_time)
        
        # Tone control (0-1, where 0 = dark, 0.5 = neutral, 1 = bright)
        self.tone_sig = Sig(0.5)
        self.tone = SigTo(self.tone_sig, time=self.smooth_time)
        
        # Distortion processing using pyo's efficient Disto object
        # Disto uses waveshaping: y = (1 + k) * x / (1 + k * abs(x))
        # 4x faster than tanh/atan2 methods
        self.distorted = Disto(
            self.input,
            drive=self.drive,
            slope=0.9,  # Fixed slope for consistent character
            mul=1.0
        )
        
        # Tone control using complementary filters
        # Low-pass for removing harshness
        self.tone_lp_freq = Scale(self.tone, inmin=0, inmax=1, outmin=1000, outmax=8000)
        self.tone_lp = ButLP(self.distorted, freq=self.tone_lp_freq)
        
        # High-pass for removing muddiness
        self.tone_hp_freq = Scale(self.tone, inmin=0, inmax=1, outmin=500, outmax=100)
        self.tone_hp = ButHP(self.tone_lp, freq=self.tone_hp_freq)
        
        # Post-distortion gain compensation
        # Reduces volume slightly as drive increases to maintain consistent loudness
        self.comp_gain = Scale(self.drive, inmin=0, inmax=1, outmin=1.0, outmax=0.7)
        self.compensated = self.tone_hp * self.comp_gain
        
        # Equal-loudness mixing (uses sqrt for perceptual balance)
        # This prevents volume jumps when changing mix
        self.dry_gain = Sqrt(1 - self.mix)
        self.wet_gain = Sqrt(self.mix)
        
        # Final mixed output
        self.dry_path = self.input * self.dry_gain
        self.wet_path = self.compensated * self.wet_gain
        self.output = self.dry_path + self.wet_path
        
    def set_drive(self, drive):
        """Set distortion drive amount (0-1)
        
        0.0-0.2: Subtle warmth
        0.2-0.5: Moderate crunch
        0.5-0.8: Heavy distortion
        0.8-1.0: Extreme saturation
        """
        drive = max(0.0, min(1.0, float(drive)))
        self.drive_sig.value = drive
    
    def set_mix(self, mix):
        """Set wet/dry mix (0-1)
        
        0: Completely dry (bypass)
        0.5: Equal mix
        1: Completely wet
        """
        mix = max(0.0, min(1.0, float(mix)))
        self.mix_sig.value = mix
    
    def set_tone(self, tone):
        """Set tone control (0-1)
        
        0: Dark (more low-pass)
        0.5: Neutral
        1: Bright (less low-pass)
        """
        tone = max(0.0, min(1.0, float(tone)))
        self.tone_sig.value = tone
    
    def get_status(self):
        """Get current module status"""
        return {
            'module_id': self.module_id,
            'drive': self.drive_sig.value,
            'mix': self.mix_sig.value,
            'tone': self.tone_sig.value
        }
    
    def get_schema(self):
        """Get parameter schema for this module"""
        return {
            "name": f"Distortion ({self.module_id})",
            "type": "distortion",
            "params": {
                "drive": {
                    "type": "float", 
                    "min": 0, 
                    "max": 1, 
                    "default": 0.0, 
                    "smoothing_ms": 20,
                    "notes": "0-0.2: warmth, 0.2-0.5: crunch, 0.5-1.0: heavy"
                },
                "mix": {
                    "type": "float", 
                    "min": 0, 
                    "max": 1, 
                    "default": 0.0, 
                    "smoothing_ms": 20,
                    "notes": "Dry/wet mix with equal-loudness compensation"
                },
                "tone": {
                    "type": "float", 
                    "min": 0, 
                    "max": 1, 
                    "default": 0.5, 
                    "smoothing_ms": 20,
                    "notes": "0=dark, 0.5=neutral, 1=bright"
                }
            },
            "notes": "Master insert distortion using pyo Disto (4x faster than tanh)"
        }