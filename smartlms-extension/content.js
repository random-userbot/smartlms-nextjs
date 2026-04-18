/**
 * SmartLMS Assistant - Content Script
 * Extracts YouTube transcripts by accessing internal page data.
 */

console.log("🚀 SmartLMS Assistant Active");

// Listen for messages from the Popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "EXTRACT_TRANSCRIPT") {
        extractTranscript().then(sendResponse);
        return true; // Keep channel open for async
    }
});

async function extractTranscript() {
    try {
        // 1. Get YouTube Video ID
        const urlParams = new URLSearchParams(window.location.search);
        const videoId = urlParams.get('v');
        if (!videoId) throw new Error("Video ID not found.");

        // 2. Fetch the page source to find the TimedText URL
        // We look for the 'playerResponse' object which is embedded in the page
        const response = await fetch(window.location.href);
        const html = await response.text();
        
        // Find the caption track URL
        const tracksMatch = html.match(/"captionTracks":\s*(\[.*?\])/);
        if (!tracksMatch) throw new Error("No captions found for this video.");
        
        const tracks = JSON.parse(tracksMatch[1]);
        // Priority: English -> Any other -> First available
        const track = tracks.find(t => t.languageCode === 'en' || t.languageCode === 'en-US') || tracks[0];
        
        if (!track || !track.baseUrl) throw new Error("Captions detected but no data URL available.");

        // 3. Fetch the actual transcript (XML or JSON)
        const transcriptResponse = await fetch(track.baseUrl + '&fmt=json3');
        const transcriptData = await transcriptResponse.json();

        // 4. Clean and format the text
        const cleanText = transcriptData.events
            .filter(e => e.segs)
            .map(e => e.segs.map(s => s.utf8).join(' '))
            .join(' ')
            .replace(/\s+/g, ' ')
            .trim();

        return { 
            success: true, 
            transcript: cleanText, 
            title: document.title.replace(' - YouTube', ''),
            videoId: videoId
        };

    } catch (error) {
        console.error("SmartLMS Extraction Error:", error);
        return { success: false, error: error.message };
    }
}
