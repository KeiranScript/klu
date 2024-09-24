async function checkApiKey() {
  const apiKey = getCookie('api_key');
  if (!apiKey) {
    console.log('No API Key found in cookie');
    redirectToLogin();
    return;
  }

  try {
    const response = await fetch('/verify', {
      method: 'POST',
      headers: { 'Authorization': apiKey },
      body: JSON.stringify({ apiKey })
    });

    if (response.ok) {
      console.log('API Key is valid');
    } else {
      console.log('Invalid API Key');
      redirectToLogin();
    }
  } catch (error) {
    console.error('Error verifying API Key:', error);
    redirectToLogin();
  }
}

window.addEventListener('load', checkApiKey);

document.getElementById('file-upload').addEventListener('change', async function(e) {
  const file = e.target.files[0];
  if (!file) return;

  // Clear the previous upload information
  resetUploadStatus();

  // Proceed with uploading the file
  await uploadFile(file);
});

async function uploadFile(file) {
  const apiKey = getCookie('api_key');
  if (!apiKey) {
    redirectToLogin();
    return;
  }

  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await fetch('/upload', {
      method: 'POST',
      headers: { 'Authorization': apiKey },
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

  copyButton.onclick = () => copyToClipboard(fileUrl, copyButton);
}

async function copyToClipboard(fileUrl, button) {
  try {
    await navigator.clipboard.writeText(fileUrl);
    button.textContent = 'Copied!';
    button.classList.add('animate-pulse');
    setTimeout(() => {
      button.textContent = 'Copy URL';
      button.classList.remove('animate-pulse');
    }, 2000);
  } catch (error) {
    console.error('Failed to copy URL:', error);
  }
}

// Function to redirect to login page
function redirectToLogin() {
  window.location.href = '/login';
}

window.addEventListener('load', checkApiKey);
document.getElementById('file-upload').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  resetUploadStatus(); // Clear previous upload information
  await uploadFile(file); // Proceed with uploading the file
});

function resetUploadStatus() {
  const fileInput = document.getElementById('file-upload');
  const statusElement = document.getElementById('upload-status');
  const messageElement = document.getElementById('upload-message');
  const copyButton = document.getElementById('copy-url');

  fileInput.value = ''; // Reset the file input
  messageElement.textContent = ''; // Clear previous status
  statusElement.classList.add('hidden'); // Hide status
  copyButton.classList.add('hidden'); // Hide copy button
}

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  return parts.length === 2 ? parts.pop().split(';').shift() : null;
}

function showError(message) {
  const errorElement = document.getElementById('error-message');
  errorElement.textContent = message;
  errorElement.classList.remove('hidden');
}
