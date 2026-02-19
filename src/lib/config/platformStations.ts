// Platform to station IDs mapping for live arrival queries
// Each platform has a list of station IDs to query for arrivals
export const PLATFORM_STATIONS: Record<string, string[]> = {
  "1": ["20623", "20624"],
  "2": ["20623", "20624"],
  "3": ["20623", "20624"],
  "4": ["20623", "20624"],
  "5": ["20623", "20624"],
  "6": ["20623", "20624"],
  "7": ["20623", "20624"],
  "8": ["20623", "20624"],
  "9": ["20623", "20624"],
  "10": ["20623", "20624"],
  "EAST": ["20623", "20624", "20621"], //["21149", "20621"]
  "SOUTH": ["20623", "20624", '21711'], // "22459", "21711",
  "MAIN": [ "20623", "20624"], // "22062"
  "WEST": ["20623", "20624"] // "20897"
};

// Get station IDs for a given platform
export function getStationIdsForPlatform(platformNumber: string): string[] {
  const key = platformNumber.trim().toUpperCase();
  return PLATFORM_STATIONS[key] || [];
}
