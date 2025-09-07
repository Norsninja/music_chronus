"""
INCREMENTAL BUILD - Acid Filter built step by step
Each test level adds one more component to isolate the problem
"""

from pyo import *

class AcidFilter:
    """
    Incremental acid - uncomment one level at a time
    """
    
    def __init__(self, input_signal, voice_id="acid1", server=None):
        """
        Initialize acid incrementally
        """
        self.voice_id = voice_id
        self.server = server or Server.get_server()
        self.input_signal = input_signal
        
        # Parameter smoothing time
        self.smooth_time = 0.02
        
        # === LEVEL 1: Just pass through (WORKS) ===
        # self.output = self.input_signal
        
        # === LEVEL 2: Add wet/dry mix parameters ===
        self.mix_sig = Sig(1.0)  # Start fully wet
        self.mix = SigTo(self.mix_sig, time=self.smooth_time)
        
        # Test explicit linear mix
        self.dry_factor = 1.0 - self.mix
        self.wet_factor = self.mix
        
        # === LEVEL 3: Add Disto ===
        self.drive_sig = Sig(0.2)
        self.drive = SigTo(self.drive_sig, time=self.smooth_time)
        self.disto_drive = self.drive * 0.5 + 0.5  # 0.5-1.0 range
        self.disto_slope = -self.drive * 0.20 + 0.92  # 0.92-0.72
        
        self.distortion = Disto(
            self.input_signal,
            drive=self.disto_drive,
            slope=self.disto_slope,
            mul=1.0
        )
        
        # === TEST: Add post-drive compensation ===
        self.post_drive_trim = 1.0 / (1.0 + self.drive * 0.8)
        self.drive_compensated = self.distortion * self.post_drive_trim
        
        # === LEVEL 4: Add MoogLP ===
        self.cutoff_sig = Sig(1500.0)
        self.cutoff = SigTo(self.cutoff_sig, time=self.smooth_time)
        self.res_sig = Sig(0.45)
        self.res = SigTo(self.res_sig, time=self.smooth_time)
        
        # === LEVEL 5: Add envelope modulation ===
        self.env_amount_sig = Sig(2500.0)
        self.env_amount = SigTo(self.env_amount_sig, time=self.smooth_time)
        
        self.main_env = Adsr(
            attack=0.001,
            decay=0.25,
            sustain=0.0,
            release=0.01,
            dur=0,
            mul=1.0
        )
        self.main_env.setExp(0.75)
        
        # === TEST: Add accent envelope (but don't use it yet) ===
        self.accent_sig = Sig(0.0)  # 0-1, normally controlled by sequencer
        self.accent = SigTo(self.accent_sig, time=0.001)  # Very fast for step accuracy
        
        self.accent_env = Adsr(
            attack=0.001,
            decay=0.08,  # Shorter than main
            sustain=0.0,
            release=0.01,
            dur=0,
            mul=1.0
        )
        self.accent_env.setExp(0.75)
        
        # === FIX: Simplify accent modulation to avoid signal graph break ===
        # For now, just use main envelope (accent feature disabled)
        # The complex accent calculation was breaking the signal flow
        
        # Simple version without accent for now
        self.cutoff_mod = self.cutoff + self.main_env * self.env_amount
        self.cutoff_clipped = Clip(self.cutoff_mod, min=80.0, max=5000.0)
        
        # === TEST: Add resonance scaling (HPF proxy) ===
        # This reduces resonance at low cutoffs, mimicking 303's HPF in feedback
        self.res_scale = Clip(self.cutoff_clipped / 400.0, min=0.0, max=1.0) * 0.8 + 0.2
        self.res_eff = Clip(self.res * self.res_scale, min=0.0, max=0.98)
        
        self.filter = MoogLP(
            self.drive_compensated,  # Use compensated signal instead of raw distortion
            freq=self.cutoff_clipped,  # Now using modulated cutoff
            res=self.res_eff  # Use scaled resonance instead of raw
        )
        
        # === LEVEL 6: Add post-filter clipping for safety ===
        self.clipped = Clip(self.filter, min=-0.98, max=0.98)
        self.output = self.input_signal * self.dry_factor + self.clipped * self.wet_factor
        
        print(f"[INCREMENTAL ACID] Level 6: Full chain with clipping")
        
    def gate(self, state):
        """Trigger envelopes if they exist"""
        if hasattr(self, 'main_env'):
            if state > 0:
                self.main_env.play()
                if hasattr(self, 'accent_env'):
                    self.accent_env.play()
            else:
                self.main_env.stop()
                if hasattr(self, 'accent_env'):
                    self.accent_env.stop()
    
    def set_cutoff(self, freq):
        """Set cutoff if it exists"""
        if hasattr(self, 'cutoff_sig'):
            freq = max(80.0, min(5000.0, float(freq)))
            self.cutoff_sig.value = freq
    
    def set_res(self, res):
        """Set resonance if it exists"""
        if hasattr(self, 'res_sig'):
            res = max(0.0, min(0.98, float(res)))
            self.res_sig.value = res
    
    def set_env_amount(self, amount):
        """Set envelope amount if it exists"""
        if hasattr(self, 'env_amount_sig'):
            amount = max(0.0, min(5000.0, float(amount)))
            self.env_amount_sig.value = amount
    
    def set_decay(self, decay):
        """Set decay if envelope exists"""
        if hasattr(self, 'main_env'):
            decay = max(0.02, min(1.0, float(decay)))
            self.main_env.decay = decay
    
    def set_accent(self, accent):
        """Stub for now"""
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
        """Set drive if it exists"""
        if hasattr(self, 'drive_sig'):
            drive = max(0.0, min(1.0, float(drive)))
            self.drive_sig.value = drive
    
    def set_mix(self, mix):
        """Set wet/dry mix"""
        if hasattr(self, 'mix_sig'):
            mix = max(0.0, min(1.0, float(mix)))
            self.mix_sig.value = mix
    
    def set_vol_comp(self, comp):
        """Stub"""
        pass
    
    def get_output(self):
        """Get the output signal"""
        return self.output
    
    def get_status(self):
        """Get status"""
        return {
            'voice_id': self.voice_id,
            'incremental_level': 2
        }