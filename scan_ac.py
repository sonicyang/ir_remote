import signal
import subprocess

# Timing Constants      [min,max]
msgDelay_timings    = [20000,4000000000]
startPeak_timings     = [3000,4000]
startTrough_timings = [1500,1800]
oneZero_threshold    = 600

class Alarm(Exception):
    pass
def alarm_handler(signum, frame):
    raise Alarm

signal.signal(signal.SIGALRM, alarm_handler)
process = subprocess.Popen("mode2 -d /dev/lirc0", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

def wait_read():
    timings = []
    breakLoop = False

    while True:
        if (len(timings) != 0):
            signal.alarm(1)

        try:
            nextline = process.stdout.readline()
        except Alarm:
            breakLoop = True
        signal.alarm(0)

        if nextline == '' and process.poll() != None:
            breakLoop = True

        if (breakLoop):
            break
        try:
            timings.append(int(nextline[6:-1]))
        except Exception:
            pass

    return timings

def valBetween(val, extremes):
    return val >= extremes[0] and val <= extremes[1]

def startBit(current, timings):
    if valBetween(timings[current],msgDelay_timings):
        if valBetween(timings[current+1],startPeak_timings):
            if valBetween(timings[current+2],startTrough_timings):
                return True
    return False

def timingsToBinary(timings):
    messages = []
    msgNum = -1
    for i in range(0, len(timings)):
        if startBit(i, timings):
            msgNum = msgNum + 1
            messages.append([])
            continue
        if (msgNum >= 0):
            messages[msgNum].append(timings[i])

    binary = ["", "", ""]
    for i in range(0, len(messages)):
        messages[i] = messages[i][3:]
        messages[i] = messages[i][::2]
        for timing in messages[i]:
            if (int(timing) > oneZero_threshold):
                binary[i] = binary[i] + "1"
            else:
                binary[i] = binary[i] + "0"
    return binary

def split_by_n(seq,n):
    while seq:
        yield seq[:n]
        seq = seq[n:]

def confirmCheckSum(binary):
    checksum = 0
    binaryBytes = list(split_by_n(binary,8))
    for x in range(0, len(binaryBytes)-1):
        checksum = checksum + int(binaryBytes[x][::-1], 2)

    binaryChecksum = bin(checksum)[2:]
    while (len(binaryChecksum) < 8):
        binaryChecksum = "0" + binaryChecksum
    binaryChecksum = binaryChecksum[-8:]

    return binaryChecksum == binaryBytes[len(binaryBytes)-1][::-1]

def binaryToTime(binary):
    timeNum = int(binary, 2)
    timeMinutes = timeNum%60
    timeHours = (timeNum - timeMinutes) / 60
    return str(timeHours) + ":" + str(timeMinutes)

while True:
    timings = wait_read()

    if (timings[0] == " could not open /dev/lirc0"):
        print "Could not open /dev/lirc0"
        break

    binary = timingsToBinary(timings)

    print ""
    print "----------MESSAGE----------"
    print "-----CHECKSUMS-----"
    print "Signal: " + str(confirmCheckSum(binary[0]))
    print "-----SETTINGS-----"
    print binary[0]
    print hex(int(binary[0][40:], 2))
    binaryBytes = list(split_by_n(binary[0],8))
    print binaryBytes
# 11000100 11010011 01100100 10000000 00000000 00100100 11000000 10010000 11000100 00000000 00000000 00000000 00000000 00010110
# 11000100 11010011 01100100 10000000 00000000 00100100 11000000 01010000 11000100 0000000000000000000000000000000010010110

    # print "Power: " + str(bool(int(binary[2][40:41])))
    # print "Temperature: " + str(int(binary[2][49:55][::-1], 2))

    # modeNum = int(binary[2][44:47][::-1], 2)
    # if modeNum==0:
        # print "Mode: Auto"
    # elif modeNum==2:
        # print "Mode: Rain"
    # elif modeNum==3:
        # print "Mode: Ice"
    # elif modeNum==4:
        # print "Mode: Sun"
    # elif modeNum==6:
        # print "Mode: Fan"
    # else:
        # print "Mode: Unknown"

    # fanNum = int(binary[2][68:72][::-1], 2)
    # if fanNum==10:
        # print "Fan Speed: Auto"
    # elif fanNum==11:
        # print "Fan Speed: Night"
    # elif (fanNum >= 3 and fanNum <= 7):
        # print "Fan Speed: " + str(fanNum-2)
    # else:
        # print "Fan Speed: Unknown"
    # print ""

    # print "Econo: " + str(bool(int(binary[2][130:131])))
    # print "Powerful: " + str(bool(int(binary[2][104:105])))
    # print "Silent: " + str(bool(int(binary[2][109:110])))
    # print "Mold Proof: " + str(bool(int(binary[2][137:138])))
    # print "Sensor: " + str(bool(int(binary[2][129:130])))
    # print "Swing: " + str(str(binary[2][64:68]) == "1111")
    # print ""

    # print "Time: " + binaryToTime(binary[1][40:51][::-1])

    # if (str(binary[2][41:42]) == "1"):
        # print "On Timer: " + binaryToTime(binary[2][80:91][::-1])
    # else:
        # print "On Timer: None"

    # if (str(binary[2][42:43]) == "1"):
        # print "Off Timer: " + binaryToTime(binary[2][92:103][::-1])
    # else:
        # print "Off Timer: None"

    print "----------END----------"

