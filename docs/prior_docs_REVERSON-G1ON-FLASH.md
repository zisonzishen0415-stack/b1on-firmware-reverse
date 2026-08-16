# Reverson G1on / MS-series — Flash & Validation Checklist (M4)

Built artifacts (2026-08-14):

- `ZoomMultistompZDL/build/probes/K9Probe.ZDL` — 9-knob handler probe (flash FIRST)
- `ZoomMultistompZDL/dist/Reverson.ZDL` — the 9-knob reverse reverb

Reverson ZDL build facts (from the linker): `.fardata: 0 bytes`, no `.switch:*`
sections, the only external symbol is `__c6xabi_divf` (resolved by the
bundled RTS blob), state carved lazily from `ctx[3]` (~160 KB of the 512 KB
floor). Same knob config as K9Probe: stock blobs for knobs 1..3, synthesized
LineSel clones for knobs 4..9.

## 0. Before touching the pedal

1. Back up the pedal's current effect list (Zoom Effect Manager: export/save).
2. Install [Zoom Effect Manager](https://zoomeffectmanager.com/en/download/)
   2.3.3+ and confirm it talks to the pedal (connect pedal FIRST, then open
   the app; see `research_docs/docs_INSTALLING-ZDLS.md`).

## 1. Flash K9Probe first (de-risks the 9-knob ABI)

1. In Zoom Effect Manager: Settings -> `Read Effects from folder` -> point at
   `ZoomMultistompZDL/build/probes/`.
2. Enable `Effects from devices` + `From Folder`, add **K9Probe**, write to
   the pedal.
3. Load K9Probe (Filter category) and run its pass criteria
   (`src/hardware_probes/k9probe/README.md`):
   - Page 1: Knob1..3 -> audible L/R gain steps per channel, no freeze.
   - Page 2: Knob4..6 -> no freeze, gain changes.
   - Page 3: Knob7..9 -> no freeze, gain changes.
   - Toggle bypass a few times.
   - **PASS** = every knob on all three pages changes the sound on its
     expected channel and the pedal never freezes.
4. If it freezes on a page 2/3 knob: stop and record which knob; the
   synthesized-clone ABI needs work (see k9probe README fail triage). Do NOT
   flash Reverson until K9Probe passes — they share the same handler config.

## 2. Flash Reverson

1. Point Zoom Effect Manager at `ZoomMultistompZDL/dist/` instead.
2. Add **Reverson**, write to the pedal.
3. If it flashes but does not appear in the Reverb category browser: install
   at least one stock Reverb effect first (known category-visibility quirk,
   same as the Drive-category case in `docs_INSTALLING-ZDLS.md`).

## 3. On-device checks (pass criteria)

1. **Load**: Reverson appears and loads in the Reverb category.
2. **Bypass**: toggle on/off — no freeze, dry passthrough when off.
3. **Page 1**: Mix -> dry/wet balance; Rev -> wash turns into a gated
   reverse swell at the top end; Space -> swell span/width grows.
4. **Page 2**: Tone -> dark/bright; Grain -> delay-like graininess turns
   smooth/reverb-like; Duck -> wet dips while playing.
5. **Page 3**: Mode -> the 5 positions change character in big steps
   (1 Wash / 2 Reverse / 3 Gated / 4 Shoegaze / 5 Space); Trig -> trigger
   behavior (low = every note blooms, high = only strong attacks); Predelay
   -> the swell starts later, the wash floor stays.
6. **Audio**: a palm-muted low riff should not turn to mud (wet HPF);
   picking a note after a chord should swell the previous chord backwards
   (the reverse layer) when Rev is high.
7. **Defaults**: a freshly added Reverson should sound like the `diiv`
   render (`out/v2_final_diiv.wav`) — the manifest defaults ARE the preset.

## 4. Record results

Update this file (or `research_docs/`) with: pedal model + firmware version,
whether K9Probe passed/failed and which knob failed, Reverson load/knob/audio
results, and any normalization oddities (raw param values that don't match
the 0..0.14 rail). The known open question is the exact raw scaling for the
synthesized knob-4..9 handlers — if a knob audibly behaves as 0 or max,
tweak `zoom_param_norm` usage in `reverson_zdl.c` and rebuild.
