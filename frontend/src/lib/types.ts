export type DietaryType = "veg" | "jain" | "vegan" | "eggetarian" | "halal" | "non_veg" | "any" | null;
export type NextAction = "ask_followup" | "recommend_combos" | "crisis_support";

export interface ComboItem {
  item_id: string;
  name: string;
  price_inr: number;
  dietary_type: "veg" | "egg" | "non_veg";
  category: string;
}

export interface ComboRestaurant {
  id: string;
  name: string;
  rating: number;
  eta_mins: number;
}

export interface ComboRecommendation {
  combo_id: string;
  mood_badge: string;
  title: string;
  restaurant: ComboRestaurant;
  items: ComboItem[];
  total_price_inr: number;
  why_it_fits: string;
  match_score: number;
  dietary_type: "veg" | "egg" | "non_veg";
  coupon_badge?: string | null;
  source?: "swiggy_mcp_live" | "demo_fallback";
}

export interface UserContextSummary {
  primary_mood: string;
  energy_level: "low" | "medium" | "high";
  effort_to_eat: "zero_mess" | "standard";
  max_eta_mins: number;
  dietary_type: DietaryType;
  allergies: string[];
  max_budget_inr: number | null;
  craving_profiles: string[];
  search_queries?: string[];
  spice_tolerance: string;
  state_confidence: number;
}

export interface FullUserContext {
  session_id: string;
  turn_count: number;
  user_state: {
    primary_mood: string;
    emotional_valence: number;
    energy_level: string;
    stress_level: string;
    goal: string;
  };
  food_preferences: {
    craving_profiles: string[];
    search_queries?: string[];
    spice_tolerance: string;
    effort_to_eat: string;
    portion_size: string;
    excluded_ingredients: string[];
  };
  hard_constraints: {
    dietary_type: DietaryType;
    allergies: string[];
    max_budget_inr: number | null;
    max_eta_mins: number;
  };
  routing: {
    state_confidence: number;
    next_action: NextAction;
    clarifying_question: string | null;
  };
}

export interface CrisisResource {
  name: string;
  contact: string;
  availability: string;
  region: string;
}

export interface ChatTurnResponse {
  session_id: string;
  turn_count: number;
  action: NextAction;
  agent_message: string;
  user_context: UserContextSummary;
  full_context: FullUserContext;
  recommendations: ComboRecommendation[];
  quick_reply_pills: string[];
  crisis_resources: CrisisResource[];
  latency_ms: number;
  llm_mode: string;
  catalog_source?: "swiggy_mcp_live" | "demo_fallback";
}

export interface CartEntry {
  combo: ComboRecommendation;
  quantity: number;
  line_total_inr: number;
}

export interface CartResponse {
  session_id: string;
  items: CartEntry[];
  total_items: number;
  total_price_inr: number;
  swiggy_synced?: boolean;
  swiggy_message?: string | null;
}

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  llm_provider: string;
  catalog_restaurants: number;
  catalog_items: number;
  storage_backend: string;
  catalog_backend: string;
  daily_request_limit: number;
  daily_requests_used: number;
  daily_requests_remaining: number;
  swiggy_mcp_connected?: boolean;
  swiggy_mcp_url?: string;
}

export interface SwiggyAddress {
  address_id: string;
  label: string;
  address_line: string;
  lat?: number | null;
  lng?: number | null;
}

export interface SwiggyAuthStatus {
  connected: boolean;
  mcp_url: string;
  demo_fallback_mode: boolean;
  selected_address_id?: string | null;
  addresses: SwiggyAddress[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  action?: NextAction;
  recommendations?: ComboRecommendation[];
  crisis_resources?: CrisisResource[];
  quick_reply_pills?: string[];
  user_context?: UserContextSummary;
  catalog_source?: "swiggy_mcp_live" | "demo_fallback";
  isRefinementList?: boolean;
}
