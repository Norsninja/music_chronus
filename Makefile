# Music Chronus Makefile
# Simple automation for common tasks

.PHONY: help test run clean failover stress install

help:
	@echo "Music Chronus - Make Targets"
	@echo "============================"
	@echo "make install  - Install Python dependencies"
	@echo "make test     - Run quick failover test"
	@echo "make run      - Start audio supervisor"
	@echo "make failover - Test failover timing"
	@echo "make stress   - Run comprehensive test suite"
	@echo "make clean    - Remove generated files"

install:
	@echo "Installing dependencies..."
	python3 -m venv venv
	. venv/bin/activate && pip install --upgrade pip
	. venv/bin/activate && pip install sounddevice numpy scipy python-osc psutil

test: failover
	@echo "Quick test complete"

run:
	@echo "Starting Audio Supervisor..."
	@echo "Press Ctrl+C to stop"
	. venv/bin/activate && python -c "import sys; sys.path.insert(0, 'src'); from music_chronus import AudioSupervisor; import time; s = AudioSupervisor(); s.start(); \
		print('Running... Press Ctrl+C to stop'); \
		try: \
			while True: time.sleep(1); \
		except KeyboardInterrupt: pass; \
		finally: s.stop()"

failover:
	@echo "Testing failover performance..."
	. venv/bin/activate && python test_failover_quick.py

stress:
	@echo "Running comprehensive test suite..."
	@echo "NOTE: Ensure no background audio is playing!"
	. venv/bin/activate && python test_supervisor.py

clean:
	@echo "Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -f test_refactor.py
	@echo "Clean complete"

# Development helpers
.PHONY: status check-audio

status:
	@echo "Checking project status..."
	@echo "Virtual env:" && ls -la venv/bin/activate 2>/dev/null || echo "Not found - run 'make install'"
	@echo "Audio device:" && pactl info | grep "Server Name" || echo "PulseAudio not running"
	@echo "Python version:" && python3 --version

check-audio:
	@echo "Checking for audio interference..."
	@ps aux | grep -E "(spotify|chrome|firefox|vlc|mpv|rhythmbox)" | grep -v grep || echo "No obvious audio apps running"
	@echo "PulseAudio clients:"
	@pactl list clients | grep -E "application.name|application.process.binary" || echo "No active clients"