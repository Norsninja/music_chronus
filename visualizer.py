#!/usr/bin/env python3
"""
Terminal-based Music Visualizer for Music Chronus
Real-time audio visualization with 8-bit aesthetic
"""

import os
import time
import threading
import signal
import sys
from pathlib import Path
from collections import deque
from typing import Dict, List, Optional, Any

from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn
from rich.columns import Columns
from rich import box

from pythonosc import udp_client
from pythonosc import dispatcher
from pythonosc import osc_server
from pythonosc.osc_server import ThreadingOSCUDPServer


class MusicChronusVisualizer:
    """Terminal visualizer for Music Chronus engine"""
    
    def __init__(self):
        # Rich console and layout
        self.console = Console()
        self.layout = Layout()
        
        # OSC configuration
        self.osc_ip = "127.0.0.1"
        self.osc_monitor_port = 5006  # Receive visualization broadcast data
        self.osc_viz_port = 5006      # Same port for viz data
        
        # Voice configuration (dynamic)
        self.num_voices = self._detect_voice_count()
        self.voice_count_detected = False  # Track if auto-detected from OSC
        
        # Data buffers (thread-safe with locks)
        self.data_lock = threading.Lock()
        self.reconfigure_lock = threading.Lock()  # For voice count changes
        self.osc_messages = deque(maxlen=20)  # Last 20 OSC messages
        self.audio_levels = [0.0] * self.num_voices  # Dynamic voice count
        self.master_level = 0.0
        self.spectrum_data = [0.0] * 8  # 8 frequency bands
        
        # Engine status
        self.engine_connected = False
        self.last_status_update = 0
        self.status_data = {}
        
        # Control flags
        self.running = True
        self.refresh_rate = 20  # Target FPS
        
        # Initialize pet
        self.pet = None  # Will be initialized after layout
        
        # Initialize components
        self.setup_layout()
        self.setup_osc_listener()
        
        # Create pet after layout is ready
        self.pet = ChronusPet(self)
        
        print(f"[VISUALIZER] Initialized with {self.num_voices} voices")
        
    def _detect_voice_count(self) -> int:
        """Detect voice count from environment or use default"""
        # Try environment variable first (matches engine configuration)
        try:
            env_voices = os.environ.get('CHRONUS_NUM_VOICES')
            if env_voices:
                num_voices = int(env_voices)
                # Clamp to valid range (1-16)
                num_voices = max(1, min(16, num_voices))
                print(f"[VISUALIZER] Using CHRONUS_NUM_VOICES={num_voices}")
                return num_voices
        except (ValueError, TypeError):
            pass
        
        # Default to 4 voices for backward compatibility
        print("[VISUALIZER] No CHRONUS_NUM_VOICES found, defaulting to 4 voices")
        return 4
    
    def _reconfigure_voice_count(self, new_count: int):
        """Safely reconfigure voice count during runtime"""
        with self.reconfigure_lock:
            if new_count == self.num_voices:
                return  # No change needed
            
            print(f"[VISUALIZER] Reconfiguring from {self.num_voices} to {new_count} voices")
            
            # Update voice count
            old_count = self.num_voices
            self.num_voices = new_count
            
            # Resize audio levels buffer (preserve existing data where possible)
            with self.data_lock:
                old_levels = self.audio_levels[:]
                self.audio_levels = [0.0] * new_count
                
                # Copy over existing levels
                for i in range(min(old_count, new_count)):
                    self.audio_levels[i] = old_levels[i]
            
            self.voice_count_detected = True
            print(f"[VISUALIZER] Reconfigured to {new_count} voices")
        
    def setup_layout(self):
        """Configure the Rich layout with panels"""
        # Create main layout structure
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="pet", size=8),  # Pet panel area
            Layout(name="footer", size=3)
        )
        
        # Split main area into columns
        self.layout["main"].split_row(
            Layout(name="levels", ratio=1),
            Layout(name="spectrum", ratio=2),
            Layout(name="messages", ratio=1)
        )
        
        # Header
        self.layout["header"].update(
            Panel(
                Text("🎵 MUSIC CHRONUS VISUALIZER 🎵", justify="center", style="bold cyan"),
                box=box.DOUBLE,
                style="cyan"
            )
        )
        
        # Footer with status
        self.layout["footer"].update(
            Panel(
                Text("Press Ctrl+C to exit", justify="center"),
                box=box.ROUNDED,
                style="dim"
            )
        )
        
    def setup_osc_listener(self):
        """Setup OSC listener thread"""
        # Create dispatcher for OSC messages
        self.dispatcher = dispatcher.Dispatcher()
        
        # Catch all OSC messages for monitoring
        self.dispatcher.set_default_handler(self.handle_osc_message)
        
        # Specific handlers for visualization data (future)
        self.dispatcher.map("/viz/spectrum", self.handle_spectrum_data)
        self.dispatcher.map("/viz/levels", self.handle_level_data)
        
        # Start OSC server in thread
        def start_osc_server():
            try:
                # Monitor existing OSC traffic
                server = ThreadingOSCUDPServer(
                    (self.osc_ip, self.osc_monitor_port),
                    self.dispatcher
                )
                self.console.print(f"[green]OSC listener started on port {self.osc_monitor_port}[/green]")
                server.serve_forever()
            except Exception as e:
                # OSC listener is optional - visualizer works with status file alone
                self.console.print(f"[yellow]OSC listener not available (port {self.osc_monitor_port}): Running in status-file-only mode[/yellow]")
        
        self.osc_thread = threading.Thread(target=start_osc_server, daemon=True)
        self.osc_thread.start()
        
    def handle_osc_message(self, addr: str, *args):
        """Handle incoming OSC messages"""
        with self.data_lock:
            # Add to message history
            timestamp = time.strftime("%H:%M:%S")
            self.osc_messages.append({
                'time': timestamp,
                'addr': addr,
                'args': args[:3] if args else []  # Limit args display
            })
            
            # Parse specific message types
            if addr.startswith("/gate/"):
                # Gate message - extract voice state
                voice = addr.split("/")[-1]
                if voice.startswith("voice") and args:
                    idx = int(voice[-1]) - 1
                    if 0 <= idx < self.num_voices:
                        self.audio_levels[idx] = float(args[0]) * 0.5
                        
            self.engine_connected = True
            self.last_status_update = time.time()
            
    def handle_spectrum_data(self, addr: str, *args):
        """Handle spectrum analysis data"""
        # Log to message display FIRST so it appears in OSC panel
        self.handle_osc_message(addr, *args)
        
        # Then process the data
        with self.data_lock:
            if args and len(args) >= 8:
                self.spectrum_data = [float(x) for x in args[:8]]
                # Mark as receiving live data
                self.engine_connected = True
                self.last_status_update = time.time()
                
    def handle_level_data(self, addr: str, *args):
        """Handle audio level data"""
        # Log to message display FIRST so it appears in OSC panel
        self.handle_osc_message(addr, *args)
        
        # Auto-detect voice count from first message if not already detected
        if not self.voice_count_detected and args:
            received_count = len(args)
            if received_count != self.num_voices:
                print(f"[VISUALIZER] Auto-detecting {received_count} voices from OSC data")
                self._reconfigure_voice_count(received_count)
        
        # Then process the data
        with self.data_lock:
            if args:
                # Process all received voice levels (dynamic count)
                received_count = len(args)
                for i in range(min(received_count, self.num_voices)):
                    self.audio_levels[i] = float(args[i])
                
                # Zero out any voices not in the received data
                for i in range(received_count, self.num_voices):
                    self.audio_levels[i] = 0.0
                    
                # Mark as receiving live data  
                self.engine_connected = True
                self.last_status_update = time.time()
                
    def read_status_file(self):
        """Read engine_status.txt for additional data"""
        try:
            status_file = Path("engine_status.txt")
            if status_file.exists():
                with open(status_file, 'r') as f:
                    line = f.readline().strip()
                    if line:
                        # Parse status line
                        parts = line.split(" | ")
                        for part in parts:
                            if "AUDIO:" in part:
                                self.master_level = float(part.split(":")[1])
                            elif "GATES:" in part:
                                self.status_data['gates'] = int(part.split(":")[1])
                            elif "MSG:" in part:
                                self.status_data['msg_count'] = int(part.split(":")[1])
        except Exception:
            pass  # Silently ignore file read errors
            
    def create_level_meters(self) -> Panel:
        """Create voice level meter display"""
        with self.data_lock:
            table = Table(box=None, padding=0, show_header=False)
            table.add_column("Voice", style="cyan")
            table.add_column("Level", min_width=20)
            table.add_column("Value", style="green")
            
            # Dynamic voice count
            for i in range(self.num_voices):
                level = self.audio_levels[i] if i < len(self.audio_levels) else 0.0
                # Handle NaN and invalid values
                if level != level or level is None:  # NaN check
                    level = 0.0
                level = max(0.0, min(1.0, level))  # Clamp to valid range
                
                bar_width = int(level * 20)
                bar = "█" * bar_width + "░" * (20 - bar_width)
                
                # Color based on level
                if level > 0.8:
                    bar_style = "red"
                elif level > 0.5:
                    bar_style = "yellow"
                else:
                    bar_style = "green"
                    
                table.add_row(
                    f"Voice{i+1}",
                    Text(bar, style=bar_style),
                    f"{level:.2f}"
                )
                
            # Add master level
            master_level = self.master_level
            # Handle NaN and invalid values
            if master_level != master_level or master_level is None:  # NaN check
                master_level = 0.0
            master_level = max(0.0, min(1.0, master_level))  # Clamp to valid range
            
            bar_width = int(master_level * 20)
            bar = "█" * bar_width + "░" * (20 - bar_width)
            table.add_row(
                "MASTER",
                Text(bar, style="bold cyan"),
                f"{self.master_level:.3f}"
            )
            
        return Panel(table, title="Audio Levels", box=box.ROUNDED, border_style="green")
        
    def create_spectrum_display(self) -> Panel:
        """Create frequency spectrum display"""
        with self.data_lock:
            # Frequency labels
            freq_labels = ["63", "125", "250", "500", "1k", "2k", "4k", "8k"]
            
            # Create spectrum bars
            lines = []
            max_height = 10
            
            for row in range(max_height, 0, -1):
                line = ""
                for i, value in enumerate(self.spectrum_data):
                    # Handle NaN and invalid values
                    if value != value or value is None:  # NaN check
                        value = 0.0
                    value = max(0.0, min(1.0, value))  # Clamp to valid range
                    
                    bar_height = int(value * max_height)
                    if bar_height >= row:
                        line += "██"
                    else:
                        line += "  "
                    line += " "
                lines.append(Text(line, style="cyan"))
                
            # Add frequency labels
            label_line = " ".join(f"{label:^3}" for label in freq_labels)
            lines.append(Text(label_line, style="dim"))
            
            spectrum_text = Text.from_markup("\n".join(str(line) for line in lines))
            
        return Panel(
            spectrum_text,
            title="Frequency Spectrum",
            box=box.ROUNDED,
            border_style="blue"
        )
        
    def create_message_display(self) -> Panel:
        """Create OSC message monitor display"""
        with self.data_lock:
            table = Table(box=None, padding=0, show_header=True)
            table.add_column("Time", style="dim", width=8)
            table.add_column("Message", style="yellow")
            
            # Add recent messages
            for msg in reversed(list(self.osc_messages)[-10:]):  # Show last 10
                args_str = ", ".join(str(arg)[:10] for arg in msg['args'])
                table.add_row(
                    msg['time'],
                    f"{msg['addr']} {args_str}"
                )
                
        return Panel(table, title="OSC Messages", box=box.ROUNDED, border_style="yellow")
        
    def update_display(self):
        """Update all display panels"""
        # Read status file
        self.read_status_file()
        
        # Update panels
        self.layout["levels"].update(self.create_level_meters())
        self.layout["spectrum"].update(self.create_spectrum_display())
        self.layout["messages"].update(self.create_message_display())
        
        # Update pet
        if self.pet:
            self.layout["pet"].update(self.pet.render())
        
        # Update footer with connection status
        status = "✓ Connected" if self.engine_connected else "✗ Disconnected"
        color = "green" if self.engine_connected else "red"
        
        footer_text = f"[{color}]{status}[/{color}] | "
        if self.status_data.get('msg_count'):
            footer_text += f"Messages: {self.status_data['msg_count']} | "
        if self.status_data.get('gates'):
            footer_text += f"Active Gates: {self.status_data['gates']} | "
        footer_text += "Press Ctrl+C to exit"
        
        self.layout["footer"].update(
            Panel(
                Text(footer_text, justify="center"),
                box=box.ROUNDED,
                style="dim"
            )
        )
        
    def run(self):
        """Main visualization loop"""
        self.console.print("[bold green]Music Chronus Visualizer Starting...[/bold green]")
        
        # Setup signal handler for clean exit
        def signal_handler(sig, frame):
            self.running = False
            self.console.print("\n[yellow]Shutting down visualizer...[/yellow]")
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        
        # Main display loop with Rich Live
        with Live(self.layout, console=self.console, refresh_per_second=self.refresh_rate) as live:
            while self.running:
                self.update_display()
                time.sleep(1.0 / self.refresh_rate)
                
                # Check connection timeout
                if time.time() - self.last_status_update > 2.0:
                    self.engine_connected = False


class ChronusPet:
    """Musical companion that reacts to the quality of music being created"""
    
    def __init__(self, visualizer):
        self.visualizer = visualizer
        
        # Pet states
        self.states = {
            "sleeping": {
                "frames": ["( -_- )", "( =_= )", "( -_- )", "( =_= )"],
                "message": "zzz... no music detected",
                "color": "dim white"
            },
            "waking": {
                "frames": ["( o.o )", "( o_o )", "( o.o )", "( o_o )"],
                "message": "oh? something's happening...",
                "color": "yellow"
            },
            "vibing": {
                "frames": ["( ^_^ )", "( ^‿^ )", "( ^_^ )", "( ^‿^ )"],
                "message": "nice sounds! keep going!",
                "color": "green"
            },
            "dancing": {
                "frames": ["\\( ^o^ )/", "/( ^o^ )\\", "\\( ^o^ )/", "/( ^o^ )\\"],
                "message": "this is getting good!",
                "color": "cyan"
            },
            "raving": {
                "frames": ["\\( >◡< )/", "~( >◡< )~", "/( >◡< )\\", "~( >◡< )~"],
                "message": "AMAZING! Peak musical energy!",
                "color": "magenta"
            },
            "transcendent": {
                "frames": [
                    "✧･ﾟ: *✧･ﾟ:* \\( ◕‿◕ )/ *:･ﾟ✧*:･ﾟ✧",
                    "･ﾟ✧*:･ﾟ✧ \\( ◕‿◕ )/ ✧･ﾟ: *✧･ﾟ:*",
                    "*✧･ﾟ:*✧･ﾟ \\( ◕‿◕ )/ ･ﾟ✧*:･ﾟ✧*",
                    "✧･ﾟ: *✧･ﾟ:* \\( ◕‿◕ )/ *:･ﾟ✧*:･ﾟ✧"
                ],
                "message": "TRANSCENDENT! Musical nirvana achieved!",
                "color": "bold magenta"
            }
        }
        
        # Current state
        self.current_state = "sleeping"
        self.frame_index = 0
        self.frame_counter = 0
        self.frames_per_animation = 3  # Slow down animation
        
        # Musical score tracking
        self.musical_score = 0
        self.score_history = deque(maxlen=20)  # Track recent scores
        
        # State transition thresholds
        self.state_thresholds = {
            "sleeping": (0, 10),
            "waking": (10, 30),
            "vibing": (30, 50),
            "dancing": (50, 70),
            "raving": (70, 90),
            "transcendent": (90, 100)
        }
        
    def calculate_musical_score(self):
        """Calculate a score based on current musical activity"""
        score = 0
        
        # Check audio levels (max 25 points)
        # Filter out NaN values first
        valid_levels = []
        for level in self.visualizer.audio_levels:
            if level == level and level is not None:  # Not NaN
                valid_levels.append(max(0.0, min(1.0, level)))
            else:
                valid_levels.append(0.0)
        
        active_voices = sum(1 for level in valid_levels if level > 0.1)
        # Scale points based on actual voice count (max 25 points)
        if self.visualizer.num_voices > 0:
            points_per_voice = 25.0 / self.visualizer.num_voices
            score += min(active_voices * points_per_voice, 25)
        
        # Check spectrum balance (max 25 points)
        if self.visualizer.spectrum_data:
            # Filter out NaN values from spectrum data
            valid_spectrum = []
            for band in self.visualizer.spectrum_data:
                if band == band and band is not None:  # Not NaN
                    valid_spectrum.append(max(0.0, min(1.0, band)))
                else:
                    valid_spectrum.append(0.0)
            
            # Count bands with energy
            active_bands = sum(1 for band in valid_spectrum if band > 0.1)
            score += active_bands * 3  # Up to 24 points for 8 bands
            
            # Bonus for balanced spectrum (not all in one frequency)
            if active_bands > 3 and len(valid_spectrum) > 0:
                variance = max(valid_spectrum) - min(valid_spectrum)
                if 0.2 < variance < 0.8:  # Good dynamic range
                    score += 5
        
        # Check for activity patterns (max 25 points)
        # Only count musical OSC messages, not status messages
        if self.visualizer.osc_messages:
            # Filter for musical messages (gates, mods, seq)
            musical_messages = [
                msg for msg in self.visualizer.osc_messages 
                if any(prefix in msg.get('addr', '') 
                      for prefix in ['/gate/', '/mod/', '/seq/'])
            ]
            recent_messages = len(musical_messages)
            if recent_messages > 0:  # Changed from > 5 to > 0
                score += min(recent_messages * 3, 25)  # Scale up points
        
        # Energy variance bonus (max 25 points)
        # Only add variance if there's actual activity
        if score > 0:  # Only track variance when music is playing
            self.score_history.append(score)
            if len(self.score_history) > 5:
                variance = max(self.score_history) - min(self.score_history)
                if variance > 10:  # Music is changing, not static
                    score += min(variance, 25)
        else:
            # Clear history when no activity
            self.score_history.clear()
        
        # Clamp to 0-100
        return max(0, min(100, score))
    
    def update_state(self):
        """Update pet state based on musical score"""
        self.musical_score = self.calculate_musical_score()
        
        # Find appropriate state for current score
        new_state = "sleeping"
        for state, (min_score, max_score) in self.state_thresholds.items():
            if min_score <= self.musical_score < max_score:
                new_state = state
                break
        
        # State change detection
        if new_state != self.current_state:
            self.current_state = new_state
            self.frame_index = 0  # Reset animation
    
    def render(self):
        """Render the pet panel"""
        self.update_state()
        
        # Get current animation frame
        state_data = self.states[self.current_state]
        
        # Update animation frame
        self.frame_counter += 1
        if self.frame_counter >= self.frames_per_animation:
            self.frame_counter = 0
            self.frame_index = (self.frame_index + 1) % len(state_data["frames"])
        
        current_frame = state_data["frames"][self.frame_index]
        
        # Create score bar
        bar_width = 40
        filled = int((self.musical_score / 100) * bar_width)
        score_bar = "█" * filled + "░" * (bar_width - filled)
        
        # Determine score color
        if self.musical_score < 30:
            bar_color = "red"
        elif self.musical_score < 60:
            bar_color = "yellow"
        else:
            bar_color = "green"
        
        # Build display
        lines = []
        lines.append("")  # Spacing
        lines.append(Text(current_frame, justify="center", style=state_data["color"]))
        lines.append("")
        lines.append(Text(state_data["message"], justify="center", style=state_data["color"]))
        lines.append("")
        lines.append(Text(f"Musical Energy: {self.musical_score}/100", justify="center"))
        lines.append(Text(f"[{score_bar}]", justify="center", style=bar_color))
        lines.append("")
        
        # Combine lines
        content = Columns(lines, align="center", expand=True)
        
        return Panel(
            content,
            title="🎵 Chronus Pet 🎵",
            box=box.DOUBLE,
            border_style=state_data["color"],
            padding=(0, 2)
        )


if __name__ == "__main__":
    visualizer = MusicChronusVisualizer()
    visualizer.run()