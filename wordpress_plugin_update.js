// WordPress Plugin JavaScript Update
// Add this to your existing WordPress plugin's chat function

// Example of how to modify your existing chat request
function sendChatMessage(sessionId, userMessage, userToken) {
    const chatRequest = {
        session_id: sessionId,
        message: userMessage,
        user_token: userToken,
        domain: window.location.hostname  // Add this line
    };
    
    // Your existing fetch logic here
    fetch('/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(chatRequest)
    })
    .then(response => response.json())
    .then(data => {
        // Handle response
    });
}

// For streaming endpoint, update similarly:
function sendStreamingChatMessage(sessionId, userMessage, userToken) {
    const chatRequest = {
        session_id: sessionId,
        message: userMessage,
        user_token: userToken,
        domain: window.location.hostname  // Add this line
    };
    
    // Your existing streaming logic here
}