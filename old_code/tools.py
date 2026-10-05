import time

from streamlit import feedback

import errors
import serial
import threading
from errors import ModbusError


class Calculator:
    def __init__(self):
        pass  # __init__ 方法不需要返回值，直接用 pass 占位即可

    def crc(data: bytes, flag: str = 'string', poly: int = 0xA001, inv: bool = False):
        """
        计算Modbus CRC-16校验码，支持自定义多项式
        :param data: 待校验的数据（字节序列）
        :param poly: CRC多项式，默认为0xA001
        :param flag: 返回值类型，'string' 返回字符串形式，'bytes' 返回整数形式
        :return: 计算得到的16位CRC校验值
        """
        res = 0xFFFF  # 初始值
        for byte in data:
            res ^= byte
            for _ in range(8):
                if res & 0x0001:
                    res >>= 1
                    res ^= poly  # 使用自定义多项式
                else:
                    res >>= 1
        # 交换高低字节以符合Modbus标准
        res = ((res >> 8) & 0xFF) | ((res & 0xFF) << 8)
        res_string = format(res, 'X').zfill(4)  # 确保字符串长度为4位

        if flag == 'str':
            if inv:
                return res_string
            return res_string[2:4] + res_string[0:2]  # 交换高低字节的顺序
        elif flag == 'list':
            if inv:
                return [res % 256, res // 256]
            return [res // 256, res % 256]
        else:
            raise ValueError("Invalid flag value. Use 'str' or 'bytes'.")
    
    def intToList(num, length = 2):
        bytes_big = None
        if num < 0 : bytes_big = num.to_bytes(length, byteorder='big', signed=True)
        if num >= 0: bytes_big = num.to_bytes(length, byteorder='big', signed=False)
        return list(bytes_big)

    def bytesToInt_bigAndSigned(abytes):
        return int.from_bytes(abytes, byteorder='big', signed=True)

    def listToString(alist):
        res = ''
        for num in alist:
            res += hex(num)[2:].zfill(2) + ' '
        return res


class ModbusCommunicator:
    def __init__(self, serName, bps=115200, timeout=10, sendingTime = 0.1):
        self.serName = serName
        self.bps = bps
        self.timeout = timeout
        self.sendingTime = sendingTime
        self.ser = serial.Serial(self.serName, self.bps, timeout=0)
        self.lock = threading.Lock()

    def communicateByList(self, command):
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
        """
        查询Modbus寄存器，支持自动重试
        """
        for attempt in range(retries):
            command = [queryDevice, 0x03] + Calculator.intToList(queryAddress) + Calculator.intToList(queryLength)
            command += Calculator.crc(bytes(command), flag='list')
            feedbackList = self.communicateByList(command)

            # 检查反馈是否为空
            if not feedbackList:
                if attempt < retries - 1:
                    print(f"查询无响应 (尝试 {attempt + 1}/{retries})，等待 0.2 秒后重试...")
                    time.sleep(0.2)
                    continue
                else:
                    print(f"查询最终失败: 地址=0x{queryAddress:04X}, 无响应")
                    raise ModbusError("查询无响应")

            # 检查异常响应（功能码 > 0x20）
            if feedbackList[1] > 0x20:
                # 再读一次确认
                feedbackList = self.communicateByList(command)
                if feedbackList and feedbackList[1] > 0x20:
                    if attempt < retries - 1:
                        print(f"查询异常 (尝试 {attempt + 1}/{retries})，等待 0.2 秒后重试...")
                        time.sleep(0.2)
                        continue
                    else:
                        print(f"查询最终失败: 地址=0x{queryAddress:04X}, 响应={feedbackList}")
                        raise ModbusError

            # 解析返回值（原逻辑不变）
            ans = []
            if returnType == "register":
                for i in range(queryLength):
                    ans.append(feedbackList[2 * i + 3] * 256 + feedbackList[2 * i + 4])
            if returnType == "bytes":
                for i in range(queryLength * 2):
                    ans.append(feedbackList[i])
            return ans

        # 如果循环结束仍未返回（理论上不会）
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
    #     print(f"写命令反馈 (hex): {' '.join(f'{x:02X}' for x in feedbackList)}")#用于调试
    #     if feedbackList[1] > 0x20:
    #         feedbackList = self.communicateByList(command)
    #         if feedbackList[1] > 0x20:
    #             raise ModbusError
    #
    #     return 0

    def writeByBytes(self, writeAddress, data, writeLength=1, writeDevice=1, retries=3):
        """
        写入Modbus寄存器，支持自动重试
        :param retries: 最大重试次数（默认3次）
        """
        for attempt in range(retries):
            # 1. 构建命令
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

            # 2. 发送命令并读取反馈
            feedbackList = self.communicateByList(command)

            # 3. 检查反馈是否异常
            if feedbackList and feedbackList[1] > 0x20:  # 异常响应（功能码最高位为1）
                # 可能是噪声，再读一次确认
                feedbackList = self.communicateByList(command)
                if feedbackList and feedbackList[1] > 0x20:
                    # 如果还没到最大重试次数，等待后重试
                    if attempt < retries - 1:
                        print(f"写入失败 (尝试 {attempt + 1}/{retries})，等待 0.2 秒后重试...")
                        time.sleep(0.2)
                        continue  # 进入下一次重试
                    else:
                        # 最后一次尝试也失败，抛出异常
                        print(f"写命令最终失败: 地址=0x{writeAddress:04X}, 数据={data}, 响应={feedbackList}")
                        raise ModbusError
            # 4. 成功则直接返回
            return 0

        # 如果循环结束仍未返回（理论上不会执行到这里）
        raise ModbusError("写入重试次数用尽但未返回")

    def close(self):
        self.ser.close()

if __name__ == '__main__':
    #testCommunicator = ModbusCommunicator("COM8")
    #testCommunicator.writeByBytes(0x5607, 1)
    #testCommunicator.close()

    result = Calculator.crc('>02d01', flag='string')
    print(result)  # 输出字符串形式的CRC校验码
    #result = Calculator.intToList(53267)
    #print(result)
    #print([hex(num) for num in result])
    #print(Calculator.crc(bytes([0x01, 0x06, 0x00, 0x38, 0x00, 0x02]), 'str', inv = True))
    pass