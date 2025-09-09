"""
Master Limiter Module for Music Chronus
Prevents clipping and protects against audio spikes
"""

from pyo import *

class LimiterModule:
    """
    Master limiter to prevent clipping and protect audio engine
    Uses PyO's Compress with high ratio for limiting
    """
    
    def __init__(self, input_signal, module_id="limiter1", thresh=-3, ratio=20):
        """
        Initialize master limiter
        
        Args:
            input_signal: Audio signal to limit
            module_id: Unique identifier for this module
            thresh: Threshold in dB (default -3dB for headroom)
            ratio: Compression ratio (20:1 acts as limiter)
        """
        self.input = input_signal
        self.module_id = module_id
        
        # Compress with high ratio = limiter
        # thresh: -3dB gives headroom before clipping
        # ratio: 20:1 is effectively limiting
        # risetime: 0.005s fast attack to catch transients
        # falltime: 0.05s smooth release
        self.limiter = Compress(
            input=self.input,
            thresh=thresh,    # Threshold in dB
            ratio=ratio,      # 20:1 = limiting
            risetime=0.005,   # 5ms attack (fast for transients)
            falltime=0.05,    # 50ms release (smooth)
            lookahead=5.0,    # 5ms lookahead for better transient handling
            knee=0,           # Hard knee for true limiting (integer)
            outputAmp=False,  # Don't normalize output (boolean)
            mul=1,            # Unity gain
            add=0             # No DC offset
        )
        
        # Output is the limited signal
        self.output = self.limiter
        
        print(f"[LIMITER] Master limiter active: thresh={thresh}dB, ratio={ratio}:1")
        
    def set_threshold(self, thresh_db):
        """Set limiter threshold in dB"""
        self.limiter.setThresh(thresh_db)
        print(f"[LIMITER] Threshold set to {thresh_db}dB")
        
    def get_schema(self):
        """Get parameter schema for this module"""
        return {
            "name": f"Master Limiter ({self.module_id})",
            "type": "limiter",
            "params": {
                "threshold": {"type": "float", "min": -20, "max": 0, "default": -3, "unit": "dB"},
                "ratio": {"type": "float", "min": 4, "max": 100, "default": 20, "notes": "20:1+ for limiting"},
                "attack": {"type": "float", "min": 0.001, "max": 0.1, "default": 0.005, "unit": "seconds"},
                "release": {"type": "float", "min": 0.01, "max": 1.0, "default": 0.05, "unit": "seconds"}
            },
            "notes": "Master limiter prevents clipping and protects audio engine"
        }