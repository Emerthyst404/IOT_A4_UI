# FILE: control_panel.py
# PROJECT: IOT A4
# COURSE: SENG3030 - Internet of Things
# DATE: 12-01-2025
# AUTHORS: Josh Horsley, Josh Rice, Christian Tan and Kalina Cathcart
# DESCRIPTION: Control Panel for managing MQTT device subscriptions

import streamlit as st
import paho.mqtt.client as mqtt 
import queue
import time 
from datetime import datetime
import random
import ssl
from collections import defaultdict

# Set up message queue
@st.cache_resource
def get_msg_q():
    return queue.Queue()
MSG_Q = get_msg_q()

# Webpage Title 
st.title("MQTT Control Panel")

# MQTT Settings
MQTT_BROKER = "p07da41d.ala.us-east-1.emqxsl.com"
MQTT_PORT = 8883
MQTT_USERNAME = "Jhorsley3072"
MQTT_PASSWORD = "3072"
BASE_TOPIC = "SENG3030/Thursday/Jhorsley3072/"

# Discovery topic set to listen to eveything on the SENG3030 channel 
DISCOVERY_TOPIC = "SENG3030/#"

# Session State Initialization
if 'mqtt_connected' not in st.session_state:
    st.session_state.mqtt_connected = False

if 'discovered_topics' not in st.session_state:
    st.session_state.discovered_topics = set()

if 'topic_last_seen' not in st.session_state:
    st.session_state.topic_last_seen = {}

if 'managed_devices' not in st.session_state:
    st.session_state.managed_devices = []

if 'device_subscriptions' not in st.session_state:
    st.session_state.device_subscriptions = defaultdict(set)


# FUNCTION:     on_connect
# PARAMETERS:   client - MQTT client object
#               userdata - user-defined data (not used here)
#               flags - connection flags
#               rc - result code (0 = success)
# RETURNS:      none
# DESCRIPTION:  When the connection to MQTT broker is complete, the program needs are initialized. 
#               If the connection is ok, the function will update the session state, and subscribe to all topics. 
#               If the connection fails, it will pair the appropriate error message to help identify what needs correction.              
def on_connect(client, userdata, flags, rc):
    print(f"Connection attempt result: rc={rc}")
    
    ok = (rc == 0)
    MSG_Q.put({"type": "status", "connected": ok})

    if ok:
        st.session_state.mqtt_connected = True
        print("Successfully connected!")
        # Subscribe to discovery topic
        client.subscribe(DISCOVERY_TOPIC)
        print(f"Subscribed to: {DISCOVERY_TOPIC}")
    else:
        st.session_state.mqtt_connected = False
        error_messages = {
            1: "Incorrect protocol version",
            2: "Invalid client identifier",
            3: "Server unavailable",
            4: "Bad username or password",
            5: "Not authorized"
        }
        error_msg = error_messages.get(rc, f"Unknown error: {rc}")
        print(f"Connection failed: {error_msg}")
        MSG_Q.put({"type": "status", "connected": False, "rc": rc, "error": error_msg})


# FUNCTION:    on_message
# PARAMETERS:  client - MQTT client object
#              userdata - user-defined data (not used here)
#              msg - message object containing topic and payload
# RETURNS:     None
# DESCRIPTION: whenever there is a message from any subscription topic, this function will
#              decode the message from bytes into a string, and put it into the queue for streamlit to process.  
def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8')
        topic = msg.topic
        timestamp = datetime.now()
        
        MSG_Q.put({
            "type": "message", 
            "topic": topic, 
            "payload": payload,
            "timestamp": timestamp
        })
        
    except Exception as e:
        print(f"Error processing message: {e}")
        MSG_Q.put({"type": "error", "error": str(e)})


# FUNCTION:    on_disconnect
# PARAMETERS:  client - MQTT client object
#              userdata - user-defined data (not used here)
#              rc - result code
# RETURNS:     None
# DESCRIPTION: Called when client disconnects from the MQTT broker
def on_disconnect(client, userdata, rc):
    st.session_state.mqtt_connected = False
    print(f"Disconnected with result code: {rc}")


# Create MQTT client and ensure it is only created once 
if 'mqtt_client' not in st.session_state:
    print("Creating new MQTT client...")
    
    # Create unique ID for the connection 
    client_id = f"control_panel_{random.randint(10000, 99999)}"
    client = mqtt.Client(client_id=client_id, callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
    
    # configure TLS/SSL for secure connection to port 8883
    client.tls_set(
        ca_certs="cert.pem",  
        tls_version=ssl.PROTOCOL_TLS_CLIENT
    )
    client.tls_insecure_set(False)
    
    # Register functions to be called during corresponding events 
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    # Username and password for connection
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    # Attmept to connect 
    try:
        print(f"Connecting to {MQTT_BROKER}:{MQTT_PORT}")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        st.session_state.mqtt_client = client
        print("Connection initiated")
    except Exception as e:
        st.error(f"Connection failed: {e}")
        print(f"Exception: {e}")


# Process messages from queue
while True:
    try:
        msg = MSG_Q.get_nowait()
    except queue.Empty:
        break

    if msg['type'] == 'status':
        st.session_state.mqtt_connected = msg['connected']
    elif msg['type'] == 'message':
        topic = msg['topic']
        timestamp = msg['timestamp']
        
        # Add to discovered topics
        st.session_state.discovered_topics.add(topic)
        st.session_state.topic_last_seen[topic] = timestamp


# Connection Status
if st.session_state.mqtt_connected:
    st.success("Connected to MQTT Broker")
else:
    st.warning("Connecting to MQTT Broker...")

st.divider()

# Control Panel Layout
col1, col2 = st.columns([1, 1])

with col1:

    # Topic Section 
    st.subheader("Discovered Topics")
    
    # Filter options for topics 
    filter_text = st.text_input("Filter topics", placeholder="e.g., sht40, mic")
    
    # Sort the topics found under SENG3030
    sorted_topics = sorted(st.session_state.discovered_topics)
    if filter_text:
        sorted_topics = [t for t in sorted_topics if filter_text.lower() in t.lower()]
    
    st.write(f"**Total topics discovered:** {len(st.session_state.discovered_topics)}")
    st.write(f"**Filtered topics:** {len(sorted_topics)}")
    
    # Display the topics in an expander
    with st.expander("View All Topics", expanded=True):
        if sorted_topics:
            for topic in sorted_topics[:50]:  # Limit display to 50
                last_seen = st.session_state.topic_last_seen.get(topic)
                if last_seen:
                    time_ago = (datetime.now() - last_seen).total_seconds()
                    st.text(f"• {topic} ({time_ago:.0f}s ago)")
                else:
                    st.text(f"• {topic}")
            
            if len(sorted_topics) > 50:
                st.info(f"Showing 50 of {len(sorted_topics)} topics. Use filter to narrow down.")
        else:
            st.info("No topics discovered yet. Messages will appear here as they arrive.")

with col2:
   # Add/manage devices section
    st.subheader("Device Management")
    st.write("**Configure Devices:**")
    
    # Add new device
    with st.form("add_device_form"):
        new_device = st.text_input("Device ID", placeholder="e.g., ppatel4567")
        add_button = st.form_submit_button("Add Device")
        
        if add_button and new_device:
            if new_device not in st.session_state.managed_devices:
                st.session_state.managed_devices.append(new_device)
                st.success(f"Added device: {new_device}")
            else:
                st.warning(f"Device {new_device} already exists")
    
        # Display managed devices
    if st.session_state.managed_devices:
        st.write("**Managed Devices:**")
        for device in st.session_state.managed_devices:
            with st.expander(f"📱 {device}"):
                subs = st.session_state.device_subscriptions[device]
                st.write(f"Active subscriptions: {len(subs)}")
                
                # Fixed indentation here - moved left by one level
                if subs:
                    st.write("**Current subscriptions:**")
                    
                    for sub in list(subs):
                        # Create two columns: one for topic name, one for button
                        col_sub1, col_sub2 = st.columns([3, 1])
                        
                        with col_sub1:
                            st.text(sub)
                        
                        with col_sub2:
                            # Unsubscribe button for this topic
                            if st.button("❌", key=f"unsub_{device}_{sub}"):
                                # Send MQTT unsubscribe message to device
                                unsub_topic = f"{BASE_TOPIC}{device}/unsubscribe"
                                st.session_state.mqtt_client.publish(unsub_topic, sub)
                                
                                # Remove from local tracking
                                st.session_state.device_subscriptions[device].discard(sub)
                                
                               
                                st.success(f"Sent unsubscribe: {sub}")
                
                # Remove device
                if st.button("Remove Device", key=f"remove_{device}"):
                    st.session_state.managed_devices.remove(device)
                    del st.session_state.device_subscriptions[device]
                    st.rerun()
    else:
        st.info("No devices configured. Add a device above.")

st.divider()

# Subscription Management
st.subheader("Subscribe Device to Topic")

if st.session_state.managed_devices and st.session_state.discovered_topics:
    col_sub1, col_sub2, col_sub3 = st.columns([2, 2, 1])
    
    with col_sub1:
        target_device = st.selectbox(
            "Select Device",
            st.session_state.managed_devices,
            key="target_device"
        )
    
    with col_sub2:
        # Topic pattern input
        topic_pattern = st.text_input(
            "Topic Pattern",
            placeholder="SENG3030/Thursday/bjones1234/sht40/#",
            key="topic_pattern"
        )
    
    with col_sub3:
        st.write("")  # Spacer
        st.write("")  # Spacer
        if st.button("Subscribe", type="primary"):
            if topic_pattern and target_device:
                # Send subscribe message
                sub_topic = f"{BASE_TOPIC}{target_device}/subscribe"
                st.session_state.mqtt_client.publish(sub_topic, topic_pattern)
                st.session_state.device_subscriptions[target_device].add(topic_pattern)
                st.success(f"✅ Sent subscribe command to {target_device}")
                st.info(f"Topic: {sub_topic}")
                st.info(f"Payload: {topic_pattern}")
    
    # Quick subscribe buttons for discovered topics
    st.write("**Quick Subscribe (select from discovered):**")
    
    # Group topics by base path
    topic_groups = defaultdict(list)
    for topic in sorted(st.session_state.discovered_topics):
        parts = topic.split('/')
        if len(parts) >= 4:
            base = '/'.join(parts[:4])  # e.g., SENG3030/Thursday/user
            topic_groups[base].append(topic)
    
    for base, topics in list(topic_groups.items())[:5]:  # Show first 5 groups
        with st.expander(f"📂 {base}"):
            # Extract sensor types
            sensor_types = set()
            for topic in topics:
                parts = topic.split('/')
                if len(parts) >= 5:
                    sensor_types.add(parts[4])
            
            for sensor in sorted(sensor_types):
                pattern = f"{base}/{sensor}/#"
                if st.button(f"Subscribe to {sensor}", key=f"quick_{target_device}_{base}_{sensor}"):
                    sub_topic = f"{BASE_TOPIC}{target_device}/subscribe"
                    st.session_state.mqtt_client.publish(sub_topic, pattern)
                    st.session_state.device_subscriptions[target_device].add(pattern)
                    st.success(f"Subscribed {target_device} to {pattern}")

elif not st.session_state.managed_devices:
    st.info("Add a device first to enable subscriptions")
elif not st.session_state.discovered_topics:
    st.info("No topics discovered yet. Wait for messages to arrive.")

st.divider()

# Debug Information
with st.expander("Debug Information"):
    st.write(f"**Broker:** {MQTT_BROKER}:{MQTT_PORT}")
    st.write(f"**Username:** {MQTT_USERNAME}")
    st.write(f"**Base Topic:** {BASE_TOPIC}")
    if 'mqtt_client' in st.session_state:
        st.write(f"**Client ID:** {st.session_state.mqtt_client._client_id.decode()}")
    st.write(f"**Connected:** {st.session_state.mqtt_connected}")
    st.write(f"**Topics Discovered:** {len(st.session_state.discovered_topics)}")
    st.write(f"**Managed Devices:** {len(st.session_state.managed_devices)}")

# Auto-refresh every 2 seconds to stay up-to-date
time.sleep(2)
st.rerun()

