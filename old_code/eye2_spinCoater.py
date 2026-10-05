import cv2, os

cap_id = 0                 # 0 通常代表第一个 USB 摄像头，1、2…可切换别的
cap = cv2.VideoCapture(cap_id, cv2.CAP_DSHOW)   # CAP_DSHOW 是 Windows 下加速/稳定兼容
if not cap.isOpened():
    raise IOError(f'无法打开摄像头 {cap_id}')

# 可选：设置分辨率、曝光
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)   # 0.25 表示关闭自动曝光（部分相机有效）
cap.set(cv2.CAP_PROP_EXPOSURE, -10)
cap.set(cv2.CAP_PROP_GAIN, 0)               # 增益 0 最暗
cap.set(cv2.CAP_PROP_BRIGHTNESS, 50)


save_dir = 'dataset1'
os.makedirs(save_dir, exist_ok=True)
count = 0

print('按 空格 拍照，按 q 退出')
while True:
    ret, frame = cap.read()
    if not ret:
        print('帧丢失')
        break

    cv2.imshow('USB Camera', frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord(' '):          # 空格拍照
        fn = os.path.join(save_dir, f'pic_{count}.jpg')
        cv2.imwrite(fn, frame)
        print('已保存:', fn)
        count += 1

cap.release()
cv2.destroyAllWindows()