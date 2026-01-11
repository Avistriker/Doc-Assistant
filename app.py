import os
import PyPDF2 as pdf
import requests
from flask import Flask, render_template, request, jsonify
from urllib.parse import urlparse
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== CONFIGURATION ==========

# DeepSeek API configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.sambanova.ai/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "DeepSeek-V3.1")

# Flask configuration
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

# Application settings
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads/")
MAX_CONTENT_LENGTH_MB = int(os.getenv("MAX_CONTENT_LENGTH_MB", "16"))
CHAT_HISTORY_LIMIT = int(os.getenv("CHAT_HISTORY_LIMIT", "100"))
ENABLE_AI_MODE = os.getenv("ENABLE_AI_MODE", "True").lower() == "true"
DEFAULT_CHAT_MODE = os.getenv("DEFAULT_CHAT_MODE", "no_ai")

# Rate limiting
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

# Initialize Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH_MB * 1024 * 1024
app.config['SECRET_KEY'] = SECRET_KEY

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Global variables to store content
pdf_content = ""
web_content = ""
chat_mode = DEFAULT_CHAT_MODE  # Use environment variable default
chat_history = []

# ========== HELPER FUNCTIONS ==========

def extract_text_from_pdf(file_path):
    """Extract text from PDF file"""
    text = ""
    try:
        with open(file_path, "rb") as file:
            reader = pdf.PdfReader(file)
            num_pages = len(reader.pages)
            
            for page_num in range(num_pages):
                page = reader.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text += f"--- Page {page_num + 1} ---\n{page_text}\n\n"
            
        return text, num_pages
    except Exception as e:
        logger.error(f"Error extracting PDF {file_path}: {str(e)}")
        return f"Error extracting PDF: {str(e)}", 0

def summarize_pdf_text(text, max_sentences=5):
    """Create a simple summary of PDF text"""
    if not text:
        return "No text extracted from PDF."
    
    # Simple summary: take first few sentences and last few sentences
    sentences = text.replace('\n', ' ').split('. ')
    
    if len(sentences) <= max_sentences * 2:
        return text[:500] + "..." if len(text) > 500 else text
    
    summary_sentences = sentences[:max_sentences] + sentences[-max_sentences:]
    summary = '. '.join(summary_sentences) + '.'
    
    return summary[:1000] + "..." if len(summary) > 1000 else summary

def scrape_website_simple(url):
    """Simple web scraper without AI"""
    try:
        # Validate URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text from paragraphs and headings
        text_elements = []
        
        # Get headings
        for heading in soup.find_all(['h1', 'h2', 'h3']):
            text_elements.append(heading.get_text(strip=True))
        
        # Get paragraphs
        for paragraph in soup.find_all('p'):
            para_text = paragraph.get_text(strip=True)
            if para_text and len(para_text) > 20:
                text_elements.append(para_text)
        
        # Get list items
        for li in soup.find_all('li'):
            li_text = li.get_text(strip=True)
            if li_text and len(li_text) > 10:
                text_elements.append(f"• {li_text}")
        
        content = '\n'.join(text_elements[:50])  # Limit to 50 elements
        
        if not content:
            # Fallback: get all text
            content = soup.get_text()
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            content = '\n'.join(lines[:100])
        
        return content[:5000]  # Limit to 5000 characters
        
    except Exception as e:
        logger.error(f"Error scraping website {url}: {str(e)}")
        return f"Error scraping website: {str(e)}"

def summarize_web_content(content):
    """Summarize web content"""
    if not content:
        return "No content scraped."
    
    # Simple summary: take first 5 lines and last 5 lines
    lines = content.split('\n')
    
    if len(lines) <= 10:
        return content[:500] + "..." if len(content) > 500 else content
    
    summary_lines = lines[:5] + ["..."] + lines[-5:]
    return '\n'.join(summary_lines)

def basic_chat_response(question, pdf_text, web_text):
    """Basic rule-based chat response"""
    question_lower = question.lower()
    
    # Check for greetings
    greetings = ['hello', 'hi', 'hey', 'greetings']
    if any(greet in question_lower for greet in greetings):
        return "Hello! I'm your document assistant. I can help you with PDF and web content analysis."
    
    # Check for help
    if 'help' in question_lower:
        return """I can help you with:
1. Upload and analyze PDF documents
2. Scrape and analyze website content
3. Answer basic questions about loaded content
4. Switch to AI mode for more advanced questions (if enabled)"""
    
    # Check for content-related questions
    responses = []
    
    if pdf_text:
        if any(word in question_lower for word in ['pdf', 'document', 'file']):
            # Provide basic information about PDF
            lines = pdf_text.split('\n')
            page_count = len([line for line in lines if line.startswith('--- Page')])
            char_count = len(pdf_text)
            
            # Extract first few lines for preview
            preview_lines = []
            for line in lines:
                if not line.startswith('--- Page') and len(line.strip()) > 10:
                    preview_lines.append(line.strip())
                    if len(preview_lines) >= 3:
                        break
            
            preview = "\n".join(preview_lines[:3])
            
            responses.append(f"📄 **PDF Information:**")
            responses.append(f"- Pages: {page_count}")
            responses.append(f"- Characters: {char_count:,}")
            responses.append(f"- Preview: {preview[:200]}..." if len(preview) > 200 else f"- Preview: {preview}")
    
    if web_text:
        if any(word in question_lower for word in ['web', 'website', 'site', 'page', 'url']):
            # Provide basic information about web content
            lines = web_text.split('\n')
            line_count = len(lines)
            char_count = len(web_text)
            
            # Extract first few lines for preview
            preview = "\n".join([line.strip() for line in lines[:3] if line.strip()])
            
            responses.append(f"🌐 **Website Information:**")
            responses.append(f"- Lines extracted: {line_count}")
            responses.append(f"- Characters: {char_count:,}")
            responses.append(f"- Preview: {preview[:200]}..." if len(preview) > 200 else f"- Preview: {preview}")
    
    if responses:
        return '\n'.join(responses)
    
    # Check for summary requests
    if 'summary' in question_lower or 'summarize' in question_lower:
        if pdf_text:
            summary = summarize_pdf_text(pdf_text)
            return f"📄 **PDF Summary:**\n{summary}"
        elif web_text:
            summary = summarize_web_content(web_text)
            return f"🌐 **Website Summary:**\n{summary}"
        else:
            return "No content loaded. Please upload a PDF or scrape a website first."
    
    # Default response
    return "I can analyze your PDF and web content. Please upload a PDF or enter a website URL, then ask specific questions about the content."

# ========== AI FUNCTIONS ==========

def call_deepseek_api(messages, temperature=0.1, top_p=0.1, max_tokens=2000):
    """Call DeepSeek-V3.1 API for AI responses"""
    if not DEEPSEEK_API_KEY:
        logger.warning("AI mode called but no API key configured")
        return "AI mode is not configured. Please check API settings in environment variables."
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens
    }
    
    try:
        logger.info(f"Calling DeepSeek API with {len(messages)} messages")
        response = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            logger.error(f"API Error: {response.status_code} - {response.text[:200]}")
            return f"API Error: {response.status_code} - {response.text[:200]}"
            
    except requests.exceptions.Timeout:
        logger.error("API request timeout")
        return "AI request timed out. Please try again."
    except Exception as e:
        logger.error(f"Connection error: {str(e)}")
        return f"Connection error: {str(e)}"

def ai_chat_response(question, pdf_text, web_text):
    """AI-powered chat response using DeepSeek-V3.1"""
    if not ENABLE_AI_MODE:
        return "AI mode is disabled. Please enable it in the configuration."
    
    # Build context from loaded content
    context_parts = []
    
    if pdf_text:
        # Include significant portion of PDF text for AI analysis
        pdf_preview = pdf_text[:3000]  # Include more context for AI
        context_parts.append(f"PDF Content (partial):\n{pdf_preview}")
    
    if web_text:
        # Include significant portion of web text for AI analysis
        web_preview = web_text[:2000]  # Include more context for AI
        context_parts.append(f"Web Content (partial):\n{web_preview}")
    
    context = "\n\n".join(context_parts)
    
    system_prompt = """You are ChatGenius, a helpful AI assistant powered by DeepSeek-V3.1. 
Answer questions based on the provided context when available. 
If the context doesn't contain the answer, provide a helpful general response.
Be concise but informative, and format your responses clearly with proper paragraphs.
When analyzing PDF or web content, provide detailed insights, summaries, and answer specific questions about the content."""
    
    user_message = f"Question: {question}\n\n"
    
    # Add content status information
    content_status = []
    if pdf_text:
        pdf_lines = pdf_text.split('\n')
        page_count = len([line for line in pdf_lines if line.startswith('--- Page')])
        content_status.append(f"PDF: {page_count} pages, {len(pdf_text):,} characters")
    if web_text:
        web_lines = web_text.split('\n')
        content_status.append(f"Web: {len(web_lines)} lines, {len(web_text):,} characters")
    
    if content_status:
        user_message += f"Available content: {', '.join(content_status)}\n\n"
    
    if context:
        user_message += f"Context:\n{context}\n\nPlease answer based on this context:"
    else:
        user_message += "No content loaded. Please answer this general question:"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    return call_deepseek_api(messages)

# ========== ROUTES ==========

@app.route('/')
def index():
    """Render main chat interface"""
    return render_template('chat.html', 
                         ai_enabled=ENABLE_AI_MODE,
                         default_mode=DEFAULT_CHAT_MODE)

@app.route('/api/upload_pdf', methods=['POST'])
def upload_pdf():
    """Handle PDF upload for both modes"""
    global pdf_content
    
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['pdf_file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Please upload a PDF file'}), 400
    
    # Save file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"pdf_{timestamp}_{file.filename}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    try:
        file.save(file_path)
        
        # Extract text from PDF
        extracted_text, num_pages = extract_text_from_pdf(file_path)
        
        if isinstance(extracted_text, str) and extracted_text.startswith("Error"):
            return jsonify({'error': extracted_text}), 500
        
        pdf_content = extracted_text
        logger.info(f"PDF uploaded: {filename}, {num_pages} pages, {len(extracted_text):,} chars")
        
        # Create summary
        summary = summarize_pdf_text(extracted_text)
        
        return jsonify({
            'success': True,
            'message': f'✅ PDF uploaded successfully!',
            'details': f'Extracted {len(extracted_text):,} characters from {num_pages} pages.',
            'summary': summary[:500] + "..." if len(summary) > 500 else summary,
            'preview': extracted_text[:300] + "..." if len(extracted_text) > 300 else extracted_text,
            'num_pages': num_pages
        })
        
    except Exception as e:
        logger.error(f"Failed to process PDF {filename}: {str(e)}")
        return jsonify({'error': f'Failed to process PDF: {str(e)}'}), 500
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@app.route('/api/scrape_website', methods=['POST'])
def scrape_website():
    """Handle website scraping for both modes"""
    global web_content
    
    data = request.json
    url = data.get("url", "").strip()
    
    if not url:
        return jsonify({'error': 'Please provide a website URL'}), 400
    
    # Scrape website
    scraped_content = scrape_website_simple(url)
    
    if scraped_content.startswith("Error"):
        return jsonify({'error': scraped_content}), 400
    
    web_content = scraped_content
    logger.info(f"Website scraped: {url}, {len(scraped_content):,} chars")
    
    # Create summary
    summary = summarize_web_content(scraped_content)
    
    return jsonify({
        'success': True,
        'message': '✅ Website scraped successfully!',
        'details': f'Extracted {len(scraped_content):,} characters.',
        'summary': summary[:500] + "..." if len(summary) > 500 else summary,
        'preview': scraped_content[:300] + "..." if len(scraped_content) > 300 else scraped_content,
        'lines': len(scraped_content.split('\n'))
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages for both modes"""
    global chat_mode, pdf_content, web_content
    
    data = request.json
    question = data.get("question", "").strip()
    mode = data.get("mode", chat_mode)
    
    if not question:
        return jsonify({'error': 'Please enter a question'}), 400
    
    # Limit chat history size
    if len(chat_history) >= CHAT_HISTORY_LIMIT:
        chat_history.pop(0)
    
    # Store in history
    chat_history.append({
        'timestamp': datetime.now().isoformat(),
        'question': question,
        'mode': mode
    })
    
    # Get response based on mode
    if mode == "ai" and ENABLE_AI_MODE:
        response = ai_chat_response(question, pdf_content, web_content)
    else:
        if mode == "ai" and not ENABLE_AI_MODE:
            response = "AI mode is disabled. Using basic mode instead.\n\n" + \
                      basic_chat_response(question, pdf_content, web_content)
        else:
            response = basic_chat_response(question, pdf_content, web_content)
    
    # Update history with response
    if chat_history:
        chat_history[-1]['response'] = response[:500] + "..." if len(response) > 500 else response
    
    logger.info(f"Chat: mode={mode}, question={question[:50]}...")
    
    return jsonify({
        'success': True,
        'response': response,
        'mode': mode,
        'has_pdf': len(pdf_content) > 0,
        'has_web': len(web_content) > 0
    })

@app.route('/api/set_mode', methods=['POST'])
def set_mode():
    """Set chat mode - User controls this explicitly"""
    global chat_mode
    
    data = request.json
    mode = data.get("mode", DEFAULT_CHAT_MODE)
    
    if mode not in ["no_ai", "ai"]:
        return jsonify({'error': 'Invalid mode'}), 400
    
    if mode == "ai" and not ENABLE_AI_MODE:
        return jsonify({
            'error': 'AI mode is disabled in configuration',
            'mode': 'no_ai'
        }), 400
    
    chat_mode = mode
    logger.info(f"Chat mode changed to: {mode}")
    
    return jsonify({
        'success': True,
        'message': f'Mode switched to {"AI" if mode == "ai" else "Basic"}',
        'mode': mode
    })

@app.route('/api/clear_content', methods=['POST'])
def clear_content():
    """Clear loaded content"""
    global pdf_content, web_content
    
    data = request.json
    content_type = data.get("type", "all")
    
    message = ""
    if content_type == "pdf" or content_type == "all":
        pdf_content = ""
        message += "PDF content cleared. "
    if content_type == "web" or content_type == "all":
        web_content = ""
        message += "Web content cleared. "
    
    logger.info(f"Content cleared: {content_type}")
    
    return jsonify({
        'success': True,
        'message': message.strip() or "No content to clear"
    })

@app.route('/api/get_status', methods=['GET'])
def get_status():
    """Get current status"""
    return jsonify({
        'mode': chat_mode,
        'pdf_loaded': len(pdf_content) > 0,
        'pdf_length': len(pdf_content),
        'web_loaded': len(web_content) > 0,
        'web_length': len(web_content),
        'history_count': len(chat_history),
        'ai_enabled': ENABLE_AI_MODE,
        'max_history': CHAT_HISTORY_LIMIT
    })

@app.route('/api/clear_history', methods=['POST'])
def clear_history():
    """Clear chat history"""
    global chat_history
    chat_history = []
    logger.info("Chat history cleared")
    return jsonify({'success': True, 'message': 'Chat history cleared'})

@app.route('/api/test_ai', methods=['GET'])
def test_ai():
    """Test AI connection to DeepSeek-V3.1"""
    if not ENABLE_AI_MODE:
        return jsonify({
            'success': False,
            'message': 'AI mode is disabled in configuration'
        })
    
    if not DEEPSEEK_API_KEY:
        return jsonify({
            'success': False,
            'message': 'AI API key not configured'
        })
    
    try:
        test_response = call_deepseek_api([
            {"role": "system", "content": "You are a helpful assistant. Respond with exactly: 'AI connection successful to DeepSeek-V3.1'"},
            {"role": "user", "content": "Test connection"}
        ], max_tokens=50)
        
        if "ai connection successful" in test_response.lower():
            return jsonify({
                'success': True,
                'message': '✅ DeepSeek-V3.1 Connection Successful',
                'response': test_response
            })
        else:
            return jsonify({
                'success': False,
                'message': '⚠️ AI responded but not as expected',
                'response': test_response[:100]
            })
    except Exception as e:
        logger.error(f"AI test failed: {str(e)}")
        return jsonify({
            'success': False,
            'message': '❌ DeepSeek-V3.1 Connection Failed',
            'error': str(e)
        })

# ========== ERROR HANDLERS ==========

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': f'File too large. Maximum size is {MAX_CONTENT_LENGTH_MB}MB'}), 413

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(f"Server error: {str(e)}")
    return jsonify({'error': 'Internal server error'}), 500

# ========== MAIN ==========

if __name__ == "__main__":
    # Create directories
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('uploads', exist_ok=True)
    
    # Check for required packages
    print("=" * 60)
    print("🤖 ChatGenius - Document Assistant")
    print("=" * 60)
    print(f"Configuration loaded from: {'.env' if os.path.exists('.env') else 'default'}")
    print(f"AI Mode Enabled: {ENABLE_AI_MODE}")
    print(f"Default Mode: {DEFAULT_CHAT_MODE}")
    print(f"Upload Folder: {UPLOAD_FOLDER}")
    print(f"Max File Size: {MAX_CONTENT_LENGTH_MB}MB")
    print("=" * 60)
    
    # Check dependencies
    required_packages = ['requests', 'PyPDF2', 'flask', 'bs4', 'python-dotenv']
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'PyPDF2':
                import PyPDF2
            elif package == 'bs4':
                import bs4
            elif package == 'python-dotenv':
                import dotenv
            else:
                __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing packages:", ", ".join(missing_packages))
        print("Install with: pip install", " ".join(missing_packages))
    else:
        print("✅ All required packages installed")
    
    # Check AI configuration
    if ENABLE_AI_MODE:
        if DEEPSEEK_API_KEY:
            print("✅ AI Mode: Enabled with API key")
        else:
            print("⚠️ AI Mode: Enabled but no API key configured")
    else:
        print("ℹ️ AI Mode: Disabled")
    
    print(f"\n🌐 Starting server on http://{FLASK_HOST}:{FLASK_PORT}")
    print("=" * 60)
    
    app.run(debug=FLASK_DEBUG, port=FLASK_PORT, host=FLASK_HOST)