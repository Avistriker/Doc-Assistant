// Global variables
let currentMode = 'no_ai';

// DOM Elements
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const pdfFileInput = document.getElementById('pdf-file');
const websiteUrlInput = document.getElementById('website-url');

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    updateTime();
    setupEventListeners();
    updateStatus();
    
    // Update time every minute
    setInterval(updateTime, 60000);
});

// Update current time
function updateTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const dateString = now.toLocaleDateString();
    document.getElementById('current-time').textContent = `${dateString} ${timeString}`;
}

// Setup event listeners
function setupEventListeners() {
    // Mode toggle buttons
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const mode = this.dataset.mode;
            setMode(mode);
        });
    });
    
    // PDF file input
    pdfFileInput.addEventListener('change', handlePDFUpload);
    
    // PDF upload area click
    const pdfUploadArea = document.getElementById('pdf-upload-area');
    if (pdfUploadArea) {
        pdfUploadArea.addEventListener('click', () => pdfFileInput.click());
        
        // Drag and drop for PDF
        pdfUploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            pdfUploadArea.style.borderColor = '#4361ee';
            pdfUploadArea.style.background = 'rgba(67, 97, 238, 0.05)';
        });
        
        pdfUploadArea.addEventListener('dragleave', () => {
            pdfUploadArea.style.borderColor = '';
            pdfUploadArea.style.background = '';
        });
        
        pdfUploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            pdfUploadArea.style.borderColor = '';
            pdfUploadArea.style.background = '';
            
            if (e.dataTransfer.files.length) {
                pdfFileInput.files = e.dataTransfer.files;
                handlePDFUpload();
            }
        });
    }
    
    // Enter key for URL input
    websiteUrlInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            scrapeWebsite();
        }
    });
    
    // Enter key for chat input
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
}

// Set chat mode - User explicitly controls this
async function setMode(mode) {
    if (mode === currentMode) return; // Don't do anything if already in this mode
    
    showLoading(`Switching to ${mode === 'ai' ? 'AI' : 'Basic'} mode...`);
    
    try {
        const response = await fetch('/api/set_mode', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ mode: mode })
        });
        
        const result = await response.json();
        
        if (result.success) {
            currentMode = mode;
            
            // Update UI buttons
            document.querySelectorAll('.mode-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.mode === mode);
            });
            
            // Update mode description
            const description = document.getElementById('mode-description');
            const currentModeElement = document.getElementById('current-mode');
            
            if (mode === 'ai') {
                description.innerHTML = `<p><strong>AI Mode:</strong> Uses DeepSeek-V3.1 for intelligent analysis and conversations.</p>`;
                currentModeElement.textContent = 'AI Mode';
                
                // Test AI connection when switching to AI mode
                const aiStatus = document.getElementById('ai-status');
                aiStatus.innerHTML = '<span style="color: var(--warning);">Testing...</span>';
                
                try {
                    const aiTestResponse = await fetch('/api/test_ai');
                    const aiResult = await aiTestResponse.json();
                    
                    if (aiResult.success) {
                        aiStatus.innerHTML = '<span style="color: var(--success);">Connected ✓</span>';
                        addSystemMessage('✅ Switched to AI Mode 🤖 - DeepSeek-V3.1 connection successful!');
                    } else {
                        aiStatus.innerHTML = '<span style="color: var(--danger);">Failed ✗</span>';
                        addSystemMessage(`⚠️ Switched to AI Mode 🤖 - AI connection failed: ${aiResult.message}`);
                    }
                } catch (error) {
                    aiStatus.innerHTML = '<span style="color: var(--danger);">Error ✗</span>';
                    addSystemMessage('❌ Switched to AI Mode 🤖 - Could not test AI connection');
                }
            } else {
                description.innerHTML = `<p><strong>Basic Mode:</strong> Upload PDFs, scrape websites, and get basic summaries without AI.</p>`;
                currentModeElement.textContent = 'Basic Mode';
                addSystemMessage('📄 Switched to Basic Mode - No AI required!');
            }
            
            addSystemMessage(`Mode changed to ${mode === 'ai' ? 'AI Mode 🤖' : 'Basic Mode 📄'}. You can now ask questions about your content.`);
        } else {
            showError(`Failed to switch mode: ${result.error || 'Unknown error'}`);
        }
    } catch (error) {
        showError('Network error switching mode: ' + error.message);
    } finally {
        hideLoading();
        updateStatus();
    }
}

// Handle PDF upload
async function handlePDFUpload() {
    if (!pdfFileInput.files.length) return;
    
    const file = pdfFileInput.files[0];
    const maxSize = 16 * 1024 * 1024; // 16MB
    
    if (file.size > maxSize) {
        showResult('pdf', 'error', 'PDF file is too large. Maximum size is 16MB.');
        return;
    }
    
    const formData = new FormData();
    formData.append('pdf_file', file);
    
    showLoading('Uploading and processing PDF...');
    
    try {
        const response = await fetch('/api/upload_pdf', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            showResult('pdf', 'success', result);
            addSystemMessage(`📄 PDF uploaded successfully! ${result.details}`);
            
            // Ask if user wants to analyze the PDF
            setTimeout(() => {
                const analyzeMessage = `PDF loaded (${result.num_pages} pages, ${result.details.split(' ')[2]} characters). `;
                const modeMessage = currentMode === 'ai' 
                    ? "You're in AI mode. Ask me questions about the PDF content!"
                    : "You're in Basic mode. Ask about page count, character count, or switch to AI mode for detailed analysis.";
                
                addSystemMessage(analyzeMessage + modeMessage);
            }, 1000);
        } else {
            showResult('pdf', 'error', result.error || 'Failed to upload PDF');
        }
    } catch (error) {
        showResult('pdf', 'error', 'Network error: ' + error.message);
    } finally {
        hideLoading();
        updateStatus();
    }
}

// Show result for PDF or Web
function showResult(type, status, data) {
    const resultDiv = document.getElementById(`${type}-result`);
    
    if (status === 'success') {
        resultDiv.className = '';
        resultDiv.innerHTML = `
            <div class="result-header">
                <i class="fas fa-check-circle"></i>
                <strong>${data.message}</strong>
            </div>
            <div class="result-details">${data.details}</div>
            <div class="result-summary">
                <strong>Summary:</strong> ${data.summary}
            </div>
            <div class="result-preview">
                <strong>Preview:</strong> ${data.preview}
            </div>
            <div class="result-actions">
                <button class="btn btn-small clear-btn" onclick="clearContent('${type}')">
                    <i class="fas fa-trash"></i> Clear ${type === 'pdf' ? 'PDF' : 'Web Content'}
                </button>
                ${currentMode === 'ai' ? 
                    `<button class="btn btn-small" onclick="askAboutContent('${type}')" style="margin-left: 5px;">
                        <i class="fas fa-question-circle"></i> Ask AI about this
                    </button>` : 
                    `<button class="btn btn-small" onclick="suggestAIMode()" style="margin-left: 5px;">
                        <i class="fas fa-brain"></i> Switch to AI for analysis
                    </button>`
                }
            </div>
        `;
    } else {
        resultDiv.className = 'error';
        resultDiv.innerHTML = `
            <div class="result-header error">
                <i class="fas fa-exclamation-circle"></i>
                <strong>Error</strong>
            </div>
            <div class="result-details">${data}</div>
        `;
    }
}

// Ask AI about content
function askAboutContent(type) {
    if (currentMode !== 'ai') {
        addSystemMessage("Please switch to AI mode first to ask detailed questions about the content.");
        return;
    }
    
    let questions = [];
    if (type === 'pdf') {
        questions = [
            "What is this PDF about?",
            "Summarize the main points of this PDF",
            "What are the key findings in this document?",
            "Extract the most important information from this PDF"
        ];
    } else {
        questions = [
            "What is this website about?",
            "Summarize the main content of this webpage",
            "What are the key points on this website?",
            "What information does this website provide?"
        ];
    }
    
    // Add suggested questions to chat
    const questionText = `Here are some questions you can ask about the ${type === 'pdf' ? 'PDF' : 'website'}:`;
    addSystemMessage(questionText);
    
    setTimeout(() => {
        questions.forEach((question, index) => {
            setTimeout(() => {
                addSystemMessage(`${index + 1}. "${question}"`);
            }, index * 300);
        });
    }, 500);
}

// Suggest AI mode
function suggestAIMode() {
    addSystemMessage("💡 For detailed analysis, summarization, and intelligent questions about your content, switch to AI Mode using the buttons above!");
}

// Scrape website
async function scrapeWebsite() {
    const url = websiteUrlInput.value.trim();
    if (!url) {
        showError('Please enter a website URL');
        return;
    }
    
    showLoading('Scraping website content...');
    
    try {
        const response = await fetch('/api/scrape_website', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url: url })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showResult('web', 'success', result);
            addSystemMessage(`🌐 Website scraped successfully! ${result.details}`);
            
            // Ask if user wants to analyze the website
            setTimeout(() => {
                const analyzeMessage = `Website content loaded (${result.lines} lines, ${result.details.split(' ')[2]} characters). `;
                const modeMessage = currentMode === 'ai' 
                    ? "You're in AI mode. Ask me questions about the website content!"
                    : "You're in Basic mode. Ask about line count, character count, or switch to AI mode for detailed analysis.";
                
                addSystemMessage(analyzeMessage + modeMessage);
            }, 1000);
            
            websiteUrlInput.value = '';
        } else {
            showResult('web', 'error', result.error || 'Failed to scrape website');
        }
    } catch (error) {
        showResult('web', 'error', 'Network error: ' + error.message);
    } finally {
        hideLoading();
        updateStatus();
    }
}

// Send chat message
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;
    
    // Add user message to chat
    addUserMessage(message);
    userInput.value = '';
    
    // Show typing indicator
    const typingId = showTypingIndicator();
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                question: message,
                mode: currentMode
            })
        });
        
        const result = await response.json();
        
        removeTypingIndicator(typingId);
        
        if (result.success) {
            addBotMessage(result.response, result.mode);
            
            // If in basic mode and asking complex questions, suggest AI mode
            if (currentMode === 'no_ai' && result.response.includes('Switch to AI mode')) {
                setTimeout(() => {
                    addSystemMessage("💡 For better answers to complex questions, try switching to AI Mode!");
                }, 1000);
            }
        } else {
            addBotMessage(`Error: ${result.error || 'Unknown error occurred'}`);
        }
        
        updateStatus();
    } catch (error) {
        removeTypingIndicator(typingId);
        addBotMessage(`Network error: ${error.message}`);
    }
}

// Add user message to chat
function addUserMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user-message';
    messageDiv.innerHTML = `
        <div class="message-header">
            <i class="fas fa-user"></i>
            <span class="sender">You</span>
        </div>
        <div class="message-content">
            ${escapeHtml(message)}
        </div>
    `;
    
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Add bot message to chat
function addBotMessage(message, mode = 'no_ai') {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';
    
    // Format message with basic markdown
    const formattedMessage = formatMessage(message);
    
    let modeIndicator = '';
    if (mode === 'ai') {
        modeIndicator = '<span style="font-size: 0.8em; color: #4361ee; margin-left: 10px;">🤖 AI Response (DeepSeek-V3.1)</span>';
    } else {
        modeIndicator = '<span style="font-size: 0.8em; color: #6c757d; margin-left: 10px;">📄 Basic Response</span>';
    }
    
    messageDiv.innerHTML = `
        <div class="message-header">
            <i class="fas fa-robot"></i>
            <span class="sender">ChatGenius</span>
            ${modeIndicator}
        </div>
        <div class="message-content">
            ${formattedMessage}
        </div>
    `;
    
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Add system message
function addSystemMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message system-message';
    messageDiv.innerHTML = `
        <div class="message-content" style="background: #e7f4ff; color: #036; font-style: italic; text-align: center;">
            <i class="fas fa-info-circle"></i> ${escapeHtml(message)}
        </div>
    `;
    
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Format message with basic markdown
function formatMessage(text) {
    if (!text) return '';
    
    // Convert line breaks
    let formatted = text.replace(/\n/g, '<br>');
    
    // Convert **bold**
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Convert *italic*
    formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    // Convert bullet points (simple)
    formatted = formatted.replace(/^\s*[-•*]\s+(.+)$/gm, '<li>$1</li>');
    
    // Wrap consecutive list items in ul
    formatted = formatted.replace(/(<li>.*<\/li>)(\s*<li>.*<\/li>)+/gs, '<ul>$&</ul>');
    
    // Convert code blocks
    formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    return formatted;
}

// Show typing indicator
function showTypingIndicator() {
    const typingId = 'typing-' + Date.now();
    const typingDiv = document.createElement('div');
    typingDiv.id = typingId;
    typingDiv.className = 'message bot-message';
    
    typingDiv.innerHTML = `
        <div class="message-header">
            <i class="fas fa-robot"></i>
            <span class="sender">ChatGenius</span>
            <span style="font-size: 0.8em; color: #6c757d; margin-left: 10px;">${currentMode === 'ai' ? 'AI is thinking...' : 'Processing...'}</span>
        </div>
        <div class="message-content">
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    
    // Add CSS for typing indicator
    const style = document.createElement('style');
    style.textContent = `
        .typing-indicator {
            display: flex;
            align-items: center;
            gap: 4px;
            height: 20px;
        }
        .typing-indicator span {
            width: 8px;
            height: 8px;
            background: #6c757d;
            border-radius: 50%;
            animation: typing 1.4s infinite ease-in-out;
        }
        .typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
        .typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
        @keyframes typing {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }
    `;
    document.head.appendChild(style);
    
    chatMessages.appendChild(typingDiv);
    scrollToBottom();
    
    return typingId;
}

// Remove typing indicator
function removeTypingIndicator(id) {
    const element = document.getElementById(id);
    if (element) {
        element.remove();
    }
}

// Clear content
async function clearContent(type) {
    try {
        const response = await fetch('/api/clear_content', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ type: type })
        });
        
        const result = await response.json();
        
        if (result.success) {
            if (type === 'pdf' || type === 'all') {
                document.getElementById('pdf-result').innerHTML = '';
                pdfFileInput.value = '';
                document.getElementById('pdf-status').textContent = 'Not loaded';
            }
            if (type === 'web' || type === 'all') {
                document.getElementById('web-result').innerHTML = '';
                websiteUrlInput.value = '';
                document.getElementById('web-status').textContent = 'Not loaded';
            }
            
            addSystemMessage(result.message);
            updateStatus();
        }
    } catch (error) {
        showError('Failed to clear content: ' + error.message);
    }
}

// Clear chat
async function clearChat() {
    try {
        const response = await fetch('/api/clear_history', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            chatMessages.innerHTML = `
                <div class="message bot-message">
                    <div class="message-header">
                        <i class="fas fa-robot"></i>
                        <span class="sender">ChatGenius</span>
                    </div>
                    <div class="message-content">
                        <p>Chat cleared! How can I help you today?</p>
                        <p>Current mode: <strong>${currentMode === 'ai' ? 'AI Mode 🤖' : 'Basic Mode 📄'}</strong></p>
                    </div>
                </div>
            `;
            addSystemMessage('Chat history cleared');
        }
    } catch (error) {
        // Still clear locally even if API fails
        chatMessages.innerHTML = `
            <div class="message bot-message">
                <div class="message-header">
                    <i class="fas fa-robot"></i>
                    <span class="sender">ChatGenius</span>
                </div>
                <div class="message-content">
                    <p>Chat cleared! How can I help you today?</p>
                    <p>Current mode: <strong>${currentMode === 'ai' ? 'AI Mode 🤖' : 'Basic Mode 📄'}</strong></p>
                </div>
            </div>
        `;
        addSystemMessage('Chat cleared');
    }
}

// Update status panel
async function updateStatus() {
    try {
        const response = await fetch('/api/get_status');
        const status = await response.json();
        
        // Update current mode variable
        currentMode = status.mode;
        
        // Update PDF status
        const pdfStatus = document.getElementById('pdf-status');
        if (status.pdf_loaded) {
            pdfStatus.innerHTML = `<span style="color: var(--success);">Loaded (${formatNumber(status.pdf_length)} chars)</span>`;
        } else {
            pdfStatus.textContent = 'Not loaded';
        }
        
        // Update web status
        const webStatus = document.getElementById('web-status');
        if (status.web_loaded) {
            webStatus.innerHTML = `<span style="color: var(--success);">Loaded (${formatNumber(status.web_length)} chars)</span>`;
        } else {
            webStatus.textContent = 'Not loaded';
        }
        
        // Update mode display
        const currentModeElement = document.getElementById('current-mode');
        if (status.mode === 'ai') {
            currentModeElement.textContent = 'AI Mode';
            
            // Update UI buttons
            document.querySelectorAll('.mode-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.mode === 'ai');
            });
        } else {
            currentModeElement.textContent = 'Basic Mode';
            
            // Update UI buttons
            document.querySelectorAll('.mode-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.mode === 'no_ai');
            });
        }
    } catch (error) {
        console.error('Failed to update status:', error);
    }
}

// Test AI connection
async function testAIConnection() {
    const aiStatus = document.getElementById('ai-status');
    aiStatus.innerHTML = '<span style="color: var(--warning);">Testing...</span>';
    
    try {
        const response = await fetch('/api/test_ai');
        const result = await response.json();
        
        if (result.success) {
            aiStatus.innerHTML = '<span style="color: var(--success);">Connected ✓</span>';
            addSystemMessage('✅ DeepSeek-V3.1 connection test successful!');
        } else {
            aiStatus.innerHTML = '<span style="color: var(--danger);">Failed ✗</span>';
            addSystemMessage(`❌ AI connection failed: ${result.message}`);
        }
    } catch (error) {
        aiStatus.innerHTML = '<span style="color: var(--danger);">Error ✗</span>';
        addSystemMessage('❌ Could not test AI connection: Network error');
    }
}

// Show loading overlay
function showLoading(text = 'Processing...') {
    const overlay = document.getElementById('loading-overlay');
    const loadingText = document.getElementById('loading-text');
    
    loadingText.textContent = text;
    overlay.style.display = 'flex';
}

// Hide loading overlay
function hideLoading() {
    document.getElementById('loading-overlay').style.display = 'none';
}

// Show error message
function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `
        <div style="background: #f94144; color: white; padding: 10px 15px; border-radius: 8px; margin: 10px 0;">
            <i class="fas fa-exclamation-circle"></i> ${escapeHtml(message)}
        </div>
    `;
    
    // Insert at the beginning of chat
    chatMessages.insertBefore(errorDiv, chatMessages.firstChild);
    
    // Auto remove after 5 seconds
    setTimeout(() => errorDiv.remove(), 5000);
}

// Utility functions
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Initialize with current mode from server
updateStatus();