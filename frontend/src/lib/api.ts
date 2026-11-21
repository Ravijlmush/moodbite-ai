import {
  CartResponse,
  ChatTurnResponse,
  ComboRecommendation,
  DietaryType,
  HealthResponse,
  StressSuiteReport,
  SwiggyAuthStatus,
} from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export interface TurnPayload {
  session_id: string;
  user_id: string;
  message: string;
  location: { lat: number; lng: number };
  active_filters: {
    dietary_type: DietaryType;
    max_budget_inr: number | null;
  };
  address_id?: string | null;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Health check failed (${res.status})`);
  }
  return res.json();
}

export async function fetchStressReport(): Promise<StressSuiteReport> {
  const res = await fetch(`${API_BASE}/api/v1/stress-report`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Stress report fetch failed (${res.status})`);
  }
  return res.json();
}

export class RateLimitError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RateLimitError";
  }
}

export async function sendChatTurn(payload: TurnPayload): Promise<ChatTurnResponse> {
  const res = await fetch(`${API_BASE}/api/v1/chat/turn`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (res.status === 429) {
    const errBody = await res.json().catch(() => null);
    throw new RateLimitError(
      errBody?.detail?.message || "Daily request limit reached (20/20). Resets at midnight UTC."
    );
  }
  if (!res.ok) {
    throw new Error(`Chat turn failed (${res.status})`);
  }
  return res.json();
}

export interface StreamHandlers {
  onStatus?: (message: string) => void;
  onToken?: (text: string) => void;
  onRecommendations?: (recs: ComboRecommendation[]) => void;
  onQuota?: (info: { limit: number; remaining: number }) => void;
}

export async function streamChatTurn(
  payload: TurnPayload,
  handlers: StreamHandlers
): Promise<ChatTurnResponse> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/chat/turn/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (res.status === 429) {
      const errBody = await res.json().catch(() => null);
      throw new RateLimitError(
        errBody?.detail?.message || "Daily request limit reached (20/20). Resets at midnight UTC."
      );
    }

    const limitHeader = res.headers.get("X-RateLimit-Limit");
    const remHeader = res.headers.get("X-RateLimit-Remaining");
    if (limitHeader && remHeader && handlers.onQuota) {
      handlers.onQuota({
        limit: Number(limitHeader),
        remaining: Number(remHeader),
      });
    }

    if (!res.ok || !res.body) {
      return sendChatTurn(payload);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalPayload: ChatTurnResponse | null = null;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split(/\r?\n\r?\n/);
      buffer = events.pop() || "";

      for (const rawEvent of events) {
        const lines = rawEvent.split(/\r?\n/);
        let eventName = "message";
        const dataLines: string[] = [];
        for (const line of lines) {
          if (line.startsWith("event:")) {
            eventName = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).trim());
          }
        }
        if (dataLines.length === 0) continue;
        const rawData = dataLines.join("\n");
        const parsed = JSON.parse(rawData);

        if (eventName === "status" && handlers.onStatus) {
          handlers.onStatus(parsed.message);
        } else if (eventName === "token" && handlers.onToken) {
          handlers.onToken(parsed.text);
        } else if (eventName === "recommendations" && handlers.onRecommendations) {
          handlers.onRecommendations(parsed as ComboRecommendation[]);
        } else if (eventName === "done") {
          finalPayload = parsed as ChatTurnResponse;
        }
      }
    }

    if (finalPayload) {
      return finalPayload;
    }
    return sendChatTurn(payload);
  } catch (err) {
    if (err instanceof RateLimitError) {
      throw err;
    }
    return sendChatTurn(payload);
  }
}

export async function sendRefineChip(payload: {
  session_id: string;
  user_id: string;
  chip: string;
  location: { lat: number; lng: number };
  active_filters?: { dietary_type: DietaryType; max_budget_inr: number | null };
  address_id?: string | null;
}): Promise<ChatTurnResponse> {
  const res = await fetch(`${API_BASE}/api/v1/chat/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Refine failed (${res.status})`);
  }
  return res.json();
}

export async function addComboToSwiggyCart(payload: {
  session_id: string;
  combo: ComboRecommendation;
  address_id?: string | null;
}): Promise<CartResponse> {
  const res = await fetch(`${API_BASE}/api/v1/cart/add-combo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: payload.session_id,
      restaurant_id: payload.combo.restaurant.id,
      item_ids: payload.combo.items.map((it) => it.item_id),
      combo_id: payload.combo.combo_id,
      combo: payload.combo,
      address_id: payload.address_id ?? null,
    }),
  });
  if (!res.ok) {
    throw new Error(`Add combo to Swiggy cart failed (${res.status})`);
  }
  return res.json();
}

export async function fetchSwiggyStatus(): Promise<SwiggyAuthStatus> {
  const res = await fetch(`${API_BASE}/auth/swiggy/status`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Swiggy status failed (${res.status})`);
  }
  return res.json();
}

export async function connectSwiggyToken(
  accessToken: string,
  addressId?: string | null
): Promise<SwiggyAuthStatus> {
  const res = await fetch(`${API_BASE}/auth/swiggy/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ access_token: accessToken, address_id: addressId ?? null }),
  });
  if (!res.ok) {
    throw new Error(`Swiggy token connect failed (${res.status})`);
  }
  return res.json();
}

export async function disconnectSwiggy(): Promise<SwiggyAuthStatus> {
  const res = await fetch(`${API_BASE}/auth/swiggy/logout`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`Swiggy logout failed (${res.status})`);
  }
  return res.json();
}

export function getSwiggyOAuthLoginUrl(): string {
  return `${API_BASE}/auth/swiggy/login`;
}

export async function addComboToCart(payload: {
  session_id: string;
  combo_id: string;
  quantity?: number;
  combo?: ComboRecommendation;
}): Promise<CartResponse> {
  const res = await fetch(`${API_BASE}/api/v1/cart/add`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Add to cart failed (${res.status})`);
  }
  return res.json();
}

export async function removeComboFromCart(
  sessionId: string,
  comboId: string
): Promise<CartResponse> {
  const res = await fetch(
    `${API_BASE}/api/v1/cart/${encodeURIComponent(sessionId)}/${encodeURIComponent(comboId)}`,
    { method: "DELETE" }
  );
  if (!res.ok) {
    throw new Error(`Remove from cart failed (${res.status})`);
  }
  return res.json();
}

export async function resetSession(sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/api/v1/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  }).catch(() => undefined);
}
