function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'substack-article';
}

function normaliseFilename(name) {
  const cleaned = name.trim();
  return cleaned.toLowerCase().endsWith('.md') ? cleaned : `${cleaned}.md`;
}

function setStatus(message) {
  if (statusTimer) {
    clearTimeout(statusTimer);
    statusTimer = null;
  }
  statusLabel.textContent = message;
  if (message !== defaultStatus) {
    statusTimer = setTimeout(() => {
      statusLabel.textContent = defaultStatus;
      statusTimer = null;
    }, 3000);
  }
}
