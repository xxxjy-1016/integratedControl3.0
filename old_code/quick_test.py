"""Legacy quick test implementation retained for migration reference."""
import serial
import time

devices = {
    "COM7": "hand (机械手)",
    "COM8": "leg (传送带)",
    "COM9": "mouth (注射泵)",
    "COM14": "spinCoater (旋涂机)"
}

def test_device(com, name):
    """Test a connection to one device."""
    try:
        ser = serial.Serial(com, 115200, timeout=1)
        # Send the query command.
        test_cmd = b'\x01\x03\x02\x02\x00\x01\x24\x72'  # Gripper query command.
        ser.write(test_cmd)
        time.sleep(0.2)
        response = ser.read(50)
        ser.close()
        
        if response:
            print(f"  ✅ {name} ({com}): 已连接 - 收到响应 {len(response)} bytes")
            return True
        else:
            print(f"  ⚠️ {name} ({com}): 已连接 - 无响应")
            return False
    except Exception as e:
        print(f"  ❌ {name} ({com}): {str(e)}")
        return False

print("=" * 50)
print("   薄膜制备设备连接检测")
print("=" * 50)

for com, name in devices.items():
    test_device(com, name)

print("=" * 50)
print("检测完成")
