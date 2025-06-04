import { useState, useEffect, useRef, useCallback, useMemo, memo } from "react"
import "./App.css"

type Message = { role: "user" | "assistant"; content: string }
type Chat = { id: string; title: string; messages: Message[] }

const LOGO = "/tou_logo_blue.png"

// Мемоизированный компонент заголовка
const AppHeader = memo(({ onSettings, onClearChat }: { onSettings: () => void, onClearChat: () => void }) => {
  return (
    <header className="cgpt-header">
      <div className="cgpt-header-left">
        <img src={LOGO} alt="ToU Logo" className="cgpt-logo" draggable={false} />
        <span className="cgpt-title">TouGPT</span>
      </div>
      <div className="cgpt-header-actions">
        <button className="cgpt-header-btn" title="Очистить чат" onClick={onClearChat}>
          <span className="cgpt-icon">🗑️</span>
        </button>
        <button className="cgpt-header-btn" title="Настройки" onClick={onSettings}>
          <span className="cgpt-icon">⚙️</span>
        </button>
      </div>
    </header>
  )
})

// Мемоизированный сайдбар с оптимизацией рендеринга
const Sidebar = memo(({ chats, activeId, onSelect, onNew, onDelete, isMobile, onCloseSidebar }: {
  chats: Chat[]
  activeId: string
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  isMobile: boolean
  onCloseSidebar: () => void
}) => {
  // Мемоизируем обработчики для предотвращения ререндеров
  const handleChatSelect = useCallback((id: string) => {
    onSelect(id)
    if (isMobile) onCloseSidebar()
  }, [onSelect, isMobile, onCloseSidebar])

  const handleDelete = useCallback((e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    onDelete(id)
  }, [onDelete])

  // Мемоизируем список чатов
  const chatList = useMemo(() => (
    chats.map(chat => (
      <div key={chat.id} className={`cgpt-sidebar-item${chat.id === activeId ? " active" : ""}`}>
        <button
          className="cgpt-sidebar-title-btn"
          onClick={() => handleChatSelect(chat.id)}
          title={chat.title}
        >
          <span className="cgpt-sidebar-chat-icon">💬</span>
          <span className="cgpt-sidebar-title">{chat.title}</span>
        </button>
        <button
          className="cgpt-sidebar-delete"
          title="Удалить чат"
          onClick={(e) => handleDelete(e, chat.id)}
          tabIndex={-1}
        >
          🗑️
        </button>
      </div>
    ))
  ), [chats, activeId, handleChatSelect, handleDelete])

  return (
    <aside className="cgpt-sidebar">
      {isMobile && (
        <button className="cgpt-sidebar-close" onClick={onCloseSidebar} title="Закрыть меню">
          ✕
        </button>
      )}
      <div className="cgpt-sidebar-top">
        <button className="cgpt-sidebar-new" onClick={onNew}>
          <span className="cgpt-plus-icon">+</span> Новый чат
        </button>
      </div>
      <div className="cgpt-sidebar-list">
        {chats.length === 0 ? (
          <div className="cgpt-sidebar-empty">История чатов пуста</div>
        ) : (
          chatList
        )}
      </div>
      
      {/* Telegram боты */}
      <div className="cgpt-sidebar-bots">
        <span className="cgpt-sidebar-bots-title">Telegram-боты:</span>
        <div className="cgpt-sidebar-bots-list">
          <a
            className="cgpt-sidebar-bots-link"
            href="https://t.me/tou_ai_bot"
            target="_blank"
            rel="noopener noreferrer"
          >
            <span className="cgpt-bot-icon">🤖</span> Tou AI Bot
          </a>
          <a
            className="cgpt-sidebar-bots-link"
            href="https://t.me/tou_student_bot"
            target="_blank"
            rel="noopener noreferrer"
          >
            <span className="cgpt-bot-icon">🎓</span> Student Bot
          </a>
        </div>
      </div>
      
      <div className="cgpt-sidebar-bottom">
        <div className="cgpt-sidebar-footer">
          <span>© {new Date().getFullYear()} ToU</span>
        </div>
      </div>
    </aside>
  )
})

// Оптимизированный компонент сообщений с виртуализацией
const ChatMessages = memo(({ messages, loading }: { messages: Message[]; loading: boolean }) => {
  const bottomRef = useRef<HTMLDivElement>(null)
  const messagesRef = useRef<HTMLDivElement>(null)
  
  // Оптимизированная прокрутка с debounce
  const scrollToBottom = useCallback(() => {
    if (bottomRef.current) {
      const shouldScroll = messagesRef.current 
        ? messagesRef.current.scrollTop + messagesRef.current.clientHeight >= messagesRef.current.scrollHeight - 100
        : true
      
      if (shouldScroll) {
        bottomRef.current.scrollIntoView({ behavior: "smooth", block: "end" })
      }
    }
  }, [])

  useEffect(() => {
    const timeoutId = setTimeout(scrollToBottom, 100)
    return () => clearTimeout(timeoutId)
  }, [messages, loading, scrollToBottom])
  
  // Оптимизированное форматирование сообщений
  const formatMessage = useCallback((content: string) => {
    if (!content.includes("```")) {
      return <span>{content}</span>
    }

    const parts = content.split(/(```[\s\S]*?```)/g)
    return (
      <>
        {parts.map((part, index) => {
          if (part.startsWith("```") && part.endsWith("```")) {
            const code = part.slice(3, -3)
            const lines = code.split("\n")
            const language = lines[0].trim()
            const actualCode = language ? lines.slice(1).join("\n") : code
            
            return (
              <div key={index} className="cgpt-code-block">
                <div className="cgpt-code-header">
                  <span className="cgpt-code-lang">{language || "код"}</span>
                  <button 
                    className="cgpt-code-copy" 
                    onClick={() => navigator.clipboard?.writeText(actualCode.trim())}
                    title="Копировать код"
                  >
                    Копировать
                  </button>
                </div>
                <pre className="cgpt-code-content">{actualCode.trim()}</pre>
              </div>
            )
          } else {
            return <span key={index}>{part}</span>
          }
        })}
      </>
    )
  }, [])

  // Мемоизированный список сообщений
  const messageList = useMemo(() => (
    messages.map((msg, i) => (
      <div key={`${i}-${msg.role}`} className={`cgpt-chat-msg cgpt-chat-msg-${msg.role}`}>
        <div className="cgpt-chat-msg-avatar">
          {msg.role === "user" ? "🧑" : "🤖"}
        </div>
        <div className="cgpt-chat-msg-content">
          {formatMessage(msg.content)}
        </div>
      </div>
    ))
  ), [messages, formatMessage])
  
  return (
    <div ref={messagesRef} className="cgpt-chat-messages">
      {messages.length === 0 && (
        <div className="cgpt-chat-empty">
          <div className="cgpt-chat-empty-logo">
            <img src={LOGO} alt="ToU Logo" className="cgpt-big-logo" loading="lazy" />
          </div>
          <div className="cgpt-chat-empty-title">TouGPT</div>
          <div className="cgpt-chat-empty-desc">
            Привет! Я AI-ассистент университета Торайгырова. Задайте вопрос, чтобы начать диалог.
          </div>
          <div className="cgpt-chat-examples">
            <button className="cgpt-chat-example-btn">Расскажи о консультациях по программированию</button>
            <button className="cgpt-chat-example-btn">Где находится библиотека?</button>
            <button className="cgpt-chat-example-btn">Какие элективные курсы рекомендуются?</button>
          </div>
        </div>
      )}
      
      {messageList}
      
      {loading && (
        <div className="cgpt-chat-msg cgpt-chat-msg-assistant">
          <div className="cgpt-chat-msg-avatar">🤖</div>
          <div className="cgpt-chat-msg-content">
            <div className="cgpt-typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
      )}
      <div ref={bottomRef} className="cgpt-scroll-anchor" />
    </div>
  )
})

// Оптимизированный компонент ввода с автоматическим изменением размера
const ChatInput = memo(({ value, onChange, onSend, loading }: { 
  value: string; 
  onChange: (v: string) => void; 
  onSend: () => void; 
  loading: boolean 
}) => {
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const [rows, setRows] = useState(1)
  
  // Оптимизированная регулировка высоты
  const adjustRows = useCallback(() => {
    if (inputRef.current) {
      const textarea = inputRef.current
      textarea.style.height = 'auto'
      const lineHeight = 24
      const maxHeight = lineHeight * 5
      const scrollHeight = Math.min(textarea.scrollHeight, maxHeight)
      const newRows = Math.max(1, Math.ceil(scrollHeight / lineHeight))
      
      setRows(newRows)
      textarea.style.height = `${scrollHeight}px`
    }
  }, [])
  
  useEffect(() => {
    adjustRows()
  }, [value, adjustRows])
  
  useEffect(() => {
    if (inputRef.current && !loading) {
      inputRef.current.focus()
    }
  }, [loading])
  
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      if (!loading && value.trim()) {
        onSend()
      }
    }
  }, [loading, value, onSend])
  
  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value)
  }, [onChange])
  
  return (
    <form className="cgpt-chat-input-row" onSubmit={e => { e.preventDefault(); onSend() }}>
      <textarea
        ref={inputRef}
        className="cgpt-chat-input"
        placeholder="Введите сообщение..."
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        disabled={loading}
        rows={rows}
        maxLength={2000}
        autoComplete="off"
        spellCheck="true"
      />
      <button
        className="cgpt-chat-send-btn"
        type="submit"
        disabled={loading || !value.trim()}
        title="Отправить"
      >
        <span className="cgpt-send-icon">
          {loading ? "⏳" : "→"}
        </span>
      </button>
    </form>
  )
})

// Оптимизированное модальное окно настроек
const SettingsModal = memo(({ open, onClose, theme, onToggleTheme, apiKey, setApiKey, onSaveApiKey }: {
  open: boolean
  onClose: () => void
  theme: string
  onToggleTheme: () => void
  apiKey: string
  setApiKey: (v: string) => void
  onSaveApiKey: () => void
}) => {
  const [showKey, setShowKey] = useState(false)
  const [isKeyValid, setIsKeyValid] = useState(true)
  
  // Мемоизированная проверка валидности API ключа
  const validateApiKey = useCallback((key: string) => {
    if (!key) return true
    return key.startsWith('AIza') && key.length > 20
  }, [])
  
  useEffect(() => {
    setIsKeyValid(validateApiKey(apiKey))
  }, [apiKey, validateApiKey])
  
  const handleBackdropClick = useCallback((e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }, [onClose])
  
  const handleSave = useCallback(() => {
    onSaveApiKey()
    const btn = document.querySelector('.cgpt-save-btn') as HTMLElement
    if (btn) {
      btn.style.transform = 'scale(0.95)'
      setTimeout(() => {
        btn.style.transform = ''
      }, 150)
    }
  }, [onSaveApiKey])

  const toggleShowKey = useCallback(() => setShowKey(v => !v), [])
  const handleApiKeyChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setApiKey(e.target.value)
  }, [setApiKey])
  
  if (!open) return null
  
  return (
    <div className="cgpt-modal-bg" onClick={handleBackdropClick}>
      <div className="cgpt-modal" onClick={e => e.stopPropagation()}>
        <div className="cgpt-modal-header">
          <span>⚙️ Настройки</span>
          <button className="cgpt-modal-close" onClick={onClose} title="Закрыть">
            ✖
          </button>
        </div>
        <div className="cgpt-modal-content">
          <div className="cgpt-settings-row">
            <span className="cgpt-settings-label">Тема интерфейса</span>
            <div className="cgpt-theme-toggle">
              <button 
                className={`cgpt-theme-btn ${theme === 'light' ? 'active' : ''}`} 
                onClick={() => {if(theme !== 'light') onToggleTheme()}}
              >
                <span className="cgpt-theme-icon">☀️</span> 
                <span>Светлая</span>
              </button>
              <button 
                className={`cgpt-theme-btn ${theme === 'dark' ? 'active' : ''}`} 
                onClick={() => {if(theme !== 'dark') onToggleTheme()}}
              >
                <span className="cgpt-theme-icon">🌙</span> 
                <span>Тёмная</span>
              </button>
            </div>
          </div>
          
          <div className="cgpt-settings-section">
            <h3 className="cgpt-settings-section-title">🔑 API-ключ Gemini</h3>
            <div className="cgpt-settings-row">
              <span className="cgpt-settings-label">
                Ключ для доступа к AI {apiKey && (
                  <span className={`cgpt-key-status ${isKeyValid ? 'valid' : 'invalid'}`}>
                    {isKeyValid ? '✅' : '❌'}
                  </span>
                )}
              </span>
              <div className="cgpt-api-key-container">
                <input
                  className={`cgpt-chat-input ${!isKeyValid && apiKey ? 'error' : ''}`}
                  type={showKey ? "text" : "password"}
                  value={apiKey}
                  onChange={handleApiKeyChange}
                  placeholder="Введите ключ Gemini API..."
                  autoComplete="off"
                />
                <button 
                  className="cgpt-toggle-view-btn" 
                  onClick={toggleShowKey}
                  title={showKey ? "Скрыть ключ" : "Показать ключ"}
                  type="button"
                >
                  {showKey ? "🙈" : "👁️"}
                </button>
              </div>
            </div>
            <div className="cgpt-settings-actions">
              <button 
                className="cgpt-btn cgpt-save-btn" 
                onClick={handleSave}
                disabled={!apiKey.trim()}
              >
                💾 Сохранить ключ
              </button>
            </div>
            <div className="cgpt-settings-hint">
              <p><strong>Как получить API-ключ:</strong></p>
              <p>1. Перейдите на <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener noreferrer">Google AI Studio</a></p>
              <p>2. Войдите в аккаунт Google</p>
              <p>3. Нажмите "Create API key"</p>
              <p>4. Скопируйте ключ и вставьте сюда</p>
              <p><em>Ключ сохраняется только в вашем браузере и используется для запросов к AI.</em></p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
})

// Вспомогательная функция для создания заголовка чата
function getChatTitle(messages: Message[]): string {
  if (!messages.length) return "Новый чат"
  const first = messages.find(m => m.role === "user")
  if (!first) return "Новый чат"
  
  // Ограничим длину заголовка
  let title = first.content
  if (title.length > 40) {
    title = title.substring(0, 37) + "..."
  }
  return title
}

// Основной компонент приложения
export default function App() {
  // Состояние чатов
  const [chats, setChats] = useState<Chat[]>(() => {
    try {
      const raw = localStorage.getItem("tou-chats")
      if (raw) {
        const arr = JSON.parse(raw)
        return Array.isArray(arr) && arr.length > 0 ? arr : [{
          id: crypto.randomUUID(),
          title: "Новый чат",
          messages: []
        }]
      }
    } catch {}
    return [{
      id: crypto.randomUUID(),
      title: "Новый чат",
      messages: []
    }]
  })
  
  // Активный чат и состояние приложения
  const [activeId, setActiveId] = useState(() => chats[0]?.id || "")
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false)
  const [windowWidth, setWindowWidth] = useState(() => 
    typeof window !== "undefined" ? window.innerWidth : 1024
  )
  
  // Тема и API ключ
  const [theme, setTheme] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("tou-theme") || 
        (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    }
    return "light"
  })
  const [apiKey, setApiKey] = useState(() => localStorage.getItem("tou-apikey") || "")

  const isMobile = useMemo(() => windowWidth < 768, [windowWidth])

  // Эффекты для сохранения данных
  useEffect(() => { 
    try {
      localStorage.setItem("tou-chats", JSON.stringify(chats))
    } catch (e) {
      console.warn('Не удалось сохранить чаты в localStorage:', e)
    }
  }, [chats])
  
  useEffect(() => {
    document.body.classList.toggle("tou-dark", theme === "dark")
    try {
      localStorage.setItem("tou-theme", theme)
    } catch (e) {
      console.warn('Не удалось сохранить тему в localStorage:', e)
    }
  }, [theme])
  
  useEffect(() => {
    try {
      localStorage.setItem("tou-apikey", apiKey)
    } catch (e) {
      console.warn('Не удалось сохранить API ключ в localStorage:', e)
    }
  }, [apiKey])
  
  // Следим за размером окна
  useEffect(() => {
    let timeoutId: NodeJS.Timeout
    const handleResize = () => {
      clearTimeout(timeoutId)
      timeoutId = setTimeout(() => setWindowWidth(window.innerWidth), 100)
    }
    window.addEventListener('resize', handleResize, { passive: true })
    return () => {
      window.removeEventListener('resize', handleResize)
      clearTimeout(timeoutId)
    }
  }, [])

  // Проверка на существование активного чата
  useEffect(() => {
    if (!chats.find(c => c.id === activeId) && chats.length > 0) {
      setActiveId(chats[0].id)
    }
  }, [chats, activeId])

  const activeChat = useMemo(() => 
    chats.find(c => c.id === activeId) || chats[0] || {
      id: crypto.randomUUID(),
      title: "Новый чат",
      messages: []
    }, [chats, activeId])

  // Обработчики событий
  // Отправка сообщения
  const handleSend = useCallback(async () => {
    if (!input.trim() || loading) return
    
    const userMsg: Message = { role: "user", content: input.trim() }
    const currentChatId = activeChat.id
    
    setChats(prev =>
      prev.map(chat =>
        chat.id === currentChatId
          ? { ...chat, messages: [...chat.messages, userMsg] }
          : chat
      )
    )
    
    setInput("")
    setLoading(true)
    setError(null)
    
    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 30000) // 30 секунд таймаут
      
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json", 
          ...(apiKey ? { "X-API-Key": apiKey } : {})
        },
        body: JSON.stringify({ 
          question: userMsg.content, 
          ...(apiKey ? { api_key: apiKey } : {})
        }),
        signal: controller.signal
      })
      
      clearTimeout(timeoutId)
      
      let data: any = null
      try { 
        data = await res.json() 
      } catch(e) {
        throw new Error("Ошибка при обработке ответа сервера")
      }
      
      const aiMsg: Message = { 
        role: "assistant", 
        content: data?.answer || "Ошибка сервера. Попробуйте позже."
      }
      
      setChats(prev =>
        prev.map(chat =>
          chat.id === currentChatId
            ? { 
                ...chat, 
                messages: [...chat.messages, aiMsg], 
                title: chat.title === "Новый чат" ? getChatTitle([userMsg, ...chat.messages]) : chat.title 
              }
            : chat
        )
      )
      
      if (!res.ok) {
        setError(data?.answer || "Ошибка сервера. Попробуйте позже.")
      }
    } catch(err: any) {
      console.error("Ошибка запроса:", err)
      
      let errorMessage = "Нет соединения с сервером. Проверьте интернет или попробуйте позже."
      if (err.name === 'AbortError') {
        errorMessage = "Превышено время ожидания ответа. Попробуйте позже."
      }
      
      const aiMsg: Message = { role: "assistant", content: errorMessage }
      
      setChats(prev =>
        prev.map(chat =>
          chat.id === currentChatId
            ? { ...chat, messages: [...chat.messages, aiMsg] }
            : chat
        )
      )
      
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }, [input, apiKey, loading, activeChat.id])

  // Создание нового чата
  const handleNewChat = useCallback(() => {
    const newChat: Chat = {
      id: crypto.randomUUID(),
      title: "Новый чат",
      messages: []
    }
    
    setChats(prev => [newChat, ...prev])
    setActiveId(newChat.id)
    setInput("")
    setError(null)
    
    if (isMobile) {
      setIsMobileSidebarOpen(false)
    }
  }, [isMobile])

  // Удаление чата
  const handleDeleteChat = useCallback((id: string) => {
    setChats(prev => {
      const filtered = prev.filter(c => c.id !== id)
      
      if (filtered.length === 0) {
        const newChat: Chat = { 
          id: crypto.randomUUID(), 
          title: "Новый чат", 
          messages: [] 
        }
        setActiveId(newChat.id)
        return [newChat]
      }
      
      if (id === activeId) {
        setActiveId(filtered[0].id)
      }
      
      return filtered
    })
  }, [activeId])

  // Очистка текущего чата
  const handleClearChat = useCallback(() => {
    if (activeChat && activeChat.messages.length > 0) {
      if (window.confirm("Очистить текущий чат?")) {
        setChats(prev => 
          prev.map(chat => 
            chat.id === activeChat.id 
              ? { ...chat, messages: [], title: "Новый чат" } 
              : chat
          )
        )
      }
    }
  }, [activeChat])

  // Переключение темы
  const handleToggleTheme = useCallback(() => 
    setTheme(t => (t === "dark" ? "light" : "dark")), []
  )
  
  // Сохранение API ключа
  const handleSaveApiKey = useCallback(() => {
    setShowSettings(false)
    // Показываем более красивое уведомление
    const notification = document.createElement('div')
    notification.textContent = '✅ API-ключ сохранен!'
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: var(--cgpt-primary);
      color: white;
      padding: 12px 20px;
      border-radius: 8px;
      z-index: 9999;
      animation: slideIn 0.3s ease;
    `
    document.body.appendChild(notification)
    setTimeout(() => {
      notification.remove()
    }, 3000)
  }, [])

  const toggleMobileSidebar = useCallback(() => {
    setIsMobileSidebarOpen(prev => !prev)
  }, [])
  
  // Обработка примеров запросов с улучшенным UX
  useEffect(() => {
    const handleExampleClick = (e: Event) => {
      const target = e.target as HTMLElement
      if (target.classList.contains('cgpt-chat-example-btn')) {
        const text = target.textContent || ''
        setInput(text)
        // Небольшая задержка для лучшего UX
        setTimeout(() => {
          handleSend()
        }, 150)
      }
    }
    
    document.addEventListener('click', handleExampleClick)
    return () => document.removeEventListener('click', handleExampleClick)
  }, [handleSend])

  return (
    <div className={`cgpt-root${theme === "dark" ? " tou-dark" : ""}`}>
      {/* Кнопка открытия меню на мобильных */}
      {isMobile && (
        <button 
          className="cgpt-mobile-menu-toggle" 
          onClick={toggleMobileSidebar}
          aria-label="Открыть меню"
        >
          ☰
        </button>
      )}
      
      {/* Сайдбар (на мобильных открывается по кнопке) */}
      <div className={`cgpt-sidebar-container ${isMobileSidebarOpen ? "open" : ""}`}>
        {isMobile && (
          <div className="cgpt-sidebar-backdrop" onClick={() => setIsMobileSidebarOpen(false)}></div>
        )}
        <Sidebar
          chats={chats}
          activeId={activeChat.id}
          onSelect={setActiveId}
          onNew={handleNewChat}
          onDelete={handleDeleteChat}
          isMobile={isMobile}
          onCloseSidebar={() => setIsMobileSidebarOpen(false)}
        />
      </div>
      
      {/* Основная часть */}
      <div className="cgpt-main">
        <AppHeader onSettings={() => setShowSettings(true)} onClearChat={handleClearChat} />
        <div className="cgpt-chat-area">
          <ChatMessages messages={activeChat.messages} loading={loading} />
          {error && (
            <div className="cgpt-chat-error">
              <span className="cgpt-error-icon">⚠️</span> {error}
            </div>
          )}
          <ChatInput
            value={input}
            onChange={setInput}
            onSend={handleSend}
            loading={loading}
          />
        </div>
      </div>
      
      {/* Модальные окна */}
      <SettingsModal
        open={showSettings}
        onClose={() => setShowSettings(false)}
        theme={theme}
        onToggleTheme={handleToggleTheme}
        apiKey={apiKey}
        setApiKey={setApiKey}
        onSaveApiKey={handleSaveApiKey}
      />
    </div>
  )
}
