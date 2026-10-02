# MatchCaller remote administration planning

These notes preserve the requirements discussed before archiving the development
worktree on October 2, 2026. No remote administration features were implemented
in this task. The existing application code was at commit `80551ca` and already
on `main` when these notes were saved.

## Agreed requirements

The user wants a web interface accessible while connected to the Abbey Tavern
Wi-Fi so tournament organizers can recover the display without unplugging and
reconnecting the Raspberry Pi. The interface should support both restarting
MatchCaller and rebooting the entire Pi. The proposed controls were clearly
separated, with confirmation for the full reboot; the user accepted both controls.

The Abbey Wi-Fi is open to everyone. The user explicitly requires a secure login
rather than treating access to the Wi-Fi as authorization to restart the display.

## Current deployment

`scripts/setup_bashrc.sh` installs a console-login launch block in `.bashrc`.
`start_matchcaller.sh` reads `STARTGG_API_TOKEN` from the environment, waits for
network connectivity, pulls repository updates, and launches the Python TUI.
The TUI itself is not currently managed by a dedicated systemd service. The
existing `matchcaller-display-log.service` captures diagnostics only.

The initial recommendation was to supervise the TUI with systemd and run the
control interface independently so it remains available when the TUI fails.
This is a proposed architecture, not an approved implementation design.

## Decisions still open

- Whether access must be restricted to Abbey Wi-Fi or whether an authenticated
  internet-accessible interface would also be acceptable. This was the last
  question asked and has not been answered.
- How organizers authenticate and how HTTPS certificates are provisioned.
  HTTPS was recommended because untrusted patrons share the network.
- How the control process receives narrowly scoped permission to restart the
  TUI and reboot the Pi.
- How organizers discover the control page and whether the venue network permits
  communication between Wi-Fi clients. This needs an onsite check.

## Deferred token rotation

An earlier concern about an expired start.gg token did not require an emergency
remote change. The user planned to update the token directly while onsite.
Future remote token rotation remains useful but was not implemented.

Encrypting a token to an existing Pi SSH public key was explored. A local public
key matched one GitHub account key, but the Pi's actual key was never confirmed.
Tailscale SSH and a dedicated age encryption key were later suggested; neither
was selected or provisioned. Do not assume any of these access paths exist on
the Pi, and do not commit plaintext credentials.
