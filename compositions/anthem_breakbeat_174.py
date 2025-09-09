#!/usr/bin/env python3
"""
Anthem-Style Breakbeat Composition at 174 BPM
Music Chronus - Epic DnB Anthem Generator

Uses all 4 available voices for maximum impact:
- Voice 1: Kick drum (deep sub frequencies 43-50Hz)
- Voice 2: Sub bass with acid filter (saw wave simulation with formants)
- Voice 3: Snare (white noise simulation via high-Q filter)
- Voice 4: Hi-hats and atmospheric elements

Structure: Intro -> Drop -> Breakdown -> Build -> Final Drop
Total runtime: ~3 minutes of pure anthem energy
"""

from pythonosc import udp_client
import time
import math

# Initialize OSC client
client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

# Global BPM and timing calculations
BPM = 174
BEAT_DURATION = 60.0 / BPM  # ~0.345 seconds per beat
SIXTEENTH_NOTE = BEAT_DURATION / 4  # ~0.086 seconds per 16th note

def setup_engine():
    """Initialize the engine and set up basic parameters"""
    print("🎵 Initializing Music Chronus Engine...")
    client.send_message("/engine/start", 1)
    time.sleep(0.5)
    
    # Set global effects
    client.send_message("/mod/reverb1/mix", 0.4)
    client.send_message("/mod/reverb1/room", 0.7)
    client.send_message("/mod/reverb1/damp", 0.3)
    
    client.send_message("/mod/delay1/time", 0.25)
    client.send_message("/mod/delay1/feedback", 0.6)
    client.send_message("/mod/delay1/mix", 0.3)
    
    print("✅ Engine initialized with epic reverb and delay")

def configure_voice1_kick():
    """Configure Voice 1 as deep kick drum"""
    # Deep sub-bass kick configuration
    client.send_message("/mod/voice1/freq", 47.0)  # Deep sub frequency
    client.send_message("/mod/voice1/amp", 0.9)
    client.send_message("/mod/voice1/filter/freq", 120.0)  # Low-pass for thump
    client.send_message("/mod/voice1/filter/q", 1.5)
    
    # Punchy ADSR for kick
    client.send_message("/mod/voice1/adsr/attack", 0.001)
    client.send_message("/mod/voice1/adsr/decay", 0.15)
    client.send_message("/mod/voice1/adsr/sustain", 0.2)
    client.send_message("/mod/voice1/adsr/release", 0.3)
    
    # Minimal reverb for kick
    client.send_message("/mod/voice1/send/reverb", 0.1)
    client.send_message("/mod/voice1/send/delay", 0.0)

def configure_voice2_bass():
    """Configure Voice 2 as acid sub bass"""
    # Sub bass with acid filter
    client.send_message("/mod/voice2/freq", 41.2)  # E1
    client.send_message("/mod/voice2/amp", 0.7)
    client.send_message("/mod/voice2/filter/freq", 200.0)
    client.send_message("/mod/voice2/filter/q", 3.0)
    
    # ADSR for bass line
    client.send_message("/mod/voice2/adsr/attack", 0.01)
    client.send_message("/mod/voice2/adsr/decay", 0.2)
    client.send_message("/mod/voice2/adsr/sustain", 0.8)
    client.send_message("/mod/voice2/adsr/release", 0.1)
    
    # Acid filter setup
    client.send_message("/mod/acid1/cutoff", 800.0)
    client.send_message("/mod/acid1/res", 0.7)
    client.send_message("/mod/acid1/env_amount", 3000.0)
    client.send_message("/mod/acid1/decay", 0.3)
    client.send_message("/mod/acid1/drive", 0.4)
    client.send_message("/mod/acid1/mix", 1.0)
    
    client.send_message("/mod/voice2/send/reverb", 0.2)
    client.send_message("/mod/voice2/send/delay", 0.1)

def configure_voice3_snare():
    """Configure Voice 3 as snare/noise percussion"""
    # High frequency with high Q to simulate noise
    client.send_message("/mod/voice3/freq", 220.0)
    client.send_message("/mod/voice3/amp", 0.8)
    client.send_message("/mod/voice3/filter/freq", 2500.0)  # Bright snare
    client.send_message("/mod/voice3/filter/q", 8.0)  # High Q for noise-like character
    
    # Sharp snare ADSR
    client.send_message("/mod/voice3/adsr/attack", 0.001)
    client.send_message("/mod/voice3/adsr/decay", 0.08)
    client.send_message("/mod/voice3/adsr/sustain", 0.1)
    client.send_message("/mod/voice3/adsr/release", 0.12)
    
    client.send_message("/mod/voice3/send/reverb", 0.5)
    client.send_message("/mod/voice3/send/delay", 0.3)

def configure_voice4_hats():
    """Configure Voice 4 as hi-hats and atmosphere"""
    # High frequency for crisp hats
    client.send_message("/mod/voice4/freq", 8000.0)
    client.send_message("/mod/voice4/amp", 0.4)
    client.send_message("/mod/voice4/filter/freq", 6000.0)
    client.send_message("/mod/voice4/filter/q", 2.0)
    
    # Very short ADSR for hats
    client.send_message("/mod/voice4/adsr/attack", 0.001)
    client.send_message("/mod/voice4/adsr/decay", 0.03)
    client.send_message("/mod/voice4/adsr/sustain", 0.0)
    client.send_message("/mod/voice4/adsr/release", 0.05)
    
    client.send_message("/mod/voice4/send/reverb", 0.3)
    client.send_message("/mod/voice4/send/delay", 0.2)

def play_kick_pattern(pattern, duration):
    """Play kick drum pattern"""
    steps = len(pattern)
    step_duration = duration / steps
    
    for i, step in enumerate(pattern):
        if step in ['X', 'x']:
            # Accent for 'X', normal for 'x'
            if step == 'X':
                client.send_message("/mod/voice1/freq", 50.0)  # Slightly higher for accent
            else:
                client.send_message("/mod/voice1/freq", 47.0)
            
            client.send_message("/gate/voice1", 1.0)
            time.sleep(0.01)  # Brief gate
            client.send_message("/gate/voice1", 0.0)
        
        time.sleep(step_duration - 0.01 if step != '.' else step_duration)

def play_bass_pattern(pattern, notes, duration):
    """Play bass pattern with note progression"""
    steps = len(pattern)
    step_duration = duration / steps
    note_index = 0
    
    for i, step in enumerate(pattern):
        if step in ['X', 'x']:
            # Get current note frequency
            note_freq = notes[note_index % len(notes)]
            client.send_message("/mod/voice2/freq", note_freq)
            
            if step == 'X':
                # Accent: boost acid filter
                client.send_message("/mod/acid1/cutoff", 1500.0)
            else:
                client.send_message("/mod/acid1/cutoff", 800.0)
            
            client.send_message("/gate/voice2", 1.0)
            client.send_message("/gate/acid1", 1.0)
            
            note_index += 1
            
            time.sleep(step_duration * 0.8)  # Hold for most of the step
            client.send_message("/gate/voice2", 0.0)
            client.send_message("/gate/acid1", 0.0)
            time.sleep(step_duration * 0.2)
        else:
            time.sleep(step_duration)

def play_snare_pattern(pattern, duration):
    """Play snare pattern"""
    steps = len(pattern)
    step_duration = duration / steps
    
    for i, step in enumerate(pattern):
        if step in ['X', 'x']:
            if step == 'X':
                # Accent snare
                client.send_message("/mod/voice3/filter/freq", 3000.0)
                client.send_message("/mod/voice3/amp", 0.9)
            else:
                client.send_message("/mod/voice3/filter/freq", 2500.0)
                client.send_message("/mod/voice3/amp", 0.6)
            
            client.send_message("/gate/voice3", 1.0)
            time.sleep(0.02)
            client.send_message("/gate/voice3", 0.0)
        
        time.sleep(step_duration - 0.02 if step != '.' else step_duration)

def play_hats_pattern(pattern, duration):
    """Play hi-hats pattern"""
    steps = len(pattern)
    step_duration = duration / steps
    
    for i, step in enumerate(pattern):
        if step in ['X', 'x']:
            if step == 'X':
                client.send_message("/mod/voice4/amp", 0.6)
            else:
                client.send_message("/mod/voice4/amp", 0.3)
            
            client.send_message("/gate/voice4", 1.0)
            time.sleep(0.01)
            client.send_message("/gate/voice4", 0.0)
        
        time.sleep(step_duration - 0.01 if step != '.' else step_duration)

def intro_section():
    """Intro: Build up the energy (16 bars)"""
    print("🎼 INTRO: Building the anthem...")
    
    # Bass notes progression (E, D, F#, G, A)
    bass_notes = [41.2, 36.7, 49.0, 49.0, 55.0, 55.0, 61.7, 61.7]
    
    # Simple intro patterns
    kick_pattern = "X...X...X...X..."
    snare_pattern = "....X.......X..."
    hats_pattern = "x.x.x.x.x.x.x.X."
    
    # 4 bars minimal
    for bar in range(4):
        print(f"  Intro bar {bar + 1}/4")
        
        # Add elements progressively
        if bar >= 0:  # Kick from start
            play_kick_pattern(kick_pattern, BEAT_DURATION * 4)
        
        time.sleep(-BEAT_DURATION * 4)  # Reset timing
        
        if bar >= 1:  # Add hats
            play_hats_pattern(hats_pattern, BEAT_DURATION * 4)
        
        time.sleep(-BEAT_DURATION * 4)  # Reset timing
        
        if bar >= 2:  # Add snare
            play_snare_pattern(snare_pattern, BEAT_DURATION * 4)

def main_drop():
    """Main drop: Full energy anthem (32 bars)"""
    print("🔥 MAIN DROP: Full anthem power!")
    
    # Complex breakbeat patterns
    kick_pattern = "X...X...X.X.X..."
    bass_pattern = "X.x.X.x.X.x.X.x."
    snare_pattern = "....X.x...X.X..."
    hats_pattern = "x.x.x.X.x.x.x.X."
    
    # Anthem bass progression
    bass_notes = [41.2, 36.7, 49.0, 55.0, 61.7, 55.0, 49.0, 46.2]
    
    # 8 bars of full energy
    for bar in range(8):
        print(f"  Drop bar {bar + 1}/8 - MAXIMUM ENERGY!")
        
        # Start all patterns simultaneously using threading-like approach
        start_time = time.time()
        
        # Play all elements together (simplified version)
        for step in range(16):  # 16th notes in a bar
            step_time = start_time + (step * SIXTEENTH_NOTE)
            current_time = time.time()
            
            if current_time < step_time:
                time.sleep(step_time - current_time)
            
            # Check each pattern at this step
            if kick_pattern[step] in ['X', 'x']:
                freq = 50.0 if kick_pattern[step] == 'X' else 47.0
                client.send_message("/mod/voice1/freq", freq)
                client.send_message("/gate/voice1", 1.0)
                client.send_message("/gate/voice1", 0.0)
            
            if bass_pattern[step] in ['X', 'x']:
                note_freq = bass_notes[(bar * 2 + step // 8) % len(bass_notes)]
                client.send_message("/mod/voice2/freq", note_freq)
                cutoff = 1500.0 if bass_pattern[step] == 'X' else 800.0
                client.send_message("/mod/acid1/cutoff", cutoff)
                client.send_message("/gate/voice2", 1.0)
                client.send_message("/gate/acid1", 1.0)
            
            if snare_pattern[step] in ['X', 'x']:
                freq = 3000.0 if snare_pattern[step] == 'X' else 2500.0
                client.send_message("/mod/voice3/filter/freq", freq)
                client.send_message("/gate/voice3", 1.0)
                client.send_message("/gate/voice3", 0.0)
            
            if hats_pattern[step] in ['X', 'x']:
                amp = 0.6 if hats_pattern[step] == 'X' else 0.3
                client.send_message("/mod/voice4/amp", amp)
                client.send_message("/gate/voice4", 1.0)
                client.send_message("/gate/voice4", 0.0)

def breakdown_section():
    """Breakdown: Atmospheric section (16 bars)"""
    print("🌅 BREAKDOWN: Atmospheric tension...")
    
    # Minimal patterns for breakdown
    kick_pattern = "X.......X......."
    bass_pattern = "X.....X........."
    snare_pattern = "........X......."
    atmosphere_pattern = "x...x...x...x..."
    
    # Lower frequencies for atmosphere
    bass_notes = [27.5, 30.9, 32.7, 36.7]  # Lower octave
    
    # Reduce effects for intimate feel
    client.send_message("/mod/reverb1/mix", 0.7)
    client.send_message("/mod/delay1/feedback", 0.8)
    
    # Configure voice4 for atmospheric pads
    client.send_message("/mod/voice4/freq", 220.0)
    client.send_message("/mod/voice4/filter/freq", 1000.0)
    client.send_message("/mod/voice4/adsr/attack", 0.5)
    client.send_message("/mod/voice4/adsr/release", 2.0)
    
    for bar in range(4):
        print(f"  Breakdown bar {bar + 1}/4")
        
        start_time = time.time()
        
        for step in range(16):
            step_time = start_time + (step * SIXTEENTH_NOTE)
            current_time = time.time()
            
            if current_time < step_time:
                time.sleep(step_time - current_time)
            
            if kick_pattern[step] == 'X':
                client.send_message("/mod/voice1/freq", 45.0)
                client.send_message("/gate/voice1", 1.0)
                client.send_message("/gate/voice1", 0.0)
            
            if bass_pattern[step] == 'X':
                note_freq = bass_notes[bar % len(bass_notes)]
                client.send_message("/mod/voice2/freq", note_freq)
                client.send_message("/mod/acid1/cutoff", 600.0)
                client.send_message("/gate/voice2", 1.0)
                client.send_message("/gate/acid1", 1.0)
            
            if snare_pattern[step] == 'X':
                client.send_message("/mod/voice3/filter/freq", 2000.0)
                client.send_message("/gate/voice3", 1.0)
                client.send_message("/gate/voice3", 0.0)
            
            if atmosphere_pattern[step] == 'x':
                client.send_message("/gate/voice4", 1.0)

def buildup_section():
    """Build-up: Tension building to final drop (8 bars)"""
    print("⚡ BUILD-UP: Rising tension...")
    
    # Gradually increasing intensity
    kick_patterns = [
        "X.......X.......",
        "X...X...X...X...",
        "X.X.X.X.X.X.X.X.",
        "X.x.X.x.X.x.X.x."
    ]
    
    # Rising bass notes
    bass_notes = [36.7, 41.2, 46.2, 49.0, 55.0, 61.7, 65.4, 73.4]
    
    # Restore effects for big impact
    client.send_message("/mod/reverb1/mix", 0.5)
    client.send_message("/mod/delay1/feedback", 0.6)
    
    for bar in range(4):
        print(f"  Build-up bar {bar + 1}/4 - Intensity: {(bar + 1) * 25}%")
        
        kick_pattern = kick_patterns[bar]
        
        # Increase filter cutoff gradually
        cutoff = 800 + (bar * 400)
        client.send_message("/mod/acid1/cutoff", cutoff)
        
        start_time = time.time()
        
        for step in range(16):
            step_time = start_time + (step * SIXTEENTH_NOTE)
            current_time = time.time()
            
            if current_time < step_time:
                time.sleep(step_time - current_time)
            
            if kick_pattern[step] in ['X', 'x']:
                freq = 48.0 + (bar * 2)  # Rising kick frequency
                client.send_message("/mod/voice1/freq", freq)
                client.send_message("/gate/voice1", 1.0)
                client.send_message("/gate/voice1", 0.0)
            
            # Add bass every 4th step with rising notes
            if step % 4 == 0:
                note_freq = bass_notes[(bar * 4 + step // 4) % len(bass_notes)]
                client.send_message("/mod/voice2/freq", note_freq)
                client.send_message("/gate/voice2", 1.0)
                client.send_message("/gate/acid1", 1.0)
            
            # Snare build
            if step == 8 and bar >= 2:  # Snare enters later
                client.send_message("/gate/voice3", 1.0)
                client.send_message("/gate/voice3", 0.0)

def final_drop():
    """Final drop: Ultimate anthem climax (32 bars)"""
    print("🚀 FINAL DROP: ULTIMATE ANTHEM CLIMAX!")
    
    # Most complex patterns for finale
    kick_pattern = "X.x.X.X.x.X.X.x."
    bass_pattern = "X.X.x.X.X.x.X.X."
    snare_pattern = "..x.X.x...X.X.x."
    hats_pattern = "XxXxXxXxXxXxXxXx"
    
    # Epic bass progression
    bass_notes = [41.2, 49.0, 55.0, 61.7, 65.4, 61.7, 55.0, 49.0]
    
    # Maximum effects for epic finale
    client.send_message("/mod/reverb1/mix", 0.6)
    client.send_message("/mod/delay1/mix", 0.4)
    
    for bar in range(8):
        print(f"  FINAL DROP bar {bar + 1}/8 - EPIC CLIMAX!")
        
        # Acid filter automation
        base_cutoff = 1000 + (bar * 200)
        
        start_time = time.time()
        
        for step in range(16):
            step_time = start_time + (step * SIXTEENTH_NOTE)
            current_time = time.time()
            
            if current_time < step_time:
                time.sleep(step_time - current_time)
            
            # Dynamic acid cutoff modulation
            cutoff_mod = base_cutoff + (200 * math.sin(step * 0.5))
            client.send_message("/mod/acid1/cutoff", cutoff_mod)
            
            if kick_pattern[step] in ['X', 'x']:
                freq = 52.0 if kick_pattern[step] == 'X' else 48.0
                client.send_message("/mod/voice1/freq", freq)
                client.send_message("/gate/voice1", 1.0)
                client.send_message("/gate/voice1", 0.0)
            
            if bass_pattern[step] in ['X', 'x']:
                note_freq = bass_notes[(bar * 2 + step // 8) % len(bass_notes)]
                client.send_message("/mod/voice2/freq", note_freq)
                client.send_message("/gate/voice2", 1.0)
                client.send_message("/gate/acid1", 1.0)
            
            if snare_pattern[step] in ['X', 'x']:
                freq = 3500.0 if snare_pattern[step] == 'X' else 2800.0
                client.send_message("/mod/voice3/filter/freq", freq)
                client.send_message("/gate/voice3", 1.0)
                client.send_message("/gate/voice3", 0.0)
            
            if hats_pattern[step] in ['X', 'x']:
                amp = 0.7 if hats_pattern[step] == 'X' else 0.4
                client.send_message("/mod/voice4/amp", amp)
                client.send_message("/gate/voice4", 1.0)
                client.send_message("/gate/voice4", 0.0)

def outro():
    """Outro: Epic conclusion"""
    print("🎆 OUTRO: Epic conclusion...")
    
    # Final powerful hits
    for i in range(4):
        # Big final kick
        client.send_message("/mod/voice1/freq", 55.0)
        client.send_message("/gate/voice1", 1.0)
        
        # Final bass note
        client.send_message("/mod/voice2/freq", 41.2)  # Deep E
        client.send_message("/mod/acid1/cutoff", 2000.0)
        client.send_message("/gate/voice2", 1.0)
        client.send_message("/gate/acid1", 1.0)
        
        # Final snare
        client.send_message("/mod/voice3/filter/freq", 4000.0)
        client.send_message("/gate/voice3", 1.0)
        
        time.sleep(BEAT_DURATION)
        
        # Release all
        client.send_message("/gate/voice1", 0.0)
        client.send_message("/gate/voice2", 0.0)
        client.send_message("/gate/acid1", 0.0)
        client.send_message("/gate/voice3", 0.0)
        
        time.sleep(BEAT_DURATION * 3)

def main():
    """Main composition execution"""
    print("🎵 CHRONUS NEXUS: ANTHEM BREAKBEAT GENERATOR")
    print(f"🔥 BPM: {BPM} | Genre: Anthem DnB | Duration: ~3 minutes")
    print("=" * 60)
    
    try:
        # Initialize
        setup_engine()
        time.sleep(1)
        
        # Configure all voices
        configure_voice1_kick()
        configure_voice2_bass()
        configure_voice3_snare()
        configure_voice4_hats()
        
        print("🎛️ All voices configured for anthem breakbeat")
        time.sleep(1)
        
        # Execute composition structure
        intro_section()          # 16 bars intro
        time.sleep(1)
        
        main_drop()              # 32 bars main drop
        time.sleep(1)
        
        breakdown_section()      # 16 bars breakdown
        time.sleep(1)
        
        buildup_section()        # 8 bars build-up
        time.sleep(0.5)
        
        final_drop()             # 32 bars final drop
        time.sleep(1)
        
        outro()                  # Epic conclusion
        
        print("🎆 ANTHEM COMPLETE! The crowd goes wild!")
        
    except KeyboardInterrupt:
        print("\n⚠️ Performance interrupted by user")
    except Exception as e:
        print(f"❌ Error during performance: {e}")
    finally:
        # Emergency stop - gate off all voices
        print("🛑 Stopping all voices...")
        for voice in range(1, 5):
            client.send_message(f"/gate/voice{voice}", 0.0)
        client.send_message("/gate/acid1", 0.0)
        
        print("✅ Anthem breakbeat session complete!")

if __name__ == "__main__":
    main()