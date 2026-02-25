// Configuration
const API_URL = window.location.hostname === 'localhost' 
    ? 'http://localhost:8000/admin/api'
    : 'https://enategawebsitechatbot-production.up.railway.app/admin/api';

let credentials = null;
let currentEditFile = null;

// Auth helpers
function getAuthHeader() {
    if (!credentials) return {};
    const encoded = btoa(`${credentials.username}:${credentials.password}`);
    return { 'Authorization': `Basic ${encoded}` };
}

// Login
document.getElementById('login-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    credentials = { username, password };
    
    try {
        const response = await fetch(`${API_URL}/files`, {
            headers: getAuthHeader()
        });
        
        if (response.ok) {
            document.getElementById('login-screen').classList.add('hidden');
            document.getElementById('admin-screen').classList.remove('hidden');
            loadFiles();
            loadStatus();
        } else {
            document.getElementById('login-error').textContent = 'Invalid credentials';
            credentials = null;
        }
    } catch (error) {
        document.getElementById('login-error').textContent = 'Connection error';
        credentials = null;
    }
});

function logout() {
    credentials = null;
    document.getElementById('admin-screen').classList.add('hidden');
    document.getElementById('login-screen').classList.remove('hidden');
    document.getElementById('username').value = '';
    document.getElementById('password').value = '';
    document.getElementById('login-error').textContent = '';
}

// Load files
async function loadFiles() {
    try {
        const response = await fetch(`${API_URL}/files`, {
            headers: getAuthHeader()
        });
        
        if (!response.ok) throw new Error('Failed to load files');
        
        const files = await response.json();
        displayFiles(files);
    } catch (error) {
        showNotification('Failed to load files', 'error');
    }
}

function displayFiles(files) {
    const container = document.getElementById('files-list');
    
    if (files.length === 0) {
        container.innerHTML = '<p style="padding: 40px; text-align: center; color: #999;">No files found</p>';
        return;
    }
    
    container.innerHTML = files.map(file => `
        <div class="file-item">
            <div class="file-info">
                <h3>${file.name}</h3>
                <p>${formatSize(file.size)} • Modified: ${formatDate(file.modified)}</p>
            </div>
            <div class="file-actions">
                <button onclick="editFile('${file.name}')" class="btn-secondary">Edit</button>
                <button onclick="deleteFile('${file.name}')" class="btn-danger">Delete</button>
            </div>
        </div>
    `).join('');
}

// Load status
async function loadStatus() {
    try {
        const response = await fetch(`${API_URL}/status`, {
            headers: getAuthHeader()
        });
        
        if (!response.ok) throw new Error('Failed to load status');
        
        const status = await response.json();
        document.getElementById('status-info').textContent = 
            `${status.files} files • ${status.chunks} chunks in ${status.collection}`;
    } catch (error) {
        console.error('Failed to load status:', error);
    }
}

// Create file
function showCreateModal() {
    currentEditFile = null;
    document.getElementById('modal-title').textContent = 'Create New File';
    document.getElementById('file-name').value = '';
    document.getElementById('file-name').disabled = false;
    document.getElementById('file-content').value = '';
    document.getElementById('file-modal').classList.remove('hidden');
}

// Edit file
async function editFile(filename) {
    try {
        const response = await fetch(`${API_URL}/files/${filename}`, {
            headers: getAuthHeader()
        });
        
        if (!response.ok) throw new Error('Failed to load file');
        
        const file = await response.json();
        currentEditFile = filename;
        document.getElementById('modal-title').textContent = `Edit ${filename}`;
        document.getElementById('file-name').value = filename;
        document.getElementById('file-name').disabled = true;
        document.getElementById('file-content').value = file.content;
        document.getElementById('file-modal').classList.remove('hidden');
    } catch (error) {
        showNotification('Failed to load file', 'error');
    }
}

// Save file
async function saveFile() {
    const filename = document.getElementById('file-name').value.trim();
    const content = document.getElementById('file-content').value;
    
    if (!filename) {
        showNotification('Please enter a filename', 'error');
        return;
    }
    
    if (!filename.endsWith('.txt')) {
        showNotification('Filename must end with .txt', 'error');
        return;
    }
    
    try {
        let response;
        
        if (currentEditFile) {
            // Update existing file
            response = await fetch(`${API_URL}/files/${currentEditFile}`, {
                method: 'PUT',
                headers: {
                    ...getAuthHeader(),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ content })
            });
        } else {
            // Create new file
            response = await fetch(`${API_URL}/files`, {
                method: 'POST',
                headers: {
                    ...getAuthHeader(),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ name: filename, content })
            });
        }
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to save file');
        }
        
        showNotification('File saved successfully', 'success');
        closeModal();
        loadFiles();
        loadStatus();
    } catch (error) {
        showNotification(error.message, 'error');
    }
}

// Delete file
async function deleteFile(filename) {
    if (!confirm(`Are you sure you want to delete ${filename}?`)) return;
    
    try {
        const response = await fetch(`${API_URL}/files/${filename}`, {
            method: 'DELETE',
            headers: getAuthHeader()
        });
        
        if (!response.ok) throw new Error('Failed to delete file');
        
        showNotification('File deleted successfully', 'success');
        loadFiles();
        loadStatus();
    } catch (error) {
        showNotification('Failed to delete file', 'error');
    }
}

// Re-ingest
async function reingest() {
    if (!confirm('This will re-ingest all files to Qdrant. This may take a few minutes. Continue?')) return;
    
    const progressModal = document.getElementById('progress-modal');
    const progressLog = document.getElementById('progress-log');
    const progressStatus = document.getElementById('progress-status');
    
    progressModal.classList.remove('hidden');
    progressLog.innerHTML = '';
    progressStatus.textContent = 'Starting...';
    progressStatus.className = 'progress-status';
    
    try {
        const response = await fetch(`${API_URL}/reingest`, {
            method: 'POST',
            headers: getAuthHeader()
        });
        
        if (!response.ok) {
            throw new Error('Failed to start re-ingestion');
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.substring(6));
                        
                        // Add to log
                        const logEntry = document.createElement('div');
                        logEntry.className = `log-entry ${data.status}`;
                        logEntry.textContent = data.message;
                        progressLog.appendChild(logEntry);
                        progressLog.scrollTop = progressLog.scrollHeight;
                        
                        // Update status
                        if (data.status === 'success') {
                            progressStatus.textContent = '✓ Completed';
                            progressStatus.className = 'progress-status success';
                            setTimeout(() => {
                                progressModal.classList.add('hidden');
                                loadStatus();
                                showNotification('Re-ingestion completed successfully!', 'success');
                            }, 2000);
                        } else if (data.status === 'error') {
                            progressStatus.textContent = '✗ Failed';
                            progressStatus.className = 'progress-status error';
                        } else if (data.status === 'progress') {
                            progressStatus.textContent = '⟳ Processing...';
                            progressStatus.className = 'progress-status progress';
                        }
                    } catch (e) {
                        console.error('Failed to parse SSE data:', e);
                    }
                }
            }
        }
    } catch (error) {
        progressStatus.textContent = '✗ Error';
        progressStatus.className = 'progress-status error';
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry error';
        logEntry.textContent = error.message;
        progressLog.appendChild(logEntry);
    }
}

function closeProgressModal() {
    document.getElementById('progress-modal').classList.add('hidden');
}

// Refresh
function refreshFiles() {
    loadFiles();
    loadStatus();
    showNotification('Refreshed', 'success');
}

// Modal
function closeModal() {
    document.getElementById('file-modal').classList.add('hidden');
    currentEditFile = null;
}

function closeProgressModal() {
    document.getElementById('progress-modal').classList.add('hidden');
}

// Notification
function showNotification(message, type = 'info') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification ${type}`;
    notification.classList.remove('hidden');
    
    setTimeout(() => {
        notification.classList.add('hidden');
    }, 3000);
}

// Helpers
function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function formatDate(timestamp) {
    const date = new Date(parseFloat(timestamp) * 1000);
    return date.toLocaleString();
}
