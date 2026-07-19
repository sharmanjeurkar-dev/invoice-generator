import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

// Fail gracefully during the build phase if variables are evaluated early
if (!supabaseUrl || !supabaseAnonKey) {
  if (process.env.NODE_ENV === 'production') {
    console.warn(
      "Supabase environment variables are missing. If this is during a Next.js static build phase, this warning is normal as long as variables are provided at runtime."
    );
  }
}

// Fall back to empty strings during build to prevent compilation crashes
export const supabase = createClient(
  supabaseUrl || 'https://placeholder-url.supabase.co', 
  supabaseAnonKey || 'placeholder-anon-key'
);