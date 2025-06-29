import "./style.css";
import Alpine from "alpinejs";

(window as any).Alpine = Alpine;

const AirconPower = {
  ON: "on",
  OFF: "off",
} as const;
type AirconPower = (typeof AirconPower)[keyof typeof AirconPower];

const AirconFan = {
  AUTO: "auto",
  F1: "f1",
  F2: "f2",
  F3: "f3",
  F4: "f4",
  F5: "f5",
} as const;
type AirconFan = (typeof AirconFan)[keyof typeof AirconFan];

const AirconSwing = {
  AUTO: "auto",
  P1: "p1",
  P2: "p2",
  P3: "p3",
  P4: "p4",
  P5: "p5",
} as const;
type AirconSwing = (typeof AirconSwing)[keyof typeof AirconSwing];

const AirconMode = {
  COOL: "cool",
  DRY: "dry",
  HEAT: "heat",
} as const;
type AirconMode = (typeof AirconMode)[keyof typeof AirconMode];

type AirconState = {
  power: AirconPower;
  mode: AirconMode;
  temp: number;
  fan: AirconFan;
  swing: AirconSwing;
};

export type AirconStore = AirconState & {
  update: (newState: AirconState) => void;
  powerOff: () => void;
  enableCoolMode: () => void;
  enableDryMode: () => void;
  enableHeatMode: () => void;
  toggleFan: () => boolean;
  toggleSwing: () => boolean;
  decrementTemp: () => boolean;
  incrementTemp: () => boolean;
};

function createAirconStore(): AirconStore {
  // prettier-ignore
  const swingModes: AirconSwing[] = [AirconSwing.AUTO, AirconSwing.P1, AirconSwing.P2, AirconSwing.P3, AirconSwing.P4, AirconSwing.P5];
  const nextSwingMode = (current: AirconSwing): AirconSwing => {
    const idx = swingModes.indexOf(current);
    return swingModes[(idx + 1) % swingModes.length];
  };

  // prettier-ignore
  const fanModes: AirconFan[] = [AirconFan.AUTO, AirconFan.F1, AirconFan.F2, AirconFan.F3, AirconFan.F4, AirconFan.F5];
  const nextFanMode = (current: AirconFan): AirconFan => {
    const idx = fanModes.indexOf(current);
    return fanModes[(idx + 1) % fanModes.length];
  };

  return {
    power: AirconPower.OFF,
    mode: AirconMode.COOL,
    temp: 25,
    fan: AirconFan.AUTO,
    swing: AirconSwing.AUTO,

    update(newState) {
      this.power = newState.power;
      this.mode = newState.mode;
      this.temp = newState.temp;
      this.fan = newState.fan;
      this.swing = newState.swing;
    },

    powerOff() {
      this.power = AirconPower.OFF;
    },

    enableCoolMode() {
      this.power = AirconPower.ON;
      this.mode = AirconMode.COOL;
    },
    enableDryMode() {
      this.power = AirconPower.ON;
      this.mode = AirconMode.DRY;
    },
    enableHeatMode() {
      this.power = AirconPower.ON;
      this.mode = AirconMode.HEAT;
    },

    toggleFan() {
      if (this.power === AirconPower.OFF) return false;
      this.fan = nextFanMode(this.fan);
      return true;
    },
    toggleSwing() {
      if (this.power === AirconPower.OFF) return false;
      this.swing = nextSwingMode(this.swing);
      return true;
    },

    decrementTemp() {
      if (this.power === AirconPower.OFF) return false;
      if (this.temp <= 16) return false;
      this.temp -= 1;
      return true;
    },
    incrementTemp() {
      if (this.power === AirconPower.OFF) return false;
      if (this.temp >= 30) return false;
      this.temp += 1;
      return true;
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

(window as any).handleToggleFan = function () {
  if (Alpine.store("aircon").toggleFan()) {
    postAirconStateDebounced();
  }
};

(window as any).handleToggleSwing = function () {
  if (Alpine.store("aircon").toggleSwing()) {
    postAirconStateDebounced();
  }
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
