# Updates / Versioning (Don't change unless forking the project)
update_check_url = "https://raw.githubusercontent.com/brad07x/MeshLink/main/rev"
update_url = "https://github.com/brad07x/MeshLink"
rev = 2

# Imports
import yaml
import xml.dom.minidom
import os
from pubsub import pub
import discord
from meshtastic.tcp_interface import TCPInterface
from meshtastic.serial_interface import SerialInterface
from meshtastic.protobuf import portnums_pb2
import asyncio
import time
import requests

## Config Processing
# Load Config
with open("./config.yml",'r') as file:
    config = yaml.safe_load(file)

# Define Config Options
config_options = [
    "max_message_length",
    "message_channel_ids",
    "info_channel_ids",
    "token",
    "prefix",
    "discord_prefix",
    "use_serial",
    "radio_ip",
    "send_channel_index",
    "ignore_self",
    "send_packets",
    "verbose_packets",
    "weather_lat",
    "weather_long",
    "max_weather_hours",
    "ping_on_messages",
    "message_role",
    "use_discord",
    "send_mesh_commands_to_discord",
    "guild_id",
]

# Check for missing config options
for i in config_options:
    if i not in config:
        print("Config option "+i+" missing in config.yml (check github for example)")
        exit()

# Check for unneeded config options
for i in config:
    if i not in config_options:
        print("Config option "+i+" is not needed anymore")

## Update Check
oversion = requests.get(update_check_url)
if(oversion.ok):
    if(rev < int(oversion.text)):
        for i in range(10):
            print("New MeshLink update ready "+update_url)

## Initialize Globals
# Discord User ID mappings for Mentions
discord_user_ids = {}


## Discord Client Setup
# Discord Client Intents
intents = discord.Intents.default()
intents.message_content = True # Enable message content intent for processing commands, ensure bot settings match
intents.members = True  # Enable member intent for dynamic lookups of guild (server) members' User IDs - needed for mentions

# Enable/Disable
if config["use_discord"]:
    client = discord.Client(intents=intents)
else:
    client = None

# Discord User ID Mappings for Guild/Server - Mentions
async def update_discord_user_ids():
    global discord_user_ids
    guild = discord.utils.get(client.guilds, id=config["guild_id"])
    if guild:
        for member in guild.members:
            print(f"Member found: {member.name} with ID {member.id}")
            discord_user_ids[member.name] = member.id
        print("Updated discord_user_ids:", discord_user_ids)
    else:
        print("Guild not found. Check conifg template for formatting and restart.")

# Discord - Formatting for Mentions
def format_mentions(message, user_id_map):
    for username, user_id in user_id_map.items():
        mention = f"<@{user_id}>"
        message = message.replace(f"@{username}", mention)
    return message

# Discord Message Send & Format Mentions
def send_msg(message):
    global config, discord_user_ids
    print(message)
    if config["use_discord"]:
        if client.is_ready():
            formatted_message = format_mentions(message, discord_user_ids)
            for channel_id in config["message_channel_ids"]:
                asyncio.run_coroutine_threadsafe(client.get_channel(channel_id).send(formatted_message), client.loop)

# Discord Info Packet Send
def send_info(message):
    global config
    print(message)
    if config["use_discord"]:
        if (client.is_ready()):
            for i in config["info_channel_ids"]:
                asyncio.run_coroutine_threadsafe(client.get_channel(i).send(message),client.loop)

# ??? - Forked from Murturtle/MeshLink - Thanks for sharing a great project!
def asdf(a):
    print("ACK")
    print(a)

## Discord Client Initialization/Startup

if config["use_discord"]:
    # Complete login and update Discord Guild User IDs for Mentions; send ready message to Discord.
    @client.event
    async def on_ready():   
        print('Logged in as {0.user}'.format(client))
        await update_discord_user_ids()
        print("discord_user_ids:", discord_user_ids)
        print(f'Logged in as {client.user.name}')
        send_msg("MeshLink ready...")

    # $send (message) - Process incoming Discord messages using the 'send' command and bridge to mesh.
    @client.event
    async def on_message(message):
        global interface
        if message.author == client.user:
            return
        if message.content.startswith(config["discord_prefix"]+'send'):
            if (message.channel.id in config["message_channel_ids"]):
                await message.channel.typing()
                trunk_message = message.content[len(config["discord_prefix"]+"send"):]
                final_message = message.author.name+">"+ trunk_message
                
                if(len(final_message) < config["max_message_length"] - 1):
                    await message.reply(final_message)
                    interface.sendText(final_message,channelIndex = config["send_channel_index"])
                    print(final_message)
                else:
                    await message.reply("(trunked) "+final_message[:config["max_message_length"]])
                    interface.sendText(final_message,channelIndex = config["send_channel_index"])
                    print(final_message[:config["max_message_length"]])

     # $dm (shortname) (message) - Process incoming Discord messages using the 'dm' command and send as DM to specified mesh node using shortname.
        elif message.content.startswith(config["discord_prefix"] + 'dm'):
            if message.channel.id in config["message_channel_ids"]:
                await message.channel.typing()
                # Parse Discord DM Command - $dm (node shortname) (message)
                parts = message.content[len(config["discord_prefix"] + "dm"):].strip().split(" ", 1)

                if len(parts) < 2:
                    await message.reply("Usage: `$dm <shortName> <message>`")
                    return

                shortName = parts[0].strip()
                dm_message = parts[1].strip()

                # Resolve shortName to nodeId
                nodeid = shortNameToNodeId(interface, shortName)

                if nodeid is None:
                    await message.reply(f"Node with shortName `{shortName}` not found.")
                    return

                # Construct the final DM message
                final_dm_message = message.author.name + " > " + dm_message

                # Check the length of the message - send in full if less than max
                if len(final_dm_message) < config["max_message_length"] - 1:
                    await message.reply(f"DM to {shortName} ({nodeid}): {final_dm_message}")
                    interface.sendText(final_dm_message, channelIndex=config["send_channel_index"], destinationId=nodeid)
                    print(final_dm_message)
                # If message exceeds max, truncate and send first part to mesh, discard the rest   
                else:
                    await message.reply(f"(Truncated) DM to {shortName} ({nodeid}): " + final_dm_message[:config["max_message_length"]])
                    interface.sendText(final_dm_message[:config["max_message_length"]], channelIndex=config["send_channel_index"], destinationId=nodeid)
                    print(final_dm_message[:config["max_message_length"]])
                
            else:
                return

## Meshtastic Functions
# Initialization/Node Ready - Send Message to Mesh
def onConnection(interface, topic=pub.AUTO_TOPIC):

    print("Node ready")
    interface.sendText("MeshLink ready...",channelIndex = config["send_channel_index"])
    #a = interface.sendText("hola!")
    #print(a.id)
    #interface._addResponseHandler(a.id,asdf)

    #print(a)

# Mesh Username & Packet Details Processing
def genUserName(interface, packet, details=True):
    if(packet["fromId"] in interface.nodes):
        if(interface.nodes[packet["fromId"]]["user"]):
            ret = "`"+str(interface.nodes[packet["fromId"]]["user"]["shortName"])+" "
            if details:
                ret+= packet["fromId"]+" "
            ret+= str(interface.nodes[packet["fromId"]]["user"]["longName"])+"`"
        else:
            ret = str(packet["fromId"])

        if details:    
            if("position" in interface.nodes[packet["fromId"]]):
                if("latitude" in interface.nodes[packet["fromId"]]["position"] and "longitude" in interface.nodes[packet["fromId"]]["position"]):
                    ret +=" [map](<https://www.google.com/maps/search/?api=1&query="+str(interface.nodes[packet["fromId"]]["position"]["latitude"])+"%2C"+str(interface.nodes[packet["fromId"]]["position"]["longitude"])+">)"
            
        if("hopLimit" in packet):
            if("hopStart" in packet):
                ret+=" `"+str(packet["hopStart"]-packet["hopLimit"])+"`/`"+str(packet["hopStart"])+"`"
            else:
                ret+=" `"+str(packet["hopLimit"])+"`"
        return ret
    else:
        return "`"+str(packet["fromId"])+"`"


# Mesh Packet Receive/Decode
def onReceive(packet, interface):
    # Debugging: Print Verbose Packets
    if(config["verbose_packets"]):
        print("############################################")
        print(packet)
        print("--------------------------------------------")
    # Initialize blank final message    
    final_message = ""
    
    # Handle Decoded Incoming Packet
    if("decoded" in packet):
        
        print("decoded")
        
        # Incoming Decoded Text Message 
        if(packet["decoded"]["portnum"] == "TEXT_MESSAGE_APP"):
            # Prep for bridging incoming mesh text messages - Generate final Discord message/add username/format mentions
            final_message += genUserName(interface,packet,details=False)
            text = packet["decoded"]["text"]
            final_message += " > " + format_mentions(text, discord_user_ids)
            
            # Handle 'Ping on Messages' case/config option in Discord message
            if(config["ping_on_messages"]):
                final_message += "\n||"+config["message_role"]+"||"

            # Handle Mesh-Only Commands
            if(text.startswith(config["prefix"])):
                noprefix = text[len(config["prefix"]):]

                # Ping - Respond with 'pong' message either as broadcast or DM to source node
                if(noprefix.startswith("ping")):
                    final_ping = "pong"
                    if (packet["toId"] != '^all'):
                        interface.sendText(final_ping,channelIndex=config["send_channel_index"], destinationId=packet["fromId"])
                    elif (packet["toId"] == '^all'):
                        interface.sendText(final_ping,channelIndex=config["send_channel_index"])
                    if(config["send_mesh_commands_to_discord"]):
                            send_msg("`MeshLink`> "+final_ping)
                            
                # Help - Respond with help message/commands list either as broadcast or DM to source node         
                elif (noprefix.startswith("help")):
                    final_help = "<- Help ->\n"+"ping\n"+"time\n"+"weather\n"+"hf\n"+"mesh\n"+"dmdebug"
                    interface.sendText(final_help,channelIndex=config["send_channel_index"], destinationId=packet["fromId"])
                    if(config["send_mesh_commands_to_discord"]):
                            send_msg("`MeshLink`> "+final_help)
                            
                # Direct Message Debugging - Respond with message including fromID/toID either as broadcast or DM to source node
                elif (noprefix.startswith("dmdebug")):
                    final_dmdebug = "*** Incoming Message - DMDebug ***\n"+"From ID: "+packet["fromId"]+"\n"+"To ID: "+packet["toId"]
                    if (packet["toId"] != '^all'):
                        interface.sendText(final_dmdebug,channelIndex=config["send_channel_index"], destinationId=packet["fromId"])
                    elif (packet["toId"] == '^all'):
                        interface.sendText(final_dmdebug,channelIndex=config["send_channel_index"])
                    if(config["send_mesh_commands_to_discord"]):
                            send_msg("`MeshLink`> "+final_dmdebug)
                
                # Time - Respond with current time as broadcast or DM to source node
                elif (noprefix.startswith("time")):
                    final_time = time.strftime('%H:%M:%S')
                    if (packet["toId"] != '^all'):
                        interface.sendText(final_time,channelIndex=config["send_channel_index"], destinationId=packet["fromId"])
                    elif (packet["toId"] == '^all'):
                        interface.sendText(final_time,channelIndex=config["send_channel_index"])
                    if(config["send_mesh_commands_to_discord"]):
                        send_msg("`MeshLink`> "+final_time)
                
                # Weather - Respond with weather forecast (see configuration) as broadcast or DM to source node
                elif (noprefix.startswith("weather")):
                    weather_data_res = requests.get("https://api.open-meteo.com/v1/forecast?latitude="+config["weather_lat"]+"&longitude="+config["weather_long"]+"&hourly=temperature_2m,precipitation_probability&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timeformat=unixtime&timezone=auto")
                    weather_data = weather_data_res.json()
                    final_weather = ""
                    if (weather_data_res.ok):
                        for j in range(config["max_weather_hours"]):
                                i = j+int(time.strftime('%H'))
                                final_weather += str(int(i)%24)+" "
                                final_weather += str(round(weather_data["hourly"]["temperature_2m"][i]))+"F "+str(weather_data["hourly"]["precipitation_probability"][i])+"%🌧️\n"
                        final_weather = final_weather[:-1]
                    else:
                        final_weather += "error fetching"
                    print(final_weather)
                    if (packet["toId"] != '^all'):
                        interface.sendText(final_weather,channelIndex=config["send_channel_index"], destinationId=packet["fromId"])
                    elif (packet["toId"] == '^all'):
                        interface.sendText(final_weather,channelIndex=config["send_channel_index"])
                    if(config["send_mesh_commands_to_discord"]):
                        send_msg("`MeshLink`> "+final_weather)
                
                # HF Conditions - Respond with HF conditions as broadcast or DM to source node
                elif (noprefix.startswith("hf")):
                    final_hf = ""
                    solar = requests.get("https://www.hamqsl.com/solarxml.php")
                    if(solar.ok):
                        solarxml = xml.dom.minidom.parseString(solar.text)
                        for i in solarxml.getElementsByTagName("band"):
                            final_hf += i.getAttribute("time")[0]+i.getAttribute("name") +" "+str(i.childNodes[0].data)+"\n"
                        final_hf = final_hf[:-1]
                    else:
                        final_hf += "error fetching"
                    print(final_hf)
                    if (packet["toId"] != '^all'):
                        interface.sendText(final_hf,channelIndex=config["send_channel_index"], destinationId=packet["fromId"])
                    elif (packet["toId"] == '^all'):
                        interface.sendText(final_hf,channelIndex=config["send_channel_index"])

                    if(config["send_mesh_commands_to_discord"]):
                        send_msg("`MeshLink`> "+final_hf)
                
                # Mesh Statistics - Respond with collected/calculated mesh statistics as broadcast or DM to source node
                elif (noprefix.startswith("mesh")):
                    final_mesh = "<- Mesh Stats ->"

                    # Calculate Average Channel Utilization
                    nodes_with_chutil = 0
                    total_chutil = 0
                    for i in interface.nodes:
                        a = interface.nodes[i]
                        if "deviceMetrics" in a:
                            if "channelUtilization" in a['deviceMetrics']:
                                nodes_with_chutil += 1
                                total_chutil += a['deviceMetrics']["channelUtilization"]

                    if nodes_with_chutil > 0:
                        avg_chutil = total_chutil / nodes_with_chutil
                        avg_chutil = round(avg_chutil, 1)  # Round to the nearest tenth
                        final_mesh += "\n chutil avg: " + str(avg_chutil)
                    else:
                        final_mesh += "\n chutil avg: N/A"
                        
                    if(config["send_mesh_commands_to_discord"]):
                        send_msg("`MeshLink`> "+final_mesh)

                    # # temperature average 
                    # nodes_with_temp = 0
                    # total_temp = 0
                    # for i in interface.nodes:
                    #     a = interface.nodes[i]
                    #     if "environmentMetrics" in a:
                    #         if "temperature" in a['environmentMetrics']:
                    #             nodes_with_temp += 1
                    #             total_temp += a['environmentMetrics']["temperature"]

                    # if nodes_with_temp > 0:
                    #     avg_temp = total_temp / nodes_with_temp
                    #     avg_temp = round(avg_temp, 1)  # Round to the nearest tenth
                    #     final_mesh += "\n temp avg: " + str(avg_temp)
                    # else:
                    #     final_mesh += "\n temp avg: N/A"
                    
                    if (packet["toId"] != '^all'):
                        interface.sendText(final_mesh,channelIndex=config["send_channel_index"], destinationId=packet["fromId"])
                    elif (packet["toId"] == '^all'):
                        interface.sendText(final_mesh,channelIndex=config["send_channel_index"])
                        
            # If not mesh-only command, bridge generated/final message with user info & mentions formatting to Discord        
            send_msg(final_message)
            
        else:
            # Bridge non-text mesh packets (device, position, environmental, and neighbor info) to Discord if configured.
            if(config["send_packets"]):
                if((packet["fromId"] == interface.getMyNodeInfo()["user"]["id"]) and config["ignore_self"]):
                    print("Ignoring self")
                else:
                    final_message+=genUserName(interface,packet)+" > "+str(packet["decoded"]["portnum"])
            send_info(final_message)
    else:
        # Send info for encrypted or failed decode packets to Discord.
        final_message+=genUserName(interface,packet)+" > encrypted/failed"
        send_info(final_message)
        print("failed or encrypted")

# Short Name to NodeID Mapping for Discord->Mesh DMs
def shortNameToNodeId(interface, shortName):
    for nodeId, nodeInfo in interface.nodes.items():
        if "user" in nodeInfo and nodeInfo["user"].get("shortName") == shortName:
            return nodeId
    return None

## Meshtastic Setup & Initialization
pub.subscribe(onConnection, "meshtastic.connection.established")
pub.subscribe(onReceive, "meshtastic.receive")

if (config["use_serial"]):
    interface = SerialInterface()
else:
    interface = TCPInterface(hostname=config["radio_ip"], connectNow=True)

## Discord Initialization
try:
    if config["use_discord"]:
        client.run(config["token"])
    else:
        while True:
            time.sleep(1)
except discord.HTTPException as e:
    if e.status == 429:
        print("too many requests")
