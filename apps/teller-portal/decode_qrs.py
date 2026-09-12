from PIL import Image
from pyzbar.pyzbar import decode
import os

qr_dir = 'sample_qrs'
for fname in sorted(os.listdir(qr_dir)):
    path = os.path.join(qr_dir, fname)
    try:
        img = Image.open(path)
        result = decode(img)
        if result:
            print(f'{fname}::: {result[0].data.decode()}')
        else:
            print(f'{fname}::: (unreadable)')
    except Exception as e:
        print(f'{fname}::: ERROR - {e}')
