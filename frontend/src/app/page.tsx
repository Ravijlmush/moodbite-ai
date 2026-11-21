"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { CartDrawer } from "@/components/CartDrawer";
import { ComboCard } from "@/components/ComboCard";
import { ContextDrawer } from "@/components/ContextDrawer";
import { CrisisCard } from "@/components/CrisisCard";
import { Header } from "@/components/Header";
import { InputBar } from "@/components/InputBar";
import { MessageBubble } from "@/components/MessageBubble";
import { QuickReplyPills } from "@/components/QuickReplyPills";
import { SwiggyAuthDrawer } from "@/components/SwiggyAuthDrawer";
import { TypingIndicator } from "@/components/TypingIndicator";
import {
  addComboToSwiggyCart,
  connectSwiggyToken,
  disconnectSwiggy,
  fetchHealth,
  fetchSwiggyStatus,
  removeComboFromCart,
  resetSession,
  sendRefineChip,
  streamChatTurn,
} from "@/lib/api";
import {
  CartResponse,
  ChatMessage,
  ChatTurnResponse,
  ComboRecommendation,
  FullUserContext,
  HealthResponse,
  SwiggyAuthStatus,
} from "@/lib/types";

const INITIAL_PILLS = [
  "Drained & tired",
  "Stressed, want spicy",
  "Bored, surprise me",
  "Light & fresh",
];

function makeSessionId(): string {
  return `sess_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
}

function createWelcomeMessage(): ChatMessage {
  return {
    id: "welcome_msg",
    role: "assistant",
    content:
      "Hey—how's the day going? Tell me the vibe and I'll sort out fast Swiggy combos for you.",
    action: "ask_followup",
    quick_reply_pills: INITIAL_PILLS,
    isRefinementList: false,
  };
}

export default function HomePage() {
  const [sessionId, setSessionId] = useState<string>(() => makeSessionId());
  const [messages, setMessages] = useState<ChatMessage[]>(() => [createWelcomeMessage()]);
  const [streamingText, setStreamingText] = useState<string>("");
  const [statusText, setStatusText] = useState<string>("Reading the vibe...");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const [vegOnly, setVegOnly] = useState<boolean>(false);
  const [darkMode, setDarkMode] = useState<boolean>(false);
  const [showStatePill, setShowStatePill] = useState<boolean>(true);
  const [cartOpen, setCartOpen] = useState<boolean>(false);
  const [contextOpen, setContextOpen] = useState<boolean>(false);
  const [swiggyOpen, setSwiggyOpen] = useState<boolean>(false);

  const [addingComboId, setAddingComboId] = useState<string | null>(null);
  const [cart, setCart] = useState<CartResponse>({
    session_id: "",
    items: [],
    total_items: 0,
    total_price_inr: 0,
  });

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [swiggyStatus, setSwiggyStatus] = useState<SwiggyAuthStatus | null>(null);
  const [selectedAddressId, setSelectedAddressId] = useState<string | null>(null);
  const [dailyLimit, setDailyLimit] = useState<number>(20);
  const [dailyRemaining, setDailyRemaining] = useState<number>(20);
  const [fullContext, setFullContext] = useState<FullUserContext | null>(null);
  const [lastLatencyMs, setLastLatencyMs] = useState<number | null>(null);
  const [llmMode, setLlmMode] = useState<string>("offline");
  const [catalogSource, setCatalogSource] = useState<"swiggy_mcp_live" | "demo_fallback">("demo_fallback");

  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fetchHealth()
      .then((h) => {
        setHealth(h);
        setLlmMode(h.llm_provider);
        setDailyLimit(h.daily_request_limit);
        setDailyRemaining(h.daily_requests_remaining);
      })
      .catch(() => undefined);

    fetchSwiggyStatus()
      .then((st) => {
        setSwiggyStatus(st);
        if (st.selected_address_id) {
          setSelectedAddressId(st.selected_address_id);
        }
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText, isLoading]);

  const cartQuantities = useMemo(() => {
    const map: Record<string, number> = {};
    for (const entry of cart.items) {
      map[entry.combo.combo_id] = entry.quantity;
    }
    return map;
  }, [cart.items]);

  function applyTurnResponse(res: ChatTurnResponse, isRefinement: boolean) {
    setFullContext(res.full_context);
    setLastLatencyMs(res.latency_ms);
    setLlmMode(res.llm_mode);
    if (res.catalog_source) {
      setCatalogSource(res.catalog_source);
    }
    if (res.user_context.dietary_type === "veg") {
      setVegOnly(true);
    }

    const assistantMsg: ChatMessage = {
      id: `ast_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      role: "assistant",
      content: res.agent_message,
      action: res.action,
      recommendations: res.recommendations,
      crisis_resources: res.crisis_resources,
      quick_reply_pills: res.quick_reply_pills,
      user_context: res.user_context,
      catalog_source: res.catalog_source,
      isRefinementList: isRefinement || res.action === "recommend_combos",
    };
    setMessages((prev) => [...prev, assistantMsg]);
  }

  async function handleSendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;
    setErrorBanner(null);

    const userMsg: ChatMessage = {
      id: `usr_${Date.now()}`,
      role: "user",
      content: trimmed,
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setStreamingText("");
    setStatusText("Reading the vibe...");

    try {
      const response = await streamChatTurn(
        {
          session_id: sessionId,
          user_id: "usr_web_guest",
          message: trimmed,
          location: { lat: 28.6139, lng: 77.209 },
          active_filters: {
            dietary_type: vegOnly ? "veg" : null,
            max_budget_inr: null,
          },
          address_id: selectedAddressId,
        },
        {
          onStatus: (msg) => setStatusText(msg),
          onToken: (chunk) => setStreamingText((prev) => prev + chunk),
          onQuota: ({ limit, remaining }) => {
            setDailyLimit(limit);
            setDailyRemaining(remaining);
            setHealth((prev) =>
              prev
                ? {
                    ...prev,
                    daily_request_limit: limit,
                    daily_requests_remaining: remaining,
                    daily_requests_used: Math.max(0, limit - remaining),
                  }
                : prev
            );
          },
        }
      );
      setStreamingText("");
      applyTurnResponse(response, false);
    } catch (err) {
      setStreamingText("");
      setErrorBanner(
        err instanceof Error
          ? `${err.message}. Ensure the FastAPI backend is running on port 8000.`
          : "Could not reach the MoodBite backend."
      );
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSelectRefineChip(chip: string) {
    if (isLoading) return;
    setErrorBanner(null);

    const userMsg: ChatMessage = {
      id: `ref_${Date.now()}`,
      role: "user",
      content: chip,
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setStatusText("Updating fast combos near you...");

    try {
      const response = await sendRefineChip({
        session_id: sessionId,
        user_id: "usr_web_guest",
        chip,
        location: { lat: 28.6139, lng: 77.209 },
        active_filters: {
          dietary_type: vegOnly ? "veg" : null,
          max_budget_inr: null,
        },
        address_id: selectedAddressId,
      });
      applyTurnResponse(response, true);
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "Failed to refine combos."
      );
    } finally {
      setIsLoading(false);
    }
  }

  async function handleToggleVegOnly() {
    const nextVeg = !vegOnly;
    setVegOnly(nextVeg);
    const hasRecs = messages.some(
      (m) => m.recommendations && m.recommendations.length > 0
    );
    if (nextVeg && hasRecs && !isLoading) {
      await handleSelectRefineChip("Veg only");
    }
  }

  async function handleAddToCart(combo: ComboRecommendation) {
    setAddingComboId(combo.combo_id);
    setErrorBanner(null);
    try {
      const updatedCart = await addComboToSwiggyCart({
        session_id: sessionId,
        combo,
        address_id: selectedAddressId,
      });
      setCart(updatedCart);
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "Could not add combo to Swiggy cart."
      );
    } finally {
      setAddingComboId(null);
    }
  }

  async function handleRemoveFromCart(comboId: string) {
    try {
      const updated = await removeComboFromCart(sessionId, comboId);
      setCart(updated);
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "Could not remove combo."
      );
    }
  }

  async function handleConnectSwiggyToken(token: string) {
    const st = await connectSwiggyToken(token, selectedAddressId);
    setSwiggyStatus(st);
    if (st.selected_address_id) {
      setSelectedAddressId(st.selected_address_id);
    }
  }

  async function handleDisconnectSwiggy() {
    const st = await disconnectSwiggy();
    setSwiggyStatus(st);
    setSelectedAddressId(null);
    setCatalogSource("demo_fallback");
  }

  async function handleResetSession() {
    await resetSession(sessionId);
    const freshId = makeSessionId();
    setSessionId(freshId);
    setMessages([createWelcomeMessage()]);
    setStreamingText("");
    setFullContext(null);
    setLastLatencyMs(null);
    setErrorBanner(null);
    setCart({
      session_id: freshId,
      items: [],
      total_items: 0,
      total_price_inr: 0,
    });
  }

  return (
    <div
      className="mx-auto flex min-h-screen w-full max-w-[520px] flex-col"
      style={{
        backgroundColor: "var(--bg-primary)",
        borderLeft: "var(--border-hairline)",
        borderRight: "var(--border-hairline)",
      }}
    >
      <Header
        vegOnly={vegOnly}
        onToggleVegOnly={handleToggleVegOnly}
        cartCount={cart.total_items}
        onOpenCart={() => setCartOpen(true)}
        onOpenContext={() => setContextOpen(true)}
        onOpenSwiggy={() => setSwiggyOpen(true)}
        swiggyConnected={Boolean(swiggyStatus?.connected)}
        showStatePill={showStatePill}
        onToggleStatePill={() => setShowStatePill((s) => !s)}
        darkMode={darkMode}
        onToggleTheme={() => setDarkMode((d) => !d)}
        onResetSession={handleResetSession}
      />

      {/* Compact Sub-header Telemetry Strip */}
      <div
        className="flex items-center justify-between px-4 py-1.5"
        style={{
          backgroundColor: "var(--bg-subtle)",
          borderBottom: "var(--border-hairline)",
        }}
      >
        <span
          className="font-mono-meta text-[10px] font-semibold uppercase tracking-[0.06em]"
          style={{ color: "var(--text-secondary)" }}
        >
          {catalogSource === "swiggy_mcp_live" ? "SWIGGY MCP LIVE" : "DEMO CATALOG"} • {llmMode.toUpperCase()}
          {fullContext ? ` • TURN ${fullContext.turn_count}/3` : ""}
        </span>
        <span
          className="font-mono-meta text-[10px] font-semibold uppercase tracking-[0.06em]"
          style={{ color: "var(--text-secondary)" }}
        >
          {dailyLimit - dailyRemaining}/{dailyLimit} TODAY
          {lastLatencyMs !== null ? ` • ${lastLatencyMs.toFixed(0)} MS` : ""}
        </span>
      </div>

      {/* Chat Stream */}
      <main className="flex-1 space-y-5 px-4 py-5">
        {errorBanner ? (
          <div
            className="p-3 text-[13px]"
            style={{
              backgroundColor: "var(--bg-subtle)",
              border: "var(--border-strong)",
              borderRadius: "8px",
              color: "var(--text-primary)",
            }}
          >
            <span className="font-mono-meta font-semibold uppercase">NOTICE: </span>
            {errorBanner}
          </div>
        ) : null}

        {messages.map((msg, index) => {
          const isLatestAssistant = index === messages.length - 1 && msg.role === "assistant";
          return (
            <section key={msg.id} className="space-y-3">
              {showStatePill && msg.user_context ? (
                <div
                  className="font-mono-meta inline-block px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.04em]"
                  style={{
                    backgroundColor: "var(--bg-subtle)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "6px",
                    color: "var(--text-primary)",
                  }}
                >
                  MOOD={msg.user_context.primary_mood.toUpperCase()} | EFFORT={msg.user_context.effort_to_eat.toUpperCase()} | ETA&lt;={msg.user_context.max_eta_mins}M
                  {msg.user_context.search_queries && msg.user_context.search_queries.length > 0
                    ? ` | MCP=${msg.user_context.search_queries[0].toUpperCase()}`
                    : ""}
                </div>
              ) : null}

              <MessageBubble role={msg.role} content={msg.content} />

              {msg.action === "crisis_support" && msg.crisis_resources ? (
                <CrisisCard resources={msg.crisis_resources} />
              ) : null}

              {msg.recommendations && msg.recommendations.length > 0 ? (
                <div className="space-y-3 pt-1">
                  {msg.recommendations.map((combo) => (
                    <ComboCard
                      key={combo.combo_id}
                      combo={combo}
                      inCartQuantity={cartQuantities[combo.combo_id] || 0}
                      adding={addingComboId === combo.combo_id}
                      onAddToCart={handleAddToCart}
                    />
                  ))}
                </div>
              ) : null}

              {isLatestAssistant && msg.quick_reply_pills && msg.quick_reply_pills.length > 0 ? (
                <QuickReplyPills
                  pills={msg.quick_reply_pills}
                  label={msg.isRefinementList ? "REFINE LIST:" : undefined}
                  disabled={isLoading}
                  onSelect={(pill) =>
                    msg.isRefinementList
                      ? handleSelectRefineChip(pill)
                      : handleSendMessage(pill)
                  }
                />
              ) : null}
            </section>
          );
        })}

        {isLoading ? (
          streamingText ? (
            <MessageBubble role="assistant" content={streamingText} />
          ) : (
            <TypingIndicator statusText={statusText} />
          )
        ) : null}

        <div ref={bottomRef} />
      </main>

      <InputBar disabled={isLoading} onSend={handleSendMessage} />

      <CartDrawer
        open={cartOpen}
        cart={cart}
        onClose={() => setCartOpen(false)}
        onRemoveItem={handleRemoveFromCart}
      />

      <ContextDrawer
        open={contextOpen}
        context={fullContext}
        health={health}
        lastLatencyMs={lastLatencyMs}
        llmMode={llmMode}
        onClose={() => setContextOpen(false)}
      />

      <SwiggyAuthDrawer
        open={swiggyOpen}
        status={swiggyStatus}
        selectedAddressId={selectedAddressId}
        onSelectAddress={(aid) => setSelectedAddressId(aid)}
        onConnectToken={handleConnectSwiggyToken}
        onDisconnect={handleDisconnectSwiggy}
        onClose={() => setSwiggyOpen(false)}
      />
    </div>
  );
}
