# Music Chronus Makefile
# Phase 2 Complete: Modular Synthesis with <10ms Failover

.PHONY: help test run clean failover stress install test-quick test-audio

help:
	@echo "Music Chronus - Make Targets"
	@echo "============================"
	@echo "make install     - Install Python dependencies"
	@echo "make run         - Start AudioSupervisor with ModuleHost (2.12ms failover)"
	@echo "make test        - Run validation tests"
	@echo "make test-quick  - Quick validation only"
	@echo "make test-audio  - Audio accuracy tests (MUS-01/02)"
	@echo "make failover    - Test failover performance"
	@echo "make stress      - Run comprehensive test suite"
	@echo "make clean       - Remove generated files"

install:
	@echo "Installing dependencies..."
	python3 -m venv venv
	. venv/bin/activate && pip install --upgrade pip
	. venv/bin/activate && pip install sounddevice numpy scipy python-osc psutil

test: failover
	@echo "Quick test complete"

run:
	@echo "Starting AudioSupervisor with ModuleHost..."
	@echo "Failover: 2.12ms average (validated)"
	@echo "OSC Control on port 5005:"
	@echo "  /mod/<module>/<param> <value>"
	@echo "  /gate/<module> on|off"
	@echo "Press Ctrl+C to stop"
	. venv/bin/activate && python -m src.music_chronus.supervisor_v2_fixed

test-quick:
	@echo "Running quick validation..."
	. venv/bin/activate && python test_simple_validation.py

test-audio:
	@echo "Running audio accuracy tests..."
	. venv/bin/activate && python tests/test_mus_01_frequency_accuracy.py
	. venv/bin/activate && python tests/test_mus_02_adsr_timing.py

failover:
	@echo "Testing failover performance..."
	. venv/bin/activate && python test_modulehost_fixed.py

stress:
	@echo "Running comprehensive test suite..."
	@echo "NOTE: Ensure no background audio is playing!"
	. venv/bin/activate && python test_modulehost_fixed.py
	. venv/bin/activate && python tests/test_module_chain_integration.py

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