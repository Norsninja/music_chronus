// SuperDirt startup with PulseAudio
s.options.numBuffers = 1024 * 256;
s.options.memSize = 8192 * 32;
s.options.numWireBufs = 128;  // Fixed typo - was numWireBus
s.options.maxNodes = 1024 * 32;
s.options.numOutputBusChannels = 2;
s.options.numInputBusChannels = 2;

s.waitForBoot {
    ~dirt = SuperDirt(2, s);
    ~dirt.loadSoundFiles;
    s.sync;
    ~dirt.start(57120, 0 ! 12);
    "==========================================".postln;
    "SuperDirt is ready with PulseAudio!".postln;
    "Audio routing through Windows".postln;
    "==========================================".postln;
};