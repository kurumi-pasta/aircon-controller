import "./style.css";
import Alpine from "alpinejs";

(window as any).Alpine = Alpine;

type AirconState = {
  power: string;
  mode: string;
  temp: number;
  fan: string;
  direction: string;
};

export type AirconStore = AirconState & {
  update: (newState: AirconState) => void;
  powerOff: () => void;
  enableCoolMode: () => void;
  enableDryMode: () => void;
  enableHeatMode: () => void;
  decrementTemp: () => boolean;
  incrementTemp: () => boolean;
};

function createAirconStore(): AirconStore {
  return {
    power: "off",
    mode: "cool",
    temp: 25,
    fan: "auto",
    direction: "auto",

    update(newState) {
      this.power = newState.power;
      this.mode = newState.mode;
      this.temp = newState.temp;
      this.fan = newState.fan;
      this.direction = newState.direction;
    },

    powerOff() {
      this.power = "off";
    },

    enableCoolMode() {
      this.power = "on";
      this.mode = "cool";
    },
    enableDryMode() {
      this.power = "on";
      this.mode = "dry";
    },
    enableHeatMode() {
      this.power = "on";
      this.mode = "heat";
    },

    decrementTemp() {
      if (this.power === "on" && this.temp > 16) {
        this.temp -= 1;
        return true;
      } else {
        return false;
      }
    },
    incrementTemp() {
      if (this.power === "on" && this.temp < 30) {
        this.temp += 1;
        return true;
      } else {
        return false;
      }
    },
  };
}

Alpine.store("aircon", createAirconStore());
Alpine.start();

// クリックハンドラ
(window as any).handlePowerOff = function () {
  Alpine.store("aircon").powerOff();
  postAirconState();
};

(window as any).handleEnableCoolMode = function () {
  Alpine.store("aircon").enableCoolMode();
  postAirconState();
};

(window as any).handleEnableDryMode = function () {
  Alpine.store("aircon").enableDryMode();
  postAirconState();
};

(window as any).handleEnableHeatMode = function () {
  Alpine.store("aircon").enableHeatMode();
  postAirconState();
};

(window as any).handleIncrementTemp = function () {
  if (Alpine.store("aircon").incrementTemp()) {
    postAirconStateDebounced();
  }
};

(window as any).handleDecrementTemp = function () {
  if (Alpine.store("aircon").decrementTemp()) {
    postAirconStateDebounced();
  }
};

// debounce付きAPI送信関数
let debounceTimer: ReturnType<typeof setTimeout> | null = null;
function postAirconStateDebounced() {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(postAirconState, 400);
}

// エアコン状態をAPIにPOSTする関数
async function postAirconState() {
  try {
    const store = Alpine.store("aircon");
    await fetch("/api/aircon/state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(store),
    });
  } catch (e) {
    console.error("エアコン状態のAPI送信失敗", e);
  }
}

// 初期状態をAPIから取得
(async function () {
  try {
    const res = await fetch("/api/aircon/state");
    if (!res.ok) throw new Error("Failed to fetch aircon state");
    const state = await res.json();
    Alpine.store("aircon").update(state);
  } catch (e) {
    console.error("エアコン状態取得失敗", e);
  }
})();
