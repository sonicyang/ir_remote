# HVAC-IR-Control - Python port for RPI3
# Eric Masse (Ericmas001) - 2017-06-30
# https://github.com/Ericmas001/HVAC-IR-Control
# Tested on Mitsubishi Model MSZ-FE12NA

# From original: https://github.com/r45635/HVAC-IR-Control
# (c)  Vincent Cruvellier - 10th, January 2016 - Fun with ESP8266

import ir_sender
import pigpio
from datetime import datetime

class PowerMode:
    """
    PowerMode
    """
    PowerOff = 0b00100000       # 0x00      0000 0000        0
    PowerOn = 0b00100100        # 0x20      0010 0000       32

class ClimateMode:
    """
    ClimateMode
    """
    Hot = 0b00000001            # 0x08      0000 1000        8
    Cold = 0b00000011           # 0x18      0001 1000       24
    Dry = 0b00000010            # 0x10      0001 0000       16

class VanneVerticalMode:
    """
    VanneVerticalMode
    """
    Auto = 0b00000000         # 0x00      0000 0000        0
    Top = 0b00001000           # 0x10      0001 0000       16
    MiddleTop = 0b00010000     # 0x20      0010 0000       32
    Middle = 0b00011000         # 0x30      0011 0000       48
    MiddleDown = 0b00100000    # 0x40      0100 0000       64
    Down = 0b00101000          # 0x50      0101 0000       80

class FanMode:
    """
    FanMode
    """
    Speed1 = 0b00000010         # 0x01      0000 0001        1
    Speed2 = 0b00000011         # 0x02      0000 0010        2
    Speed3 = 0b00000101         # 0x03      0000 0011        3
    Auto = 0b00000000           # 0x80      1000 0000      128

class TimeControlMode:
    """
    TimeControlMode
    """
    NoTimeControl = 0b00000000  # 0x00      0000 0000        0
    ControlStart = 0b00000101   # 0x05      0000 0101        5
    ControlEnd = 0b00000011     # 0x03      0000 0011        3
    ControlBoth = 0b00000111    # 0x07      0000 0111        7

class AreaMode:
    """
    AreaMode
    """
    NotSet = 0b00000000         # 0x00      0000 0000        0
    Left = 0b01000000           # 0x40      0100 0000       64
    Right = 0b11000000          # 0xC0      1100 0000      192
    Full = 0b10000000           # 0x80      1000 0000      128

class Delay:
    """
    Delay
    """
    HdrMark = 3400
    HdrSpace = 1750
    BitMark = 450
    OneSpace = 1300
    ZeroSpace = 420
    RptMark = 440
    RptSpace = 17100

class Index:
    """
    Index
    """
    Header0 = 0
    Header1 = 1
    Header2 = 2
    Header3 = 3
    Header4 = 4
    Power = 5
    Climate = 6
    Temperature = 7
    FanAndVerticalVanne = 8
    Clock = 9
    EndTime = 10
    StartTime = 11
    TimeControlAndArea = 12
    CRC = 13

class Constants:
    """
    Constants
    """
    Frequency = 38000       # 38khz
    MinTemp = 16
    MaxTemp = 31
    MaxMask = 0xFF
    NbBytes = 14
    NbPackets = 1           # For Mitsubishi IR protocol we have to send two time the packet data

class Mitsubishi:
    """
    Mitsubishi
    """
    def __init__(self, gpio_pin, log_level=ir_sender.LogLevel.Minimal):
        self.log_level = log_level
        self.gpio_pin = gpio_pin

    def power_off(self):
        """
        power_off
        """
        self.__send_command(
            ClimateMode.Dry,
            23,
            FanMode.Auto,
            VanneVerticalMode.Auto,
            PowerMode.PowerOff)

    def send_command(self,
                     climate_mode=ClimateMode.Dry,
                     temperature=23,
                     fan_mode=FanMode.Auto,
                     vanne_vertical_mode=VanneVerticalMode.Auto):
        """
        send_command
        """
        self.__send_command(
            climate_mode,
            temperature,
            fan_mode,
            vanne_vertical_mode,
            PowerMode.PowerOn)

    def __log(self, min_log_level, message):
        if min_log_level <= self.log_level:
            print(message)

    def __send_command(self, climate_mode, temperature, fan_mode, vanne_vertical_mode, power_mode):

        sender = ir_sender.IrSender(self.gpio_pin, "NEC", dict(
            leading_pulse_duration=Delay.HdrMark,
            leading_gap_duration=Delay.HdrSpace,
            one_pulse_duration=Delay.BitMark,
            one_gap_duration=Delay.OneSpace,
            zero_pulse_duration=Delay.BitMark,
            zero_gap_duration=Delay.ZeroSpace,
            trailing_pulse_duration=Delay.RptMark,
            trailing_gap_duration=Delay.RptSpace), self.log_level)

        # data array is a valid trame, only byte to be chnaged will be updated.
        data = [0x23, 0xCB, 0x26, 0x01, 0x00, 0x20,
                0x08, 0x06, 0x30, 0x45, 0x67, 0x00,
                0x00, 0x1F]

        self.__log(ir_sender.LogLevel.Verbose, '')

        data[Index.Power] = power_mode
        self.__log(ir_sender.LogLevel.Verbose, 'PWR: {0:03d}  {0:02x}  {0:08b}'.format(data[Index.Power]))
        self.__log(ir_sender.LogLevel.Verbose, '')

        data[Index.Climate] = climate_mode
        self.__log(ir_sender.LogLevel.Verbose, 'CLS: {0:03d}  {0:02x}  {0:08b}'.format(data[Index.Climate]))
        self.__log(ir_sender.LogLevel.Verbose, '')

        data[Index.Temperature] = max(Constants.MinTemp, min(Constants.MaxTemp, temperature)) - 16
        self.__log(ir_sender.LogLevel.Verbose, 'TMP: {0:03d}  {0:02x}  {0:08b} (asked: {1})'.format(data[Index.Temperature], temperature))
        self.__log(ir_sender.LogLevel.Verbose, '')

        data[Index.FanAndVerticalVanne] = fan_mode | vanne_vertical_mode
        self.__log(ir_sender.LogLevel.Verbose, 'FAN: {0:03d}  {0:02x}  {0:08b}'.format(data[Index.FanAndVerticalVanne]))
        self.__log(ir_sender.LogLevel.Verbose, '')

        data[Index.Clock] = 0
        data[Index.EndTime] = 0
        data[Index.TimeControlAndArea] = 0

        # CRC is a simple bits addition
        # sum every bytes but the last one
        data[Index.CRC] = sum(data[:-1]) % (Constants.MaxMask + 1)
        self.__log(ir_sender.LogLevel.Verbose, 'CRC: {0:03d}  {0:02x}  {0:08b}'.format(data[Index.CRC]))
        self.__log(ir_sender.LogLevel.Verbose, '')

        # self.__log(list(map(lambda x: '{0:08b}'.format(x), data)))

        sender.send_data(data, Constants.MaxMask, True, Constants.NbPackets)
