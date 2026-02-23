// web/src/lib/supabaseClient.js
import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
  console.warn("Supabase env not configured (VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY).");
}

const globalKey = "__mugo_supabase__";

export const supabase =
  globalThis[globalKey] ||
  (globalThis[globalKey] = createClient(SUPABASE_URL, SUPABASE_ANON_KEY));