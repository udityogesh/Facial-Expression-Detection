// Wait for the page to load
document.addEventListener('DOMContentLoaded', function() {
    const videoFeed = document.getElementById('video-feed');
    
    // Add error handling for video feed
    videoFeed.addEventListener('error', function() {
        console.error('Error loading video feed');
        alert('Unable to access camera. Please ensure camera permissions are granted and the server is running.');
    });
    
    // Add loading indicator
    videoFeed.addEventListener('load', function() {
        console.log('Video feed loaded successfully');
    });
    
    // Optional: Add keyboard shortcuts
    document.addEventListener('keydown', function(event) {
        // Press 'R' to reload the video feed
        if (event.key === 'r' || event.key === 'R') {
            location.reload();
        }
    });
    
    console.log('Face Emotion Detection App Initialized');
});

// Optional: Add emotion highlighting based on detection
// This is a placeholder for future enhancements where you could
// highlight the currently detected emotion in the grid
