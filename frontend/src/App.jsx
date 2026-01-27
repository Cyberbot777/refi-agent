import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { 
  Send, 
  Home, 
  FileText, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle,
  Loader2,
  Building2,
  Shield,
  Calculator,
  Clock,
  ChevronDown,
  RefreshCw
} from 'lucide-react'

const API_URL = 'http://localhost:8000'

// Test cases for quick selection
const TEST_CASES = [
  { id: 'REFI-FHA-001', program: 'FHA', desc: 'Good loan - should PASS', expected: 'APPROVED' },
  { id: 'REFI-FHA-002', program: 'FHA', desc: 'Only 4 months', expected: 'DENIED' },
  { id: 'REFI-FHA-003', program: 'FHA', desc: 'Same rate - no NTB', expected: 'DENIED' },
  { id: 'REFI-FHA-004', program: 'FHA', desc: 'Near cash limit', expected: 'CONDITIONS' },
  { id: 'REFI-VA-001', program: 'VA', desc: 'Good loan - should PASS', expected: 'APPROVED' },
  { id: 'REFI-VA-002', program: 'VA', desc: 'Rate only 0.40%', expected: 'DENIED' },
  { id: 'REFI-VA-003', program: 'VA', desc: 'Recoupment > 36mo', expected: 'DENIED' },
  { id: 'REFI-VA-004', program: 'VA', desc: '20% PITI trigger', expected: 'MANUAL' },
]

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [currentTool, setCurrentTool] = useState('')
  const [showTestCases, setShowTestCases] = useState(false)
  const messagesContainerRef = useRef(null)
  const inputRef = useRef(null)

  // Check if user is near bottom of scroll container
  const isNearBottom = () => {
    if (!messagesContainerRef.current) return true
    const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current
    const threshold = 150 // pixels from bottom
    return scrollHeight - scrollTop - clientHeight < threshold
  }

  // Smart scroll - only auto-scroll if user is near bottom
  const scrollToBottom = () => {
    if (isNearBottom() && messagesContainerRef.current) {
      // Scroll the container directly instead of using scrollIntoView
      messagesContainerRef.current.scrollTo({
        top: messagesContainerRef.current.scrollHeight,
        behavior: 'smooth'
      })
    }
  }

  // Only auto-scroll if user is near bottom
  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setIsLoading(true)
    setCurrentTool('')

    try {
      const response = await fetch(`${API_URL}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage }),
      })

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let assistantMessage = ''

      setMessages(prev => [...prev, { role: 'assistant', content: '' }])

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              
              if (data.type === 'chunk') {
                assistantMessage += data.content
                setMessages(prev => {
                  const newMessages = [...prev]
                  newMessages[newMessages.length - 1].content = assistantMessage
                  return newMessages
                })
              } else if (data.type === 'tool') {
                setCurrentTool(data.content)
              } else if (data.type === 'done') {
                setCurrentTool('')
              } else if (data.type === 'error') {
                setMessages(prev => {
                  const newMessages = [...prev]
                  newMessages[newMessages.length - 1].content = `Error: ${data.content}`
                  newMessages[newMessages.length - 1].isError = true
                  return newMessages
                })
              }
            } catch (e) {
              // Ignore JSON parse errors for incomplete chunks
            }
          }
        }
      }
    } catch (error) {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: `Connection error: ${error.message}`, 
        isError: true 
      }])
    } finally {
      setIsLoading(false)
      setCurrentTool('')
    }
  }

  const selectTestCase = (testCase) => {
    setInput(`Process refinance application ${testCase.id}`)
    setShowTestCases(false)
    inputRef.current?.focus()
  }

  const getStatusIcon = (expected) => {
    switch (expected) {
      case 'APPROVED':
        return <CheckCircle2 className="w-4 h-4 text-success-500" />
      case 'DENIED':
        return <XCircle className="w-4 h-4 text-danger-500" />
      default:
        return <AlertTriangle className="w-4 h-4 text-warning-500" />
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-slate-900/80 backdrop-blur-sm border-b border-white/10 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
              <Home className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-white">Streamline Refi Agent</h1>
              <p className="text-xs text-white/50">FHA Streamline & VA IRRRL</p>
            </div>
          </div>
          
          <div className="flex items-center gap-6 text-sm">
            <div className="flex items-center gap-2 text-white/60">
              <Shield className="w-4 h-4" />
              <span>Kind Lending</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col max-w-6xl mx-auto w-full px-6 py-6 overflow-hidden">
        {/* Messages Area */}
        <div 
          ref={messagesContainerRef}
          className="flex-1 overflow-y-auto mb-4 space-y-4"
        >
          {messages.length === 0 && (
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center py-12"
            >
              <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-primary-500/20 to-primary-700/20 flex items-center justify-center">
                <Calculator className="w-10 h-10 text-primary-400" />
              </div>
              <h2 className="text-2xl font-semibold text-white mb-2">
                Streamline Government Refinance
              </h2>
              <p className="text-white/60 mb-8 max-w-md mx-auto">
                Multi-agent underwriting for FHA Streamline and VA IRRRL refinances. 
                Enter an application ID to begin analysis.
              </p>
              
              {/* Quick Start */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 max-w-2xl mx-auto">
                <div className="bg-white/5 rounded-lg p-3 border border-white/10">
                  <FileText className="w-5 h-5 text-primary-400 mb-2" />
                  <p className="text-xs text-white/60">Package Validation</p>
                </div>
                <div className="bg-white/5 rounded-lg p-3 border border-white/10">
                  <Shield className="w-5 h-5 text-primary-400 mb-2" />
                  <p className="text-xs text-white/60">Eligibility Check</p>
                </div>
                <div className="bg-white/5 rounded-lg p-3 border border-white/10">
                  <Clock className="w-5 h-5 text-primary-400 mb-2" />
                  <p className="text-xs text-white/60">Seasoning Analysis</p>
                </div>
                <div className="bg-white/5 rounded-lg p-3 border border-white/10">
                  <Calculator className="w-5 h-5 text-primary-400 mb-2" />
                  <p className="text-xs text-white/60">NTB Calculation</p>
                </div>
              </div>
            </motion.div>
          )}

          <AnimatePresence>
            {messages.map((message, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.05 }}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div className={`max-w-4xl rounded-xl px-4 py-3 ${
                  message.role === 'user' 
                    ? 'bg-primary-600 text-white' 
                    : message.isError 
                      ? 'bg-danger-500/20 border border-danger-500/30 text-white'
                      : 'bg-white/5 border border-white/10 text-white'
                }`}>
                  {message.role === 'assistant' ? (
                    <div className="markdown-content">
                      <ReactMarkdown>{message.content || '...'}</ReactMarkdown>
                    </div>
                  ) : (
                    <p>{message.content}</p>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Loading indicator */}
          {isLoading && currentTool && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-2 text-primary-400 text-sm"
            >
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>{currentTool}...</span>
            </motion.div>
          )}
        </div>

        {/* Test Cases Dropdown */}
        <div className="relative mb-3">
          <button
            onClick={() => setShowTestCases(!showTestCases)}
            className="flex items-center gap-2 text-sm text-white/60 hover:text-white/80 transition-colors"
          >
            <span>Test Cases</span>
            <ChevronDown className={`w-4 h-4 transition-transform ${showTestCases ? 'rotate-180' : ''}`} />
          </button>
          
          <AnimatePresence>
            {showTestCases && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="absolute bottom-full left-0 mb-2 bg-slate-800 border border-white/10 rounded-lg shadow-xl p-2 w-80 z-10"
              >
                <div className="grid gap-1">
                  {TEST_CASES.map((tc) => (
                    <button
                      key={tc.id}
                      onClick={() => selectTestCase(tc)}
                      className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-white/5 transition-colors text-left"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                            tc.program === 'FHA' ? 'bg-primary-500/20 text-primary-400' : 'bg-emerald-500/20 text-emerald-400'
                          }`}>
                            {tc.program}
                          </span>
                          <span className="text-sm text-white font-mono">{tc.id}</span>
                        </div>
                        <p className="text-xs text-white/50 mt-0.5">{tc.desc}</p>
                      </div>
                      {getStatusIcon(tc.expected)}
                    </button>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Input Area */}
        <form onSubmit={handleSubmit} className="relative">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Enter command (e.g., 'Process REFI-FHA-001')"
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-4 pr-14 text-white placeholder-white/40 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/30 transition-all"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="absolute right-3 top-1/2 -translate-y-1/2 w-10 h-10 rounded-lg bg-primary-600 hover:bg-primary-500 disabled:bg-white/10 disabled:cursor-not-allowed flex items-center justify-center transition-colors"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 text-white animate-spin" />
            ) : (
              <Send className="w-5 h-5 text-white" />
            )}
          </button>
        </form>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/5 px-6 py-3">
        <div className="max-w-6xl mx-auto flex items-center justify-between text-xs text-white/40">
          <span>Streamline Government Refinance Checklist v1.0</span>
          <span>Kind Lending AI Automation</span>
        </div>
      </footer>
    </div>
  )
}

export default App
