/**
 * SmartLMS Assistant - Popup Logic
 * Handles Auto-Auth and Smart Syncing.
 */

// --- CONFIGURATION ---
const BACKEND_URL = 'https://smartlms.online';
const FRONTEND_MATCH = '*.vercel.app';      

// --- STATE ---
let authToken = null;
let lecturesMap = {}; 

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', async () => {
    updateStatus("Detecting Session...");
    await initAuth();
    await checkPageContext(); 

    // UI Event Listeners
    document.getElementById('course-select').addEventListener('change', loadLectures);
    document.getElementById('lecture-select').addEventListener('change', onLectureSelected);
    document.getElementById('sync-btn').addEventListener('click', handleSync);
});

/**
 * PAGE CONTEXT: Are we on YT or SmartLMS?
 */
async function checkPageContext() {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const infoLabel = document.getElementById('info-label');
    const vTitle = document.getElementById('v-title');

    if (tab && tab.url.includes("youtube.com/watch")) {
        infoLabel.innerText = "YouTube Mode";
        vTitle.innerText = tab.title.replace(' - YouTube', '');
        document.getElementById('video-info').style.display = 'block';
        document.getElementById('sync-btn').disabled = false;
    } else {
        infoLabel.innerText = "Dashboard Mode";
        vTitle.innerText = "Select a lecture to sync";
        document.getElementById('video-info').style.display = 'block';
    }
}

/**
 * AUTO-AUTH: Deep Scan for JWT
 */
async function initAuth() {
    try {
        const tabs = await chrome.tabs.query({});
        const dashboardTabs = tabs.filter(t => 
            t && t.url && (t.url.includes("smartlms") || t.url.includes("vercel.app") || t.url.includes("smartlms.online"))
        );
        
        if (dashboardTabs.length === 0) {
            updateStatus("Dashboard not open", "#ff4d4d");
            showError("Please keep your SmartLMS Dashboard open.");
            return;
        }

        let foundToken = null;

        // Scan each candidate tab until we find a login
        for (const tab of dashboardTabs) {
            const [{ result }] = await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                func: () => {
                    const isJWT = (str) => typeof str === 'string' && str.startsWith('ey') && str.length > 50;
                    
                    const scan = (obj) => {
                        if (!obj) return null;
                        for (let key in obj) {
                            try {
                                const val = obj[key];
                                if (isJWT(val)) return val;
                                // If it's a string, try parsing as JSON to look inside
                                if (typeof val === 'string' && val.startsWith('{')) {
                                    const deep = JSON.parse(val);
                                    const found = scan(deep);
                                    if (found) return found;
                                }
                                if (typeof val === 'object') {
                                    const found = scan(val);
                                    if (found) return found;
                                }
                            } catch (e) {}
                        }
                        return null;
                    };

                    // 1. Try Cookies
                    const cookieMatch = document.cookie.match(/token=([^;]+)/) || document.cookie.match(/access_token=([^;]+)/);
                    if (cookieMatch && isJWT(cookieMatch[1])) return cookieMatch[1];

                    // 2. Scan localStorage
                    const lsFound = scan(localStorage);
                    if (lsFound) return lsFound;

                    // 3. Scan sessionStorage
                    const ssFound = scan(sessionStorage);
                    if (ssFound) return ssFound;

                    return null;
                }
            });

            if (result) {
                foundToken = result;
                break;
            }
        }

        if (foundToken) {
            authToken = foundToken;
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
 * FETCH: Load Courses
 */
async function loadCourses() {
    try {
        const res = await fetch(`${BACKEND_URL}/api/courses`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        const data = await res.json();
        const select = document.getElementById('course-select');
        select.innerHTML = '<option value="">Select Course</option>';
        data.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.id;
            opt.innerText = c.title;
            select.appendChild(opt);
        });
    } catch (err) {
        showError("Failed to load courses.");
    }
}

/**
 * FETCH: Load Lectures
 */
async function loadLectures() {
    const courseId = document.getElementById('course-select').value;
    const select = document.getElementById('lecture-select');
    if (!courseId) return;

    select.disabled = true;
    select.innerHTML = '<option>Loading...</option>';
    lecturesMap = {}; 

    try {
        const res = await fetch(`${BACKEND_URL}/api/lectures/course/${courseId}`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        const data = await res.json();
        
        select.innerHTML = '<option value="">Select Lecture</option>';
        data.forEach(l => {
            lecturesMap[l.id] = l; 
            const opt = document.createElement('option');
            opt.value = l.id;
            const prefix = l.youtube_url ? "✨ " : "";
            opt.innerText = prefix + l.title;
            select.appendChild(opt);
        });
        select.disabled = false;
    } catch (err) {
        showError("Failed to load lectures.");
    }
}

/**
 * UI: Update when lecture is picked
 */
function onLectureSelected() {
    const id = document.getElementById('lecture-select').value;
    const lecture = lecturesMap[id];
    const status = document.getElementById('sync-status');
    const vTitle = document.getElementById('v-title');
    const btn = document.getElementById('sync-btn');

    if (!lecture) {
        btn.disabled = true;
        return;
    }

    if (lecture.youtube_url) {
        vTitle.innerText = `Ready to Sync: ${lecture.title}`;
        status.innerText = "YouTube Link Detected (Background mode enabled)";
        status.style.color = "#44ff44";
        btn.disabled = false;
    } else {
        vTitle.innerText = lecture.title;
        status.innerText = "No video source defined for this lecture.";
        status.style.color = "#aaaaaa";
        btn.disabled = true;
    }
}

async function handleSync() {
    const id = document.getElementById('lecture-select').value;
    const lecture = lecturesMap[id];
    if (!lecture) return;

    const btn = document.getElementById('sync-btn');
    const btnText = document.getElementById('btn-text');
    setLoading(true);
    btnText.innerText = "Extracting...";

    try {
        let transcriptText = "";

        // 1. Foreground Logic
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tab && tab.url.includes("youtube.com/watch")) {
            const resp = await chrome.tabs.sendMessage(tab.id, { action: "EXTRACT_TRANSCRIPT" });
            if (resp && resp.success) transcriptText = resp.transcript;
        }

        // 2. Background Logic
        if (!transcriptText && lecture.youtube_url) {
            btnText.innerText = "Background Fetching...";
            transcriptText = await extractTranscriptInBackground(lecture.youtube_url);
        }

        if (!transcriptText) throw new Error("Could not extract transcript.");

        btnText.innerText = "Pushing to Cloud...";
        const syncRes = await fetch(`${BACKEND_URL}/api/lectures/${id}/sync-transcript`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({ transcript: transcriptText })
        });

        if (syncRes.ok) {
            btnText.innerText = "SUCCESS! Synced.";
            btn.style.background = "#44ff44";
            setTimeout(() => window.close(), 1500);
        } else {
            throw new Error("Backend rejection.");
        }
    } catch (err) {
        showError(err.message);
        setLoading(false);
        btnText.innerText = "Sync Transcript";
    }
}

async function extractTranscriptInBackground(youtubeUrl) {
    try {
        const response = await fetch(youtubeUrl);
        if (!response.ok) throw new Error(`YouTube check failed: ${response.status}`);
        
        const html = await response.text();
        const tracksMatch = html.match(/"captionTracks":\s*(\[.*?\])/);
        if (!tracksMatch) throw new Error("This video has no accessible captions.");
        
        const tracks = JSON.parse(tracksMatch[1]);
        if (!tracks || tracks.length === 0) throw new Error("Captions are disabled for this video.");
        
        const track = tracks[0];
        const transRes = await fetch(track.baseUrl + '&fmt=json3');
        
        if (!transRes.ok) throw new Error(`Caption fetch failed: ${transRes.status}`);
        
        const text = await transRes.text();
        if (!text || text.trim() === "") throw new Error("YouTube sent an empty transcript.");
        
        const data = JSON.parse(text);
        if (!data.events) throw new Error("Malformed transcript data received.");
        
        return data.events
            .filter(e => e.segs)
            .map(e => e.segs.map(s => s.utf8).join(' '))
            .join(' ')
            .replace(/\s+/g, ' ')
            .trim();
    } catch (e) {
        console.error("BG Extract Error Details:", e);
        // Bubble up the specific error message
        throw e;
    }
}

function updateStatus(text, color = "white") {
    const el = document.getElementById('auth-status');
    if (el) { el.innerText = text; el.style.color = color; }
}

function showError(msg) {
    const el = document.getElementById('error-msg');
    if (el) { el.innerText = msg; el.style.display = 'block'; }
}

function setLoading(isLoading) {
    const loader = document.getElementById('btn-loader');
    const btn = document.getElementById('sync-btn');
    if (loader) loader.style.display = isLoading ? 'block' : 'none';
    if (btn) btn.disabled = isLoading;
}
