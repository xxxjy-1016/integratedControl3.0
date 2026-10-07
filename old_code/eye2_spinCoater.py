import cv2, os

cap_id = 0                 # Camera index 0 usually selects the first USB camera; 1, 2, etc. select others.
cap = cv2.VideoCapture(cap_id, cv2.CAP_DSHOW)   # CAP_DSHOW improves compatibility and startup on Windows.
if not cap.isOpened():
    raise IOError(f'无法打开摄像头 {cap_id}')

# Optionally configure resolution and exposure.
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)   # Exposure value 0.25 disables automatic exposure on some cameras.
cap.set(cv2.CAP_PROP_EXPOSURE, -10)
cap.set(cv2.CAP_PROP_GAIN, 0)               # Gain 0 gives the darkest image.
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
    elif key == ord(' '):          # Press Space to capture an image.
        fn = os.path.join(save_dir, f'pic_{count}.jpg')
        cv2.imwrite(fn, frame)
        print('已保存:', fn)
        count += 1

cap.release()
cv2.destroyAllWindows()