// src/lib/sse.ts
import { API_BASE_URL } from "./config";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export type StreamChunk = { type: 'chunk', content: string } | { type: 'tool_call', name: string, args: any };

export async function* streamChat(message: string, conversationId: string): AsyncGenerator<StreamChunk, void, unknown> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": "dev_key",
    },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });

  if (!response.ok) {
    throw new Error(`Chat API error: ${response.statusText}`);
  }

  const reader = response.body?.getReader();
  const decoder = new TextDecoder("utf-8");

  if (!reader) return;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    
    // Server-Sent Events parsing (basic)
    const lines = chunk.split('\n');
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const dataStr = line.substring(6).trim();
        if (dataStr === '[DONE]') {
          return;
        }
        
        try {
          const parsed = JSON.parse(dataStr);
          if (parsed.type === 'chunk') {
            yield { type: 'chunk', content: parsed.content };
          } else if (parsed.type === 'tool_call') {
            yield { type: 'tool_call', name: parsed.name, args: parsed.args };
          } else if (parsed.type === 'error') {
            throw new Error(parsed.content);
          }
        } catch (e) {
          // Incomplete chunk or parsing error, ignore for now
          console.warn("SSE parse error", e);
        }
      }
    }
  }
}
