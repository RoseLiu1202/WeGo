import React, { useState, useEffect, useRef } from 'react';
import { Send, User, MessageSquare } from 'lucide-react';

const API_BASE = 'https://cynthia-weatherworn-unprotestingly.ngrok-free.dev/api/v1'; // Update to your backend URL

export default function ChatInterface() {
  const [username, setUsername] = useState('');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [chatId, setChatId] = useState('');
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleUsernameSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim()) {
      setError('Please enter a username');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE}/chats`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          chat_name: 'General Chat',
          user_ids: [username.trim()]
        })
      });

      if (!response.ok) {
        throw new Error('Failed to create/join chat');
      }

      const data = await response.json();
      setChatId(data.chat_id);
      setIsLoggedIn(true);
     
      await loadMessages(data.chat_id);
    } catch (err) {
      setError('Failed to connect. Please try again.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const loadMessages = async (id) => {
    try {
      const response = await fetch(`${API_BASE}/chats/${id}/messages`);
      if (response.ok) {
        const data = await response.json();
        if (Array.isArray(data)) {
          setMessages(data);
        }
      }
    } catch (err) {
      console.error('Failed to load messages:', err);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || isLoading) return;

    const messageText = newMessage.trim();
    setNewMessage('');
    setIsLoading(true);

    const tempMessage = {
      user_name: username,
      text: messageText,
      timestamp: new Date().toISOString(),
      isTemp: true
    };
    setMessages(prev => [...prev, tempMessage]);

    try {
      const response = await fetch(`${API_BASE}/chats/${chatId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: username,
          user_name: username,
          text: messageText
        })
      });

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

      const data = await response.json();
     
      setMessages(prev => prev.map(msg =>
        msg.isTemp ? { ...msg, isTemp: false, message_id: data.message_id } : msg
      ));

      setTimeout(() => loadMessages(chatId), 1000);
    } catch (err) {
      setError('Failed to send message. Please try again.');
      setMessages(prev => prev.filter(msg => !msg.isTemp));
      setNewMessage(messageText);
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isLoggedIn) {
    return (
      <div style={styles.loginContainer}>
        <div style={styles.loginBox}>
          <div style={styles.iconContainer}>
            <MessageSquare size={48} color="#4F46E5" />
          </div>
          <h1 style={styles.title}>Welcome to Chat</h1>
          <p style={styles.subtitle}>Enter your username to start chatting</p>
         
          <form onSubmit={handleUsernameSubmit} style={styles.form}>
            <div style={styles.inputGroup}>
              <label style={styles.label}>Username</label>
              <div style={styles.inputWrapper}>
                <User size={20} style={styles.inputIcon} color="#9CA3AF" />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  style={styles.input}
                  placeholder="Enter your username"
                  disabled={isLoading}
                />
              </div>
            </div>
           
            {error && (
              <div style={styles.error}>{error}</div>
            )}
           
            <button
              type="submit"
              disabled={isLoading}
              style={{
                ...styles.button,
                ...(isLoading ? styles.buttonDisabled : {})
              }}
            >
              {isLoading ? 'Connecting...' : 'Start Chatting'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.chatContainer}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.headerContent}>
          <div style={styles.headerLeft}>
            <MessageSquare size={24} color="#4F46E5" />
            <h1 style={styles.headerTitle}>Chat Room</h1>
          </div>
          <div style={styles.userBadge}>
            <User size={16} color="#4F46E5" />
            <span style={styles.userBadgeText}>{username}</span>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div style={styles.messagesContainer}>
        <div style={styles.messagesContent}>
          {messages.length === 0 ? (
            <div style={styles.emptyState}>
              <MessageSquare size={48} color="#D1D5DB" />
              <p style={styles.emptyText}>No messages yet. Start the conversation!</p>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div
                key={idx}
                style={{
                  ...styles.messageRow,
                  justifyContent: msg.user_name === username ? 'flex-end' : 'flex-start'
                }}
              >
                <div
                  style={{
                    ...styles.messageBubble,
                    ...(msg.user_name === username ? styles.messageBubbleSent : styles.messageBubbleReceived),
                    ...(msg.isTemp ? styles.messageBubbleTemp : {})
                  }}
                >
                  <div style={styles.messageHeader}>
                    <span style={{
                      ...styles.messageUsername,
                      color: msg.user_name === username ? '#C7D2FE' : '#4F46E5'
                    }}>
                      {msg.user_name}
                    </span>
                  </div>
                  <p style={styles.messageText}>{msg.text}</p>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={styles.errorContainer}>
          <div style={styles.error}>{error}</div>
        </div>
      )}

      {/* Input */}
      <div style={styles.inputArea}>
        <form onSubmit={handleSendMessage} style={styles.inputForm}>
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Type your message..."
            style={styles.messageInput}
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !newMessage.trim()}
            style={{
              ...styles.sendButton,
              ...(isLoading || !newMessage.trim() ? styles.sendButtonDisabled : {})
            }}
          >
            <Send size={20} />
          </button>
        </form>
      </div>
    </div>
  );
}

const styles = {
  loginContainer: {
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '20px',
  },
  loginBox: {
    backgroundColor: 'white',
    borderRadius: '16px',
    boxShadow: '0 10px 25px rgba(0,0,0,0.1)',
    padding: '40px',
    width: '100%',
    maxWidth: '400px',
  },
  iconContainer: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: '24px',
  },
  title: {
    fontSize: '28px',
    fontWeight: 'bold',
    textAlign: 'center',
    color: '#1F2937',
    marginBottom: '8px',
  },
  subtitle: {
    textAlign: 'center',
    color: '#6B7280',
    marginBottom: '32px',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  inputGroup: {
    display: 'flex',
    flexDirection: 'column',
  },
  label: {
    fontSize: '14px',
    fontWeight: '500',
    color: '#374151',
    marginBottom: '8px',
  },
  inputWrapper: {
    position: 'relative',
  },
  inputIcon: {
    position: 'absolute',
    left: '12px',
    top: '50%',
    transform: 'translateY(-50%)',
  },
  input: {
    width: '100%',
    paddingLeft: '40px',
    paddingRight: '16px',
    paddingTop: '12px',
    paddingBottom: '12px',
    border: '1px solid #D1D5DB',
    borderRadius: '8px',
    fontSize: '16px',
    outline: 'none',
  },
  button: {
    width: '100%',
    backgroundColor: '#4F46E5',
    color: 'white',
    padding: '12px',
    borderRadius: '8px',
    fontWeight: '600',
    border: 'none',
    cursor: 'pointer',
    fontSize: '16px',
  },
  buttonDisabled: {
    backgroundColor: '#A5B4FC',
    cursor: 'not-allowed',
  },
  error: {
    backgroundColor: '#FEF2F2',
    color: '#DC2626',
    padding: '12px',
    borderRadius: '8px',
    fontSize: '14px',
  },
  chatContainer: {
    minHeight: '100vh',
    backgroundColor: '#F3F4F6',
    display: 'flex',
    flexDirection: 'column',
  },
  header: {
    backgroundColor: 'white',
    borderBottom: '1px solid #E5E7EB',
    padding: '16px 24px',
  },
  headerContent: {
    maxWidth: '1024px',
    margin: '0 auto',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  headerTitle: {
    fontSize: '20px',
    fontWeight: 'bold',
    color: '#1F2937',
  },
  userBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    backgroundColor: '#EEF2FF',
    padding: '8px 16px',
    borderRadius: '20px',
  },
  userBadgeText: {
    fontSize: '14px',
    fontWeight: '500',
    color: '#4338CA',
  },
  messagesContainer: {
    flex: 1,
    overflowY: 'auto',
    padding: '24px',
  },
  messagesContent: {
    maxWidth: '1024px',
    margin: '0 auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  emptyState: {
    textAlign: 'center',
    color: '#6B7280',
    paddingTop: '48px',
    paddingBottom: '48px',
  },
  emptyText: {
    marginTop: '12px',
  },
  messageRow: {
    display: 'flex',
  },
  messageBubble: {
    maxWidth: '400px',
    padding: '12px 16px',
    borderRadius: '16px',
  },
  messageBubbleSent: {
    backgroundColor: '#4F46E5',
    color: 'white',
  },
  messageBubbleReceived: {
    backgroundColor: 'white',
    color: '#1F2937',
    border: '1px solid #E5E7EB',
  },
  messageBubbleTemp: {
    opacity: 0.6,
  },
  messageHeader: {
    marginBottom: '4px',
  },
  messageUsername: {
    fontSize: '12px',
    fontWeight: '600',
  },
  messageText: {
    wordBreak: 'break-word',
    margin: 0,
  },
  errorContainer: {
    maxWidth: '1024px',
    margin: '0 auto',
    padding: '0 24px 8px',
  },
  inputArea: {
    backgroundColor: 'white',
    borderTop: '1px solid #E5E7EB',
    padding: '24px',
  },
  inputForm: {
    maxWidth: '1024px',
    margin: '0 auto',
    display: 'flex',
    gap: '12px',
  },
  messageInput: {
    flex: 1,
    padding: '12px 16px',
    border: '1px solid #D1D5DB',
    borderRadius: '24px',
    fontSize: '16px',
    outline: 'none',
  },
  sendButton: {
    backgroundColor: '#4F46E5',
    color: 'white',
    padding: '12px',
    borderRadius: '50%',
    border: 'none',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '48px',
    height: '48px',
  },
  sendButtonDisabled: {
    backgroundColor: '#A5B4FC',
    cursor: 'not-allowed',
  },
};