// The data list (NVDB-style): which road properties the panel shows, grouped, and which of them
// can colour the map. New data types become rows here, never new tabs.
import type { Strings } from "./i18n";

export type Mode = "category" | "surface" | "maxspeed" | "aadt" | "width" | "owner";
export type DataId = "category" | "owner" | "surface" | "lanes" | "width" | "structures" | "maxspeed" | "aadt";

export interface DataType { id: DataId; label: keyof Strings; colour?: Mode }

export const DATA_GROUPS: { label: keyof Strings; items: DataType[] }[] = [
  { label: "grp_network", items: [
    { id: "category", label: "layer_category", colour: "category" },
    { id: "owner", label: "layer_owner", colour: "owner" },
  ] },
  { label: "grp_road", items: [
    { id: "surface", label: "layer_surface", colour: "surface" },
    { id: "lanes", label: "lanes" },
    { id: "width", label: "layer_width", colour: "width" },
    { id: "structures", label: "structures" },
  ] },
  { label: "grp_traffic", items: [
    { id: "maxspeed", label: "layer_maxspeed", colour: "maxspeed" },
    { id: "aadt", label: "layer_aadt", colour: "aadt" },
  ] },
];

export const DATA_TYPES: DataType[] = DATA_GROUPS.flatMap((g) => g.items);
export const COLOUR_MODES: DataType[] = DATA_TYPES.filter((d) => d.colour);
export const DEFAULT_DATA: DataId[] = ["category", "owner", "surface", "maxspeed"];
