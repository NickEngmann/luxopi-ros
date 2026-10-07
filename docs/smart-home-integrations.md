# Optional Home Assistant, Music Assistant, and Sendspin integrations

LuxoPI uses the same service boundaries as Reachy. Home Assistant is the shared
household state and automation layer; the robot bridge publishes health and
handles bounded high-level commands. Music Assistant receives commands over its
authenticated REST API. Sendspin is a separate, always-on system service that
registers the robot speaker as a Music Assistant player. ROS does not start or
stop the audio daemon, and media playback remains independent of robot motion
and voice processing.

## Robot credentials and endpoints

On the robot, store secrets in private files, following Reachy's
`~/.config/reachy/{ha_token,ma_token,ma_url}` convention:

```sh
install -d -m 700 ~/.config/luxopi
install -m 600 /dev/null ~/.config/luxopi/ha_token
install -m 600 /dev/null ~/.config/luxopi/ma_token
printf '%s\n' 'http://garden.local:8123' > ~/.config/luxopi/ha_url
printf '%s\n' 'http://garden.local:8095' > ~/.config/luxopi/ma_url
chmod 600 ~/.config/luxopi/ha_url ~/.config/luxopi/ma_url
```

Put the Home Assistant and Music Assistant profile tokens in their respective
token files. `LUXOPI_CONFIG_DIR` can change the directory. Environment overrides
`LUXOPI_HA_URL`, `LUXOPI_HA_TOKEN`, `LUXOPI_MA_URL`, and `LUXOPI_MA_TOKEN` remain
available for containers and tests. The defaults match the Reachy topology:
Home Assistant at `http://100.110.232.145:8123`; Music Assistant falls back to
port 8095 on the Home Assistant host. A `ma_url` file allows LAN/Tailscale
selection in deployments where the robot and Garden are on different networks.

Launch the optional ROS adapter with:

```sh
ros2 launch luxo_behaviors luxo_system.launch.py enable_smart_home_bridge:=true
```

Set `LUXOPI_MA_PLAYER_ID` to the robot's Sendspin player ID from Music
Assistant. The adapter writes `sensor.luxopi_state` and
`binary_sensor.luxopi_available` through the HA REST state API, as documented
for Reachy's temporary status entities. Home Assistant remains the shared
state surface; use its official Music Assistant integration for normal
`media_player` entities and household automations.

The bridge calls HA service APIs for source selection. `open Spotify` requires
`LUXOPI_HA_MUSIC_PLAYER_ENTITY` to name the configured Home Assistant
`media_player` entity. Optional `LUXOPI_HA_COMMANDS=true` subscribes to the HA
WebSocket API and accepts only allowlisted animation and media events. Direct
joint or motor commands are never accepted from HA events. The worker keeps
network timeouts away from ROS callbacks, and an HA outage does not affect
local motion or safety behavior.

## Sendspin player service

Install the official Sendspin client in the robot's system environment and
review [`systemd/luxopi-sendspin.service`](../systemd/luxopi-sendspin.service).
Install it as a dedicated systemd unit rather than enabling a child process in
the ROS bridge. The unit runs under the unprivileged `luxopi` account, restarts
after failures, and always uses `--hardware-volume false`; Music Assistant must
change software music gain without changing the hardware mixer shared with any
voice or microphone path.

Before enabling the unit on hardware, set its `User`/`Group` and ALSA device to
the robot's actual audio setup. If voice and music share an ALSA card, configure
a shared mixer such as ALSA `dmix`; do not point a second process at an
exclusive `default`/hardware device. The simulation container has no physical
audio device, so this service is a deployment template and is not enabled by
simulator tests. Use a systemd drop-in to add `--audio-device <shared-device>`
after verifying the robot's audio path.

## Validation

Offline tests cover HA authentication and service calls, HA event allowlisting,
Music Assistant's command/args REST contract, file-based credentials, endpoint
fallback, and the separate Sendspin systemd service. No credentials, network
music server, or physical speaker are required. The bridge and Sendspin service
remain opt-in on hardware.

The deployment follows [Reachy's HA state helper](https://github.com/NickEngmann/smarthome-reachy-mini-display/blob/main/robot/marisol_backend/ha_state.py),
[Reachy's Music Assistant client](https://github.com/NickEngmann/smarthome-reachy-mini-display/blob/main/robot/marisol_backend/marisol_realtime.py),
and [Reachy's Sendspin systemd unit](https://github.com/NickEngmann/smarthome-reachy-mini-display/blob/main/robot/system/reachy-sendspin.service).
