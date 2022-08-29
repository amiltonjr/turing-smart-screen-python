import struct

from serial.tools.list_ports import comports

from library.lcd_comm import *


class Command(IntEnum):
    HELLO = 0xCA  # Establish communication before driving the screen
    SET_ORIENTATION = 0xCB  # Sets the screen orientation
    DISPLAY_BITMAP = 0xCC  # Displays an image on the screen
    SET_LIGHTING = 0xCD  # Sets the screen backplate RGB LED color
    SET_BRIGHTNESS = 0xCE  # Sets the screen brightness


class OrientationValueRevB(IntEnum):
    ORIENTATION_PORTRAIT = 0x0
    ORIENTATION_LANDSCAPE = 0x1


def get_rev_b_orientation(orientation: Orientation) -> OrientationValueRevB:
    if orientation == Orientation.PORTRAIT or orientation == Orientation.REVERSE_PORTRAIT:
        return OrientationValueRevB.ORIENTATION_PORTRAIT
    else:
        return OrientationValueRevB.ORIENTATION_LANDSCAPE


class LcdCommRevB(LcdComm):
    def __init__(self):
        self.openSerial()

    def __del__(self):
        try:
            self.lcd_serial.close()
        except:
            pass

    @staticmethod
    def auto_detect_com_port():
        com_ports = serial.tools.list_ports.comports()
        auto_com_port = None

        for com_port in com_ports:
            if com_port.serial_number == "2017-2-25":
                auto_com_port = com_port.device

        return auto_com_port

    def SendCommand(self, cmd: Command, payload=None, bypass_queue: bool = False):
        # New protocol (10 byte packets, framed with the command, 8 data bytes inside)
        if payload is None:
            payload = [0] * 8
        elif len(payload) < 8:
            payload = list(payload) + [0] * (8 - len(payload))

        byteBuffer = bytearray(10)
        byteBuffer[0] = cmd
        byteBuffer[1] = payload[0]
        byteBuffer[2] = payload[1]
        byteBuffer[3] = payload[2]
        byteBuffer[4] = payload[3]
        byteBuffer[5] = payload[4]
        byteBuffer[6] = payload[5]
        byteBuffer[7] = payload[6]
        byteBuffer[8] = payload[7]
        byteBuffer[9] = cmd

        if bypass_queue:
            self.WriteData(byteBuffer)
        else:
            # Lock queue mutex then queue the request
            with config.update_queue_mutex:
                config.update_queue.put((self.WriteData, [byteBuffer]))

    def WriteData(self, byteBuffer: bytearray):
        try:
            self.lcd_serial.write(bytes(byteBuffer))
        except serial.serialutil.SerialTimeoutException:
            # We timed-out trying to write to our device, slow things down.
            print("(Write data) Too fast! Slow down!")

    def SendLine(self, line: bytes):
        config.update_queue.put((self.WriteLine, [line]))

    def WriteLine(self, line: bytes):
        try:
            self.lcd_serial.write(line)
        except serial.serialutil.SerialTimeoutException:
            # We timed-out trying to write to our device, slow things down.
            print("(Write line) Too fast! Slow down!")

    def Hello(self):
        hello = [ord('H'), ord('E'), ord('L'), ord('L'), ord('O')]

        # This command reads LCD answer on serial link, so it bypasses the queue
        self.SendCommand(Command.HELLO, payload=hello, bypass_queue=True)
        response = self.lcd_serial.read(10)

        if len(response) != 10:
            print("Device not recognised (short response to HELLO)")
        if response[0] != Command.HELLO or response[-1] != Command.HELLO:
            print("Device not recognised (bad framing)")
        if [x for x in response[1:6]] != hello:
            print("Device not recognised (No HELLO; got %r)" % (response[1:6],))
        # The HELLO response here is followed by:
        #   0x0A, 0x12, 0x00
        # It is not clear what these might be.
        # It would be handy if these were a version number, or a set of capability
        # flags. The 0x0A=10 being version 10 or 0.10, and the 0x12 being the size or the
        # indication that a backlight is present, would be nice. But that's guessing
        # based on how I'd do it.

    def InitializeComm(self):
        self.Hello()

    def Reset(self):
        # HW revision B does not implement a command to reset it: clear the screen instead
        self.Clear()

    def Clear(self):
        # HW revision B does not implement a Clear command: display a blank image on the whole screen
        blank = Image.new("RGB", (get_width(), get_height()), (255, 255, 255))
        self.DisplayPILImage(blank)

    def ScreenOff(self):
        # HW revision B does not implement a "ScreenOff" native command: using SetBrightness(0) instead
        self.SetBrightness(0)

    def ScreenOn(self):
        # HW revision B does not implement a "ScreenOn" native command: using SetBrightness() instead
        self.SetBrightness()

    def SetBrightness(self, level: int = CONFIG_DATA["display"]["BRIGHTNESS"]):
        assert 0 <= level <= 100, 'Brightness level must be [0-100]'

        # Display scales from 0 to 255, with 255 being the brightest and 0 being the darkest.
        # Convert our brightness % to an absolute value.
        level_absolute = int((level / 100) * 255)

        # Level : 0 (darkest) - 255 (brightest)
        self.SendCommand(Command.SET_BRIGHTNESS, payload=[level_absolute])

    def SetBackplateLedColor(self, led_color: tuple[int, int, int] = THEME_DATA['display']["DISPLAY_RGB_LED"]):
        self.SendCommand(Command.SET_LIGHTING, payload=led_color)

    def SetOrientation(self, orientation: Orientation = get_theme_orientation()):
        self.SendCommand(Command.SET_ORIENTATION, payload=[get_rev_b_orientation(orientation)])

    def DisplayPILImage(
            self,
            image: Image,
            x: int = 0, y: int = 0,
            image_width: int = 0,
            image_height: int = 0
    ):
        # If the image height/width isn't provided, use the native image size
        if not image_height:
            image_height = image.size[1]
        if not image_width:
            image_width = image.size[0]

        # If our image is bigger than our display, resize it to fit our screen
        if image.size[1] > get_height():
            image_height = get_height()
        if image.size[0] > get_width():
            image_width = get_width()

        assert x <= get_width(), 'Image X coordinate must be <= display width'
        assert y <= get_height(), 'Image Y coordinate must be <= display height'
        assert image_height > 0, 'Image width must be > 0'
        assert image_width > 0, 'Image height must be > 0'

        (x0, y0) = (x, y)
        (x1, y1) = (x + image_width - 1, y + image_height - 1)

        self.SendCommand(Command.DISPLAY_BITMAP,
                         payload=[(x0 >> 8) & 255, x0 & 255,
                                  (y0 >> 8) & 255, y0 & 255,
                                  (x1 >> 8) & 255, x1 & 255,
                                  (y1 >> 8) & 255, y1 & 255])
        pix = image.load()
        line = bytes()

        # Lock queue mutex then queue all the requests for the image data
        with config.update_queue_mutex:
            for h in range(image_height):
                for w in range(image_width):
                    R = pix[w, h][0] >> 3
                    G = pix[w, h][1] >> 2
                    B = pix[w, h][2] >> 3

                    # Revision A: 0bRRRRRGGGGGGBBBBB
                    #               fedcba9876543210
                    # Revision B: 0bgggBBBBBRRRRRGGG
                    # That is...
                    #   High 3 bits of green in b0-b2
                    #   Low 3 bits of green in b13-b15
                    #   Red 5 bits in b3-b7
                    #   Blue 5 bits in b8-b12
                    rgb = (B << 8) | (G >> 3) | ((G & 7) << 13) | (R << 3)
                    line += struct.pack('H', rgb)

                    # Send image data by multiple of DISPLAY_WIDTH bytes
                    if len(line) >= get_width() * 8:
                        self.SendLine(line)
                        line = bytes()

            # Write last line if needed
            if len(line) > 0:
                self.SendLine(line)
