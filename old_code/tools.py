import time

from streamlit import feedback

import errors
import serial
import threading
from errors import ModbusError


class Calculator:
    """Represent calculator and its associated operations."""
    def __init__(self):
        """Initialize calculator dependencies and internal state."""
        pass  # __init__ returns no value; pass is sufficient for an empty initializer.

    def crc(data: bytes, flag: str = 'string', poly: int = 0xA001, inv: bool = False):
        """Calculate Modbus CRC-16 for a byte sequence using poly (default 0xA001).

        Where supported, flag="string" returns hexadecimal text and flag="bytes" returns the integer checksum."""
        res = 0xFFFF  # Initial value.
        for byte in data:
            res ^= byte
            for _ in range(8):
                if res & 0x0001:
                    res >>= 1
                    res ^= poly  # Use the custom polynomial.
                else:
                    res >>= 1
        # Swap high and low bytes for the Modbus wire format.
        res = ((res >> 8) & 0xFF) | ((res & 0xFF) << 8)
        res_string = format(res, 'X').zfill(4)  # Pad the string to four digits.

        if flag == 'str':
            if inv:
                return res_string
            return res_string[2:4] + res_string[0:2]  # Swap high and low byte order.
        elif flag == 'list':
            if inv:
                return [res % 256, res // 256]
            return [res // 256, res % 256]
        else:
            raise ValueError("Invalid flag value. Use 'str' or 'bytes'.")
    
    def intToList(num, length = 2):
        """Int to list."""
        bytes_big = None
        if num < 0 : bytes_big = num.to_bytes(length, byteorder='big', signed=True)
        if num >= 0: bytes_big = num.to_bytes(length, byteorder='big', signed=False)
        return list(bytes_big)

    def bytesToInt_bigAndSigned(abytes):
        """Bytes to int big and signed."""
        return int.from_bytes(abytes, byteorder='big', signed=True)

    def listToString(alist):
        """List to string."""
        res = ''
        for num in alist:
            res += hex(num)[2:].zfill(2) + ' '
        return res


class ModbusCommunicator:
    """Represent modbus communicator and its associated operations."""
    def __init__(self, serName, bps=115200, timeout=10, sendingTime = 0.1):
        """Initialize modbus communicator dependencies and internal state."""
        self.serName = serName
        self.bps = bps
        self.timeout = timeout
        self.sendingTime = sendingTime
        self.ser = serial.Serial(self.serName, self.bps, timeout=0)
        self.lock = threading.Lock()

    def communicateByList(self, command):
        """Communicate by list."""
        with self.lock:
          self.ser.reset_input_buffer()
          self.ser.reset_output_buffer()
          #print("write:", Calculator.listToString(command))
          self.ser.write(bytes(command))
          time.sleep(self.sendingTime)
          feedback = self.ser.read(40)
          feedbackList = list(feedback.strip())
          #print("get  :", Calculator.listToString(feedbackList))
          return feedbackList

    # def queryByBytes(self, queryAddress, queryLength = 1, queryDevice = 1, returnType = "register"):
    #     command = [queryDevice, 0x03] + Calculator.intToList(queryAddress) + Calculator.intToList(queryLength)
    #     command += Calculator.crc(bytes(command), flag = 'list')
    #     feedbackList = self.communicateByList(command)
    #     #print(feedbackList)
    #     #return feedbackList
    #     if feedbackList[1] > 0x20:
    #         feedbackList = self.communicateByList(command)
    #         if feedbackList[1] > 0x20:
    #             raise ModbusError
    #
    #     ans = []
    #     if returnType == "register":
    #         for i in range(queryLength):
    #             ans.append(feedbackList[2 * i + 3] * 256 + feedbackList[2 * i + 4])
    #
    #     if returnType == "bytes":
    #         for i in range(queryLength * 2):
    #             ans.append(feedbackList[i])
    #
    #     return ans
    def queryByBytes(self, queryAddress, queryLength=1, queryDevice=1, returnType="register", retries=3):
        """Query Modbus registers with automatic retries."""
        for attempt in range(retries):
            command = [queryDevice, 0x03] + Calculator.intToList(queryAddress) + Calculator.intToList(queryLength)
            command += Calculator.crc(bytes(command), flag='list')
            feedbackList = self.communicateByList(command)

            # Check for empty feedback.
            if not feedbackList:
                if attempt < retries - 1:
                    print(f"查询无响应 (尝试 {attempt + 1}/{retries})，等待 0.2 秒后重试...")
                    time.sleep(0.2)
                    continue
                else:
                    print(f"查询最终失败: 地址=0x{queryAddress:04X}, 无响应")
                    raise ModbusError("查询无响应")

            # Check exception responses with function code above 0x20.
            if feedbackList[1] > 0x20:
                # Read once more to confirm.
                feedbackList = self.communicateByList(command)
                if feedbackList and feedbackList[1] > 0x20:
                    if attempt < retries - 1:
                        print(f"查询异常 (尝试 {attempt + 1}/{retries})，等待 0.2 秒后重试...")
                        time.sleep(0.2)
                        continue
                    else:
                        print(f"查询最终失败: 地址=0x{queryAddress:04X}, 响应={feedbackList}")
                        raise ModbusError

            # Parse the returned value using the existing convention.
            ans = []
            if returnType == "register":
                for i in range(queryLength):
                    ans.append(feedbackList[2 * i + 3] * 256 + feedbackList[2 * i + 4])
            if returnType == "bytes":
                for i in range(queryLength * 2):
                    ans.append(feedbackList[i])
            return ans

        # Fallback if the loop finishes without returning.
        raise ModbusError("查询重试次数用尽")

    # def writeByBytes(self, writeAddress, data, writeLength = 1, writeDevice = 1):
    #     command = []
    #     if writeLength == 1:
    #         command = [writeDevice, 0x06] + Calculator.intToList(writeAddress) + Calculator.intToList(data)
    #         command += Calculator.crc(bytes(command), flag = 'list')
    #     else:
    #         command = [writeDevice, 0x10] + Calculator.intToList(writeAddress) + Calculator.intToList(writeLength) + [2 * writeLength]
    #         for cur in data:
    #             command += Calculator.intToList(cur, length = 1)
    #         command += Calculator.crc(bytes(command), flag = 'list')
    #
    #     feedbackList = self.communicateByList(command)
    #     #print(command, feedbackList)
    # Historical debug output prints the write-command response in hexadecimal.
    #     if feedbackList[1] > 0x20:
    #         feedbackList = self.communicateByList(command)
    #         if feedbackList[1] > 0x20:
    #             raise ModbusError
    #
    #     return 0

    def writeByBytes(self, writeAddress, data, writeLength=1, writeDevice=1, retries=3):
        """Write Modbus registers with automatic retries; retries defaults to three attempts."""
        for attempt in range(retries):
            # 1. Construct the command.
            command = []
            if writeLength == 1:
                command = [writeDevice, 0x06] + Calculator.intToList(writeAddress) + Calculator.intToList(data)
                command += Calculator.crc(bytes(command), flag='list')
            else:
                command = [writeDevice, 0x10] + Calculator.intToList(writeAddress) + Calculator.intToList(
                    writeLength) + [2 * writeLength]
                for cur in data:
                    command += Calculator.intToList(cur, length=1)
                command += Calculator.crc(bytes(command), flag='list')

            # 2. Send the command and read feedback.
            feedbackList = self.communicateByList(command)

            # 3. Check for an exceptional response.
            if feedbackList and feedbackList[1] > 0x20:  # An exception response sets the high bit of the function code.
                # Read again to distinguish a noisy response.
                feedbackList = self.communicateByList(command)
                if feedbackList and feedbackList[1] > 0x20:
                    # Wait and retry if attempts remain.
                    if attempt < retries - 1:
                        print(f"写入失败 (尝试 {attempt + 1}/{retries})，等待 0.2 秒后重试...")
                        time.sleep(0.2)
                        continue  # Continue with the next attempt.
                    else:
                        # Raise an exception after the final failed attempt.
                        print(f"写命令最终失败: 地址=0x{writeAddress:04X}, 数据={data}, 响应={feedbackList}")
                        raise ModbusError
            # 4. Return immediately on success.
            return 0

        # Fallback if the retry loop finishes without returning.
        raise ModbusError("写入重试次数用尽但未返回")

    def close(self):
        """Close."""
        self.ser.close()

if __name__ == '__main__':
    #testCommunicator = ModbusCommunicator("COM8")
    #testCommunicator.writeByBytes(0x5607, 1)
    #testCommunicator.close()

    result = Calculator.crc('>02d01', flag='string')
    print(result)  # Return the CRC as a string.
    #result = Calculator.intToList(53267)
    #print(result)
    #print([hex(num) for num in result])
    #print(Calculator.crc(bytes([0x01, 0x06, 0x00, 0x38, 0x00, 0x02]), 'str', inv = True))
    pass