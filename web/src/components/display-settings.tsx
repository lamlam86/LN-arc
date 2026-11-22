"use client";

import * as React from "react";

import { MoonStar, SunMedium } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";

const NIGHT_KEY = "ln_night_light";
const BRIGHT_KEY = "ln_brightness";

const MIN_BRIGHTNESS = 60;
const MAX_BRIGHTNESS = 120;

interface DisplaySettings {
  night: boolean;
  brightness: number;
  setNight: (value: boolean) => void;
  setBrightness: (value: number) => void;
}

const DisplaySettingsContext = React.createContext<DisplaySettings | null>(null);

function clampBrightness(value: number): number {
  if (!Number.isFinite(value)) return 100;
  return Math.min(MAX_BRIGHTNESS, Math.max(MIN_BRIGHTNESS, Math.round(value / 5) * 5));
}

export function DisplaySettingsProvider({ children }: { children: React.ReactNode }) {
  const [night, setNightState] = React.useState(false);
  const [brightness, setBrightnessState] = React.useState(100);

  React.useEffect(() => {
    const storedNight = window.localStorage.getItem(NIGHT_KEY);
    const storedBrightness = Number(window.localStorage.getItem(BRIGHT_KEY) ?? "100");
    setNightState(storedNight === "1");
    setBrightnessState(clampBrightness(storedBrightness));
  }, []);

  const setNight = React.useCallback((value: boolean) => {
    setNightState(value);
    window.localStorage.setItem(NIGHT_KEY, value ? "1" : "0");
  }, []);

  const setBrightness = React.useCallback((value: number) => {
    const next = clampBrightness(value);
    setBrightnessState(next);
    window.localStorage.setItem(BRIGHT_KEY, String(next));
  }, []);

  const dimOpacity = brightness < 100 ? ((100 - brightness) / 100) * 0.55 : 0;
  const brightOpacity = brightness > 100 ? ((brightness - 100) / 100) * 0.35 : 0;

  return (
    <DisplaySettingsContext.Provider value={{ night, brightness, setNight, setBrightness }}>
      {children}
      {/* Warm overlay (night light). Above the app, but never blocks input. */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-[9998] transition-[background-color] duration-300"
        style={{
          backgroundColor: night ? "rgba(255, 154, 54, 0.14)" : "rgba(255, 154, 54, 0)",
          mixBlendMode: "multiply",
        }}
      />
      {/* Brightness overlay: darkens below 100%, lifts above 100%. */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-[9999] transition-opacity duration-300"
        style={{
          backgroundColor: brightness < 100 ? "#000" : "#fff",
          opacity: brightness < 100 ? dimOpacity : brightOpacity,
          mixBlendMode: brightness < 100 ? "multiply" : "screen",
        }}
      />
    </DisplaySettingsContext.Provider>
  );
}

export function useDisplaySettings(): DisplaySettings {
  const settings = React.useContext(DisplaySettingsContext);
  if (!settings) throw new Error("useDisplaySettings must be used inside DisplaySettingsProvider");
  return settings;
}

export function DisplaySettingsControl() {
  const { night, brightness, setNight, setBrightness } = useDisplaySettings();

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          size="icon"
          variant={night ? "secondary" : "ghost"}
          aria-label="Night light and brightness"
          title="Night light and brightness"
        >
          {night ? <MoonStar className="size-4 text-amber-300" /> : <SunMedium className="size-4" />}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72">
        <div className="space-y-4">
          <div>
            <h4 className="font-medium text-sm">Display</h4>
            <p className="text-muted-foreground text-xs">Reduce blue light and adjust brightness.</p>
          </div>

          <div className="flex items-center justify-between gap-3">
            <div className="space-y-0.5">
              <Label htmlFor="night-light" className="text-sm">
                Night light
              </Label>
              <p className="text-muted-foreground text-xs">Warm tint for low-light use.</p>
            </div>
            <Switch id="night-light" checked={night} onCheckedChange={setNight} />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-sm">Brightness</Label>
              <span className="text-muted-foreground text-xs tabular-nums">{brightness}%</span>
            </div>
            <Slider
              value={[brightness]}
              min={MIN_BRIGHTNESS}
              max={MAX_BRIGHTNESS}
              step={5}
              onValueChange={([value]) => setBrightness(value)}
            />
            <div className="flex justify-between text-[10px] text-muted-foreground">
              <span>Dimmer</span>
              <span>Brighter</span>
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
