#!/usr/bin/env python
"""
MQTT 測試發佈器
用於測試 Streamlit 監控系統
"""
import paho.mqtt.client as mqtt
import time
import json
import random

# MQTT 設定
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_LIGHT = "home/light/status"
MQTT_TOPIC_TEMP = "home/livingroom/temperature"
MQTT_TOPIC_HUMIDITY = "home/livingroom/humidity"

# 創建 MQTT 客戶端
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"✓ 成功連接到 MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    else:
        print(f"✗ 連接失敗，錯誤代碼: {reason_code}")

def on_publish(client, userdata, mid, reason_code=None, properties=None):
    print(f"✓ 訊息已發佈 (mid: {mid})")

client.on_connect = on_connect
client.on_publish = on_publish

# 連接到 MQTT Broker
print(f"正在連接到 {MQTT_BROKER}:{MQTT_PORT}...")
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

# 等待連接建立
time.sleep(1)

print("\n開始發送測試數據...")
print("按 Ctrl+C 停止\n")

try:
    light_state = False
    base_temp = 25.0
    base_humidity = 50.0
    
    while True:
        # 發送電燈狀態（每 5 秒切換一次）
        light_state = not light_state
        light_status = "on" if light_state else "off"
        client.publish(MQTT_TOPIC_LIGHT, json.dumps({"status": light_status}), qos=1)
        print(f"發送電燈狀態: {light_status}")
        
        # 發送溫度（模擬溫度變化）
        temp = base_temp + random.uniform(-2, 2)
        client.publish(MQTT_TOPIC_TEMP, json.dumps({"value": round(temp, 1)}), qos=1)
        print(f"發送溫度: {temp:.1f} °C")
        
        # 發送濕度（模擬濕度變化）
        humidity = base_humidity + random.uniform(-5, 5)
        humidity = max(0, min(100, humidity))  # 限制在 0-100 之間
        client.publish(MQTT_TOPIC_HUMIDITY, json.dumps({"value": round(humidity, 1)}), qos=1)
        print(f"發送濕度: {humidity:.1f} %")
        
        print("-" * 40)
        time.sleep(2)  # 每 2 秒發送一次數據

except KeyboardInterrupt:
    print("\n\n正在停止...")
    client.loop_stop()
    client.disconnect()
    print("✓ 已斷開連接")

