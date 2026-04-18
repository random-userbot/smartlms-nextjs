/**
 * SmartLMS Assistant - Popup Logic
 * Handles Auto-Auth and Syncing.
 */

// --- CONFIGURATION ---
// Update these to match your actual URLs
const BACKEND_URL = 'https://smartlms.online';
const FRONTEND_MATCH = '*.vercel.app';      // Pattern to find your dashboard

// --- STATE ---
let authToken = null;
let currentTranscript = null;

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', async () => {
    updateStatus("Detecting Session...");
    await initAuth();
    await checkYouTubePage();

    // UI Event Listeners
    document.getElementById('course-select').addEventListener('change', loadLectures);
    document.getElementById('sync-btn').addEventListener('click', handleSync);
});

/**
 * AUTO-AUTH: Find an open SmartLMS tab and grab the token
 */
async function initAuth() {
    try {
        const tabs = await chrome.tabs.query({ url: [`https://${FRONTEND_MATCH}/*`, `http://localhost:3000/*`] });

        if (tabs.length === 0) {
            updateStatus("Dashboard not open", "#ff4d4d");
            showError("Please open your SmartLMS Dashboard in another tab to authenticate.");
            return;
        }

        // Run script in the dashboard tab to get the token
        const [{ result }] = await chrome.scripting.executeScript({
            target: { tabId: tabs[0].id },
            func: () => localStorage.getItem('token')
        });

        if (result) {
            authToken = result;
            updateStatus("Authenticated", "#44ff44");
            loadCourses();
        } else {
            updateStatus("Login Required", "#ffcc00");
            showError("Please log in to your SmartLMS dashboard.");
        }
    } catch (err) {
        console.error("Auth Detection Failed", err);
        updateStatus("Auth Error", "#ff4d4d");
    }
}

/**
 * YOUTUBE DETECTION: Check if current tab is a video
 */
async function checkYouTubePage() {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab.url.includes("youtube.com/watch")) {
        document.getElementById('video-info').style.display = 'block';
        document.getElementById('v-title').innerText = tab.title.replace(' - YouTube', '');
        document.getElementById('sync-btn').disabled = false;
    } else {
        showError("Navigate to a YouTube video to sync.");
    }
}

/**
 * FETCH: Load Courses from Backend
 */
async function loadCourses() {
    try {
        const res = await fetch(`${BACKEND_URL}/api/courses`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        const data = await res.json();
        const select = document.getElementById('course-select');

        // Populate courses (Filter for teacher's own courses or just show all)
        data.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.id;
            opt.innerText = c.title;
            select.appendChild(opt);
        });
    } catch (err) {
        showError("Failed to load courses from backend.");
    }
}

/**
 * FETCH: Load Lectures based on Course
 */
async function loadLectures() {
    const courseId = document.getElementById('course-select').value;
    const lectureSelect = document.getElementById('lecture-select');
    if (!courseId) return;

    lectureSelect.disabled = true;
    lectureSelect.innerHTML = '<option>Loading Lectures...</option>';

    try {
        const res = await fetch(`${BACKEND_URL}/api/lectures/course/${courseId}`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        const data = await res.json();

        lectureSelect.innerHTML = '<option value="">Select Lecture</option>';
        data.forEach(l => {
            const opt = document.createElement('option');
            opt.value = l.id;
            opt.innerText = l.title;
            lectureSelect.appendChild(opt);
        });
        lectureSelect.disabled = false;
    } catch (err) {
        showError("Failed to load lectures.");
    }
}

/**
 * SYNC: The main event
 */
async function handleSync() {
    const lectureId = document.getElementById('lecture-select').value;
    if (!lectureId) {
        showError("Please select a target lecture.");
        return;
    }

    const btn = document.getElementById('sync-btn');
    const btnText = document.getElementById('btn-text');
    const loader = document.getElementById('btn-loader');

    setLoading(true);
    btnText.innerText = "Extracting...";

    try {
        // 1. Tell Content Script to grab transcript
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        const response = await chrome.tabs.sendMessage(tab.id, { action: "EXTRACT_TRANSCRIPT" });

        if (!response || !response.success) {
            throw new Error(response?.error || "Extraction failed.");
        }

        btnText.innerText = "Syncing to Cloud...";

        // 2. POST to our new backend endpoint
        const syncRes = await fetch(`${BACKEND_URL}/api/lectures/${lectureId}/sync-transcript`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({ transcript: response.transcript })
        });

        if (syncRes.ok) {
            btnText.innerText = "SUCCESS! Synced.";
            btn.style.background = "#44ff44";
            setTimeout(() => window.close(), 1500);
        } else {
            throw new Error("Backend rejection. Check logs.");
        }

    } catch (err) {
        showError(err.message);
        setLoading(false);
        btnText.innerText = "Sync Transcript";
    }
}

// --- UTILS ---

function updateStatus(text, color = "white") {
    const el = document.getElementById('auth-status');
    el.innerText = text;
    el.style.color = color;
}

function showError(msg) {
    const el = document.getElementById('error-msg');
    el.innerText = msg;
    el.style.display = 'block';
}

function setLoading(isLoading) {
    const loader = document.getElementById('btn-loader');
    const btn = document.getElementById('sync-btn');
    loader.style.display = isLoading ? 'block' : 'none';
    btn.disabled = isLoading;
}
