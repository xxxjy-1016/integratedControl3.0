import brain
import ui
import sys
import threading
import time
from threadController import threadController
from dataStructures import SpinInfo

tasksList = []
threads = {}
curTask = 0
window = None

def getTasks():
    while True:
        global window
        global tasksList
        tasksList = window.get_spin_coating_parameters()
        time.sleep(0.1)

def operatingTasks():
    while True:
        global curTask
        while curTask < len(tasksList):
            task = tasksList[curTask]
            print(task)
            curTask += 1
        time.sleep(0.1)

def App_related_code():
    pass
    # app = ui.QApplication(sys.argv)

    # font = ui.QFont("Microsoft YaHei", 10)
    # app.setFont(font)


    # window =ui.MainWindow()
    # window.show()

    # getTasksThread = threading.Thread(target=getTasks)
    # threads["getTasksThread"] = getTasksThread
    # getTasksThread.start()
    # operatingTasksThread = threading.Thread(target=operatingTasks)
    # threads["operatingTasksThread"] = operatingTasksThread
    # operatingTasksThread.start()

try:
    movementBrain = brain.masterController()
    movementBrain.init()
    movementBrain.moveTo(movementBrain.coordinate_origin)
    movementBrain.spinCoater.returnToOriginOfSingleRevolution()
    n = 24
    for i in range(n):
        movementBrain.prepareForMultiGlass(i + 1)
    movementBrain.moveTo(movementBrain.coordinate_origin)
    params = []
    for i in range(n):
        params.append({'t_delay' : 37 + 2, 't_spin' : 42 + 2 * 2, 't_heat' : 666, 't_win' : 0, 't_wait_heat' : 0, 'glass_id' : i + 1,'vol1' : 30, 'vol2' : 30, 'spinInfoList' : [SpinInfo(4700, 42, 0.4545, 0.4545)]})
    plan = threadController.plan_antiSolution(n, params)

    print("全局调度时刻表：")
    print("-" * 65)
    for step in plan:
        print(f"Time: {step['time']:>4}s | Glass: #{step['glass_id']} | Action: {step['action']:<8} | {step['desc']}")
    print("-" * 65)
    threads = []
    for i in range(len(plan)):
        step = plan[i]
        id  = step['glass_id']
        if step['action'] == 'Task_A':
            TA = threading.Thread(target = movementBrain.OneStepMethod_A, args = (id, params[id - 1]['vol1'], params[id - 1]['spinInfoList'],))
            print(f"{step['time']}s: Glass #{id} Task_A")
            TA.start()
            threads.append(TA)
        if step['action'] == 'Task_B' :
            TB = threading.Thread(target = movementBrain.OneStepMethod_B, args = (params[id - 1]['vol2'],))
            print(f"{step['time']}s: Glass #{id} Task_B")
            TB.start()
            threads.append(TB)
        if step['action'] == 'Task_H':
            TH = threading.Thread(target = movementBrain.OneStepMethod_H, args = (id,))
            print(f"{step['time']}s: Glass #{id} Task_H")
            TH.start()
            threads.append(TH)
        if step['action'] == 'Task_T':
            TT = threading.Thread(target = movementBrain.OneStepMethod_T, args = (id,))
            print(f"{step['time']}s: Glass #{id} Task_T")
            TT.start()
            threads.append(TT)

        if i == len(plan) - 1:
            break
        time.sleep(plan[i + 1]['time'] - plan[i]['time'])

    for thread in threads:
        thread.join()
    movementBrain.close()
    #sys.exit(app.exec())

except Exception as e:
    movementBrain.moveTo(movementBrain.coordinate_origin)
    movementBrain.close()
    raise e