"""Legacy test dcm implementation retained for migration reference."""
import time
import serial
import sys

# Attempt connection to COM7.
try:
    ser = serial.Serial('COM7', 9600, timeout=1)
    print(f"串口已打开: {ser.portstr}")
except Exception as e:
    print(f"无法打开串口: {e}")
    sys.exit(1)

# Send the DCM query command.
query_dcm = ">02d0172DE"
print(f"发送查询命令: {query_dcm}")
ser.write(query_dcm.encode('utf-8'))

# Wait for a response.
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

# Close the serial port.
ser.close()
print("测试完成")
