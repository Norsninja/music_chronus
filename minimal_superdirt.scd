// Minimal SuperDirt setup
s.boot;
s.doWhenBooted {
    SuperDirt.start;
    "SuperDirt started!".postln;
};