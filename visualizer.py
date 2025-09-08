#!/usr/bin/env python3
"""
Terminal-based Music Visualizer for Music Chronus
Real-time audio visualization with 8-bit aesthetic
"""

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
        
        # Data buffers (thread-safe with locks)
        self.data_lock = threading.Lock()
        self.osc_messages = deque(maxlen=20)  # Last 20 OSC messages
        self.audio_levels = [0.0] * 4  # 4 voices
        self.master_level = 0.0
        self.spectrum_data = [0.0] * 8  # 8 frequency bands
        
        # Engine status
        self.engine_connected = False
        self.last_status_update = 0
        self.status_data = {}
        
        # Control flags
        self.running = True
        self.refresh_rate = 20  # Target FPS
        
        # Initialize components
        self.setup_layout()
        self.setup_osc_listener()
        
    def setup_layout(self):
        """Configure the Rich layout with panels"""
        # Create main layout structure
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
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
                    if 0 <= idx < 4:
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
        
        # Then process the data
        with self.data_lock:
            if args and len(args) >= 4:
                self.audio_levels = [float(x) for x in args[:4]]
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
            
            for i in range(4):
                level = self.audio_levels[i]
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
            bar_width = int(self.master_level * 20)
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


if __name__ == "__main__":
    visualizer = MusicChronusVisualizer()
    visualizer.run()