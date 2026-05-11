# VA Effect Mapping

## Purpose

This document records the design direction for the effect layer in the real-time music system.
The goal is not to let valence and arousal directly twist isolated effect knobs, but to build
a stable macro-control layer that can shape the perceived emotional character of the sound.

This note is intentionally implementation-agnostic. It should guide future frontend audio work
whether the renderer remains on Tone.js, expands with custom Web Audio nodes, or adopts a more
specialized DSP path later.

## Current Understanding

The current system already separates responsibilities in a useful way:

- the backend decides emotion, harmony, and melody structure
- the frontend renders sound in real time
- valence/arousal are already available as compact control inputs

What is still missing is a stronger effect architecture. Right now, effect behavior is closer to
"parameter nudging" than "emotional sound design". The next step is to define a musically meaningful
control layer between VA and low-level effect nodes.

## Design Goals

- Make effects reflect emotional state in a perceptible but controlled way
- Avoid brittle one-to-one mappings such as `arousal -> reverb.wet`
- Keep the dry musical material intelligible
- Separate fast expressive change from slow environmental change
- Make the system extensible when more emotion features are added later

## Core Principle

VA should not directly control raw effect-node parameters.

Instead, VA should first be mapped into a small set of effect macros. Those macros should then drive
multiple low-level parameters together. This creates more coherent sound changes and reduces the risk
of unstable or unnatural responses.

Recommended flow:

`valence/arousal -> effect macros -> low-level effect parameters -> rendered sound`

## Recommended Effect Macros

The effect layer should expose a handful of high-level dimensions rather than many unrelated controls.

### 1. Space

Represents perceived distance, diffusion, room size, and environmental spread.

Typical low-level targets:

- reverb wetness
- reverb decay
- pre-delay
- stereo width
- delay send level
- diffusion or smear amount

Perceptual direction:

- lower arousal often supports larger, softer, more distant spaces
- higher arousal often benefits from tighter, drier, more immediate space
- lower valence may tolerate darker and more diffused tails

### 2. Clarity

Represents definition, openness, and how easily foreground material cuts through the mix.

Typical low-level targets:

- lowpass cutoff
- high-shelf gain
- transient preservation
- dry/wet balance
- compression intensity

Perceptual direction:

- higher valence often supports clearer and more open sound
- lower valence may benefit from softer, darker, or partially veiled sound
- clarity should not be confused with loudness

### 3. Grit

Represents roughness, instability, and controlled imperfection.

Typical low-level targets:

- saturation amount
- soft clipping
- detune depth
- wow/flutter amount
- bit reduction or noise blend

Perceptual direction:

- lower valence can support slightly more grit
- high arousal can also support additional edge, but should not always become distorted
- grit should be used selectively, not as a constant global texture

### 4. Motion

Represents internal movement in the effect field and timbral surface.

Typical low-level targets:

- tremolo depth/rate
- autopan depth/rate
- chorus depth
- filter LFO depth/rate
- delay modulation amount

Perceptual direction:

- arousal is the main driver of motion speed and strength
- low arousal can still have movement, but slower and broader
- motion should enhance life, not distract from the melody

### 5. Focus

Represents whether the sound feels forward and intimate or recessed and atmospheric.

Typical low-level targets:

- dry level versus wet level
- early reflections versus tail emphasis
- transient accent
- center image strength
- front/back mix placement

Perceptual direction:

- high focus feels close, direct, and readable
- low focus feels distant, floating, and less immediate

## VA Mapping Principles

Valence and arousal should have different jobs in the mapping design.

### Valence

Valence should primarily influence the emotional color of the effect field:

- brightness versus darkness
- openness versus veil
- purity versus roughness
- optimistic sheen versus muted heaviness

Valence is usually a better driver for timbral color than for motion speed.

### Arousal

Arousal should primarily influence energetic behavior:

- modulation speed
- transient sharpness
- space tightening or loosening
- responsiveness of macro movement

Arousal is usually a better driver for how active the effect system feels over time.

## Derived Macro Strategy

Even if the system only exposes valence and arousal upstream, the renderer should derive several
secondary control values before touching the effect nodes.

Example derived macros:

- `space`
- `clarity`
- `grit`
- `motion`
- `focus`

This keeps the audio graph stable when the emotion model changes in the future. If later work adds
emotion categories, tension, confidence, or uncertainty, those can feed the same macro layer without
rewriting the entire effect pipeline.

## Mapping Style Recommendations

### Avoid purely linear mappings

Simple linear mapping often sounds artificial because human perception of space, brightness, and motion
is not linear.

Preferred alternatives:

- S-curves for gradual but expressive response
- piecewise mappings for threshold behavior
- clamped regions where small VA changes do not immediately alter the sound

### Use asymmetry where helpful

Not every parameter should respond symmetrically around the emotional midpoint.

Examples:

- grit may remain low across most of the range, then rise more noticeably at lower valence
- space may change slowly at first, then expand more at very low arousal
- clarity may be more sensitive in the upper valence range than the lower one

### Map one macro to multiple targets

A macro should modify a small cluster of related node parameters together.

Example:

`space` could update:

- reverb wet
- reverb decay
- stereo width
- delay send

This creates a stronger perceptual identity than moving only one parameter.

## Time-Scale Design

Different effect changes should happen at different speeds.

This is one of the most important constraints in the whole system.

### Fast response

Good candidates:

- filter cutoff
- wet balance within a safe range
- modulation depth
- modulation rate

Suggested behavior:

- react within roughly 100 to 500 ms
- used for expressive liveliness

### Medium response

Good candidates:

- delay feedback
- stereo width
- saturation amount
- center/side balance

Suggested behavior:

- react over roughly 500 ms to 2 s
- used for phrase-level emotional adaptation

### Slow response

Good candidates:

- room character
- reverb personality
- patch-to-patch effect weighting
- deep atmospheric identity

Suggested behavior:

- react over roughly 2 to 8 s or by phrase boundaries
- used to avoid abrupt environmental jumps

Guiding rule:

Emotion recognition can change quickly. Environmental identity should change slowly.

## Effect Chain Layering

The effect system should be organized in layers so each layer has a clear job.

### Layer 1: Tone Shaping

Purpose:

- shape brightness
- control warmth
- add light saturation
- manage intelligibility

Likely tools:

- filter
- EQ
- saturation
- transient shaping

### Layer 2: Space

Purpose:

- define size, depth, and spread
- place the sound in an emotional environment

Likely tools:

- reverb
- delay
- stereo spread
- early reflection balance

### Layer 3: Motion

Purpose:

- add movement without rewriting composition logic
- make sustained layers feel alive

Likely tools:

- chorus
- tremolo
- autopan
- slow filter modulation

## Safety Constraints

The effect system should preserve musical readability.

Important constraints:

- do not let wet signals dominate the direct signal
- avoid making every parameter react at once
- avoid stacking brightness, width, motion, and reverb into the same extreme state
- preserve note attacks enough for melody tracking
- keep bass effects tighter than pad effects unless intentionally stylized

## Voice-Specific Effect Thinking

Different layers should not share the exact same effect behavior.

### Pad

Most suitable for:

- larger space
- slower motion
- stereo spread
- deeper atmosphere

### Melody

Most suitable for:

- moderate clarity
- selective space
- expressive but controlled motion
- readable foreground placement

### Bass

Most suitable for:

- restrained space
- low-end-safe saturation
- minimal width below the crossover region
- small and deliberate modulation

## Example Qualitative Behaviors

These are not final formulas. They are listening-oriented design heuristics.

### High valence + low arousal

Expected feeling:

- open
- soft
- calm
- slightly spacious

Possible effect direction:

- medium-high clarity
- moderate space
- low grit
- slow gentle motion

### High valence + high arousal

Expected feeling:

- bright
- immediate
- energetic
- focused

Possible effect direction:

- high clarity
- lower or tighter space
- low to medium grit
- faster motion with restrained wetness

### Low valence + low arousal

Expected feeling:

- dark
- distant
- suspended
- reflective

Possible effect direction:

- lower clarity
- higher diffusion
- moderate space
- low-speed motion
- slight grit if desired

### Low valence + high arousal

Expected feeling:

- tense
- unstable
- pressured
- edgy

Possible effect direction:

- medium-low clarity
- tighter but harsher space
- elevated grit
- faster motion
- stronger transient contrast

## Near-Term Experiment Plan

Suggested first experiments:

1. Define a first-pass macro model with `space`, `clarity`, `grit`, `motion`, and `focus`
2. Assign each macro to 2 to 4 low-level effect parameters
3. Test macro smoothing with separate fast, medium, and slow ramps
4. Tune pad, melody, and bass separately instead of sharing one global profile
5. A/B test a few stable emotional scenes rather than continuously sweeping random VA values

## Candidate Preset Personalities

Useful starting points for controlled experimentation:

- `clear_open`
- `dark_diffused`
- `tense_gritty`

These should be treated as perceptual anchors, not fixed endpoints. VA can interpolate between them
through the macro layer.

## Future Extensions

Later revisions may include:

- voice-dependent macro weighting
- phrase-aware effect transitions
- scene-level emotional memory
- additional upstream emotion descriptors beyond VA
- custom Web Audio or AudioWorklet nodes for better DSP control

## Summary

The main design move is simple:

do not map VA directly to isolated effect knobs

Instead:

- derive a small macro-control layer
- map each macro to a coherent group of parameters
- give different parameters different response times
- tune effects separately for pad, melody, and bass

That approach should make the effect layer more expressive, more stable, and much easier to evolve.
