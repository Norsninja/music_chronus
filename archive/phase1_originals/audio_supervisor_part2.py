#!/usr/bin/env python3
"""
Phase 1C: Audio Supervisor - Part 2
Supervisor, monitoring, and failover logic
"""

import sounddevice as sd
from pythonosc import dispatcher, osc_server
import asyncio
from audio_supervisor import *


@dataclass
class SupervisorMetrics:
    """Metrics tracking for supervisor"""
    crash_count: int = 0
    replacements: int = 0
    failovers: int = 0
    commands_sent: int = 0
    detection_times_ns: List[int] = None
    failover_times_ns: List[int] = None
    rebuild_times_ns: List[int] = None
    shm_leaks: int = 0
    spare_ready: bool = True
    last_failure_time: Optional[float] = None
    
    def __post_init__(self):
        if self.detection_times_ns is None:
            self.detection_times_ns = []
        if self.failover_times_ns is None:
            self.failover_times_ns = []
        if self.rebuild_times_ns is None:
            self.rebuild_times_ns = []
    
    def record_failover(self, time_ns: int, cause: str):
        """Record failover event"""
        self.failovers += 1
        self.failover_times_ns.append(time_ns)
        self.last_failure_time = time.monotonic()
        print(f"Failover completed in {time_ns/1_000_000:.2f}ms (cause: {cause})")
    
    def get_percentile(self, data_ns: List[int], percentile: int) -> float:
        """Get percentile in milliseconds"""
        if not data_ns:
            return 0.0
        sorted_data = sorted(data_ns)
        idx = int(len(sorted_data) * percentile / 100)
        idx = min(idx, len(sorted_data) - 1)
        return sorted_data[idx] / 1_000_000  # Convert to ms


class AudioSupervisor:
    """
    Main supervisor managing worker processes and audio output
    Audio I/O stays in main process for continuous output
    """
    
    def __init__(self):
        # Pre-allocate rings for primary and standby
        self.primary_audio_ring = AudioRing()
        self.standby_audio_ring = AudioRing()
        
        self.primary_cmd_ring = CommandRing()
        self.standby_cmd_ring = CommandRing()
        
        # Shared heartbeat array
        self.heartbeat_array = mp.Array('Q', 2, lock=False)  # [primary, standby]
        
        # Initial synchronized state
        self.initial_state = {
            'phase': 0.0,
            'frequency': DEFAULT_FREQUENCY,
            'amplitude': DEFAULT_AMPLITUDE
        }
        
        # Workers
        self.primary_worker = None
        self.standby_worker = None
        
        # Active ring pointer (which ring audio callback reads from)
        self.active_ring = self.primary_audio_ring
        self.active_idx = 0  # 0=primary, 1=standby
        
        # Audio stream
        self.audio_stream = None
        
        # Monitor thread
        self.monitor_thread = None
        self.monitor_stop = threading.Event()
        
        # OSC server
        self.osc_server = None
        self.osc_thread = None
        
        # Metrics
        self.metrics = SupervisorMetrics()
        
        # State
        self.running = False
        
        print("AudioSupervisor initialized")
    
    def start_workers(self):
        """Start primary and standby workers"""
        # Create primary worker
        self.primary_worker = AudioWorker(
            worker_id=0,
            cmd_ring=self.primary_cmd_ring,
            audio_ring=self.primary_audio_ring,
            heartbeat_array=self.heartbeat_array,
            initial_state=self.initial_state.copy()
        )
        
        # Create standby worker  
        self.standby_worker = AudioWorker(
            worker_id=1,
            cmd_ring=self.standby_cmd_ring,
            audio_ring=self.standby_audio_ring,
            heartbeat_array=self.heartbeat_array,
            initial_state=self.initial_state.copy()
        )
        
        # Start both workers
        if not self.primary_worker.start():
            raise RuntimeError("Failed to start primary worker")
        
        if not self.standby_worker.start():
            raise RuntimeError("Failed to start standby worker")
        
        print(f"Workers started - Primary PID: {self.primary_worker.pid}, Standby PID: {self.standby_worker.pid}")
        self.metrics.spare_ready = True
        
        return True
    
    def audio_callback(self, outdata, frames, time_info, status):
        """
        Main process audio callback - never stops during failover
        Reads from whichever ring is active
        """
        if status:
            print(f"Audio status: {status}")
        
        # Read from active ring (latest-wins policy)
        audio_data = self.active_ring.read_latest()
        
        if audio_data is not None and len(audio_data) == frames:
            outdata[:, 0] = audio_data
        else:
            # Silence on underrun
            outdata.fill(0)
    
    def monitor_workers(self):
        """
        Monitor thread - checks sentinels and heartbeats
        Runs with 2ms polling interval
        """
        print("Monitor thread started")
        
        # Initialize tracking
        last_heartbeats = [0, 0]
        last_heartbeat_times = [time.monotonic(), time.monotonic()]
        poll_interval = POLL_INTERVAL_ACTIVE
        
        workers = [self.primary_worker, self.standby_worker]
        rings = [self.primary_audio_ring, self.standby_audio_ring]
        
        while not self.monitor_stop.is_set():
            try:
                # Get sentinels
                sentinels = []
                for w in workers:
                    if w and w.sentinel:
                        sentinels.append(w.sentinel)
                
                if not sentinels:
                    time.sleep(poll_interval)
                    continue
                
                # Check for process death with timeout
                ready = connection.wait(sentinels, timeout=poll_interval)
                
                if ready:
                    # A worker died - identify which one
                    for i, worker in enumerate(workers):
                        if worker and worker.sentinel in ready:
                            detection_time = time.monotonic_ns()
                            
                            if i == self.active_idx:
                                # Primary died - failover to standby
                                print(f"Primary worker died - failing over to standby")
                                self.handle_primary_failure(detection_time)
                            else:
                                # Standby died - spawn new one
                                print(f"Standby worker died - spawning replacement")
                                self.handle_standby_failure(detection_time)
                            break
                
                # Check heartbeats
                current_time = time.monotonic()
                for i, worker in enumerate(workers):
                    if not worker:
                        continue
                    
                    current_hb = self.heartbeat_array[i]
                    
                    if current_hb == last_heartbeats[i]:
                        # No heartbeat progress
                        time_since_beat = current_time - last_heartbeat_times[i]
                        
                        if time_since_beat > HEARTBEAT_TIMEOUT:
                            detection_time = time.monotonic_ns()
                            
                            if i == self.active_idx:
                                print(f"Primary worker hung (no heartbeat) - failing over")
                                self.handle_primary_failure(detection_time, cause='heartbeat')
                            else:
                                print(f"Standby worker hung - spawning replacement")
                                self.handle_standby_failure(detection_time, cause='heartbeat')
                    else:
                        last_heartbeats[i] = current_hb
                        last_heartbeat_times[i] = current_time
                
                # Dynamic polling adjustment
                if self.metrics.last_failure_time:
                    time_since_failure = current_time - self.metrics.last_failure_time
                    if time_since_failure < 5.0:
                        poll_interval = 0.001  # 1ms when recently unstable
                    elif time_since_failure < 30.0:
                        poll_interval = POLL_INTERVAL_ACTIVE
                    else:
                        poll_interval = POLL_INTERVAL_IDLE
                
            except Exception as e:
                print(f"Monitor thread error: {e}")
                time.sleep(poll_interval)
        
        print("Monitor thread stopped")
    
    def handle_primary_failure(self, detection_time_ns: int, cause: str = 'sentinel'):
        """Handle primary worker failure - instant failover"""
        failover_start = time.monotonic_ns()
        
        # 1. Atomic switch to standby ring
        self.active_ring = self.standby_audio_ring
        self.active_idx = 1
        
        # 2. Record metrics
        failover_time = time.monotonic_ns() - failover_start
        self.metrics.record_failover(failover_time, cause)
        self.metrics.crash_count += 1
        
        # 3. Swap worker references (standby becomes primary)
        old_primary = self.primary_worker
        self.primary_worker = self.standby_worker
        self.standby_worker = None
        self.metrics.spare_ready = False
        
        # 4. Clean up dead worker
        if old_primary:
            try:
                old_primary.terminate()
            except:
                pass
        
        # 5. Spawn new standby (background)
        threading.Thread(target=self.spawn_new_standby, daemon=True).start()
    
    def handle_standby_failure(self, detection_time_ns: int, cause: str = 'sentinel'):
        """Handle standby worker failure - spawn replacement"""
        print(f"Standby failed ({cause}) - spawning replacement")
        
        # Clean up dead standby
        if self.standby_worker:
            try:
                self.standby_worker.terminate()
            except:
                pass
        
        self.standby_worker = None
        self.metrics.spare_ready = False
        self.metrics.crash_count += 1
        
        # Spawn replacement
        self.spawn_new_standby()
    
    def spawn_new_standby(self):
        """Spawn a new standby worker"""
        rebuild_start = time.monotonic_ns()
        
        try:
            # Swap rings if needed (standby always uses ring 1)
            if self.active_idx == 1:
                # We're using standby ring as primary, swap them
                self.primary_audio_ring, self.standby_audio_ring = self.standby_audio_ring, self.primary_audio_ring
                self.primary_cmd_ring, self.standby_cmd_ring = self.standby_cmd_ring, self.primary_cmd_ring
                self.active_ring = self.primary_audio_ring
                self.active_idx = 0
            
            # Create new standby
            self.standby_audio_ring.reset()
            self.standby_cmd_ring = CommandRing()  # Fresh command ring
            
            self.standby_worker = AudioWorker(
                worker_id=1,
                cmd_ring=self.standby_cmd_ring,
                audio_ring=self.standby_audio_ring,
                heartbeat_array=self.heartbeat_array,
                initial_state=self.initial_state.copy()
            )
            
            # Start standby
            if self.standby_worker.start():
                rebuild_time = time.monotonic_ns() - rebuild_start
                self.metrics.rebuild_times_ns.append(rebuild_time)
                self.metrics.replacements += 1
                self.metrics.spare_ready = True
                print(f"New standby spawned in {rebuild_time/1_000_000:.2f}ms")
            else:
                print("Failed to spawn new standby")
                self.metrics.spare_ready = False
                
        except Exception as e:
            print(f"Error spawning standby: {e}")
            self.metrics.spare_ready = False
    
    def broadcast_command(self, param: str, value: float):
        """Broadcast command to both workers for lockstep operation"""
        cmd = pack_command(param, value)
        
        # Write to both rings
        if self.primary_worker:
            self.primary_cmd_ring.write(cmd)
            self.primary_worker.send_wakeup()
        
        if self.standby_worker:
            self.standby_cmd_ring.write(cmd)
            self.standby_worker.send_wakeup()
        
        self.metrics.commands_sent += 2
    
    def handle_osc_message(self, address: str, *args):
        """Handle OSC control messages"""
        if address == "/engine/freq" and len(args) > 0:
            freq = float(args[0])
            freq = max(20.0, min(20000.0, freq))  # Sanitize
            self.initial_state['frequency'] = freq
            self.broadcast_command('frequency', freq)
            
        elif address == "/engine/gain" and len(args) > 0:
            gain = float(args[0])
            gain = max(0.0, min(1.0, gain))  # Sanitize
            self.initial_state['amplitude'] = gain
            self.broadcast_command('amplitude', gain)
    
    def start(self):
        """Start the supervisor system"""
        if self.running:
            return False
        
        print("Starting AudioSupervisor...")
        
        # Start workers
        if not self.start_workers():
            return False
        
        # Start monitor thread
        self.monitor_stop.clear()
        self.monitor_thread = threading.Thread(target=self.monitor_workers, daemon=True)
        self.monitor_thread.start()
        
        # Start audio stream
        try:
            self.audio_stream = sd.OutputStream(
                samplerate=SAMPLE_RATE,
                blocksize=BUFFER_SIZE,
                channels=CHANNELS,
                dtype='float32',
                latency='low',
                callback=self.audio_callback
            )
            self.audio_stream.start()
            print(f"Audio stream started: {SAMPLE_RATE}Hz, {BUFFER_SIZE} samples/buffer")
        except Exception as e:
            print(f"Failed to start audio: {e}")
            self.stop()
            return False
        
        self.running = True
        print("AudioSupervisor running - fault tolerance active")
        return True
    
    def stop(self):
        """Stop the supervisor system"""
        if not self.running:
            return
        
        print("Stopping AudioSupervisor...")
        
        # Stop monitor
        self.monitor_stop.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        
        # Stop audio
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
        
        # Stop workers
        if self.primary_worker:
            self.primary_worker.terminate()
        if self.standby_worker:
            self.standby_worker.terminate()
        
        self.running = False
        print("AudioSupervisor stopped")
    
    def get_status(self):
        """Get supervisor status"""
        status = {
            'running': self.running,
            'active_worker': 'primary' if self.active_idx == 0 else 'standby',
            'spare_ready': self.metrics.spare_ready,
            'crash_count': self.metrics.crash_count,
            'failovers': self.metrics.failovers,
            'commands_sent': self.metrics.commands_sent,
            'primary_pid': self.primary_worker.pid if self.primary_worker else None,
            'standby_pid': self.standby_worker.pid if self.standby_worker else None,
            'primary_heartbeat': self.heartbeat_array[0],
            'standby_heartbeat': self.heartbeat_array[1],
            'primary_ring_underruns': self.primary_audio_ring.underruns.value,
            'standby_ring_underruns': self.standby_audio_ring.underruns.value,
        }
        
        if self.metrics.failover_times_ns:
            status['failover_p95_ms'] = self.metrics.get_percentile(self.metrics.failover_times_ns, 95)
            status['failover_p99_ms'] = self.metrics.get_percentile(self.metrics.failover_times_ns, 99)
        
        return status


# Combine both parts
if __name__ == "__main__":
    print("Phase 1C Audio Supervisor - Complete Implementation")
    print("Run test_supervisor.py to test the system")