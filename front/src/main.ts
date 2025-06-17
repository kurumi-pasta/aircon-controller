import "./style.css";
import Alpine from "alpinejs";

(window as any).Alpine = Alpine;

Alpine.store("airconState", {
  power: "off",
  mode: "cool",
  temp: 25,
  fan: "auto",
  direction: "auto",
});

Alpine.start();

// エアコンの電源をOFFにする関数
(window as any).togglePowerOff = function () {
  const store = Alpine.store("airconState") as any;
  if (store.power !== "off") {
    Alpine.store("airconState", { ...store, power: "off" });
    postAirconStateDebounced();
  }
};

// 冷房ボタンで電源ON+モードcoolにする関数
(window as any).setCoolMode = function () {
  const store = Alpine.store("airconState") as any;
  Alpine.store("airconState", { ...store, power: "on", mode: "cool" });
  postAirconStateDebounced();
};

// 除湿ボタンで電源ON+モードdryにする関数
(window as any).setDryMode = function () {
  const store = Alpine.store("airconState") as any;
  Alpine.store("airconState", { ...store, power: "on", mode: "dry" });
  postAirconStateDebounced();
};

// 暖房ボタンで電源ON+モードheatにする関数
(window as any).setHeatMode = function () {
  const store = Alpine.store("airconState") as any;
  Alpine.store("airconState", { ...store, power: "on", mode: "heat" });
  postAirconStateDebounced();
};

// 温度を1上げる関数
(window as any).incrementTemp = function () {
  const store = Alpine.store("airconState") as any;
  if (
    store.power === "on" &&
    typeof store.temp === "number" &&
    store.temp < 30
  ) {
    Alpine.store("airconState", { ...store, temp: store.temp + 1 });
    postAirconStateDebounced();
  }
};

// 温度を1下げる関数
(window as any).decrementTemp = function () {
  const store = Alpine.store("airconState") as any;
  if (
    store.power === "on" &&
    typeof store.temp === "number" &&
    store.temp > 16
  ) {
    Alpine.store("airconState", { ...store, temp: store.temp - 1 });
    postAirconStateDebounced();
  }
};

// debounce付きAPI送信関数
let debounceTimer: ReturnType<typeof setTimeout> | null = null;
function postAirconStateDebounced() {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(postAirconState, 500);
}

// エアコン状態をAPIにPOSTする関数
async function postAirconState() {
  try {
    const state = Alpine.store("airconState");
    await fetch("/api/aircon/state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state),
    });
  } catch (e) {
    console.error("エアコン状態のAPI送信失敗", e);
  }
}

(async function () {
  try {
    const res = await fetch("/api/aircon/state");
    if (!res.ok) throw new Error("Failed to fetch aircon state");
    const state = await res.json();
    Alpine.store("airconState", state);
  } catch (e) {
    console.error("エアコン状態取得失敗", e);
  }
})();
