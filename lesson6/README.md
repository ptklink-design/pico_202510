# Streamlit & MQTT 監控系統 (Lesson 6)

這是一個基於 Streamlit 和 MQTT 協議的即時監控系統。本程式作為 MQTT 訂閱者，接收來自 IoT 設備的感測器數據，並透過 Streamlit 提供即時監控與數據視覺化介面。

## ✨ 主要功能

1.  **即時監控儀表板**
    *   **電燈狀態**: 顯示開關狀態 (ON/OFF)。
    *   **環境數據**: 即時顯示溫度與濕度。
    *   **多單位支援**: 可隨時切換 **攝氏 (°C)** 或 **華氏 (°F)** 顯示。

2.  **數據視覺化**
    *   提供溫濕度歷史趨勢圖。
    *   支援「折線圖」與「區域圖」切換。
    *   可調整顯示的時間範圍 (最近 10 ~ 500 筆數據)。

3.  **數據匯出**
    *   支援將歷史數據匯出為 CSV 檔案。
    *   匯出數據會依據當前選擇的溫度單位自動轉換。

4.  **MQTT 整合**
    *   內建 MQTT 訂閱器 (Subscriber) 接收數據。
    *   內建 MQTT 發佈器 (Publisher) 用於測試或發送控制指令。
    *   支援自動發送模擬數據模式 (Auto Publish Mode)。

## 📂 檔案結構

| 檔案名稱 | 說明 |
| :--- | :--- |
| `app.py` | 主程式 (Streamlit 應用程式)，包含 UI 與 MQTT 邏輯。 |
| `start.sh` | 啟動腳本，用於簡化啟動流程或搭配自動執行使用。 |
| `test.md` | 專案需求規格說明書。 |
| `mqtt_publisher_test.py` | 獨立的 MQTT 發送信號測試腳本。 |
| `lesson6_1.ipynb` | (教學用) Jupyter Notebook 範例 1。 |
| `lesson6_2.ipynb` | (教學用) Jupyter Notebook 範例 2。 |

## 🚀 快速開始

### 1. 環境需求
確保已安裝 Python 3.x 及以下套件：
```bash
pip install streamlit paho-mqtt pandas
```
*(若使用虛擬環境 `.venv`，專案已配置好相關依賴)*

### 2. 啟動程式

**方式 A: 使用 uv run (推薦)**
```bash
uv run streamlit run lesson6/app.py --server.port 8501
```




**方式 B: 使用啟動腳本 (推薦)**
```bash
./lesson6/start.sh
```

### 3. 設定自動執行 (可選)
若希望樹莓派開機時自動啟動，可將 `start.sh` 加入 Crontab：
```bash
# 編輯 Crontab
crontab -e

# 加入以下內容
@reboot /home/pi/Documents/GitHub/pico_202510/lesson6/start.sh > /home/pi/Documents/GitHub/pico_202510/lesson6/cron.log 2>&1
```

## ⚙️ MQTT 設定
程式預設連線至本機 MQTT Broker：
- **Broker**: `localhost`
- **Port**: `1883`
- **Topics**:
    - 電燈: `home/light/status`
    - 溫度: `home/livingroom/temperature`
    - 濕度: `home/livingroom/humidity`

若需修改，請編輯 `app.py` 中的 `MQTT_BROKER` 與相關變數。

## 🛠️ 疑難排解
- **無法連線 MQTT**: 請確認 `mosquitto` 服務是否正在運行 (`sudo systemctl status mosquitto`)。
- **圖表無數據**: 請確認是否有裝置或模擬器正在發送數據至指定 Topic，或開啟側邊欄的「自動發送模式」進行測試。
