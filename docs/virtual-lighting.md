# Simulated lamp feedback

The existing `state_manager` executable accepts `simulated_lighting` (boolean,
default false). Hardware launches retain the physical NeoPixel driver. Simulator
launches must explicitly set true: initialization selects the pure
`VirtualNeoPixelController` and never imports Blinka/board/neopixel drivers.

The virtual sink records solid RGBW, brightness, off/clear, breathing, spinning
dot/group and dual-color bouncing-direction effects invoked by the real state
callbacks. It is a visual simulation of requested effects, not measured electrical
LED feedback. Simulated clears skip physical settling sleeps and delayed-clear
threads. The physical path remains unchanged.

At the existing state publication rate (4 Hz), `/luxo/light_state` publishes a
bounded `std_msgs/String` JSON snapshot:

```json
{"simulated":true,"enabled":true,"state":"USER_CONTROL","pixel_count":60,"brightness":0.5,"rgbw":[255,255,255,0],"effect":"bouncing_direction_indicator","parameters":{"secondary_color":[0,100,255,0],"bounce_range":8,"blocking":false},"revision":7}
```

`effect` values are `off`, `solid`, `breathing`, `spinning_dot`, `spinning_group`,
and `bouncing_direction_indicator`. `parameters` describe the requested animation
(e.g. cycles, speed, group size, secondary color); the dashboard animates these
visually. There is one current snapshot, with no growing event history. `enabled`
is the light-control switch, and `effect=off`/zero RGBW may still show no light while
that switch is true (e.g. shutdown).

Input contracts remain production topics:
`/luxo/light_control` Bool; `/luxo/brightness_control` String `brightness:0.25`;
`/luxo/color_temp_control` String `color_temp:0.5`;
`/luxo/color_control` String `color:blue` (red/orange/yellow/green/cyan/blue/purple/white).
Their actual state-manager callbacks change the sink before telemetry publication.

`python3 -m pytest tests/test_virtual_lighting.py -q` covers real state effects,
color/brightness/on-off callback telemetry and absence of physical imports.
Native ROS/browser integration should additionally observe telemetry after sending
these input messages; input echo alone is insufficient evidence. Hardware LED
wiring, brightness and rendered timing remain unvalidated.
