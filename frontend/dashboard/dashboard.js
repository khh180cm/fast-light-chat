/**
 * Fast Light Chat - Agent Dashboard
 * 상담원 대시보드
 */

class AgentDashboard {
    constructor() {
        this.serverUrl = 'http://localhost:8000';
        this.socket = null;
        this.currentChatId = null;
        this.accessToken = localStorage.getItem('accessToken');
        this.agentId = null;
        this.internalNoteState = {}; // 채팅방별 내부 메모 상태 저장

        this.init();
    }

    init() {
        // DOM Elements
        this.chatList = document.getElementById('chat-list');
        this.chatDetailEmpty = document.getElementById('chat-detail-empty');
        this.chatDetailContent = document.getElementById('chat-detail-content');
        this.chatMessages = document.getElementById('chat-messages');
        this.messageInput = document.getElementById('message-input');
        this.sendBtn = document.getElementById('send-btn');
        this.agentStatusSelect = document.getElementById('agent-status');
        this.filterTabs = document.querySelectorAll('.filter-tab');
        this.internalNoteCheckbox = document.getElementById('internal-note');

        // Event Listeners
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        this.agentStatusSelect.addEventListener('change', () => {
            this.updateAgentStatus(this.agentStatusSelect.value);
        });

        this.filterTabs.forEach(tab => {
            tab.addEventListener('click', () => {
                this.filterTabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.filterChats(tab.dataset.filter);
            });
        });

        // Chat item click
        this.chatList.addEventListener('click', (e) => {
            const chatItem = e.target.closest('.chat-item');
            if (chatItem) {
                this.selectChat(chatItem.dataset.chatId);
            }
        });

        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => {
            this.messageInput.style.height = 'auto';
            this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 120) + 'px';
        });

        // 내부 메모 체크박스 상태 저장
        this.internalNoteCheckbox.addEventListener('change', () => {
            if (this.currentChatId) {
                this.internalNoteState[this.currentChatId] = this.internalNoteCheckbox.checked;
            }
        });

        // Connect to Socket.IO
        this.connect();

        // Load initial data
        this.loadChats();
    }

    connect() {
        try {
            this.socket = io(this.serverUrl, {
                transports: ['websocket', 'polling'],
                auth: {
                    type: 'agent',
                    token: this.accessToken
                }
            });

            this.socket.on('connect', () => {
                console.log('Connected to server');
            });

            this.socket.on('disconnect', () => {
                console.log('Disconnected from server');
            });

            // Agent events
            this.socket.on('agent:new_chat', (data) => {
                this.handleNewChat(data);
            });

            this.socket.on('agent:chat_assigned', (data) => {
                this.handleChatAssigned(data);
            });

            // Chat events
            this.socket.on('chat:new_message', (data) => {
                if (data.chat_id === this.currentChatId) {
                    this.addMessage(data);
                }
                this.updateChatPreview(data.chat_id, data.content);
            });

            this.socket.on('chat:typing', (data) => {
                if (data.chat_id === this.currentChatId && data.user_type === 'user') {
                    this.showTypingIndicator(data.is_typing);
                }
            });

        } catch (error) {
            console.error('Failed to connect:', error);
        }
    }

    async loadChats() {
        // Demo data - replace with API call
        const demoChats = [
            {
                id: '1',
                customer: { name: '홍길동', avatar: '홍' },
                lastMessage: '문의드립니다. 제품 관련해서...',
                time: '14:31',
                unreadCount: 2,
                status: 'active'
            },
            {
                id: '2',
                customer: { name: '김철수', avatar: '김' },
                lastMessage: '감사합니다!',
                time: '14:25',
                unreadCount: 0,
                status: 'active'
            },
            {
                id: '3',
                customer: { name: '박영희', avatar: '박' },
                lastMessage: '배송 관련 문의입니다',
                time: '14:20',
                unreadCount: 0,
                status: 'waiting'
            }
        ];

        // In production, call API:
        // const response = await fetch(`${this.serverUrl}/v1/chats`, {
        //     headers: { 'Authorization': `Bearer ${this.accessToken}` }
        // });
        // const chats = await response.json();
    }

    selectChat(chatId) {
        this.currentChatId = chatId;

        // Update UI
        document.querySelectorAll('.chat-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.chatId === chatId) {
                item.classList.add('active');
                item.classList.remove('unread');
                const badge = item.querySelector('.chat-badge');
                if (badge) badge.remove();
            }
        });

        this.chatDetailEmpty.classList.add('hidden');
        this.chatDetailContent.classList.remove('hidden');

        // Load messages
        this.loadMessages(chatId);

        // 해당 채팅방의 내부 메모 상태 복원
        this.internalNoteCheckbox.checked = this.internalNoteState[chatId] || false;

        // Join chat room via Socket.IO
        if (this.socket) {
            this.socket.emit('chat:join', { chat_id: chatId });
        }
    }

    async loadMessages(chatId) {
        this.chatMessages.innerHTML = '';

        // Demo messages - replace with API call
        const demoMessages = [
            { type: 'customer', content: '안녕하세요, 문의드립니다.', time: '14:30' },
            { type: 'agent', content: '안녕하세요! 무엇을 도와드릴까요?', time: '14:30' },
            { type: 'customer', content: '제품 관련해서 궁금한게 있어요.', time: '14:31' },
        ];

        demoMessages.forEach(msg => this.addMessage(msg));

        // Scroll to bottom
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    addMessage(data) {
        const messageEl = document.createElement('div');
        const isCustomer = data.type === 'customer' || data.sender_type === 'user';
        const isInternal = data.internal;

        messageEl.className = `message ${isCustomer ? 'customer' : 'agent'}${isInternal ? ' internal' : ''}`;

        const time = data.time || new Date(data.created_at || Date.now()).toLocaleTimeString('ko-KR', {
            hour: '2-digit',
            minute: '2-digit'
        });

        messageEl.innerHTML = `
            ${data.content}
            <span class="message-time">${time}${isInternal ? ' (내부 메모)' : ''}</span>
        `;

        this.chatMessages.appendChild(messageEl);
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    sendMessage() {
        const content = this.messageInput.value.trim();
        if (!content || !this.currentChatId) return;

        const isInternal = this.internalNoteCheckbox.checked;

        // Add message to UI immediately
        this.addMessage({
            type: 'agent',
            content: content,
            internal: isInternal
        });

        // Clear input (내부 메모 상태는 유지)
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';

        // Send via Socket.IO
        if (this.socket) {
            this.socket.emit('chat:message', {
                chat_id: this.currentChatId,
                content: content,
                type: 'text',
                internal: isInternal
            });
        }
    }

    updateAgentStatus(status) {
        if (this.socket) {
            this.socket.emit('agent:status_change', { status });
        }
    }

    filterChats(filter) {
        const chatItems = document.querySelectorAll('.chat-item');
        chatItems.forEach(item => {
            if (filter === 'all') {
                item.style.display = 'flex';
            } else if (filter === 'waiting') {
                item.style.display = item.classList.contains('waiting') ? 'flex' : 'none';
            } else if (filter === 'active') {
                item.style.display = !item.classList.contains('waiting') ? 'flex' : 'none';
            } else if (filter === 'closed') {
                item.style.display = 'none'; // Demo: no closed chats
            }
        });
    }

    handleNewChat(data) {
        // Show notification
        this.showNotification('새로운 상담 요청', data.customer?.name || '고객');

        // Update stats
        const waitingStat = document.getElementById('stat-waiting');
        waitingStat.textContent = parseInt(waitingStat.textContent) + 1;
    }

    handleChatAssigned(data) {
        console.log('Chat assigned:', data);
    }

    updateChatPreview(chatId, content) {
        const chatItem = document.querySelector(`.chat-item[data-chat-id="${chatId}"]`);
        if (chatItem) {
            const preview = chatItem.querySelector('.chat-preview');
            if (preview) {
                preview.textContent = content;
            }
        }
    }

    showTypingIndicator(isTyping) {
        const indicator = document.getElementById('customer-typing');
        indicator.classList.toggle('hidden', !isTyping);
    }

    showNotification(title, body) {
        if (Notification.permission === 'granted') {
            new Notification(title, { body });
        } else if (Notification.permission !== 'denied') {
            Notification.requestPermission().then(permission => {
                if (permission === 'granted') {
                    new Notification(title, { body });
                }
            });
        }
    }
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new AgentDashboard();

    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
});
