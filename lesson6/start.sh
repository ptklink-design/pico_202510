#!/bin/bash

# 移動到專案目錄
# 移動到專案目錄
cd /home/pi/Documents/GitHub/pico_202510/lesson6/

# 使用 uv run 執行
exec uv run streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true




