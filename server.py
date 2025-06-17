import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
import pigpio
import json

from aircon_ir_sender import (
    DEFAULT_GPIO_PIN,
    PanasonicAirconController,
    AirconState,
    AirconMode,
    AirconFan,
    AirconDirection,
)


def validate_aircon_state(data: dict[str, Any]) -> tuple[bool, str]:
    """
    AirconState用のバリデーション関数。
    必須キー: power(bool), mode(str), temp(int), fan(str), direction(str)
    値が不正な場合はFalse, エラーメッセージを返す。
    """
    # power
    valid_power = {"on", "off"}
    if "power" not in data or data["power"] not in valid_power:
        return False, "'power' must be a boolean."

    # mode
    valid_modes = {m.name.lower() for m in AirconMode}
    if (
        "mode" not in data
        or not isinstance(data["mode"], str)
        or data["mode"].lower() not in valid_modes
    ):
        return False, f"'mode' must be one of {sorted(valid_modes)}."

    # temp
    if (
        "temp" not in data
        or not isinstance(data["temp"], int)
        or not (16 <= data["temp"] <= 30)
    ):
        return False, "'temp' must be an integer between 16 and 30."

    # fan
    valid_fans = {f.name.lower() for f in AirconFan}
    if (
        "fan" not in data
        or not isinstance(data["fan"], str)
        or data["fan"].lower() not in valid_fans
    ):
        return False, f"'fan' must be one of {sorted(valid_fans)}."

    # direction
    valid_dirs = {d.name.lower() for d in AirconDirection}
    if (
        "direction" not in data
        or not isinstance(data["direction"], str)
        or data["direction"].lower() not in valid_dirs
    ):
        return False, f"'direction' must be one of {sorted(valid_dirs)}."

    return True, ""


class AirconStateRepository:
    """
    エアコン状態の永続化・取得を担うリポジトリ
    """

    def __init__(self, filepath: str = "aircon_state.json"):
        self.filepath = filepath

    def load(self) -> AirconState:
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AirconState(
                power=data["power"] == "on",
                mode=AirconMode[data["mode"].upper()],
                temp=int(data["temp"]),
                fan=AirconFan[data["fan"].upper()],
                direction=AirconDirection[data["direction"].upper()],
            )
        except Exception as e:
            # デフォルト値を返す
            print(f"Error loading aircon state: {e}")
            return AirconState()

    def save(self, state: AirconState) -> bool:
        try:
            data = {
                "power": "on" if state.power else "off",
                "mode": state.mode.name.lower(),
                "temp": state.temp,
                "fan": state.fan.name.lower(),
                "direction": state.direction.name.lower(),
            }
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gpio",
        type=int,
        default=DEFAULT_GPIO_PIN,
        help="赤外線LED接続GPIOピン (デフォルト: 18)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="HTTPサーバのポート番号 (デフォルト: 8080)",
    )
    args = parser.parse_args()

    pi = pigpio.pi()
    if not pi.connected:
        print("pigpioデーモンに接続できません。")
        exit(1)

    controller = PanasonicAirconController(pi, args.gpio)
    repository = AirconStateRepository()

    class MyHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path == "/api/aircon/state":
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                data = None
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Invalid JSON format.\n")
                    return

                is_valid, error_message = validate_aircon_state(data)
                if not is_valid:
                    self.send_response(400)
                    self.send_header("Content-type", "text/plain")
                    self.end_headers()
                    self.wfile.write(
                        f"Invalid aircon state: {error_message}".encode("utf-8")
                    )
                    return

                aircon_state = AirconState(
                    power=data["power"] == "on",
                    mode=AirconMode[data["mode"].upper()],
                    temp=int(data["temp"]),
                    fan=AirconFan[data["fan"].upper()],
                    direction=AirconDirection[data["direction"].upper()],
                )

                try:
                    repository.save(aircon_state)
                    controller.send_state(aircon_state)
                    self.send_response(200)
                    self.end_headers()
                except Exception as e:
                    self.send_response(400)
                    self.send_header("Content-type", "text/plain")
                    self.end_headers()
                    self.wfile.write(
                        f"Error parsing or sending aircon state: {str(e)}".encode(
                            "utf-8"
                        )
                    )
            else:
                self.send_response(404)
                self.end_headers()

        def do_GET(self):
            if self.path == "/api/aircon/state":
                state = repository.load()
                response_data = {
                    "power": "on" if state.power else "off",
                    "mode": state.mode.name.lower(),
                    "temp": state.temp,
                    "fan": state.fan.name.lower(),
                    "direction": state.direction.name.lower(),
                }
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode("utf-8"))

            elif self.path == "/":
                try:
                    with open("index.html", "rb") as f:
                        index_html = f.read()
                except Exception as e:
                    print(f"Error loading index.html at startup: {e}")
                    self.send_response(500)
                    self.end_headers()
                    return

                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(index_html)
            else:
                self.send_response(404)
                self.end_headers()

    httpd = HTTPServer(("", args.port), MyHandler)
    print(f"Serving HTTP on port {args.port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        httpd.server_close()
        pi.stop()


if __name__ == "__main__":
    main()
