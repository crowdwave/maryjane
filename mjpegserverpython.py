from sanic import response, Sanic
import asyncio
import timeit

# MaryJane is an mjpeg server - it works by fetching *the same* jpeg image over and over from a ram drive
# MIT license
# copyright 2021 Andrew Stuart andrew.stuart@supercoders.com.au

app = Sanic(__name__)
def package_mjpeg(img_bytes):
    return (b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + img_bytes + b'\r\n')

@app.route('/maryjane/')
async def mjpeg_server(request):
    fps = 15 # frames per second
    frame_milliseconds_budget = 1000 / fps

    # 15fps = frame_milliseconds_budget of 66.66
    # 20fps = frame_milliseconds_budget of 50
    # 30fps = frame_milliseconds_budget of 33.33
    # 60fps = frame_milliseconds_budget of 16.66

    async def stream_mjpeg(response):
        while True:
            start = timeit.default_timer()
            with open('/dev/shm/img.jpeg', mode='rb') as file:  # b is important -> binary
                await response.write(package_mjpeg(file.read()))

            stop = timeit.default_timer()
            elapsed = stop - start
            milliseconds_taken = elapsed * 1000
            difference = frame_milliseconds_budget - milliseconds_taken
            if (difference) > 0:
                # i.e. if this frame was completed MORE QUICKLY than needed to maintain FPS
                # don't continue because that would be a FPS higher than the FPS
                # instead sleep the the remaining time budget
                await asyncio.sleep(difference / 1000)

    return response.stream(stream_mjpeg, content_type='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    try:
        app.run(host="0.0.0.0", port=8080)
    except KeyboardInterrupt:
        print("Received KeyboardInterrupt, exiting")
