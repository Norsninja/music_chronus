"""
WORKING Acid Filter Module for Music Chronus
TB-303 style resonant lowpass filter with envelope modulation
Based on our debugging - accent system simplified to avoid signal graph breaks
"""

from pyo import *

class AcidFilter:
    """
    TB-303 style acid filter (WORKING VERSION)
    
    Signal flow: Input -> Disto -> MoogLP (modulated) -> Clip -> Mix -> Output
    
    Features:
    - Envelope modulation of cutoff
    - Pre-filter drive for 303 bite
    - Resonance scaling based on cutoff (HPF proxy)
    - Post-drive compensation
    - Wet/dry mix control
    
    Note: Accent system disabled as it breaks signal graph
    """
    
    def __init__(self, input_signal, voice_id="acid1", server=None):
        """
        Initialize acid filter with smoothed parameters
        """
        self.voice_id = voice_id
        self.server = server or Server.get_server()
        self.input_signal = input_signal
        
        # Parameter smoothing time
        self.smooth_time = 0.02
        
        # Base filter parameters with smoothing (brighter defaults)
        self.cutoff_sig = Sig(1500.0)  # 80-5000 Hz
        self.cutoff = SigTo(self.cutoff_sig, time=self.smooth_time)
        
        self.res_sig = Sig(0.45)  # 0-0.98
        self.res = SigTo(self.res_sig, time=self.smooth_time)
        
        self.env_amount_sig = Sig(2500.0)  # 0-5000 Hz modulation depth
        self.env_amount = SigTo(self.env_amount_sig, time=self.smooth_time)
        
        # Decay is not smoothed - ADSR params update instantly
        self.decay_sig = Sig(0.25)  # For status tracking
        
        # Drive and mix parameters
        self.drive_sig = Sig(0.2)  # 0-1 prefilter drive
        self.drive = SigTo(self.drive_sig, time=self.smooth_time)
        
        self.mix_sig = Sig(1.0)  # 0-1 wet/dry
        self.mix = SigTo(self.mix_sig, time=self.smooth_time)
        
        # Volume compensation
        self.vol_comp_sig = Sig(0.5)  # 0-1 resonance compensation factor
        self.vol_comp = SigTo(self.vol_comp_sig, time=self.smooth_time)
        
        # Create main envelope
        self.main_env = Adsr(
            attack=0.001,  # 1ms for slight chirp
            decay=0.25,    # Default decay
            sustain=0.0,   # Full decay to 0
            release=0.01,  # 10ms release
            dur=0,         # Infinite (gate controlled)
            mul=1.0
        )
        self.main_env.setExp(0.75)  # Exponential curve for natural sweep
        
        # Build DSP chain
        self.setup_signal_chain()
        
    def setup_signal_chain(self):
        """Build the DSP chain: Disto -> MoogLP -> Clip -> Mix"""
        
        # Pre-filter drive (Disto for 303 bite)
        self.disto_drive = self.drive * 0.5 + 0.5  # 0.5-1.0 range
        self.disto_slope = -self.drive * 0.20 + 0.92  # 0.92-0.72
        
        self.distortion = Disto(
            self.input_signal,
            drive=self.disto_drive,
            slope=self.disto_slope,
            mul=1.0
        )
        
        # Post-drive compensation to prevent level jumps
        self.post_drive_trim = 1.0 / (1.0 + self.drive * 0.8)
        self.drive_compensated = self.distortion * self.post_drive_trim
        
        # Calculate effective cutoff with modulation
        self.cutoff_mod = self.cutoff + self.main_env * self.env_amount
        self.cutoff_clipped = Clip(self.cutoff_mod, min=80.0, max=5000.0)
        
        # Calculate resonance scaling (HPF proxy)
        # Reduces resonance at low cutoffs, mimicking 303's HPF in feedback
        self.res_scale = Clip(self.cutoff_clipped / 400.0, min=0.0, max=1.0) * 0.8 + 0.2
        self.res_eff = Clip(self.res * self.res_scale, min=0.0, max=0.98)
        
        # MoogLP ladder filter (the heart of the acid sound)
        self.filter = MoogLP(
            self.drive_compensated,
            freq=self.cutoff_clipped,
            res=self.res_eff
        )
        
        # Resonance compensation (prevent volume drop with high resonance)
        self.res_compensation = 1.0 - (self.res_eff * self.vol_comp)
        self.filter_compensated = self.filter * self.res_compensation
        
        # Post-filter soft clip for safety
        self.clipped = Clip(self.filter_compensated, min=-0.98, max=0.98)
        
        # Wet/dry mix using explicit linear mix
        self.dry_factor = 1.0 - self.mix
        self.wet_factor = self.mix
        self.output = self.input_signal * self.dry_factor + self.clipped * self.wet_factor
        
    def gate(self, state):
        """Trigger or release the envelope"""
        if state > 0:
            self.main_env.play()
        else:
            self.main_env.stop()
    
    def set_cutoff(self, freq):
        """Set base cutoff frequency (80-5000 Hz)"""
        freq = max(80.0, min(5000.0, float(freq)))
        self.cutoff_sig.value = freq
    
    def set_res(self, res):
        """Set base resonance (0-0.98)"""
        res = max(0.0, min(0.98, float(res)))
        self.res_sig.value = res
    
    def set_env_amount(self, amount):
        """Set envelope modulation depth (0-5000 Hz)"""
        amount = max(0.0, min(5000.0, float(amount)))
        self.env_amount_sig.value = amount
    
    def set_decay(self, decay):
        """Set main envelope decay time (0.02-1.0 seconds)"""
        decay = max(0.02, min(1.0, float(decay)))
        self.decay_sig.value = decay
        # Update the ADSR directly with numeric value
        self.main_env.decay = decay
    
    def set_drive(self, drive):
        """Set pre-filter drive amount (0-1)"""
        drive = max(0.0, min(1.0, float(drive)))
        self.drive_sig.value = drive
    
    def set_mix(self, mix):
        """Set wet/dry mix (0-1)"""
        mix = max(0.0, min(1.0, float(mix)))
        self.mix_sig.value = mix
    
    def set_vol_comp(self, comp):
        """Set resonance volume compensation (0-1)"""
        comp = max(0.0, min(1.0, float(comp)))
        self.vol_comp_sig.value = comp
    
    # Stub methods for accent (not implemented to avoid signal breaks)
    def set_accent(self, accent):
        """Accent not implemented in working version"""
        pass
    
    def set_cutoff_offset(self, offset):
        """Accent not implemented"""
        pass
    
    def set_res_accent_boost(self, boost):
        """Accent not implemented"""
        pass
    
    def set_accent_decay(self, decay):
        """Accent not implemented"""
        pass
    
    def get_output(self):
        """Get the processed output signal"""
        return self.output
    
    def get_status(self):
        """Get current acid filter status"""
        return {
            'voice_id': self.voice_id,
            'cutoff': self.cutoff_sig.value,
            'res': self.res_sig.value,
            'env_amount': self.env_amount_sig.value,
            'decay': self.decay_sig.value,
            'drive': self.drive_sig.value,
            'mix': self.mix_sig.value,
            'vol_comp': self.vol_comp_sig.value,
            'accent_disabled': True
        }