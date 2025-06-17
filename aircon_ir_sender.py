from typing import Any
import pigpio
import argparse
from enum import Enum
from dataclasses import dataclass
import time

# Panasonic
# CS-221CF
# https://www.analysir.com/blog/2014/12/27/reverse-engineering-panasonic-ac-infrared-protocol/

DEFAULT_GPIO_PIN = 18  # デフォルトのGPIOピン番号

CARRIER_FREQ = 38000  # 38kHz
CARRIER_DUTY = 0.33  # 33% デューティ比


class AirconMode(Enum):
    COOL = "cool"  # 冷房
    DRY = "dry"  # 除湿
    HEAT = "heat"  # 暖房


class AirconFan(Enum):
    AUTO = "auto"  # 自動
    SILENT = "silent"  # 静
    LEVEL1 = "1"
    LEVEL2 = "2"
    LEVEL3 = "3"
    LEVEL4 = "4"


class AirconDirection(Enum):
    AUTO = "auto"  # 自動
    LEVEL1 = "1"  # 一番上
    LEVEL2 = "2"
    LEVEL3 = "3"
    LEVEL4 = "4"
    LEVEL5 = "5"  # 一番下


@dataclass(frozen=True)
class AirconIrFrameData:
    """
    赤外線信号のフレームを表すデータクラス
    - data2: 赤外線信号のエンコードされたデータ
    - data1: フレーム1データ(固定)
    """

    data2: str  # 01文字列
    data1: str = "0100000000000100000001110010000000000000000000000000000001100000"


class AirconState:
    """
    エアコンの状態（電源、モード、温度、風量、風向など）を管理するクラス
    """

    def __init__(
        self,
        power: bool = False,
        mode: AirconMode = AirconMode.COOL,
        temp: int = 25,
        fan: AirconFan = AirconFan.AUTO,
        direction: AirconDirection = AirconDirection.AUTO,
    ):
        self.power = power
        self.mode = mode
        self.temp = temp
        self.fan = fan
        self.direction = direction

    def set_power(self, on: bool):
        self.power = on

    def set_mode(self, mode: AirconMode):
        self.mode = mode

    def set_temp(self, temp: int):
        self.temp = temp

    def set_fan(self, fan: AirconFan):
        self.fan = fan

    def set_direction(self, direction: AirconDirection):
        self.direction = direction

    def __repr__(self):
        return (
            f"<AirconState power={self.power} mode={self.mode.value} temp={self.temp} "
            f"fan={self.fan.value} direction={self.direction.value}>"
        )


def encode_aircon_state(state: AirconState) -> str:
    """
    エアコンの状態を赤外線信号にエンコードする関数
    """
    # 共通部分
    bytes = [
        (1, "01000000"),
        (2, "00000100"),
        (3, "00000111"),
        (4, "00100000"),
        (5, "00000000"),
    ]

    # バイト6: 電源、モード
    b = 0b00000000
    if state.power:
        b |= 0b10000000
    match state.mode:
        case AirconMode.COOL:
            b |= 0b00001100
        case AirconMode.DRY:
            b |= 0b00000100
        case AirconMode.HEAT:
            b |= 0b00000010
    bytes.append((6, format(b, "08b")))

    # バイト7: 温度
    b = 0b00100000
    t = state.temp - 16
    b |= t << 1
    bytes.append((7, format(b, "08b")[::-1]))

    bytes.append((8, "00000001"))

    # バイト9: 風量
    bytes.append((9, "10000101"))

    bytes += [
        (10, "00000000"),
        (11, "00000000"),
        (12, "01100000"),
        (13, "00000110"),
    ]

    # バイト14: 運転プロファイル
    bytes.append((14, "00000000"))

    bytes += [
        (15, "00000000"),
        (16, "00000001"),
        (17, "00000000"),
        (18, "01101000"),
    ]

    # バイト19: チェックサム
    # 逆順で保持しているため戻してから計算
    checksum = sum(int(bit[1][::-1], 2) for bit in bytes) % 256
    # 逆順にして追加
    bytes.append((19, format(checksum, "08b")[::-1]))

    return "".join(bit[1] for bit in bytes)


class PanasonicPulseConverter:
    """
    Panasonicエアコンプロトコルのビット列→パルス列変換を担うクラス
    """

    # OFF は計測値 +30 がちょうどいい
    DEFAULT_HEADER_ON = 3500
    DEFAULT_HEADER_OFF = 1730
    DEFAULT_BIT_ON = 460
    DEFAULT_BIT0_OFF = 430
    DEFAULT_BIT1_OFF = 1300
    DEFAULT_SEPARATOR_OFF = 9990

    def __init__(
        self,
        HEADER_ON: int = DEFAULT_HEADER_ON,
        HEADER_OFF: int = DEFAULT_HEADER_OFF,
        BIT_ON: int = DEFAULT_BIT_ON,
        BIT0_OFF: int = DEFAULT_BIT0_OFF,
        BIT1_OFF: int = DEFAULT_BIT1_OFF,
        SEPARATOR_OFF: int = DEFAULT_SEPARATOR_OFF,
    ):
        self.HEADER_ON = HEADER_ON
        self.HEADER_OFF = HEADER_OFF
        self.BIT_ON = BIT_ON
        self.BIT0_OFF = BIT0_OFF
        self.BIT1_OFF = BIT1_OFF
        self.SEPARATOR_OFF = SEPARATOR_OFF

    def bits_to_pulses(self, bits: str) -> list[int]:
        """
        01文字列からPanasonic方式のパルス列を生成
        """
        pulses: list[int] = []
        for b in bits:
            pulses.append(self.BIT_ON)
            pulses.append(self.BIT1_OFF if b == "1" else self.BIT0_OFF)
        return pulses

    def frame_to_pulses(self, frame: AirconIrFrameData) -> list[int]:
        """
        AirconIrFrameDataから送信用パルス列（frame1→区切り→frame2）を生成
        Panasonicエアコン用
        """
        pulses = [self.HEADER_ON, self.HEADER_OFF]
        pulses += self.bits_to_pulses(frame.data1)
        pulses += [self.BIT_ON, self.SEPARATOR_OFF]

        pulses += [self.HEADER_ON, self.HEADER_OFF]
        pulses += self.bits_to_pulses(frame.data2)
        pulses += [self.BIT_ON]

        return pulses


def send_pulses(pi: pigpio.pi, gpio_pin: int, pulses: list[int]):
    """
    pigpioを使ってIRパルス列を送信する
    """
    marks_wid: dict[int, Any] = {}
    spaces_wid: dict[int, Any] = {}
    wave = [0] * len(pulses)
    for i in range(len(pulses)):
        p = pulses[i]
        if i % 2 == 0:  # Mark
            if p not in marks_wid:
                # キャリア波
                wf: list[pigpio.pulse] = []
                freq = CARRIER_FREQ
                duty = CARRIER_DUTY
                cycle = int(1e6 / freq)
                on = int(cycle * duty)
                off = cycle - on
                cycles = int(p / cycle)
                for _ in range(cycles):
                    wf.append(pigpio.pulse(1 << gpio_pin, 0, on))
                    wf.append(pigpio.pulse(0, 1 << gpio_pin, off))
                pi.wave_add_generic(wf)
                marks_wid[p] = pi.wave_create()
            wave[i] = marks_wid[p]
        else:  # Space
            if p not in spaces_wid:
                pi.wave_add_generic([pigpio.pulse(0, 1 << gpio_pin, p)])
                spaces_wid[p] = pi.wave_create()
            wave[i] = spaces_wid[p]

    pi.set_mode(gpio_pin, pigpio.OUTPUT)

    pi.wave_chain(wave)
    while pi.wave_tx_busy():
        time.sleep(0.002)

    for wid in marks_wid.values():
        pi.wave_delete(wid)
    for wid in spaces_wid.values():
        pi.wave_delete(wid)


class PanasonicAirconController:
    """
    エアコンの状態を管理し、赤外線信号を送信するクラス
    """

    def __init__(self, pi: pigpio.pi, gpio_pin: int):
        self.pi = pi
        self.gpio_pin = gpio_pin
        self.pulse_converter = PanasonicPulseConverter()

    def send_state(self, state: AirconState):
        encoded_bits = encode_aircon_state(state)
        aircon_frame = AirconIrFrameData(data2=encoded_bits)
        pulses = self.pulse_converter.frame_to_pulses(aircon_frame)
        send_pulses(self.pi, self.gpio_pin, pulses)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gpio",
        type=int,
        default=DEFAULT_GPIO_PIN,
        help="赤外線LED接続GPIOピン (デフォルト: 18)",
    )
    parser.add_argument(
        "--off",
        action="store_true",
        help="エアコンの電源をOFFにする (指定しなければON)",
    )
    parser.add_argument(
        "--temp",
        type=int,
        default=25,
        help="設定温度 (例: 25)",
    )

    args = parser.parse_args()
    gpio_pin = args.gpio
    power = not args.off
    temp = args.temp

    pi = pigpio.pi()
    if not pi.connected:
        print("pigpioデーモンに接続できません。")
        exit(1)

    aircon_state = AirconState(
        power=power,
        mode=AirconMode.COOL,
        temp=temp,
        fan=AirconFan.AUTO,
        direction=AirconDirection.AUTO,
    )

    encoded_bits = encode_aircon_state(aircon_state)
    aircon_frame = AirconIrFrameData(data2=encoded_bits)
    print(f"送信フレーム:\ndata1: {aircon_frame.data1}\ndata2: {aircon_frame.data2}")

    converter = PanasonicPulseConverter()
    pulses = converter.frame_to_pulses(aircon_frame)
    print(f"生成されたパルス列: {pulses}")

    send_pulses(pi, gpio_pin, pulses)
    pi.stop()


if __name__ == "__main__":
    main()
