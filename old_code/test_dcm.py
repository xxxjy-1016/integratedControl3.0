"""测试 DCM 是否能响应"""
import time
import serial
import sys

# 尝试连接 COM7
try:
    ser = serial.Serial('COM7', 9600, timeout=1)
    print(f"串口已打开: {ser.portstr}")
except Exception as e:
    print(f"无法打开串口: {e}")
    sys.exit(1)

# 发送查询 DCM 命令
query_dcm = ">02d0172DE"
print(f"发送查询命令: {query_dcm}")
ser.write(query_dcm.encode('utf-8'))

# 等待响应
print("等待 DCM 响应...")
start_time = time.time()
while time.time() - start_time < 5:
    if ser.in_waiting > 0:
        response = ser.read(ser.in_waiting).decode('ascii', errors='ignore')
        print(f"DCM 响应: {response}")
        break
    time.sleep(0.1)
else:
    print("5秒内未收到 DCM 响应")

# 关闭串口
ser.close()
print("测试完成")
