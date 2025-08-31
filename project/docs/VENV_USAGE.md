# Virtual Environment Usage

**CRITICAL**: This project uses a Python virtual environment. All dependencies are installed in `venv/`.

## Quick Reference

### Always Activate First
```bash
source venv/bin/activate
```

### Running Scripts
```bash
# WRONG - will fail with missing modules
python audio_engine_v3.py

# CORRECT - activate venv first
source venv/bin/activate
python audio_engine_v3.py
```

### Tmux Sessions
```bash
# Start audio engine in tmux
tmux new-session -d -s music 'source venv/bin/activate && python audio_engine_v3.py'

# Send commands
tmux send-keys -t music "start" Enter
```

### Running Tests
```bash
source venv/bin/activate
python test_phase1b_basic.py
```

### OSC Control
```bash
source venv/bin/activate
python -c "from pythonosc import udp_client; client = udp_client.SimpleUDPClient('127.0.0.1', 5005); client.send_message('/engine/freq', 880.0)"
```

## Installed Packages

The venv contains:
- **sounddevice** - Audio I/O
- **python-osc** (pythonosc) - OSC messaging  
- **numpy** - Numerical arrays
- **scipy** - Signal processing
- **psutil** - System monitoring
- **rtmixer** - Real-time audio mixing
- All test dependencies

## Common Errors

**"ModuleNotFoundError: No module named 'sounddevice'"**
→ You forgot to activate venv

**"python: command not found"** 
→ Use `python3` or activate venv which aliases it

## For Future Chronus Instances

Remember: **ALWAYS** run `source venv/bin/activate` before any Python operations in this project!