"""
Acid Filter Module for Music Chronus
TB-303 style resonant lowpass filter with envelope modulation
Uses MoogLP for authentic ladder filter character
"""

from pyo import *
import time

class AcidFilter:
    """
    TB-303 style acid filter insert for voice processing
    
    Signal flow: Input -> Disto (drive) -> MoogLP (modulated) -> Trim/Clip -> Mix -> Output
    
    Features:
    - Dual envelope system (main + accent)
    - Pre-filter drive for classic 303 bite
    - Resonance compensation for stable levels
    - Cutoff-dependent resonance scaling (HPF proxy)
    - Accent affects cutoff, resonance, envelope, and amplitude
    """
    
    def __init__(self, input_signal, voice_id="acid1", server=None):
        """
        Initialize acid filter with smoothed parameters
        
        Args:
            input_signal: PyoObject audio input (typically from a voice)
            voice_id: Identifier for this acid instance
            server: Pyo server instance
        """
        self.voice_id = voice_id
        self.server = server or Server.get_server()
        self.input_signal = input_signal
        
        # Parameter smoothing time (20ms as per spec)
        self.smooth_time = 0.02
        
        # Base filter parameters with smoothing (brighter defaults per Senior Dev)
        self.cutoff_sig = Sig(1500.0)  # 80-5000 Hz (was 500, now brighter)
        self.cutoff = SigTo(self.cutoff_sig, time=self.smooth_time)
        
        self.res_sig = Sig(0.45)  # 0-0.98 (was 0.4, slightly more resonance)
        self.res = SigTo(self.res_sig, time=self.smooth_time)
        
        self.env_amount_sig = Sig(2500.0)  # 0-5000 Hz modulation depth (was 1500, more sweep)
        self.env_amount = SigTo(self.env_amount_sig, time=self.smooth_time)
        
        # Decay is not smoothed - ADSR params update instantly
        self.decay_sig = Sig(0.25)  # 0.02-1.0 seconds (for status tracking)
        
        # Accent parameters
        self.accent_sig = Sig(0.0)  # 0-1, set by sequencer
        self.accent = SigTo(self.accent_sig, time=0.001)  # Very fast for step accuracy
        
        self.cutoff_offset_sig = Sig(500.0)  # 0-1000 Hz accent boost
        self.cutoff_offset = SigTo(self.cutoff_offset_sig, time=self.smooth_time)
        
        self.res_accent_boost_sig = Sig(0.3)  # 0-0.4 extra resonance
        self.res_accent_boost = SigTo(self.res_accent_boost_sig, time=self.smooth_time)
        
        # Accent decay is not smoothed - ADSR params update instantly
        self.accent_decay_sig = Sig(0.08)  # 0.02-0.15 seconds (for status tracking)
        
        # Drive and mix parameters
        self.drive_sig = Sig(0.2)  # 0-1 prefilter drive
        self.drive = SigTo(self.drive_sig, time=self.smooth_time)
        
        self.mix_sig = Sig(1.0)  # 0-1 wet/dry
        self.mix = SigTo(self.mix_sig, time=self.smooth_time)
        
        # Volume compensation
        self.vol_comp_sig = Sig(0.5)  # 0-1 resonance compensation factor
        self.vol_comp = SigTo(self.vol_comp_sig, time=self.smooth_time)
        
        # Accent weight for envelope mix
        self.accent_weight = 1.0  # Weight for accent envelope mix
        
        # Create envelopes
        self.setup_envelopes()
        
        # Create signal chain
        self.setup_signal_chain()
        
    def setup_envelopes(self):
        """Create main and accent envelopes with exponential curves"""
        
        # Get initial numeric values for envelope times
        decay_default = 0.25  # Default main decay
        accent_decay_default = 0.08  # Default accent decay
        
        # Main envelope (user-controlled decay)
        self.main_env = Adsr(
            attack=0.001,  # 1ms for slight chirp
            decay=decay_default,  # Initial numeric value
            sustain=0.0,  # Full decay to 0
            release=0.01,  # 10ms release
            dur=0,  # Infinite (gate controlled)
            mul=1.0
        )
        # Exponential curve for natural sweep
        self.main_env.setExp(0.75)
        
        # Accent envelope (short, punchy)
        self.accent_env = Adsr(
            attack=0.001,  # 1ms
            decay=accent_decay_default,  # Initial numeric value
            sustain=0.0,
            release=0.01,
            dur=0,
            mul=1.0
        )
        self.accent_env.setExp(0.75)
        
    def setup_signal_chain(self):
        """Build the DSP chain: Disto -> MoogLP -> Trim/Clip -> Mix"""
        
        # Pre-filter drive (Disto for 303 bite)
        # Map drive param 0-1 to musical ranges using PyoObject arithmetic
        self.disto_drive = self.drive * 0.5 + 0.5  # 0.5-1.0 range (PyoObject)
        self.disto_slope = -self.drive * 0.20 + 0.92  # 0.92-0.72 (softer knee with more drive)
        
        self.distortion = Disto(
            self.input_signal,
            drive=self.disto_drive,
            slope=self.disto_slope,
            mul=1.0  # Keep level consistent
        )
        
        # Post-drive compensation to prevent level jumps (PyoObject arithmetic)
        self.post_drive_trim = 1.0 / (1.0 + self.drive * 0.8)
        self.drive_compensated = self.distortion * self.post_drive_trim
        
        # Calculate envelope total (main + weighted accent)
        # Using accent parameter directly (not latched value) for v1
        self.env_total = self.main_env + (self.accent_env * self.accent * self.accent_weight)
        
        # Calculate effective cutoff with modulation (all PyoObject arithmetic)
        # cutoff_eff = clamp(80, 5000, cutoff + env_total * env_amount + accent * cutoff_offset)
        self.cutoff_eff = Clip(
            self.cutoff + self.env_total * self.env_amount + self.accent * self.cutoff_offset,
            min=80.0,
            max=5000.0
        )
        
        # Calculate resonance scaling (HPF proxy)
        # res_scale = 0.2 + 0.8 * min(1, cutoff_eff/400)
        # This reduces resonance at low cutoffs, mimicking 303's HPF in feedback
        self.res_scale = Clip(self.cutoff_eff / 400.0, min=0.0, max=1.0) * 0.8 + 0.2
        
        # Calculate effective resonance with scaling and accent boost (PyoObject arithmetic)
        self.res_eff = Clip(
            self.res * self.res_scale + self.accent * self.res_accent_boost,
            min=0.0,
            max=0.98
        )
        
        # MoogLP ladder filter (the heart of the acid sound)
        self.filter = MoogLP(
            self.drive_compensated,
            freq=self.cutoff_eff,
            res=self.res_eff
        )
        
        # Resonance compensation (prevent volume drop with high resonance)
        self.res_compensation = 1.0 - (self.res_eff * self.vol_comp)
        self.filter_compensated = self.filter * self.res_compensation
        
        # Accent amplitude boost (+2.5dB = 1.33x when accent=1)
        # Using accent parameter directly for v1 (no latching needed)
        self.accent_gain = 1.0 + self.accent * 0.33
        self.filter_with_accent = self.filter_compensated * self.accent_gain
        
        # Post-filter soft clip for safety (prevent peaks)
        self.clipped = Clip(self.filter_with_accent, min=-0.98, max=0.98)
        
        # Wet/dry mix using explicit linear mix (more reliable than Interp)
        # out = dry * (1 - mix) + wet * mix
        self.dry_factor = 1.0 - self.mix
        self.wet_factor = self.mix
        self.output = self.input_signal * self.dry_factor + self.clipped * self.wet_factor
        
    def gate(self, state):
        """
        Trigger or release the envelopes
        Note: v1 uses accent parameter directly (no latching)
        """
        if state > 0:
            # Gate on - trigger both envelopes
            self.main_env.play()
            self.accent_env.play()
        else:
            # Gate off - trigger release
            self.main_env.stop()
            self.accent_env.stop()
    
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
    
    def set_accent(self, accent):
        """Set accent level (0-1) - typically set by sequencer"""
        accent = max(0.0, min(1.0, float(accent)))
        self.accent_sig.value = accent
    
    def set_cutoff_offset(self, offset):
        """Set accent cutoff boost (0-1000 Hz)"""
        offset = max(0.0, min(1000.0, float(offset)))
        self.cutoff_offset_sig.value = offset
    
    def set_res_accent_boost(self, boost):
        """Set accent resonance boost (0-0.4)"""
        boost = max(0.0, min(0.4, float(boost)))
        self.res_accent_boost_sig.value = boost
    
    def set_accent_decay(self, decay):
        """Set accent envelope decay (0.02-0.15 seconds)"""
        decay = max(0.02, min(0.15, float(decay)))
        self.accent_decay_sig.value = decay
        # Update the accent ADSR with numeric value
        self.accent_env.decay = decay
    
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
            'accent': self.accent_sig.value,
            'cutoff_offset': self.cutoff_offset_sig.value,
            'res_accent_boost': self.res_accent_boost_sig.value,
            'accent_decay': self.accent_decay_sig.value,
            'drive': self.drive_sig.value,
            'mix': self.mix_sig.value,
            'vol_comp': self.vol_comp_sig.value
        }