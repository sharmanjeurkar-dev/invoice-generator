import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

// Create a single supabase client for interacting with your database
export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);