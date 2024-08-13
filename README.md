# MeshLink
Forked from [Murturtle/MeshLink](https://github.com/murturtle/MeshLink)
## Features

 - Send messages to and from discord
 - Send packet information to discord

 
 ### Mesh only
 - Weather forecast
 - Ping
 - HF condition checker
 - Time
 - Mesh statistics
 - DM Debug (show 'toID' / 'fromID')

### WIP
- SOS
- NEW: Initial testing for Mesh DMs from discord (WIP/Testing, possibly broken)
- NEW: MeshLink responses as DMs to DM request commands, broadcast responses to broadcast commands (WIP, but working)

## Commands
**prefix + command (default prefix is $)**
### Discord
send (message) - *`$send Hello from Discord.`*
dm (!mesh node number) (message) - *`$dm !12345abc Test DM to node 12345abc from Discord.` (use `dmdebug` to get NodeID until shortnames are implemented)*

### Mesh
ping
weather
hf
time
mesh
dmdebug

## Setup 

 1. Download the python script and config-example.yml from Github
 2. Rename config-example.yml to config.yml before editing (step 10)
 3. Install the Meshtastic python CLI https://meshtastic.org/docs/software/python/cli/installation/
 4. Install discord py https://discordpy.readthedocs.io/en/latest/intro.html
 5. Create a discord bot https://discord.com/developers
 6. Give it admin permission in your server and give it read messages intent (google it if you don't know what to do)
 7. Invite it to a server
 8. Get the discord channel id (this is where the messages will go) (again google a tutorial if don't know how to get the channel id)
 9. Get the discord bot token
 10. Add your discord bot token and channel id(s) to config.yml
 11. If you are using serial set `use_serial` to `True` otherwise get your nodes ip and put it into the `radio_ip` setting
 12. Run the script

## Suggestions/Feature Requests
Put them in issues.
