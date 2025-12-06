/**
 * Fast Light Chat Widget
 * 채널톡 스타일의 채팅 위젯
 */

class ChatWidget {
    constructor(options = {}) {
        this.serverUrl = options.serverUrl || 'http://localhost:8000';
        this.pluginKey = options.pluginKey || 'demo-plugin-key';
        this.memberId = options.memberId || this.generateSessionId();

        this.socket = null;
        this.chatId = null;
        this.isOpen = false;
        this.isConnected = false;

        this.init();
    }

    generateSessionId() {
        return 'guest_' + Math.random().toString(36).substr(2, 9);
    }

    init() {
        // DOM Elements
        this.widget = document.getElementById('chat-widget');
        this.toggleBtn = document.getElementById('chat-toggle');
        this.chatWindow = document.getElementById('chat-window');
        this.messagesContainer = document.getElementById('chat-messages');
        this.typingIndicator = document.getElementById('typing-indicator');
        this.input = document.getElementById('chat-input');
        this.sendBtn = document.getElementById('chat-send');
        this.attachBtn = document.getElementById('chat-attach');
        this.minimizeBtn = document.getElementById('chat-minimize');
        this.closeBtn = document.getElementById('chat-close');

        // Event Listeners
        this.toggleBtn.addEventListener('click', () => this.toggle());
        this.minimizeBtn.addEventListener('click', () => this.toggle());
        this.closeBtn.addEventListener('click', () => this.toggle());
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        this.input.addEventListener('input', () => this.handleTyping());

        // Connect to Socket.IO
        this.connect();
    }

    connect() {
        try {
            this.socket = io(this.serverUrl, {
                transports: ['websocket', 'polling'],
                auth: {
                    type: 'user',
                    plugin_key: this.pluginKey,
                    member_id: this.memberId,
                    session_id: this.memberId
                }
            });

            this.socket.on('connect', () => {
                console.log('Connected to chat server');
                this.isConnected = true;
                this.updateStatus('online');
            });

            this.socket.on('disconnect', () => {
                console.log('Disconnected from chat server');
                this.isConnected = false;
                this.updateStatus('offline');
            });

            this.socket.on('connect_error', (error) => {
                console.error('Connection error:', error);
                this.isConnected = false;
            });

            // Chat events
            this.socket.on('chat:new_message', (data) => {
                this.addMessage(data.content, 'agent', data.created_at);
            });

            this.socket.on('chat:typing', (data) => {
                if (data.user_type === 'agent' && data.is_typing) {
                    this.showTyping();
                } else {
                    this.hideTyping();
                }
            });

            this.socket.on('chat:message_read', (data) => {
                // Handle read receipts
                console.log('Message read:', data);
            });

            this.socket.on('chat:agent_assigned', (data) => {
                this.addSystemMessage(`상담원 ${data.agent_name || ''}님이 연결되었습니다.`);
            });

        } catch (error) {
            console.error('Failed to connect:', error);
        }
    }

    toggle() {
        this.isOpen = !this.isOpen;
        this.widget.classList.toggle('open', this.isOpen);
        this.chatWindow.classList.toggle('hidden', !this.isOpen);

        if (this.isOpen) {
            this.input.focus();
        }
    }

    updateStatus(status) {
        const statusEl = document.querySelector('.chat-header-status');
        if (statusEl) {
            statusEl.textContent = status === 'online' ? '온라인' : '오프라인';
        }
    }

    sendMessage() {
        const content = this.input.value.trim();
        if (!content) return;

        // Add message to UI immediately
        this.addMessage(content, 'user');
        this.input.value = '';

        // Send via Socket.IO
        if (this.socket && this.isConnected) {
            this.socket.emit('chat:message', {
                chat_id: this.chatId,
                content: content,
                type: 'text'
            });
        }

        // Demo: Simulate agent response
        this.simulateAgentResponse();
    }

    handleTyping() {
        if (this.socket && this.isConnected) {
            this.socket.emit('chat:typing_start', {
                chat_id: this.chatId
            });

            // Stop typing after 2 seconds of inactivity
            clearTimeout(this.typingTimeout);
            this.typingTimeout = setTimeout(() => {
                this.socket.emit('chat:typing_stop', {
                    chat_id: this.chatId
                });
            }, 2000);
        }
    }

    addMessage(content, type, timestamp = null) {
        const messageEl = document.createElement('div');
        messageEl.className = `message ${type}`;

        const time = timestamp
            ? new Date(timestamp).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })
            : new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });

        messageEl.innerHTML = `
            ${content}
            <span class="message-time">${time}</span>
        `;

        this.messagesContainer.appendChild(messageEl);
        this.scrollToBottom();
    }

    addSystemMessage(content) {
        const messageEl = document.createElement('div');
        messageEl.className = 'chat-welcome';
        messageEl.innerHTML = `<p>${content}</p>`;
        this.messagesContainer.appendChild(messageEl);
        this.scrollToBottom();
    }

    showTyping() {
        this.typingIndicator.classList.remove('hidden');
        this.scrollToBottom();
    }

    hideTyping() {
        this.typingIndicator.classList.add('hidden');
    }

    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    // Demo: Simulate agent response (remove in production)
    simulateAgentResponse() {
        this.showTyping();

        const responses = [
            '안녕하세요! 무엇을 도와드릴까요?',
            '네, 확인해보겠습니다.',
            '잠시만 기다려주세요.',
            '추가로 궁금하신 점이 있으신가요?',
            '도움이 필요하시면 말씀해주세요!',
        ];

        setTimeout(() => {
            this.hideTyping();
            const response = responses[Math.floor(Math.random() * responses.length)];
            this.addMessage(response, 'agent');
        }, 1500 + Math.random() * 1000);
    }
}

// Initialize widget when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.chatWidget = new ChatWidget({
        serverUrl: 'http://localhost:8000',
        pluginKey: 'demo-plugin-key'
    });
});
