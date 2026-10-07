
import sys
sys.path.insert(0, r'C:\\Users\\Asus\\Desktop\\OSCC india\\jarvis\\JARVIS-AI-Voice-Assistant')
try:
    from PIL import ImageGrab
    img = ImageGrab.grab()
    non_black = sum(1 for p in list(img.getdata())[:500] if sum(p[:3]) > 10)
    with open('screenshot_test_result.txt', 'w') as f:
        f.write(f'OK {img.size} nonblack={non_black}')
    img.save('test_pythonw.png')
except Exception as e:
    with open('screenshot_test_result.txt', 'w') as f:
        f.write(f'FAIL {e}')
