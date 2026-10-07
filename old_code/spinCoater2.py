import serial
import time

from sqlalchemy.util import NONE_SET

from errors import TLE
from tools import Calculator
from tools import ModbusCommunicator
import threading
from dataStructures import *

class controller:
    """Represent controller and its associated operations."""
    def __init__(self, serName, bps=115200, timeout=10, sendingTime = 0.2):
        """Initialize controller dependencies and internal state."""
        self.serName = serName
        self.bps = bps
        self.timeout = timeout
        self.sendingTime = sendingTime
        self.communicator = ModbusCommunicator(serName = self.serName, bps = self.bps, timeout = self.timeout, sendingTime = self.sendingTime)

        self.spinThread = threading.Thread(target=self.returnToOriginOfSingleRevolution)

        #self.returnToOriginOfSingleRevolutionThread = threading.Thread(target=self.returnToOriginOfSingleRevolution)
        self.closeThread = threading.Thread(target=self.blockClose)
        self.processing = False
        self.sendingTime = 0.3

        self.modbusPOSINCMD1 = None
        self.modbusPOSINCMD2 = None
        self.modbusPOSINCMD3 = None
        self.modbusPOSINCMD4 = None
        self.modbusPOSINSEL = None
        self.modbusS_ON = None

        self.MAXPOS = 8388608
        self.processingTime = 0.3

        self.setDigitalInput()
        self.stop()
        '''self.setPositionMode()
        self.setInnerMultiPositionMode()
        self.setInnerMultiPositionMovingType(0)
        self.setInnerMultiPositionControllingType(4)'''
        self.setElectronicGearRatio(10000)
        self.setSpeedMode()
        self.setInnerSpeedMode()


    def setPositionMode(self):
        """Set position mode."""
        self.communicator.writeByBytes(0x0101, 0)

    def setInnerMultiPositionMode(self):
        """Set inner multi position mode."""
        self.communicator.writeByBytes(0x4001, 1)

    def setInnerMultiPositionMovingType(self, val = 1): # 1 means absolute position, 0 means relative position
        """Set inner multi position moving type."""
        self.communicator.writeByBytes(0x5301, val)

    def setInnerMultiPositionControllingType(self, val = 4): #4 means use command to control directly and with interruption
        """Set inner multi position controlling type."""
        self.communicator.writeByBytes(0x5302, val)

    def setElectronicGearRatio(self, val = 10000):
        """Set electronic gear ratio."""
        self.communicator.writeByBytes(0x0201, Calculator.intToList(val % 65536) + Calculator.intToList(val // 65536), writeLength = 2)

    def setDigitalInput(self):
        """Set digital input."""
        self.communicator.writeByBytes(0x6001, 21)
        self.communicator.writeByBytes(0x6003, 22)
        self.communicator.writeByBytes(0x6005, 23)
        self.communicator.writeByBytes(0x6007, 24)
        self.communicator.writeByBytes(0x6009, 19)
        self.communicator.writeByBytes(0x600B, 1)

        self.modbusPOSINCMD1 = 0x6002
        self.modbusPOSINCMD2 = 0x6004
        self.modbusPOSINCMD3 = 0x6006
        self.modbusPOSINCMD4 = 0x6008
        self.modbusPOSINSEL = 0x600A
        self.modbusS_ON = 0x600C

        '''
        this function sets the 6001(DI1)port as POSINCMD1 and that means that changing POSINCMD1 will be changing 6002, DI2 as POSINCMD2 and soon
        6009(DI5) as POSINSEL (POSIN enabling)
        '''

    def setSpeedMode(self):
        """Set speed mode."""
        self.communicator.writeByBytes(0x0101, 1)

    def setInnerSpeedMode(self):
        """Set inner speed mode."""
        self.communicator.writeByBytes(0x4101, 0)

    def getSingleRevolutionLocation(self):
        """Get single revolution location."""
        response = self.communicator.queryByBytes(queryAddress = 0xD013, queryLength = 2)
        return response[1] * 65536 + response[0]

    def getElectronicGearRatio(self):
        """Get electronic gear ratio."""
        response = self.communicator.queryByBytes(queryAddress = 0x0201, queryLength = 2)
        return response[1] * 65536 + response[0]

    def getCurrentPosition(self):
        """Get current position."""
        response1 = self.communicator.queryByBytes(queryAddress = 0xD016, queryLength = 2, returnType = "bytes")
        response2 = self.communicator.queryByBytes(queryAddress = 0xD018, queryLength = 2, returnType = "bytes")
        alist = [response2[1 * 2 + 0], response2[1 * 2 + 1], response2[0 * 2 + 0], response2[0 * 2 + 1], response1[1 * 2 + 0], response1[1 * 2 + 1], response1[0 * 2 + 0], response1[0 * 2 + 1]]
        print(alist)
        return Calculator.bytesToInt_bigAndSigned(bytes(alist))

    def changeS_ON(self, val):
        """Change s on."""
        self.communicator.writeByBytes(self.modbusS_ON, val)

    def changePOSINSEL(self, val):
        """Change posinsel."""
        self.communicator.writeByBytes(self.modbusPOSINSEL, val)

    def changePOSINCMD1(self, val):
        """Change posincmd1."""
        self.communicator.writeByBytes(self.modbusPOSINCMD1, val)

    def changePOSINCMD2(self, val):
        """Change posincmd2."""
        self.communicator.writeByBytes(self.modbusPOSINCMD2, val)

    def changePOSINCMD3(self, val):
        """Change posincmd3."""
        self.communicator.writeByBytes(self.modbusPOSINCMD3, val)

    def changePOSINCMD4(self, val):
        """Change posincmd4."""
        self.communicator.writeByBytes(self.modbusPOSINCMD4, val)

    def genSoloMultiPosition(self, id=1, aimPosition=2000000000, speed=0, accTime=0, waitTime=0):
        """Gen solo multi position."""
        self.communicator.writeByBytes(0x5305 + 5 * (id - 1),Calculator.intToList(aimPosition % 65536) + Calculator.intToList(aimPosition // 65536),writeLength=2)
        if speed > 0:
            self.communicator.writeByBytes(0x5307 + 5 * (id - 1), speed)
        if accTime > 0:
            self.communicator.writeByBytes(0x5308 + 5 * (id - 1), accTime)
        if waitTime > 0:
            self.communicator.writeByBytes(0x5309 + 5 * (id - 1), waitTime)

    def startSoloMultiPositionMovement(self, id):
        """Start solo multi position movement."""
        num = id # why this is the case, not id - 1???????????????????????????????????????? very very important!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

        '''
        a thing must note here is that the num is represented by the four POISINCMDs, which decided that the num must be 0 ~ 15. so it's reasonable to inspect that num = id - 1 (id is 1 ~ 16).
        but here, empirically num = id, which is very weird, need further confirmation.
        '''

        val4 = num % 2
        num = num // 2
        val3 = num % 2
        num = num // 2
        val2 = num % 2
        num = num // 2
        val1 = num % 2

        print(f"id={id}, num={id}, val1={val1}, val2={val2}, val3={val3}, val4={val4}")# Debugging aid.

        self.changePOSINSEL(0)
        self.changePOSINCMD1(val1)
        self.changePOSINCMD2(val2)
        self.changePOSINCMD3(val3)
        self.changePOSINCMD4(val4)
        self.changePOSINSEL(1)

    def changeSoloSpeed(self, spinInfo):
        """Change solo speed."""
        acceleratingTimeInMs = spinInfo.acceleratingTime
        deceleratingTimeInMs = spinInfo.deceleratingTime
        self.communicator.writeByBytes(0x4103, acceleratingTimeInMs)
        self.communicator.writeByBytes(0x4104, deceleratingTimeInMs)
        self.communicator.writeByBytes(0x4102, spinInfo.speed)

    def enable(self): #old
        """Enable."""
        self.changeS_ON(1)

    def stop(self): # not sure
        """Stop."""
        self.changeS_ON(0)

    def returnToOriginOfSingleRevolution(self, type='glass'):
        """Return to origin of single revolution."""
        MAXPOS = self.MAXPOS
        oldElectronicGearRatio = self.getElectronicGearRatio()
        self.setElectronicGearRatio(MAXPOS)

        self.setPositionMode()
        self.setInnerMultiPositionMode()
        self.setInnerMultiPositionMovingType(0)
        self.setInnerMultiPositionControllingType(4)

        curLocation = self.getSingleRevolutionLocation()

        if type == 'glass': aimPos = MAXPOS + 3458608 - curLocation
        else: aimPos = MAXPOS + 2635000 - curLocation
        self.genSoloMultiPosition(id= 1, aimPosition = aimPos, speed = 0, accTime = 0, waitTime = 0)
        #self.genSoloMultiPosition(id= 2, aimPosition = 10000000, speed = 3000, accTime = 10000, waitTime = 0)
        self.enable()
        self.startSoloMultiPositionMovement(1)
        time.sleep(2)
        self.stop()

        self.setElectronicGearRatio(oldElectronicGearRatio)

    # def blockSpin_speedMode(self, spinInfoList):  # without thread
    #     while (self.processing == True):
    #         time.sleep(0.1)
    #
    #     self.processing = True
    #     self.setSpeedMode()
    #     self.setInnerSpeedMode()
    #     self.enable()
    #     curSpeed = 0
    #     n = len(spinInfoList)
    #
    #     for i in range(n):
    #         self.changeSoloSpeed(spinInfoList[i])
    #
    # Calculate the time to ramp from the current speed to the segment target.
    #         if spinInfoList[i].speed > curSpeed:
    #             accTime = spinInfoList[i].getAcceleratingTimeInSecs() * (spinInfoList[i].speed - curSpeed) / 1e3
    #         else:
    #             accTime = spinInfoList[i].getDeceleratingTimeInSecs() * (curSpeed - spinInfoList[i].speed) / 1e3
    #
    #         curSpeed = spinInfoList[i].speed
    #
    # Only the final segment decelerates to zero.
    #         if i == n - 1:
    #             decTime = spinInfoList[i].getDeceleratingTimeInSecs() * spinInfoList[i].speed / 1e3
    #         else:
    #             decTime = 0
    #
    # spinTime includes acceleration, constant-speed operation, and deceleration.
    #         constantTime = spinInfoList[i].spinTime - accTime - decTime
    #         if constantTime < 0:
    #             constantTime = 0
    #
    #         time.sleep(constantTime - 2 * self.sendingTime)
    #
    #         if i == n - 1:
    #             self.changeSoloSpeed(SpinInfo(0, 0,
    #                                           spinInfoList[i].acceleratingTime / 1e3,
    #                                           spinInfoList[i].deceleratingTime / 1e3))
    #             time.sleep(decTime)
    #             self.stop()
    #
    #     self.returnToOriginOfSingleRevolution('glass')
    #     self.processing = False

    def blockSpin_speedMode(self, spinInfoList):  # without thread
        """Block spin speed mode."""
        while self.processing == True:
            time.sleep(0.1)

        self.processing = True

        try:
            self.setSpeedMode()
            self.setInnerSpeedMode()

            # Servo ON
            self.enable()
            print(">> 已发送 Servo ON")

            curSpeed = 0
            n = len(spinInfoList)

            for i in range(n):

                # =====================================================
                # SpinInfo for the current segment.
                # Define spinInfo before using it.
                # =====================================================
                spinInfo = spinInfoList[i]

                # =====================================================
                # Set target speed and acceleration/deceleration times.
                # =====================================================
                self.changeSoloSpeed(spinInfo)

                print(
                    f">> 已发送速度指令: "
                    f"speed={spinInfo.speed} rpm, "
                    f"acc={spinInfo.acceleratingTime} ms, "
                    f"dec={spinInfo.deceleratingTime} ms"
                )

                # =====================================================
                # Calculate the ramp time from current speed to target speed.
                # =====================================================
                if spinInfo.speed > curSpeed:

                    if spinInfo.speed > 0:
                        accTime = (
                                spinInfo.getAcceleratingTimeInSecs()
                                * (spinInfo.speed - curSpeed)
                                / spinInfo.speed
                        )
                    else:
                        accTime = 0

                elif spinInfo.speed < curSpeed:

                    if curSpeed > 0:
                        accTime = (
                                spinInfo.getDeceleratingTimeInSecs()
                                * (curSpeed - spinInfo.speed)
                                / curSpeed
                        )
                    else:
                        accTime = 0

                else:
                    accTime = 0

                curSpeed = spinInfo.speed

                # =====================================================
                # Decelerate to zero after the final segment.
                # =====================================================
                if i == n - 1:
                    decTime = spinInfo.getDeceleratingTimeInSecs()
                else:
                    decTime = 0

                # =====================================================
                # Calculate the constant-speed duration.
                # =====================================================
                constantTime = spinInfo.spinTime - accTime - decTime

                if constantTime < 0:
                    raise ValueError(
                        f"旋转总时间不足："
                        f"总时间={spinInfo.spinTime:.3f}s，"
                        f"加速时间={accTime:.3f}s，"
                        f"减速时间={decTime:.3f}s"
                    )

                # =====================================================
                # Reserve time for communication.
                # =====================================================
                sleepTime = constantTime - 2 * self.sendingTime

                if sleepTime < 0:
                    sleepTime = 0

                print(
                    f">> 加速={accTime:.3f}s, "
                    f"匀速={constantTime:.3f}s, "
                    f"减速={decTime:.3f}s, "
                    f"等待={sleepTime:.3f}s"
                )

                # =====================================================
                # Wait through the constant-speed phase.
                # =====================================================
                time.sleep(sleepTime)

                # =====================================================
                # Set speed to zero for the final segment.
                # =====================================================
                if i == n - 1:
                    print(">> 开始减速至 0 rpm")

                    self.changeSoloSpeed(
                        SpinInfo(
                            speed=0,
                            spinTime=0,
                            acceleratingTime=spinInfo.acceleratingTime / 1000.0,
                            deceleratingTime=spinInfo.deceleratingTime / 1000.0
                        )
                    )

                    # Wait for deceleration to complete.
                    time.sleep(decTime)

                    # Servo OFF
                    self.stop()

                    print(">> 电机停止")

            # =========================================================
            # Return to the single-turn origin.
            # =========================================================
            print(">> 开始回原点")
            self.returnToOriginOfSingleRevolution('glass')
            print(">> 回原点完成")

        finally:
            self.processing = False

    def blockSpin(self, spinInfoList, mode = "speed"):
        """Block spin."""
        if mode == "speed":
            self.blockSpin_speedMode(spinInfoList)
        elif mode == "position":
            self.blockSpin_positionMode(spinInfoList)
        else:
            print("wrong mode for spin coater!!!")

    def spin(self, spinInfoList, mode = "speed"):
        """Spin."""
        if self.spinThread.is_alive(): self.spinThread.join()
        self.spinThread = threading.Thread(target=self.blockSpin, args=(spinInfoList, mode,))
        self.spinThread.start()


    def returnToOriginOfSingleRevolution_notBlocked(self, type = 'glass'):
        """Return to origin of single revolution not blocked."""
        if self.spinThread.is_alive(): self.spinThread.join()
        self.spinThread = threading.Thread(target=self.returnToOriginOfSingleRevolution, args = (type,))
        self.spinThread.start()


    def blockClose(self):
        """Block close."""
        if self.spinThread.is_alive(): self.spinThread.join()
        self.communicator.close()

    def close(self):
        """Close."""
        self.closeThread = threading.Thread(target=self.blockClose)
        self.closeThread.start()

if __name__ == '__main__':
    spinCoater = controller('COM14')
    try:
        print("=== 交互式旋涂仪控制 ===")
        print("依次输入 转速 / 时间 / 加速度，回车开始；任意一步输入 q 退出\n")

        while True:
            # 1. Rotation speed.
            s = input("请输入转速 (rpm)，或 q 退出: ").strip()
            if s.lower() == 'q':
                break

            # 2. Duration.
            t = input("请输入时间 (s)，或 q 退出: ").strip()
            if t.lower() == 'q':
                break

            # 3. Acceleration.
            a = input("请输入加速度 (rpm/s)，或 q 退出: ").strip()
            if a.lower() == 'q':
                break

            # Validate numeric input.
            try:
                speed   = float(s)
                spinTime = float(t)
                accel    = float(a)
            except ValueError:
                print(">> 输入无效，请输入数字。本次取消\n")
                continue

            # Construct and execute the spin sequence.
            if accel <= 0:
                print(">> 加速度必须大于 0\n")
                continue

            if spinTime <= 0:
                print(">> 旋转时间必须大于 0\n")
                continue

            # Calculate acceleration time from rpm and rpm/s.
            acceleratingTime = speed / accel

            spinInfo = SpinInfo(
                speed=int(round(speed)),
                spinTime=spinTime,
                acceleratingTime=acceleratingTime,
                deceleratingTime=acceleratingTime,
            )
            print(f">> 开始旋转: 转速={speed} rpm, 时间={spinTime} s, 加速度={accel} rpm/s")
            spinCoater.blockSpin([spinInfo], mode="speed")
            print(">> 旋转完成\n")

        print("已退出")

    except Exception as e:
        raise e
    finally:
        spinCoater.blockClose()

# if __name__ == '__main__':
#     spinCoater = controller('COM14')
#     try:
#
#         testSpin = [SpinInfo(speed = 5000, acceleratingTime = 1, spinTime = 1)]
#         for i in range(25):
#             spinCoater.blockSpin(testSpin, mode = "position")
#             time.sleep(10)
#             testSpin = [SpinInfo(speed = 5000, acceleratingTime = 1, spinTime = 2)]
#             spinCoater.returnToOriginOfSingleRevolution_notBlocked('glass')
#             spinCoater.spin(testSpin, mode = "position")
#             print(i+1)
#         spinCoater.returnToOriginOfSingleRevolution()
#         spinCoater.blockClose()
#     except Exception as e:
#         spinCoater.close()
#         raise e







# if __name__ == '__main__':
#     spinCoater = controller('COM14')
#     try:
#         testSpin = [SpinInfo(speed=1000, acceleratingTime=1, spinTime=1)]
#         spinCoater.blockSpin(testSpin, mode="position")
#         spinCoater.returnToOriginOfSingleRevolution('glass')
#         spinCoater.blockClose()
#     except Exception as e:
#         spinCoater.close()
#         raise e

'''
note:set acceleratingTime = a means that the spin coater will change its speed by a * 1000 rps / s
'''