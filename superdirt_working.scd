// Working SuperDirt setup with proper memory allocation
(
// First, increase memory BEFORE booting
s.options.memSize = 8192 * 64;  // Increase memory for samples
s.options.numWireBufs = 256;     // Increase wire buffers
s.options.maxNodes = 1024 * 32;  // Increase max nodes

// Boot the server
s.waitForBoot {
    // Give it a moment to settle
    1.wait;
    
    // Start SuperDirt with just 2 orbits to save memory
    ~dirt = SuperDirt(2, s);
    
    // Load only essential samples (comment out to load all)
    // ~dirt.loadSoundFiles("~/.local/share/SuperCollider/downloaded-quarks/Dirt-Samples/*");
    
    // Or load all samples (may need more memory)
    ~dirt.loadSoundFiles;
    
    // Wait for samples to load
    s.sync;
    
    // Start listening on default port
    ~dirt.start(57120, 0 ! 2);  // Just 2 orbits instead of 12
    
    "SuperDirt is ready!".postln;
};
)