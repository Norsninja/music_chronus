# Worker SIGTERM Investigation Report
Date: 2025-09-01
Investigator: Chronus Nexus

## Executive Summary
Workers in the AudioSupervisor system print "received SIGTERM" and "exited cleanly" during startup, yet continue running and processing audio. This contradictory behavior is preventing audio output despite all components appearing functional.

## Key Findings

### 1. Workers Receive SIGTERM on Startup
**Evidence:** Every worker process prints these messages immediately after starting:
```
Worker 0 received SIGTERM
Worker 0 exited cleanly
```

**Yet the worker continues running!** Heartbeat counters increment, and `process.is_alive()` returns True.

### 2. Execution Order Anomaly
The print statements appear in an impossible order:
```
Primary worker started with ModuleHost (PID: 630559)  # Line 195 in worker process
Worker 0 received SIGTERM                              # Line 157 in signal handler
Worker 0 exited cleanly                                # Line 268 at end of function
```

The "exited cleanly" message appears BEFORE the worker enters its main loop, suggesting the main loop never runs. Yet heartbeats prove it IS running.

### 3. Workers Are Healthy Without Monitor Thread
**Test results:**
- Workers created WITHOUT monitor thread: Stay alive indefinitely
- Workers created WITH monitor thread: Receive SIGTERM immediately
- Monitor thread started AFTER workers: Workers remain healthy

This proves the monitor thread is NOT killing healthy workers - something else happens during startup.

### 4. Double Output Mystery
Workers appear to print their startup message twice:
- Once when actually starting
- Once more after receiving SIGTERM

This suggests possible process forking or respawning.

### 5. OSC Server Port Conflict
The OSC server consistently fails with "Address already in use" on port 5005, indicating zombie processes or improper cleanup from previous runs.

## Diagnostic Tests Performed

### Test 1: Standalone Worker (test_worker_simple.py)
- Created worker with ID 0 (valid for 2-element heartbeat array)
- Worker prints SIGTERM messages but continues running
- Heartbeat increments normally (172, 345, 517, 689, 862)
- Worker responds to explicit terminate() call

### Test 2: Monitor Thread Isolation (test_monitor_debug.py)
- Workers start healthy without monitor
- Starting monitor thread does NOT kill workers
- No false-positive death detection observed

### Test 3: Signal Source Investigation (test_signal_debug.py)
- Simple multiprocessing workers receive SIGTERM only when explicitly sent
- No spurious signals in basic multiprocessing setup
- Parent PID correctly identified in signal handler

## Contradictions Requiring Explanation

1. **How can "Worker exited cleanly" print while the worker continues running?**
   - Line 268 is at the end of audio_worker_process()
   - Should only print after exiting the main loop
   - Yet heartbeat proves the loop is running

2. **Why does shutdown_flag not stop the main loop?**
   - Signal handler sets shutdown_flag = True
   - Main loop is `while not shutdown_flag:`
   - Loop should never start if flag is set early

3. **Where is the SIGTERM coming from?**
   - Not from monitor thread (workers die before monitor starts)
   - Not from supervisor's terminate() method
   - Not from parent process inheritance

## Hypothesis

The symptoms suggest one of these scenarios:

### Scenario A: Process Forking Issue
The worker process might be forked or exec'd in a way that causes the original process to receive SIGTERM while a child continues. This would explain the duplicate output.

### Scenario B: Signal Handler Race Condition
The SIGTERM handler might be triggered by process initialization itself, possibly related to socket creation or multiprocessing internals.

### Scenario C: Import-Time Execution
Code might be executing at import time, causing the worker function to run twice - once during import and once when actually started.

## Critical Code Sections

### Worker Signal Handler (lines 154-157)
```python
def handle_sigterm(signum, frame):
    nonlocal shutdown_flag
    shutdown_flag = True
    print(f"Worker {worker_id} received SIGTERM")
```
Only sets flag, doesn't exit immediately.

### Main Loop Condition (line 204)
```python
while not shutdown_flag:
```
Should prevent loop entry if flag is set.

### Exit Message (line 268)
```python
print(f"Worker {worker_id} exited cleanly")
```
At function end, after main loop.

## Next Investigation Steps

1. **Add process ID tracking** to determine if the SIGTERM messages come from the same process that continues running

2. **Add stack traces** to the signal handler to see where the SIGTERM originates

3. **Check multiprocessing start method** - fork vs spawn vs forkserver might affect signal handling

4. **Instrument the main loop** to verify it's actually the same process/thread processing audio

5. **Check for import-time execution** that might cause duplicate runs

## Questions for Senior Dev

1. Is there any multiprocessing initialization that might send SIGTERM to child processes?

2. Could the socket creation (line 150: `parent_socket.close()`) trigger a signal?

3. Is the print buffering causing output to appear out of order?

4. Could the worker be exec'd or forked in a way that creates this behavior?

5. Are we seeing output from multiple process instances interleaved?

## Current Impact

- No audio output despite all systems appearing functional
- OSC messages received but not processed
- Workers appear healthy to supervisor but are actually compromised
- System is very close to working - just need to resolve this startup issue

## Conclusion

The workers are experiencing a startup anomaly where they receive SIGTERM, print exit messages, yet continue running. This paradoxical behavior suggests a fundamental misunderstanding of the process lifecycle or a race condition in the multiprocessing setup. The system is otherwise healthy and all performance metrics are met - we just need to resolve this startup issue to achieve audio output.