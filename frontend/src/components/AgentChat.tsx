import { useEffect, useRef, useState } from "react";

import { agentChat, type AgentChatResponse } from "../api/modules";

type ChatMessage = {
  role: "user" | "agent";
  content: string;
  response?: AgentChatResponse;
};

export function AgentChat({ spot, onClose }: { spot: string; onClose: () => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "agent",
      content: `你好，我是「${spot}」的经营分析 Agent。\n你可以问我客流预测、波动原因、运营建议，或者做反事实推演。`,
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sessionId] = useState(() => `sess-${Date.now()}`);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  async function send(text?: string) {
    const message = (text ?? input).trim();
    if (!message || busy) return;

    setInput("");
    setMessages(prev => [...prev, { role: "user", content: message }]);
    setBusy(true);
    try {
      const response = await agentChat(message, spot, sessionId);
      setMessages(prev => [...prev, { role: "agent", content: response.reply, response }]);
    } catch {
      setMessages(prev => [
        ...prev,
        { role: "agent", content: "抱歉，请求失败了，请确认后端服务已启动。" },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="agent-dialog" role="dialog" aria-label="咨询 Agent">
      <header className="agent-dialog-head">
        <div>
          <strong>经营分析 Agent</strong>
          <small>{spot} · 证据约束回答</small>
        </div>
        <button type="button" className="agent-dialog-close" onClick={onClose} aria-label="关闭">×</button>
      </header>

      <div className="agent-dialog-body">
        {messages.map((item, index) => (
          <div key={index} className={`agent-msg agent-msg-${item.role}`}>
            <div className="agent-bubble">{item.content}</div>

            {item.response?.evidence && item.response.evidence.length > 0 && (
              <div className="agent-evidence">
                {item.response.evidence.map((ev, i) => (
                  <span key={i} className="agent-evidence-chip" title={ev.ref}>
                    {ev.label}: {ev.value}
                  </span>
                ))}
              </div>
            )}

            {item.response?.suggestions && item.response.suggestions.length > 0 && (
              <div className="agent-suggestions">
                {item.response.suggestions.map((sug, i) => (
                  <button key={i} type="button" onClick={() => send(sug)} disabled={busy}>
                    {sug}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="agent-msg agent-msg-agent"><div className="agent-bubble agent-typing">正在分析…</div></div>}
        <div ref={bottomRef} />
      </div>

      <form
        className="agent-dialog-input"
        onSubmit={event => {
          event.preventDefault();
          send();
        }}
      >
        <input
          ref={inputRef}
          value={input}
          onChange={event => setInput(event.target.value)}
          placeholder="问我客流、原因、建议，或「如果下雨呢」…"
          aria-label="向 Agent 提问"
        />
        <button type="submit" disabled={busy || !input.trim()}>发送</button>
      </form>
    </div>
  );
}