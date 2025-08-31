// SuperDirt with explicit PulseAudio configuration
(
// Force PulseAudio as audio backend
Server.default.options.device = "pulse";

// Audio settings
s.options.numBuffers = 1024 * 256;
s.options.memSize = 8192 * 32;
s.options.numWireBufs = 128;
s.options.maxNodes = 1024 * 32;
s.options.numOutputBusChannels = 2;
s.options.numInputBusChannels = 2;

// Boot with explicit audio driver
s.reboot {
    // Wait a bit for server to start
    3.wait;
    
    // Start SuperDirt
    ~dirt = SuperDirt(2, s);
    ~dirt.loadSoundFiles;
    ~dirt.start(57120, 0 ! 12);
    
    "==========================================".postln;
    "SuperDirt ready with PulseAudio!".postln;
    "Listening on port 57120".postln;
    "==========================================".postln;
};
)