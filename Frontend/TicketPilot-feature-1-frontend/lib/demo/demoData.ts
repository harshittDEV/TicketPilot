import { Trip, TrainComparisonResult, BookingOutcomeRecord, UserSettings, SchedulerOpeningInfo } from '../types';

/**
 * Explicit demo seed datasets for Tatkal Assistant
 * Labeled transparently as demo data for offline development, evaluation, and reviewer previews.
 */

export const INITIAL_DEMO_TRIPS: Trip[] = [
  {
    id: "trip-demo-01",
    sourceStation: "NDLS - New Delhi",
    destStation: "BCT - Mumbai Central",
    journeyDate: new Date(Date.now() + 86400000 * 2).toISOString().slice(0, 10), // 2 days from now
    travelClass: "3A",
    isAC: true,
    passengerCount: 2,
    preferredTrainNumber: "12952",
    preferredTrainName: "Mumbai Rajdhani Express",
    fareVsDurationPreference: "fastest",
    preferredDepartureTime: "16:55",
    status: "ready",
    createdAt: new Date(Date.now() - 3600000 * 12).toISOString(),
    updatedAt: new Date(Date.now() - 3600000 * 2).toISOString(),
  },
  {
    id: "trip-demo-02",
    sourceStation: "HWH - Howrah Junction",
    destStation: "MAS - MGR Chennai Central",
    journeyDate: new Date(Date.now() + 86400000 * 3).toISOString().slice(0, 10), // 3 days from now
    travelClass: "SL",
    isAC: false,
    passengerCount: 1,
    preferredTrainNumber: "12841",
    preferredTrainName: "Coromandel Express",
    fareVsDurationPreference: "balanced",
    preferredDepartureTime: "15:20",
    status: "planned",
    createdAt: new Date(Date.now() - 3600000 * 24).toISOString(),
    updatedAt: new Date(Date.now() - 3600000 * 24).toISOString(),
  }
];

export function getDemoSchedulerStatus(isAC: boolean, journeyDate: string): SchedulerOpeningInfo {
  // Tatkal rule: Opens 1 day prior to journey date from train origin
  // AC opens at 10:00 AM IST; Non-AC opens at 11:00 AM IST
  const targetHour = isAC ? 10 : 11;
  const targetMinute = 0;

  // Compute opening date (1 day before journey date)
  const jDate = new Date(journeyDate);
  const openDate = new Date(jDate);
  openDate.setDate(openDate.getDate() - 1);
  
  // Format as IST timestamp
  const dateStr = openDate.toISOString().slice(0, 10);
  const hourPadded = String(targetHour).padStart(2, '0');
  const openTimeIsoIST = `${dateStr}T${hourPadded}:00:00+05:30`;

  const now = Date.now();
  const openMs = new Date(openTimeIsoIST).getTime();
  const diffMinutes = (openMs - now) / 60000;

  let status: SchedulerOpeningInfo['status'] = 'UPCOMING';
  if (diffMinutes <= 0 && diffMinutes > -30) {
    status = 'WINDOW_OPEN';
  } else if (diffMinutes <= 15 && diffMinutes > 0) {
    status = 'OPENING_SOON';
  } else if (diffMinutes <= -30) {
    status = 'WINDOW_CLOSED';
  }

  return {
    openingTimestampIST: openTimeIsoIST,
    targetClassType: isAC ? 'AC' : 'NON_AC',
    openingTimeFormatted: isAC ? '10:00 AM IST' : '11:00 AM IST',
    status,
    isAuthoritative: false, // Explicitly labeled as configured default rule
    sourceExplanation: `Configured IRCTC standard opening rule (${isAC ? '10:00 AM for AC' : '11:00 AM for Non-AC'} on day prior to train origin). Note: Awaiting authoritative sync from Member 3 Scheduler for train origin offset verification.`,
    remindersConfigured: true,
    trainOriginDepartureDate: dateStr,
    originDateNotice: "Assuming boarding station is train origin. If train originates 1 day prior, Tatkal opens 1 day earlier.",
  };
}

export const DEMO_COMPARISONS: Record<string, TrainComparisonResult[]> = {
  "NDLS_BCT": [
    {
      trainNumber: "12952",
      trainName: "New Delhi - Mumbai Central Rajdhani Express",
      originStation: "NDLS - New Delhi",
      destinationStation: "BCT - Mumbai Central",
      departureTime: "16:55",
      arrivalTime: "08:35",
      duration: "15h 40m",
      durationMinutes: 940,
      travelClass: "3A",
      baseFare: 2150,
      tatkalCharge: 400,
      totalFare: 2550,
      availabilityStatus: "AVAILABLE 24",
      dataProvenance: "verified",
      freshnessTimestamp: "Just now (cached from Member 4 Engine)",
      recommendation: {
        badge: "TOP_RECOMMENDATION",
        reason: "Fastest run time, highest historical Tatkal allocation, and optimal arrival time for business day.",
        engineProvenance: "Member 4 Comparison Engine v1.0",
      },
    },
    {
      trainNumber: "12954",
      trainName: "August Kranti Tejas Rajdhani Express",
      originStation: "NZM - Hazrat Nizamuddin",
      destinationStation: "MMCT - Mumbai Central",
      departureTime: "17:15",
      arrivalTime: "10:05",
      duration: "16h 50m",
      durationMinutes: 1010,
      travelClass: "3A",
      baseFare: 2040,
      tatkalCharge: 400,
      totalFare: 2440,
      availabilityStatus: "AVAILABLE 12",
      dataProvenance: "verified",
      freshnessTimestamp: "2 mins ago",
      recommendation: {
        badge: "BACKUP_OPTION",
        reason: "Close departure time with solid Tatkal seat buffer if primary train fills within 60s.",
        engineProvenance: "Member 4 Comparison Engine v1.0",
      },
    },
    {
      trainNumber: "12926",
      trainName: "Paschim SF Express",
      originStation: "NDLS - New Delhi",
      destinationStation: "BDTS - Bandra Terminus",
      departureTime: "16:35",
      arrivalTime: "14:55",
      duration: "22h 20m",
      durationMinutes: 1340,
      travelClass: "3A",
      baseFare: 1480,
      tatkalCharge: 380,
      totalFare: 1860,
      availabilityStatus: "WL 8 (High Tatkal WL)",
      dataProvenance: "estimated",
      freshnessTimestamp: "15 mins ago",
      recommendation: {
        badge: "VALUE_PICK",
        reason: "Lower fare tier, but longer travel duration. Lower confirmation likelihood due to existing waitlist.",
        engineProvenance: "Member 4 Comparison Engine v1.0",
      },
    },
  ],
};

export const INITIAL_DEMO_HISTORY: BookingOutcomeRecord[] = [
  {
    id: "booking-hist-01",
    tripId: "trip-archived-99",
    trainNumber: "12002",
    trainName: "Bhopal Shatabdi Express",
    journeyDate: "2026-10-15",
    travelClass: "CC",
    status: "CONFIRMED",
    isManuallyRecorded: true,
    isIndependentlyVerified: false,
    pnr: "284-9182371",
    recordedAt: "2026-10-14T10:04:12+05:30",
    bookingTimestamp: "2026-10-14T10:02:45+05:30",
    notes: "Booked via IRCTC e-ticketing portal using SBI netbanking. Confirmed Seat C3-44.",
  },
  {
    id: "booking-hist-02",
    tripId: "trip-archived-98",
    trainNumber: "12301",
    trainName: "Howrah Rajdhani Express",
    journeyDate: "2026-09-28",
    travelClass: "3A",
    status: "FAILED",
    isManuallyRecorded: true,
    isIndependentlyVerified: false,
    recordedAt: "2026-09-27T10:07:30+05:30",
    notes: "Payment gateway timeout at 10:03 AM; quota exhausted upon retry.",
  }
];

export const DEFAULT_USER_SETTINGS: UserSettings = {
  preferredClasses: ["3A", "2A", "CC", "SL"],
  defaultPreference: "balanced",
  enableCountdownSeconds: true,
  schedulerNotificationsEnabled: true,
  reducedMotion: false,
  highContrastGlass: false,
  dataRetentionAcknowledged: true,
};
