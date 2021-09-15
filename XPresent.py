import numpy as np
import cv2
import sys
import os.path
import subprocess as sp
import time
from datetime import datetime
import pickle

font = cv2.FONT_HERSHEY_COMPLEX

keyFile = ""
keys = [0]
direction = 1
currentKey = 0
startTime = None

# Returns the relative next frame id
def editorController(event, currentFrame):
    global currentKey
    global direction
    global startTime

    if event == ord("c"):
        return 100
    elif event == ord("y"):
        return -100
    elif event == ord("e"):
        if currentKey < len(keys)-1:
            return keys[currentKey+1] - currentFrame
    elif event == ord("q"):
        if currentKey >= 1:
            return keys[currentKey-1] - currentFrame
    elif event == ord("d"):
        return 10
    elif event == ord("a"):
        return -10
    elif event == ord("k"):
        if currentFrame not in keys:
            keys.append(currentFrame)
            pickle.dump(keys, open(keyFile, "wb"))
    elif event == ord("l"):
        if currentFrame in keys:
            keys.remove(currentFrame)
            pickle.dump(keys, open(keyFile, "wb"))


    if currentFrame in keys:
        currentKey = keys.index(currentFrame)
        return 0

    return 0

# Returns the relative next frame id

def presentationController(event, currentFrame):
    global currentKey
    global direction
    global startTime

    if event == ord("e"):
        if currentKey < len(keys)-1:
            return keys[currentKey+1] - currentFrame
    elif event == ord("q"):
        if currentKey >= 1:
            return keys[currentKey-1] - currentFrame
    elif event == ord("d"):
        direction = 1

        if startTime == None:
            startTime = datetime.now()

        return 1
    elif event == ord("a"):
        direction = -1
        return -1

    if currentFrame in keys:
        currentKey = keys.index(currentFrame)
        return 0
    else:
        return direction

def viewer(capture, controller, resolution, fps, stream):
    cv2.namedWindow("Presentation", cv2.WINDOW_NORMAL)

    (width, height) = resolution
    currentFrame = 0

    lastUpdate = datetime.now()
    timeBetweenUpdates = int(1000.0 / fps)

    (state, frame) = capture.read()

    while capture.isOpened():
        event = cv2.waitKey(timeBetweenUpdates // 2) & 0xFF
        nextFrame = controller(event, currentFrame)

        currentFrame = currentFrame + nextFrame

        if currentFrame < 0:
            currentFrame = 0


        if nextFrame != 0:
            if 1000*(datetime.now() - lastUpdate).total_seconds() < timeBetweenUpdates:
                lastUpdate = datetime.now()
                (state, frame) = capture.read()
            else:
                lastUpdate = datetime.now()

            if nextFrame != 1:
                capture.set(cv2.CAP_PROP_POS_FRAMES, currentFrame);

        if state == True:
            frame_width = width
            frame_height = round(frame.shape[0] * width / frame.shape[1])
            border_height = round((height - frame_height) / 2)

            frame = cv2.resize(frame, (frame_width, frame_height), interpolation=cv2.INTER_AREA)

            if stream != None:
                (state, encoded) = cv2.imencode('.png', frame)

                if state == True:
                    stream.stdin.write(encoded.tobytes())

            presenterFrame = cv2.resize(frame, resolution, interpolation=cv2.INTER_AREA)
            presenterFrame = cv2.copyMakeBorder(presenterFrame, border_height, border_height, 0, 0, cv2.BORDER_CONSTANT)

            videoTime = str(int(currentFrame / fps / 60)) + "m " + str(int(currentFrame / fps % 60)) + "s"
            cv2.putText(presenterFrame, "Video time: " + videoTime, (50, 50), font, 1, (0, 255, 0), 2, cv2.LINE_AA)

            if startTime != None:
                speechTime = ':'.join(str(datetime.now() - startTime).split('.')[:1])
                cv2.putText(presenterFrame, "Speech time: " + speechTime, (50, 100), font, 1, (0, 255, 0), 2, cv2.LINE_AA)

            if currentFrame in keys:
                cv2.putText(presenterFrame, "Current key: " + str(keys.index(currentFrame)+1) + "/" + str(len(keys)), (50, 150), font, 1, (0, 255, 0), 2, cv2.LINE_AA)

            cv2.imshow("Presentation", presenterFrame)
        else:
            break; # EOF

    capture.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    if len(sys.argv) > 3:
        video = sys.argv[2]
        resolution = (1920, 1080)

        res = sys.argv[3].split("x")

        if len(res) == 2 and res[0].isnumeric() and res[1].isnumeric():
            resolution = (int(res[0]), int(res[1]))

            if os.path.isfile(video):
                capture = cv2.VideoCapture(video)
                fps = capture.get(cv2.CAP_PROP_FPS)

                if capture.isOpened():

                    try:
                        keyFile = video + ".keys"
                        keys = pickle.load(open(keyFile, "rb"))
                    except:
                        keys = [0]

                    if sys.argv[1] == "-p":
                        stream = ['ffmpeg',
                           '-re',
                           '-s', sys.argv[3],
                           '-r', str(fps),  # rtsp fps (from input server)
                           '-i', '-',
                           '-pix_fmt', 'yuv420p',
                           '-r', '30',  # output fps
                           '-g', '50',
                           '-c:v', 'libx264',
                           '-b:v', '2M',
                           '-bufsize', '64M',
                           '-maxrate', "4M",
                           '-preset', 'veryfast',
                           '-rtsp_transport', 'tcp',
                           '-segment_times', '5',
                           '-tune',
                           'zerolatency',
                           '-sdp_file',
                           'presentation.sdp',
                           '-f', 'rtp',
                           'rtp://localhost:1234']
                        streamProcess = sp.Popen(stream, stdin=sp.PIPE)

                        playback = ['ffplay',
                            '-probesize',
                            '32',
                            '-analyzeduration',
                            '0',
                            '-fflags',
                            'nobuffer',
                            '-fflags',
                            'discardcorrupt',
                            '-flags',
                            'low_delay',
                            '-sync',
                            'ext',
                            '-framedrop',
                            '-avioflags',
                            'direct',
                            '-protocol_whitelist',
                            'file,rtp,udp',
                            '-i',
                            'presentation.sdp']
                        playbackProcess = sp.Popen(playback)

                        viewer(capture, presentationController, resolution, fps, streamProcess)

                        sys.exit(0)
                    elif sys.argv[1] == "-e":
                        viewer(capture, editorController, resolution, fps, None)
                        sys.exit(0)

                else:
                    print("Unable to open video")
            else:
                print("Error: File not found: " + video)

    print("Usage: python XPresent.py [-p | -e] videoFile ['width'x'height']")
