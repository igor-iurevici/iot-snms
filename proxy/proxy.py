from flask import Flask, render_template, request, flash, redirect, url_for, jsonify
import paho.mqtt.client as mqtt
import influxdb_client, os, time, json
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# Flask setup
app = Flask(__name__)
app.config.from_pyfile('config.py')
app.secret_key = b''

# InfluxDB setup
token = os.getenv("INFLUXDB_TOKEN")
org = os.getenv("INFLUXDB_ORG")
url = os.getenv("INFLUXDB_URL")

write_client = InfluxDBClient(url=url, token=token, org=org)
write_api = write_client.write_api(write_options=SYNCHRONOUS)
bucket = "snms"

# MQTT setup
mqtt_broker = 'localhost'
mqtt_topic_config = 'snms/config'
mqtt_topic_connect = 'snms/connect'

def on_connect(client, userdata, flags, rc):
    print('Connected to MQTT broker')
    client.subscribe(mqtt_topic_connect)

def on_publish(client, userdata, mid):
    print('Message published')

def on_message(client, userdata, msg):
    print("Received MQTT message:", msg.payload.decode())
    if msg.topic == mqtt_topic_connect:
        init_config()

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_publish = on_publish
mqtt_client.on_message = on_message

# ESP32 data
latest_data = {}
sampling_rate = 500
noise_threshold = 30
alarm_level = 50 
alarm_counter = 10 



# INDEX PAGE
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST': 
        sampling_rate = int(request.form['sampling_rate'])
        noise_threshold = int(request.form['noise_threshold'])
        alarm_level = int(request.form['alarm_level'])
        alarm_counter = int(request.form['alarm_counter'])

        if all(isinstance(param, int) for param in [sampling_rate, noise_threshold, alarm_counter]) \
            and all(param is not None for param in [sampling_rate, noise_threshold, alarm_level, alarm_counter]) \
            and (sampling_rate > 50 and sampling_rate < 65535 and noise_threshold > 0 and noise_threshold < 65535 and (alarm_level > 0 and alarm_level > noise_threshold) and alarm_level < 65535 and alarm_counter > 0 and alarm_counter < 65445):
            # payload preparation
            config_data = {
                "sampling_rate": sampling_rate,
                "noise_threshold": noise_threshold,
                "alarm_level": alarm_level,
                "alarm_counter": alarm_counter
            }

            # json conversion 
            with open('esp32_config.json', 'w') as file:
                json.dump(config_data, file)

            mqtt_payload = json.dumps(config_data)

            # publish MQTT
            mqtt_client.publish(mqtt_topic_config, mqtt_payload, qos=1)
            flash(u'Configuration sent via MQTT', 'success')
            return redirect(url_for('index'))
        else:
            flash(u'Invalid configuration!', 'error')
            return redirect(url_for('index'))

    return render_template('index.html')



# RECEIVE ESP32 VALUES AND WRITE TO INFLUXDB
@app.route('/data', methods=['POST'])
def receive_data():
    payload = str(request.data.decode('utf-8'))

    # payload unpack
    if (not payload):
        return jsonify(error='Empty payload'), 400
    else:
        payload = payload.split(";")
        if (len(payload) == 3):
            latest_data["rssi_value"] = float(payload[0])
            latest_data["noise_value"] = float(payload[1])
            latest_data["alarm_flag"] = int(payload[2])
            p = Point("sample")\
                    .field("noise", latest_data["noise_value"])\
                    .field("alarm", latest_data["alarm_flag"])\
                    .field("rssi", latest_data["rssi_value"])
        else:
            latest_data["rssi_value"] = payload[0]
            p = Point("sample")\
                    .field("rssi", latest_data["rssi_value"])

    # write to InfluxDB
    write_api.write(bucket=bucket, org=org, record=p)
    print(str(payload))
    return ''


# UPDATE WEBPAGE
@app.route('/get_latest_data')
def get_latest_data():
    return jsonify(latest_data)



# ESP32 CONFIGURATION PARAMETERS
def init_config():
    # Configuration file
    if not os.path.exists('esp32_config.json'):
        default_config = {
            'sampling_rate': 500,
            'noise_threshold': 30,
            'alarm_level': 45,
            'alarm_counter': 10
        }
        with open('esp32_config.json', 'w') as file:
            json.dump(default_config, file)
    
    # Read config
    with open('esp32_config.json', 'r') as file:
        config = json.load(file)
    
    # Assign config locally
    sampling_rate = config['sampling_rate']
    noise_threshold = config['noise_threshold']
    alarm_level = config['alarm_level']
    alarm_counter = config['alarm_counter']


    # Parameters check
    if not all(isinstance(param, int) for param in [sampling_rate, noise_threshold, alarm_counter]) \
        or any(param is None for param in [sampling_rate, noise_threshold, alarm_level, alarm_counter]) \
        and not (sampling_rate > 50 and noise_threshold > 0 and (alarm_level > 0 and alarm_level > noise_threshold) and alarm_counter > 0):
        raise ValueError("Invalid configuration parameters")
    
    # MQTT connection
    while not mqtt_client.is_connected():
        mqtt_client.connect(mqtt_broker, 1883, 60)
        mqtt_client.loop_start()


    mqtt_payload = json.dumps(config)    
    mqtt_client.publish(mqtt_topic_config, mqtt_payload, qos=1, retain=True)

    return 'Configuration send via MQTT!'



if __name__ == '__main__':
    init_config()
    app.run(host='', port=8090)

