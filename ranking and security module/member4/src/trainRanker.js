
export function rankTrains(trains) {
  if (!Array.isArray(trains)) {
    throw new TypeError("Expected an array of train options");
  }

  const eligible = trains.filter((train) => {
    return (
      train &&
      train.trainNumber &&
      train.origin === "Roorkee" &&
      train.destination === "Haridwar" &&
      train.quota === "TATKAL" &&
      train.eligible === true &&
      train.availabilityVerified === true &&
      Number.isFinite(train.totalFare) &&
      train.totalFare >= 0
    );
  });

  eligible.sort((a, b) => {
    if (a.totalFare !== b.totalFare) {
      return a.totalFare - b.totalFare;
    }

    const durationA = Number.isFinite(a.durationMinutes)
      ? a.durationMinutes
      : Infinity;

    const durationB = Number.isFinite(b.durationMinutes)
      ? b.durationMinutes
      : Infinity;

    if (durationA !== durationB) {
      return durationA - durationB;
    }

    return String(a.trainNumber).localeCompare(
      String(b.trainNumber),
      "en",
      { numeric: true }
    );
  });

  return {
    selected: eligible[0] ?? null,
    ranked: eligible,
    status: eligible.length
      ? "OPTIONS_FOUND"
      : "NO_VERIFIED_OPTIONS"
  };
}
