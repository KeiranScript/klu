const description = document.getElementById('description');
const textFilePath = '/static/quotes.txt';

async function fetchRandomLine() {
  try {
    const response = await fetch(textFilePath);
    const text = await response.text();
    const lines = text.split('\n').filter(line => line.trim() !== '');

    if (lines.length > 0) {
      const randomLine = lines[Math.floor(Math.random() * lines.length)];
      startTypewriter(randomLine);
    } else {
      console.error('No lines found in the text file.');
    }
  } catch (error) {
    console.error('Error fetching the text file:', error);
  }
}

function startTypewriter(text) {
  description.innerText = text;
}

fetchRandomLine();
