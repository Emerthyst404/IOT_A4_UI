# FILE: streamlit_app.py
# PROJECT: IOT A4
# COURSE: SENG3030 - Internet of Things
# DATE: 10-26-2025
# AUTHORS: Josh Horsley, Josh Rice, Christian Tan and Kalina Cathcart
# DESCRIPTION: Streamlit application for displaying MQTT data

import streamlit as st
import paho.mqtt.client as mqtt 
import queue
import time 
from datetime import datetime
import json
import random
import ssl



@st.cache_resource
def get_msg_q():
    return queue.Queue()
MSG_Q = get_msg_q()


st.title(" MQTT Data Display ")

# MQTT Settings
MQTT_BROKER = "p07da41d.ala.us-east-1.emqxsl.com"
MQTT_PORT = 8883
MQTT_USERNAME = "Jhorsley3072"
MQTT_PASSWORD = "3072"
BASE_TOPIC = "SENG3030/Thursday/Jhorsley3072/"

# Subscribe to all topics under your base path
TOPICS = [
    BASE_TOPIC + "#"  
]

# Initialize session state for connection tracking
if 'mqtt_connected' not in st.session_state:
    st.session_state.mqtt_connected = False


# Initialize session state for sensor data
if 'sensor_data' not in st.session_state:
    st.session_state.sensor_data = {
        'sht40_temperature': None,
        'sht40_humidity': None,
        'bmp280_temperature': None,
        'bmp280_pressure': None,
        'battery': None,
        'imu_accel': None,
        'imu_gyro': None,
    }



# FUNCTION: on_connect
# PARAMETERS: client, userdata, flags, rc
# RETURNS: None
# DESCRIPTION: Handles MQTT connection
def on_connect(client, userdata, flags, rc):
    print(f"Connection attempt result: rc={rc}")

    if 'data_queue' not in st.session_state:
        st.session_state.data_queue = queue.Queue()
    
    ok = (rc ==0)

    MSG_Q.put(({"type": "status", "connected": True}))

    if ok:
        st.session_state.mqtt_connected = True
        print("Successfully connected!")
        for t in TOPICS:
            client.subscribe(t)
            print(f"Subscribed to: {t}")
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



# FUNCTION: on_message
# PARAMETERS: client, userdata, msg
# RETURNS: None
# DESCRIPTION: Handles incoming MQTT messages
def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8')
        print(f"Received on {msg.topic}")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        data = {
            'value': payload.strip(),  
            'timestamp': timestamp
        }
        
        MSG_Q.put({"type": "message", "topic": msg.topic, "data": data})

        
    except Exception as e:
        print(f"Error processing message: {e}")
        MSG_Q.put({"type": "error", "error": str(e)})



# FUNCTION: on_disconnect
# PARAMETERS: client, userdata, rc
# RETURNS: None
# DESCRIPTION: Handles MQTT disconnection
def on_disconnect(client, userdata, rc):
    st.session_state.mqtt_connected = False
    print(f"Disconnected with result code: {rc}")




# Create MQTT client and connect if not already done
if 'mqtt_client' not in st.session_state:
    print("Creating new MQTT client...")
    
    client_id = f"streamlit_{random.randint(10000, 99999)}"
    client = mqtt.Client(client_id=client_id, callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
    
    # Load CA certificate and enable certificate validation
    client.tls_set(
        ca_certs="cert.pem",  
        tls_version=ssl.PROTOCOL_TLS_CLIENT
    )
    client.tls_insecure_set(False)
    
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    try:
        print(f"Connecting to {MQTT_BROKER}:{MQTT_PORT} as {MQTT_USERNAME}")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        st.session_state.mqtt_client = client
        print("Connection initiated")
    except Exception as e:
        st.error(f"Connection failed: {e}")
        print(f"Exception: {e}")



if 'data_queue' not in st.session_state:
    st.session_state.data_queue = MSG_Q
else:
    st.session_state.data_queue = MSG_Q


# Process messages from queue
while True:
    try:
        msg = MSG_Q.get_nowait()
    except queue.Empty:
        print("Queue empty")
        break

    if msg['type'] == 'status':
        print("Message type == 'message'")

        st.session_state.mqtt_connected = msg['connected']
    elif msg['type'] == 'error':
        print("Message type == 'err'")

        st.session_state.mqtt_connected = False
        st.session_state.last_message = {
            "value": f"ERROR: {msg.get('error')}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    elif msg['type'] == 'message':
        print("Message type == 'message'")

        topic = msg['topic']
        data  = msg['data']

        print(f"topic seen: {topic}")

        # Update sensor data based on topic 
        sd = st.session_state.sensor_data
        if 'sht40/temperature' in topic:
            sd['sht40_temperature'] = data
        elif 'sht40/humidity' in topic:
            sd['sht40_humidity'] = data
        elif 'bmp280/temperature' in topic:
            sd['bmp280_temperature'] = data
        elif 'bmp280/pressure' in topic:
            sd['bmp280_pressure'] = data
        elif 'battery' in topic:
            sd['battery'] = data
        elif 'imu/accel' in topic:
            vals = [v.strip() for v in data['value'].split(',')]
            if len(vals) == 3:
                data['x'], data['y'], data['z'] = map(float, vals)
            sd['imu_accel'] = data
        elif 'imu/gyro' in topic:
            vals = [v.strip() for v in data['value'].split(',')]
            if len(vals) == 3:
                data['x'], data['y'], data['z'] = map(float, vals)
            sd['imu_gyro'] = data

        st.session_state.sensor_data = sd

# Connection Status
if st.session_state.mqtt_connected:
    st.success("Connected to MQTT Broker")
else:
    st.warning("Connecting to MQTT Broker...")


# Debug Information
with st.expander("Debug Information", expanded=True):
    st.write(f"**Broker:** {MQTT_BROKER}")
    st.write(f"**Port:** {MQTT_PORT}")
    st.write(f"**Username:** {MQTT_USERNAME}")
    if 'mqtt_client' in st.session_state:
        st.write(f"**Client ID:** {st.session_state.mqtt_client._client_id.decode()}")
    st.write(f"**Connected:** {st.session_state.mqtt_connected}")
    st.write(f"**Queue Size:** {st.session_state.data_queue.qsize()}")
    
    st.write("**Subscribed Topics:**")
    for topic in TOPICS:
        st.write(f"- {topic}")


st.divider()

# Display sensor data in columns
col1, col2, col3 = st.columns(3)

# SHT40 Temperature
with col1:
    st.subheader("Temperature")
    temp_data = st.session_state.sensor_data['sht40_temperature']

    # print(f"temp_data: {temp_data}")

    if temp_data:
        st.metric("Temperature", f"{temp_data.get('value', 'N/A')} °C")
        st.caption(f"Last update: {temp_data.get('timestamp', 'N/A')}")
    else:
        st.info("Waiting for data...")

# SHT40 Humidity
with col2:
    st.subheader("Humidity")
    hum_data = st.session_state.sensor_data['sht40_humidity']
    if hum_data:
        st.metric("Humidity", f"{hum_data.get('value', 'N/A')} %")
        st.caption(f"Last update: {hum_data.get('timestamp', 'N/A')}")
    else:
        st.info("Waiting for data...")

# Battery
with col3:
    st.subheader("Battery")
    bat_data = st.session_state.sensor_data['battery']
    if bat_data:
        st.metric("Battery Level", f"{float(bat_data.get('value', 0))/1000:.2f} V")
        st.caption(f"Last update: {bat_data.get('timestamp', 'N/A')}")
    else:
        st.info("Waiting for data...")

# Second row
col4, col5, col6 = st.columns(3)

# BMP280 Temperature
with col4:
    st.subheader("Temperature")
    temp_data = st.session_state.sensor_data['bmp280_temperature']
    if temp_data:
        st.metric("Temperature", f"{temp_data.get('value', 'N/A')} °C")
        st.caption(f"Last update: {temp_data.get('timestamp', 'N/A')}")
    else:
        st.info("Waiting for data...")

# BMP280 Pressure
with col5:
    st.subheader("Pressure")
    press_data = st.session_state.sensor_data['bmp280_pressure']
    if press_data:
        st.metric("Pressure", f"{float(press_data.get('value', 0))/100:.2f} hPa")
        st.caption(f"Last update: {press_data.get('timestamp', 'N/A')}")
    else:
        st.info("Waiting for data...")

# IMU Accelerometer
with col6:
    st.subheader("Accelerometer")
    accel_data = st.session_state.sensor_data['imu_accel']
    if accel_data:
        st.write(f"X: {accel_data.get('x', 'N/A')}")
        st.write(f"Y: {accel_data.get('y', 'N/A')}")
        st.write(f"Z: {accel_data.get('z', 'N/A')}")
        st.caption(f"Last update: {accel_data.get('timestamp', 'N/A')}")
    else:
        st.info("Waiting for data...")

# IMU Gyroscope (full width)
st.subheader("Gyroscope")
gyro_data = st.session_state.sensor_data['imu_gyro']
if gyro_data:
    g_col1, g_col2, g_col3 = st.columns(3)
    with g_col1:
        st.metric("X-axis", f"{gyro_data.get('x', 'N/A')}")
    with g_col2:
        st.metric("Y-axis", f"{gyro_data.get('y', 'N/A')}")
    with g_col3:
        st.metric("Z-axis", f"{gyro_data.get('z', 'N/A')}")
    st.caption(f"Last update: {gyro_data.get('timestamp', 'N/A')}")
else:
    st.info("Waiting for data...")



# Auto-refresh
time.sleep(2)
st.rerun()



