import math
import os
import sys
import time
import traceback

from sanic import response, Sanic
import asyncio
import timeit
from PIL import Image
import io
from pathlib import Path

# MaryJane is an mjpeg server - it works by fetching *the same* jpeg image over and over from a ram drive
# MIT license
# copyright 2021 Andrew Stuart andrew.stuart@supercoders.com.au
format = 'jpg'
mime_types = {
    'jpg': 'jpg',
    'jpeg': 'jpg',
}
mime_type = mime_types[format]

directory_latest_frame = os.getenv('DIRECTORY_LATEST_FRAME')
if not directory_latest_frame:
    print('env var DIRECTORY_LATEST_FRAME is not valid, exiting.')
    sys.exit()
frame_absolute_path = f'{directory_latest_frame}frame.jpg'

port = os.getenv('PORT_NUMBER_PREVIEW_SERVER')
if not port:
    print('env var PORT_NUMBER_PREVIEW_SERVER is not valid, exiting.')
    sys.exit()
port = int(port)

app = Sanic(__name__)


def package_mjpeg(img_bytes):
    if img_bytes:
        if mime_type == 'jpg':
            return (b'--frame\r\n'
                    b'Content-Type: image/jpg\r\n\r\n' + img_bytes + b'\r\n')


async def run():
    # if the system has not yet started generating preview images, then make our own blank image
    if not os.path.isfile(frame_absolute_path):
        source_frame_image = Image.new('RGB', (1, 1), color=(0, 0, 0))
        img_byte_arr = io.BytesIO()
        source_frame_image.save(img_byte_arr, format=format, quality=20)
        return img_byte_arr.getvalue()

    if format == 'jpg':
        # 40K to 160K bandwidth / second
        with open(frame_absolute_path, 'rb') as file:
            return file.read()

    # print(f'{frame_absolute_path}: {Path(frame_absolute_path).stat().st_size}')


@app.route('/')
@app.route('/<path:path>')  # catchall
async def mjpeg_server(request, path=''):
    # 15fps = frame_milliseconds_budget of 66.66
    # 20fps = frame_milliseconds_budget of 50
    # 30fps = frame_milliseconds_budget of 33.33
    # 60fps = frame_milliseconds_budget of 16.66
    show_stats = True
    fps = 15  # frames per second
    frame_milliseconds_budget = 1000 / fps

    bytes_sent_this_second = 0
    current_second = math.floor(time.time())
    frames_sent_this_second = 0
    remaining_time = 0

    async def stream_mjpeg(response):
        bytes_sent_this_second = 0
        current_second = math.floor(time.time())
        frames_sent_this_second = 0
        remaining_time = 0
        while True:
            # if this frame was completed MORE QUICKLY than needed to maintain FPS
            # sleep the the remaining time budget
            await asyncio.sleep(remaining_time / 1000)
            start = timeit.default_timer()
            try:
                image_bytes: bytes = await run()
                await response.send(package_mjpeg(image_bytes))
            except Exception as e:
                print(repr(e))
            if current_second == math.floor(time.time()):
                bytes_sent_this_second += len(image_bytes)
                frames_sent_this_second += 1
            else:
                if show_stats:
                    print(f'{frames_sent_this_second} frames {bytes_sent_this_second} bytes sent last second')
                frames_sent_this_second = 0
                bytes_sent_this_second = 0
                current_second = math.floor(time.time())
            milliseconds_taken_to_send_frame = (timeit.default_timer() - start) * 1000
            remaining_time = frame_milliseconds_budget - milliseconds_taken_to_send_frame
            remaining_time = max(remaining_time, 0)  # make zero if negative
            if remaining_time > 0:
                print('+', end='')

    response = await request.respond(content_type='multipart/x-mixed-replace; boundary=frame')
    await stream_mjpeg(response)


if __name__ == '__main__':
    try:
        app.run(host="0.0.0.0", port=port)
    except KeyboardInterrupt:
        print("Received KeyboardInterrupt, exiting")
    except Exception as e:
        print(traceback.format_exc())
        print(f'EXCEPTION in get_instance_info: {repr(e)}')
