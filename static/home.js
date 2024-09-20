async function checkApiKey() {
    const apiKey = getCookie('api_key');
    if (apiKey) {
        try {
            const response = await fetch('/verify', {
                method: 'POST',
                headers: {
                    'Authorization': apiKey
                },
                body: JSON.stringify({ apiKey: apiKey })
            });
            if (response.ok) {
                console.log('API Key is valid');
            } else {
                console.log('Invalid API Key');
                window.location.href = '/login';
            }
        } catch (error) {
            console.error('Error verifying API Key:', error);
            window.location.href = '/login';
        }
    } else {
        console.log('No API Key found in cookie');
        window.location.href = '/login';
    }
}

window.addEventListener('load', checkApiKey);

document.getElementById('file-upload').addEventListener('change', async function(e) {
    const file = e.target.files[0];
    if (!file) return;

    // Clear previous upload status and reset copy button
    resetUploadStatus();

    await uploadFile(file);
});

async function uploadFile(file) {
    const apiKey = getCookie('api_key');
    if (!apiKey) {
        window.location.href = '/login';
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/upload', {
            method: 'POST',
            headers: {
                'Authorization': apiKey
            },
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            showUploadStatus('File uploaded successfully!', result.file_url);
        } else {
            const errorData = await response.json();
            showError(errorData.detail || 'File upload failed. Please try again.');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('An error occurred. Please try again.');
    }
}

function showUploadStatus(message, fileUrl) {
    const statusElement = document.getElementById('upload-status');
    const messageElement = document.getElementById('upload-message');
    const copyButton = document.getElementById('copy-url');

    messageElement.textContent = message;
    statusElement.classList.remove('hidden');
    copyButton.classList.remove('hidden');

    copyButton.onclick = function() {
        navigator.clipboard.writeText(fileUrl).then(() => {
            copyButton.textContent = 'Copied!';
            copyButton.classList.add('animate-pulse');
            setTimeout(() => {
                copyButton.textContent = 'Copy URL';
                copyButton.classList.remove('animate-pulse');
            }, 2000);
        });
    };
}

function resetUploadStatus() {
    // Reset the file input
    document.getElementById('file-upload').value = null;

    // Hide the upload status and reset the message
    const statusElement = document.getElementById('upload-status');
    const copyButton = document.getElementById('copy-url');

    statusElement.classList.add('hidden');
    copyButton.classList.add('hidden');
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}

function showError(message) {
    const errorElement = document.getElementById('error-message');
    errorElement.textContent = message;
    errorElement.classList.remove('hidden');
}
