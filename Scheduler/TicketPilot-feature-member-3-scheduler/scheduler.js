const fs = require("node:fs");
const path = require("node:path");
const notifier = require("node-notifier");

const ROOT = __dirname;
const config = JSON.parse(
    fs.readFileSync(path.join(ROOT, "config.json"), "utf8")
);

const DATA_DIR = path.join(ROOT, "data");
const LOG_DIR = path.join(ROOT, "logs");
const SENT_PATH = path.join(DATA_DIR, "sent-alerts.json");
const LOG_PATH = path.join(LOG_DIR, "scheduler.log");

fs.mkdirSync(DATA_DIR, { recursive: true });
fs.mkdirSync(LOG_DIR, { recursive: true });

function log(message) {
    const line = `${new Date().toISOString()} ${message}`;
    fs.appendFileSync(LOG_PATH, line + "\n");
    console.log(line);
}

function readSent() {
    if (!fs.existsSync(SENT_PATH)) return {};
    return JSON.parse(fs.readFileSync(SENT_PATH, "utf8"));
}

let sent = readSent();

function notifyOnce(id, title, message) {
    if (sent[id]) {
        log(`DUPLICATE PREVENTED: ${id}`);
        return;
    }

    // Save the ID before requesting a Windows notification.
    sent[id] = { attemptedAt: new Date().toISOString() };
    fs.writeFileSync(SENT_PATH, JSON.stringify(sent, null, 2));

    notifier.notify({ title, message });
    log(`NOTIFICATION ATTEMPTED: ${id}`);
}


function schedule(id, time, title, message) {
    const delay = time.getTime() - Date.now();

    if (sent[id]) {
        log(`DUPLICATE PREVENTED: ${id}`);
        return;
    }

    if (delay > 0) {
        log(`SCHEDULED: ${id} at ${time.toISOString()}`);

        setTimeout(() => {
            notifyOnce(id, title, message);
        }, delay);

        return;
    }

    // Recover only if the reminder is no more than 10 minutes late.
    const tenMinutes = 10 * 60 * 1000;

    if (delay >= -tenMinutes) {
        log(`RECOVERING MISSED REMINDER: ${id}`);
        notifyOnce(id, title, `${message} (Recovery alert)`);
    } else {
        log(`MISSED/EXPIRED: ${id}; not replayed.`);
    }
}



const CLASS_TIMES = {
    "2A": "10:00",
    "3A": "10:00",
    "CC": "10:00",
    "EC": "10:00",
    "3E": "10:00",
    "SL": "11:00",
    "FC": "11:00",
    "2S": "11:00"
};

function previousDate(dateString) {
    const date = new Date(`${dateString}T00:00:00Z`);
    date.setUTCDate(date.getUTCDate() - 1);
    return date.toISOString().slice(0, 10);
}

function istDate(dateString, timeString) {
    return new Date(`${dateString}T${timeString}:00+05:30`);
}


function main() {

    log("Scheduler started. Checking pending reminders...");
    if (config.testMode) {
        const now = Date.now();

        schedule(
            "test-pre-reminder",
            new Date(now - 60_000),
            "Test: Pre-opening reminder",
            "Test reminder: the booking window opens soon."
        );

        schedule(
            "test-opening-reminder",
            new Date(now + 60_000),
            "Test: Opening-time reminder",
            "Test reminder: the opening time has arrived."
        );

        log("TEST MODE active. Two test reminders scheduled.");
        return;
    }


    const classCode = String(config.travelClass).toUpperCase();
    const openingTime = CLASS_TIMES[classCode];

    if (!openingTime) {
        throw new Error(`Unsupported Tatkal class: ${classCode}`);
    }

    const openingDate = previousDate(
        config.journeyOriginDepartureDate
    );

    const opening = istDate(openingDate, openingTime);

    log(`Travel class: ${classCode}`);
    log(`Journey origin departure date: ${config.journeyOriginDepartureDate}`);
    log(`Tatkal opening date: ${openingDate}`);
    log(`Tatkal opening time: ${openingTime} IST`);
    log(`Opening instant (UTC): ${opening.toISOString()}`);

    const preAlert = new Date(
        opening.getTime() - config.reminderMinutesBefore * 60_000
    );

    schedule(
        `${openingDate}-${classCode}-pre`,
        preAlert,
        "Tatkal reminder",
        `Tatkal opens in ${config.reminderMinutesBefore} minutes. Check your journey details.`
    );

    schedule(
        `${openingDate}-${classCode}-open`,
        opening,
        "Tatkal opening time",
        "Tatkal opening time reached. Continue manually on the official IRCTC website."
    );

    log("Real reminder times calculated and scheduled.");
}

main();
