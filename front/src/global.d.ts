import { Stores } from "alpinejs";
import { AirconStore } from "./main.ts";

declare module "alpinejs" {
  interface Stores {
    aircon: AirconStore;
  }
}
