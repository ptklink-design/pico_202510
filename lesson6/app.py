import streamlit as st
import paho.mqtt.client as mqtt
import json
import pandas as pd
import threading
import time
import random
from datetime import datetime
from collections import deque
from queue import Queue

# 頁面設定
st.set_page_config(
    page_title="MQTT 監控系統",
    page_icon="📊",
    layout="wide"
)

# MQTT 設定
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_LIGHT = "home/light/status"
MQTT_TOPIC_TEMP = "home/livingroom/temperature"
MQTT_TOPIC_HUMIDITY = "home/livingroom/humidity"
MQTT_TOPIC = "testtopic"  # 測試主題

# 初始化 session state
if 'mqtt_client' not in st.session_state:
    st.session_state.mqtt_client = None
if 'mqtt_connected' not in st.session_state:
    st.session_state.mqtt_connected = False
if 'light_status' not in st.session_state:
    st.session_state.light_status = "未知"
if 'temperature' not in st.session_state:
    st.session_state.temperature = None
if 'humidity' not in st.session_state:
    st.session_state.humidity = None
if 'data_history' not in st.session_state:
    st.session_state.data_history = deque(maxlen=1000)  # 儲存最多 1000 筆數據
if 'mqtt_thread' not in st.session_state:
    st.session_state.mqtt_thread = None
if 'publisher_client' not in st.session_state:
    st.session_state.publisher_client = None
if 'publisher_connected' not in st.session_state:
    st.session_state.publisher_connected = False
if 'auto_publish' not in st.session_state:
    st.session_state.auto_publish = False
if 'auto_publish_stop_event' not in st.session_state:
    st.session_state.auto_publish_stop_event = threading.Event()
if 'publish_thread' not in st.session_state:

    st.session_state.publish_thread = None
if 'testtopic_messages' not in st.session_state:
    st.session_state.testtopic_messages = deque(maxlen=100)  # 儲存 testtopic 訊息
if 'message_queue' not in st.session_state:
    st.session_state.message_queue = Queue()  # 線程安全的消息隊列
if 'temp_unit' not in st.session_state:
    st.session_state.temp_unit = "攝氏 (°C)"


# MQTT 回調函數（在背景線程中執行，使用隊列避免直接訪問 session_state）
def on_connect(client, userdata, flags, reason_code, properties):
    # 處理 reason_code（可能是整數或 ReasonCode 對象）
    rc_value = reason_code.value if hasattr(reason_code, 'value') else int(reason_code)
    
    # 使用事件來通知連接狀態（線程安全）
    if rc_value == 0:
        # 訂閱所有主題（參考 lesson6_2.ipynb 的訂閱模式）
        client.subscribe(MQTT_TOPIC_LIGHT, qos=1)
        client.subscribe(MQTT_TOPIC_TEMP, qos=1)
        client.subscribe(MQTT_TOPIC_HUMIDITY, qos=1)
        client.subscribe(MQTT_TOPIC, qos=1)  # 訂閱測試主題
        print(f"✓ 已連接到 MQTT Broker 並訂閱主題")
        mqtt_connect_event.set()  # 通知連接成功
    else:
        error_messages = {
            1: "協議版本不正確",
            2: "客戶端 ID 無效",
            3: "伺服器不可用",
            4: "使用者名稱或密碼錯誤",
            5: "未授權"
        }
        error_msg = error_messages.get(rc_value, f"未知錯誤 (代碼: {rc_value})")
        print(f"✗ 連接失敗: {error_msg}")
        mqtt_connect_event.set()  # 通知連接失敗

def on_message(client, userdata, message):
    """MQTT 訊息回調（在背景線程中執行，使用隊列傳遞數據）"""
    topic = message.topic
    payload = message.payload.decode('utf-8')
    timestamp = datetime.now()
    
    try:
        # 將訊息放入隊列（線程安全，從 userdata 獲取隊列）
        if userdata is not None:
            userdata.put({
                "topic": topic,
                "payload": payload,
                "timestamp": timestamp,
                "qos": message.qos
            })

    except Exception as e:
        print(f"處理訊息時發生錯誤: {e}")

def process_message_queue():
    """處理消息隊列中的訊息（在主線程中執行）"""
    if 'message_queue' not in st.session_state:
        return
    
    # 處理隊列中的所有訊息
    while not st.session_state.message_queue.empty():
        try:
            msg = st.session_state.message_queue.get_nowait()
            topic = msg["topic"]
            payload = msg["payload"]
            timestamp = msg["timestamp"]
            qos = msg["qos"]
            
            # 處理電燈開關狀態
            if topic == MQTT_TOPIC_LIGHT:
                data = json.loads(payload) if payload.startswith('{') else {"status": payload}
                status = data.get("status", payload).lower()
                if status in ["on", "開", "1", "true"]:
                    st.session_state.light_status = "開啟"
                elif status in ["off", "關", "0", "false"]:
                    st.session_state.light_status = "關閉"
                else:
                    st.session_state.light_status = payload
            
            # 處理溫度數據
            elif topic == MQTT_TOPIC_TEMP:
                data = json.loads(payload) if payload.startswith('{') else {"value": float(payload)}
                temp_value = float(data.get("value", payload))
                st.session_state.temperature = temp_value
                # 儲存到歷史記錄
                st.session_state.data_history.append({
                    "timestamp": timestamp,
                    "temperature": temp_value,
                    "humidity": st.session_state.humidity
                })
            
            # 處理濕度數據
            elif topic == MQTT_TOPIC_HUMIDITY:
                data = json.loads(payload) if payload.startswith('{') else {"value": float(payload)}
                humidity_value = float(data.get("value", payload))
                st.session_state.humidity = humidity_value
                # 更新最後一筆記錄的濕度，或創建新記錄
                if st.session_state.data_history:
                    last_record = st.session_state.data_history[-1]
                    if last_record["timestamp"] == timestamp or (timestamp - last_record["timestamp"]).seconds < 1:
                        last_record["humidity"] = humidity_value
                    else:
                        st.session_state.data_history.append({
                            "timestamp": timestamp,
                            "temperature": st.session_state.temperature,
                            "humidity": humidity_value
                        })
                else:
                    st.session_state.data_history.append({
                        "timestamp": timestamp,
                        "temperature": st.session_state.temperature,
                        "humidity": humidity_value
                    })
            
            # 處理 testtopic 訊息
            elif topic == MQTT_TOPIC:
                # 儲存 testtopic 訊息
                st.session_state.testtopic_messages.append({
                    "timestamp": timestamp,
                    "topic": topic,
                    "payload": payload,
                    "qos": qos
                })
        except Exception as e:
            print(f"處理隊列訊息時發生錯誤: {e}")

# 連接事件
mqtt_connect_event = threading.Event()

def mqtt_loop():
    """MQTT 網路循環（在背景執行，參考 lesson6_2.ipynb 的非阻塞模式）"""
    if st.session_state.mqtt_client:
        # 使用 loop_start() 非阻塞模式，類似 lesson6_2.ipynb 的第三個 cell
        st.session_state.mqtt_client.loop_start()

def start_mqtt():
    """啟動 MQTT 連接（參考 lesson6_2.ipynb 的非阻塞模式）"""
    if st.session_state.mqtt_client is None or not st.session_state.mqtt_connected:
        try:
            mqtt_connect_event.clear()
            # 創建客戶端（使用新的 Callback API 版本 2，參考 lesson6_2.ipynb）
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            # 將消息隊列作為 userdata 傳遞，避免在回調中訪問 session_state
            client.user_data_set(st.session_state.message_queue)
            client.on_connect = on_connect

            client.on_message = on_message
            
            # 連接到 MQTT Broker（參考 lesson6_2.ipynb 的連接方式）
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            st.session_state.mqtt_client = client
        
            # 使用非阻塞模式啟動網路循環（參考 lesson6_2.ipynb 第三個 cell 的 loop_start）
            client.loop_start()
            
            # 等待連接確認（最多等待 3 秒）
            if mqtt_connect_event.wait(timeout=3):
                # 在主線程中更新連接狀態（避免 ScriptRunContext 警告）
                st.session_state.mqtt_connected = True
                return True
            else:
                st.warning("⚠️ 連接超時，請檢查 MQTT Broker 是否運行")
                return False
        except Exception as e:
            st.error(f"連接 MQTT 失敗: {e}")
            return False
    return True

def stop_mqtt():
    """停止 MQTT 連接"""
    if st.session_state.mqtt_client:
        st.session_state.mqtt_client.loop_stop()
        st.session_state.mqtt_client.disconnect()
        st.session_state.mqtt_client = None
        st.session_state.mqtt_connected = False

# MQTT 發佈器函數
publisher_connect_event = threading.Event()

def on_connect_publisher(client, userdata, flags, reason_code, properties):
    # 處理 reason_code（可能是整數或 ReasonCode 對象）
    rc_value = reason_code.value if hasattr(reason_code, 'value') else int(reason_code)
    
    if rc_value == 0:
        st.session_state.publisher_connected = True
        publisher_connect_event.set()
        print(f"✓ 發佈器已連接到 MQTT Broker")
    else:
        st.session_state.publisher_connected = False
        publisher_connect_event.set()
        error_messages = {
            1: "協議版本不正確",
            2: "客戶端 ID 無效",
            3: "伺服器不可用",
            4: "使用者名稱或密碼錯誤",
            5: "未授權"
        }
        error_msg = error_messages.get(rc_value, f"未知錯誤 (代碼: {rc_value})")
        print(f"✗ 發佈器連接失敗: {error_msg}")

def on_publish_publisher(client, userdata, mid, reason_code=None, properties=None):
    print(f"✓ 訊息已發佈 (mid: {mid})")

def start_publisher():
    """啟動 MQTT 發佈器（參考 lesson6_2.ipynb 的連接模式）"""
    if st.session_state.publisher_client is None or not st.session_state.publisher_connected:
        try:
            publisher_connect_event.clear()
            # 創建客戶端（使用新的 Callback API 版本 2）
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            client.on_connect = on_connect_publisher
            client.on_publish = on_publish_publisher
            
            # 連接到 MQTT Broker
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            
            # 使用非阻塞模式啟動網路循環（參考 lesson6_2.ipynb）
            client.loop_start()
            st.session_state.publisher_client = client
            
            # 等待連接確認（最多等待 3 秒）
            if publisher_connect_event.wait(timeout=3):
                # 在主線程中更新連接狀態（避免 ScriptRunContext 警告）
                st.session_state.publisher_connected = True
                return True
            else:
                st.warning("⚠️ 發佈器連接超時，請檢查：\n1. MQTT Broker 是否運行\n2. 端口 1883 是否開放")
                return False
        except Exception as e:
            st.error(f"啟動發佈器失敗: {e}")
            import traceback
            print(f"發佈器啟動錯誤詳情: {traceback.format_exc()}")
            return False
    return True

def stop_publisher():
    """停止 MQTT 發佈器"""
    st.session_state.auto_publish = False
    if st.session_state.publisher_client:
        try:
            st.session_state.publisher_client.loop_stop()
            st.session_state.publisher_client.disconnect()
        except:
            pass
        st.session_state.publisher_client = None
        st.session_state.publisher_connected = False

def publish_data(light_status=None, temperature=None, humidity=None, test_message=None, client=None):
    """發送 MQTT 數據"""
    # 檢查是否有任何數據要發送
    if light_status is None and temperature is None and humidity is None and (test_message is None or not test_message.strip()):
        return False
    
    # 如果明確提供了 client，直接使用 (線程安全模式)
    if client is not None:
        target_client = client
        connected = client.is_connected()
    else:
        # 使用 session_state (UI 模式)
        if 'publisher_connected' not in st.session_state or not st.session_state.publisher_connected:
            if not start_publisher():
                return False
            # 等待連接穩定
            time.sleep(0.3)
        
        target_client = st.session_state.publisher_client
        connected = st.session_state.publisher_connected if 'publisher_connected' in st.session_state else False
    
    if target_client and connected:

        try:
            success_count = 0
            # 發送電燈狀態
            if light_status is not None:
                status = "on" if light_status else "off"
                result = target_client.publish(
                    MQTT_TOPIC_LIGHT, 
                    json.dumps({"status": status}), 
                    qos=1
                )
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    success_count += 1
            
            # 發送溫度
            if temperature is not None:
                result = target_client.publish(
                    MQTT_TOPIC_TEMP, 
                    json.dumps({"value": round(temperature, 1)}), 
                    qos=1
                )
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    success_count += 1
            
            # 發送濕度
            if humidity is not None:
                result = target_client.publish(
                    MQTT_TOPIC_HUMIDITY, 
 
                    json.dumps({"value": round(humidity, 1)}), 
                    qos=1
                )
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    success_count += 1
            
            # 發送到 testtopic
            if test_message is not None and test_message.strip():
                try:
                    result = target_client.publish(
                        MQTT_TOPIC, 
 
                        test_message, 
                        qos=1
                    )
                    # 等待發送完成
                    result.wait_for_publish(timeout=2)
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        success_count += 1
                        print(f"✓ 成功發送到 {MQTT_TOPIC}: {test_message}")
                    else:
                        print(f"✗ 發送失敗，錯誤代碼: {result.rc}")
                except Exception as e:
                    print(f"✗ 發送 testtopic 時發生錯誤: {e}")
                    st.error(f"發送 testtopic 失敗: {e}")
            
            return success_count > 0
        except Exception as e:
            st.error(f"發送數據失敗: {e}")
            return False
    else:
        st.warning("⚠️ 發佈器未連接，請先啟動發佈器")
        return False

def auto_publish_loop(client, stop_event):
    """自動發送數據循環 (線程安全版)"""
    base_temp = 25.0
    base_humidity = 50.0
    light_state = False
    
    print("自動發送線程啟動")
    try:
        while not stop_event.is_set():
            if client.is_connected():
                # 切換電燈狀態
                light_state = not light_state
                
                # 模擬溫度變化
                temp = base_temp + random.uniform(-2, 2)
                
                # 模擬濕度變化
                humidity = base_humidity + random.uniform(-5, 5)
                humidity = max(0, min(100, humidity))
                
                # 發送數據 (傳入 client)
                publish_data(light_status=light_state, temperature=temp, humidity=humidity, client=client)
            
            # 等待 2 秒，或直到收到停止信號
            if stop_event.wait(timeout=2):
                break
    except Exception as e:
        print(f"自動發送線程錯誤: {e}")
    print("自動發送線程結束")


# 主程式
st.title("🏠 MQTT 監控系統")
st.markdown("---")

# 處理消息隊列（在主線程中執行，避免 ScriptRunContext 警告）
process_message_queue()

# 連接狀態提示
status_col1, status_col2, status_col3 = st.columns(3)
with status_col1:
    if st.session_state.mqtt_connected:
        st.success("✓ 訂閱器已連接")
    else:
        st.error("✗ 訂閱器未連接")
        st.caption("請在側邊欄點擊「連接」按鈕")

with status_col2:
    if st.session_state.publisher_connected:
        st.success("✓ 發佈器已連接")
    else:
        st.warning("⚠️ 發佈器未連接")
        st.caption("請在側邊欄啟動發佈器以發送數據")

with status_col3:
    if st.session_state.mqtt_connected and st.session_state.publisher_connected:
        st.success("✓ 系統就緒")
    elif st.session_state.mqtt_connected:
        st.info("ℹ️ 僅接收模式")
    elif st.session_state.publisher_connected:
        st.info("ℹ️ 僅發送模式")
    else:
        st.warning("⚠️ 請連接訂閱器和發佈器")

st.markdown("---")

# 側邊欄 - MQTT 連接控制
with st.sidebar:
    st.header("⚙️ 設定")
    
    st.subheader("MQTT 連接")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔌 連接", use_container_width=True):
            with st.spinner("正在連接 MQTT..."):
                if start_mqtt():
                    st.success("✓ 連接成功")
                else:
                    st.error("✗ 連接失敗，請檢查：\n1. MQTT Broker 是否運行\n2. 端口 1883 是否開放")
            st.rerun()
    
    with col2:
        if st.button("🔌 斷開", use_container_width=True):
            stop_mqtt()
            st.rerun()
    
    # 連接狀態
    if st.session_state.mqtt_connected:
        st.success("✓ 已連接")
    else:
        st.error("✗ 未連接")
    
    st.markdown("---")
    
    # MQTT 設定
    st.subheader("MQTT 設定")
    st.text_input("Broker 地址", value=MQTT_BROKER, disabled=True)
    st.number_input("端口", value=MQTT_PORT, disabled=True)
    
    # 溫度單位設定
    st.session_state.temp_unit = st.radio(
        "溫度單位",
        ["攝氏 (°C)", "華氏 (°F)"],
        index=0 if st.session_state.temp_unit == "攝氏 (°C)" else 1
    )
    
    st.markdown("---")

    
    # 主題列表
    st.subheader("訂閱主題")
    st.code(MQTT_TOPIC_LIGHT)
    st.code(MQTT_TOPIC_TEMP)
    st.code(MQTT_TOPIC_HUMIDITY)
    st.code(MQTT_TOPIC)
    
    st.markdown("---")
    
    # MQTT 發佈器控制
    st.subheader("📤 數據發佈器")
    
    # 發佈器連接狀態
    if st.session_state.publisher_connected:
        st.success("✓ 發佈器已連接")
    else:
        st.info("發佈器未連接")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔌 啟動發佈器", use_container_width=True):
            if start_publisher():
                st.success("✓ 發佈器已啟動")
            else:
                st.error("✗ 發佈器啟動失敗")
            st.rerun()
    
    with col2:
        if st.button("🔌 停止發佈器", use_container_width=True):
            stop_publisher()
            st.info("發佈器已停止")
            st.rerun()
    
    st.markdown("---")
    
    # 手動發送數據
    st.subheader("📝 手動發送數據")
    
    with st.form("manual_publish_form"):
        light_switch = st.checkbox("💡 電燈開關", value=False)
        temp_value = st.number_input("🌡️ 溫度 (°C)", value=25.0, min_value=-10.0, max_value=50.0, step=0.1)
        humidity_value = st.number_input("💧 濕度 (%)", value=50.0, min_value=0.0, max_value=100.0, step=0.1)
        
        submitted = st.form_submit_button("📤 發送數據", use_container_width=True)
        if submitted:
            with st.spinner("正在發送數據..."):
                if publish_data(light_status=light_switch, temperature=temp_value, humidity=humidity_value):
                    st.success("✓ 數據已成功發送！")
                    st.balloons()
                else:
                    st.error("✗ 發送失敗，請檢查：\n1. 發佈器是否已啟動\n2. MQTT Broker 是否運行")
    
    st.markdown("---")
    
    # 發送到 testtopic
    st.subheader("🧪 測試主題發送")
    st.caption(f"主題: `{MQTT_TOPIC}`")
    
    with st.form("testtopic_form"):
        test_message = st.text_input("📝 測試訊息", value="Hello MQTT from Streamlit!")
        
        # 顯示發佈器狀態
        if st.session_state.publisher_connected:
            st.success("✓ 發佈器已連接，可以發送")
        else:
            st.warning("⚠️ 發佈器未連接，將自動啟動")
        
        submitted_test = st.form_submit_button("📤 發送到 testtopic", use_container_width=True)
        if submitted_test:
            if not test_message or not test_message.strip():
                st.warning("⚠️ 請輸入測試訊息")
            else:
                with st.spinner("正在發送測試訊息..."):
                    # 確保發佈器已連接
                    if not st.session_state.publisher_connected:
                        st.info("正在啟動發佈器...")
                        if not start_publisher():
                            st.error("✗ 發佈器啟動失敗，請檢查：\n1. MQTT Broker 是否運行\n2. 端口 1883 是否開放")
                        else:
                            time.sleep(0.5)  # 等待連接穩定
                    
                    if st.session_state.publisher_connected:
                        try:
                            result = publish_data(test_message=test_message)
                            if result:
                                st.success(f"✓ 測試訊息已成功發送到 `{MQTT_TOPIC}`！")
                                st.balloons()
                                st.info(f"💡 提示：請確保訂閱器已連接以查看收到的訊息")
                            else:
                                st.error("✗ 發送失敗，請檢查終端機的錯誤訊息")
                        except Exception as e:
                            st.error(f"✗ 發送時發生錯誤: {e}")
                    else:
                        st.error("✗ 發佈器未連接，請先點擊「啟動發佈器」按鈕")
    
    st.markdown("---")
    
    # 自動發送模式
    st.subheader("🔄 自動發送模式")
    
    auto_publish_enabled = st.checkbox("啟用自動發送", value=st.session_state.auto_publish)
    
    if auto_publish_enabled != st.session_state.auto_publish:
        st.session_state.auto_publish = auto_publish_enabled
        
        if st.session_state.auto_publish:
            # 啟動自動發送
            if not st.session_state.publisher_connected:
                if start_publisher():
                    st.success("✓ 發佈器已啟動，自動發送已開始")
                else:
                    st.error("✗ 發佈器啟動失敗，無法開始自動發送")
                    st.session_state.auto_publish = False
            # 再次檢查連接狀態
            if st.session_state.publisher_connected:
                if st.session_state.publish_thread is None or not st.session_state.publish_thread.is_alive():
                    # 清除停止信號
                    st.session_state.auto_publish_stop_event.clear()
                    # 啟動線程 (傳入 client 和 stop_event)
                    thread = threading.Thread(
                        target=auto_publish_loop, 
                        args=(st.session_state.publisher_client, st.session_state.auto_publish_stop_event), 
                        daemon=True
                    )
                    thread.start()
                    st.session_state.publish_thread = thread
                    st.success("✓ 自動發送已啟動")
        else:
            # 發送停止信號
            st.session_state.auto_publish_stop_event.set()
            st.info("自動發送已停止")

        st.rerun()
    
    if st.session_state.auto_publish:
        st.info("🔄 自動發送中... 每 2 秒發送一次測試數據")

# 主要內容區域
col1, col2, col3 = st.columns(3)

# 電燈開關狀態
with col1:
    st.subheader("💡 電燈狀態")
    if st.session_state.light_status == "開啟":
        st.markdown('<div style="text-align: center; padding: 20px; background-color: #ffd700; border-radius: 10px;">'
                   f'<h1 style="color: #000;">{st.session_state.light_status}</h1></div>', 
                   unsafe_allow_html=True)
    elif st.session_state.light_status == "關閉":
        st.markdown('<div style="text-align: center; padding: 20px; background-color: #333; border-radius: 10px;">'
                   f'<h1 style="color: #fff;">{st.session_state.light_status}</h1></div>', 
                   unsafe_allow_html=True)
    else:
        st.info("等待數據...")

# 溫度顯示
with col2:
    st.subheader("🌡️ 客廳溫度")

    if st.session_state.temperature is not None:
        display_temp = st.session_state.temperature
        unit_label = "°C"
        
        if st.session_state.temp_unit == "華氏 (°F)":
            display_temp = display_temp * 9/5 + 32
            unit_label = "°F"
            
        st.metric("溫度", f"{display_temp:.1f} {unit_label}")

        # 溫度顏色提示
        if st.session_state.temperature > 28:
            st.warning("溫度較高")
        elif st.session_state.temperature < 18:
            st.info("溫度較低")
    else:
        st.info("等待數據...")

# 濕度顯示
with col3:
    st.subheader("💧 客廳濕度")
    if st.session_state.humidity is not None:
        st.metric("濕度", f"{st.session_state.humidity:.1f} %")
        # 濕度顏色提示
        if st.session_state.humidity > 70:
            st.warning("濕度較高")
        elif st.session_state.humidity < 30:
            st.info("濕度較低")
    else:
        st.info("等待數據...")

st.markdown("---")

# 溫濕度圖表
st.subheader("📊 溫濕度歷史圖表")

if len(st.session_state.data_history) > 0:
    # 轉換為 DataFrame
    df = pd.DataFrame(list(st.session_state.data_history))
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 單位轉換
    if st.session_state.temp_unit == "華氏 (°F)":
        df['temperature'] = df['temperature'] * 9/5 + 32
        
    df = df.sort_values('timestamp')

    
    # 時間範圍選擇
    col1, col2 = st.columns([3, 1])
    with col1:
        if len(df) > 1:
            time_range = st.slider(
                "顯示時間範圍（最近 N 筆數據）",
                min_value=10,
                max_value=min(500, len(df)),
                value=min(100, len(df)),
                step=10
            )
            df_display = df.tail(time_range)
        else:
            df_display = df
    
    with col2:
        chart_type = st.selectbox("圖表類型", ["折線圖", "區域圖"])
    
    # 繪製圖表
    if chart_type == "折線圖":
        st.line_chart(
            df_display.set_index('timestamp')[['temperature', 'humidity']],
            use_container_width=True
        )
    else:
        st.area_chart(
            df_display.set_index('timestamp')[['temperature', 'humidity']],
            use_container_width=True
        )
    
    # 數據表格
    with st.expander("📋 查看數據表格"):
        st.dataframe(df_display[['timestamp', 'temperature', 'humidity']], use_container_width=True)
    
    # CSV 匯出功能
    st.markdown("---")
    st.subheader("💾 數據匯出")
    
    col1, col2 = st.columns(2)
    with col1:
        export_all = st.checkbox("匯出所有數據", value=False)
    
    if export_all:
        df_export = df
    else:
        df_export = df_display
    
    # 轉換為 CSV
    csv = df_export[['timestamp', 'temperature', 'humidity']].to_csv(index=False)
    
    st.download_button(
        label="📥 下載 CSV 檔案",
        data=csv,
        file_name=f"溫濕度數據_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True
    )
    
    # 統計資訊
    with st.expander("📈 統計資訊"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("數據筆數", len(df_export))
        with col2:
            if df_export['temperature'].notna().any():
                unit_label = "°F" if st.session_state.temp_unit == "華氏 (°F)" else "°C"
                st.metric("平均溫度", f"{df_export['temperature'].mean():.1f} {unit_label}")

        with col3:
            if df_export['humidity'].notna().any():
                st.metric("平均濕度", f"{df_export['humidity'].mean():.1f} %")
        with col4:
            if len(df_export) > 1:
                time_span = (df_export['timestamp'].max() - df_export['timestamp'].min())
                st.metric("時間範圍", f"{time_span.total_seconds()/60:.1f} 分鐘")

else:
    st.info("📊 等待數據中... 請確保 MQTT 連接已建立並有數據發送。")

# testtopic 訊息顯示
st.markdown("---")
st.subheader("🧪 testtopic 訊息監控")

if len(st.session_state.testtopic_messages) > 0:
    # 顯示最近的訊息
    recent_messages = list(st.session_state.testtopic_messages)[-10:]  # 顯示最近 10 條
    
    for msg in reversed(recent_messages):
        with st.expander(f"📨 {msg['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} - {msg['payload'][:50]}..."):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**主題**: `{msg['topic']}`")
                st.write(f"**QoS**: {msg['qos']}")
            with col2:
                st.write(f"**時間**: {msg['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
            
            st.code(msg['payload'], language='text')
            
            # 嘗試解析 JSON
            try:
                data = json.loads(msg['payload'])
                st.json(data)
            except:
                pass
    
    # 清除訊息按鈕
    if st.button("🗑️ 清除訊息記錄"):
        st.session_state.testtopic_messages.clear()
        st.rerun()
else:
    st.info("📭 尚未收到 testtopic 訊息。請發送測試訊息或確保有數據發送到此主題。")

# 注意：不自動啟動，需要用戶手動點擊連接按鈕
# 這樣可以避免連接問題和更好的用戶控制
