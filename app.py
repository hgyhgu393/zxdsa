import time
import threading
import requests
import os
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from datetime import datetime

# สร้าง App และรองรับ SocketIO
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# ฐานข้อมูลชั่วคราว (เก็บใน RAM)
monitors = {}

def monitor_worker(m_id):
    """ระบบหลังบ้านคอยกระตุ้นลิงก์ทุก 60 วินาที"""
    while m_id in monitors:
        url = monitors[m_id]['url']
        start_time = time.time()
        try:
            # ส่งคำขอกระตุ้นลิงก์ (Ping)
            response = requests.get(url, timeout=10)
            latency = round((time.time() - start_time) * 1000)
            status = "Online" if response.status_code == 200 else f"Error ({response.status_code})"
        except Exception:
            latency = 0
            status = "Offline"

        now = datetime.now().strftime("%H:%M:%S")
        
        # อัปเดตข้อมูลในหน่วยความจำ
        monitors[m_id]['status'] = status
        monitors[m_id]['history'].append({"time": now, "latency": latency})
        
        # เก็บประวัติแค่ 20 จุดล่าสุดเพื่อไม่ให้กิน RAM เยอะ
        if len(monitors[m_id]['history']) > 20:
            monitors[m_id]['history'].pop(0)

        # ส่งข้อมูลสดๆ ไปที่หน้าเว็บผ่าน Socket.io
        socketio.emit('stats_update', {
            'id': m_id,
            'status': status,
            'latency': latency,
            'history': monitors[m_id]['history']
        })
        
        time.sleep(60) # พัก 1 นาทีก่อนเช็กใหม่

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_monitor', methods=['POST'])
def add_monitor():
    data = request.json
    url = data.get('url')
    if not url or not url.startswith('http'):
        return jsonify({"error": "URL ไม่ถูกต้อง"}), 400
    
    m_id = str(int(time.time()))
    monitors[m_id] = {
        "id": m_id,
        "url": url,
        "status": "Checking",
        "history": []
    }
    
    # เริ่มระบบเช็กอัตโนมัติเบื้องหลัง
    thread = threading.Thread(target=monitor_worker, args=(m_id,))
    thread.daemon = True
    thread.start()
    
    return jsonify(monitors[m_id])

if __name__ == '__main__':
    # สำหรับรันในเครื่องตัวเอง
    socketio.run(app, host='0.0.0.0', port=8080, debug=True)
  
