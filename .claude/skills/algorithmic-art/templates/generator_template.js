/**
 * GENERATOR TEMPLATE - p5.js Best Practices Reference
 * ====================================================
 * This file demonstrates code structure principles for generative art.
 * Use these patterns when building your algorithm, but embed everything
 * inline in the HTML artifact (don't create separate .js files).
 *
 * This is a REFERENCE, not a pattern menu. Build what the philosophy demands.
 */

// =============================================================================
// 1. PARAMETER STRUCTURE
// =============================================================================
// Define all tunable parameters in a single object.
// Include sensible defaults. Always include seed.

let params = {
    seed: 12345,

    // Quantities - how many elements?
    particleCount: 2000,
    layerCount: 5,

    // Scales - how big, how fast?
    noiseScale: 0.003,
    speed: 1.5,
    strokeWeight: 0.8,

    // Probabilities - how likely?
    branchChance: 0.15,

    // Ratios - what proportions?
    goldenRatio: 1.618,
    damping: 0.98,

    // Thresholds - when does behavior change?
    densityThreshold: 0.7,
    maxAge: 300,

    // Colors - palette definition
    bgColor: '#faf8f5',
    palette: ['#2d2a26', '#c4956a', '#8a8078', '#5a534c', '#d4c4b0']
};

// Always keep a copy for reset functionality
let defaultParams = JSON.parse(JSON.stringify(params));


// =============================================================================
// 2. SEEDED RANDOMNESS
// =============================================================================
// CRITICAL: Always seed both random and noise for reproducibility.
// Same seed = identical output. This is the Art Blocks pattern.

function initSeed() {
    randomSeed(params.seed);
    noiseSeed(params.seed);
}

// Use random() and noise() throughout - never Math.random()
// This ensures seed-based reproducibility


// =============================================================================
// 3. CLASS STRUCTURE FOR PARTICLES/AGENTS
// =============================================================================
// When the algorithm uses particles, agents, or entities, encapsulate in classes.

class Particle {
    constructor(x, y) {
        this.pos = createVector(x, y);
        this.vel = createVector(0, 0);
        this.acc = createVector(0, 0);
        this.age = 0;
        this.maxAge = params.maxAge + random(-50, 50);
        this.history = [];
    }

    update() {
        // Apply forces from vector field / noise / etc
        let angle = noise(
            this.pos.x * params.noiseScale,
            this.pos.y * params.noiseScale
        ) * TWO_PI * 2;

        this.acc = p5.Vector.fromAngle(angle).mult(params.speed * 0.1);
        this.vel.add(this.acc);
        this.vel.mult(params.damping);
        this.pos.add(this.vel);

        this.history.push(this.pos.copy());
        this.age++;
    }

    isDead() {
        return this.age > this.maxAge ||
               this.pos.x < 0 || this.pos.x > width ||
               this.pos.y < 0 || this.pos.y > height;
    }

    display() {
        // Draw based on history, velocity, age, etc.
        let alpha = map(this.age, 0, this.maxAge, 255, 0);
        stroke(0, alpha);
        strokeWeight(params.strokeWeight);
        noFill();

        if (this.history.length > 1) {
            let prev = this.history[this.history.length - 2];
            line(prev.x, prev.y, this.pos.x, this.pos.y);
        }
    }
}


// =============================================================================
// 4. SETUP AND DRAW LIFECYCLE
// =============================================================================

function setup() {
    let canvas = createCanvas(1200, 1200);
    canvas.parent('canvas-container');

    // For static art: noLoop() + regenerate on param change
    // For animated art: let draw() run continuously
    noLoop();

    regenerate();
}

function draw() {
    initSeed(); // Always re-seed at start of draw for reproducibility

    background(params.bgColor);

    // --- YOUR ALGORITHM HERE ---
    // Build what the philosophy demands.
    // This template is a reference, not a constraint.
}


// =============================================================================
// 5. REGENERATE PATTERN
// =============================================================================
// Called when seed or parameters change. Re-initializes everything.

function regenerate() {
    // Re-seed
    initSeed();

    // Reset any state (particle arrays, grids, etc.)
    // particles = [];
    // for (let i = 0; i < params.particleCount; i++) {
    //     particles.push(new Particle(random(width), random(height)));
    // }

    // Trigger redraw
    redraw();
}


// =============================================================================
// 6. COLOR UTILITIES
// =============================================================================
// Thoughtful color handling - not random RGB.

function getColor(index) {
    // Cycle through palette
    return params.palette[index % params.palette.length];
}

function lerpPalette(t) {
    // Smoothly interpolate across palette
    let scaledT = t * (params.palette.length - 1);
    let i = floor(scaledT);
    let frac = scaledT - i;
    i = constrain(i, 0, params.palette.length - 2);
    return lerpColor(color(params.palette[i]), color(params.palette[i + 1]), frac);
}

function hexToRgb(hex) {
    let r = parseInt(hex.slice(1, 3), 16);
    let g = parseInt(hex.slice(3, 5), 16);
    let b = parseInt(hex.slice(5, 7), 16);
    return { r, g, b };
}


// =============================================================================
// 7. MATHEMATICAL UTILITIES
// =============================================================================

function goldenAngle(n) {
    // Golden angle distribution - phyllotaxis pattern
    return n * 137.508 * (PI / 180);
}

function fibonacci(n) {
    if (n <= 1) return n;
    let a = 0, b = 1;
    for (let i = 2; i <= n; i++) {
        [a, b] = [b, a + b];
    }
    return b;
}

function easeInOut(t) {
    return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
}

function mapRange(value, inMin, inMax, outMin, outMax) {
    return outMin + (outMax - outMin) * ((value - inMin) / (inMax - inMin));
}


// =============================================================================
// 8. PERFORMANCE TIPS
// =============================================================================
// - Use noStroke() when fill-only shapes
// - Batch similar operations
// - For thousands of particles, consider pixel-level operations:
//     loadPixels(); ... set(x, y, color); ... updatePixels();
// - Use beginShape/endShape for complex paths instead of many line() calls
// - For static art, use noLoop() and only redraw on parameter changes
