// lib/auth-server.ts
//
// This is the SERVER half of Better Auth (your existing `lib/auth.ts` is the
// CLIENT half — createAuthClient — and stays exactly as it is, no changes needed).
//
// This file is what actually talks to Neon. It:
//   1. Opens a Postgres pool against DATABASE_URL (your Neon connection string)
//   2. Enables email+password auth
//   3. Accepts `firm_name` as an extra signup field (matches what login/page.tsx sends)
//   4. On every new user, auto-provisions a `firm_settings` row + a `profiles`
//      row linking user -> firm, since that's what api.py's
//      GET /api/users/{user_id}/profile endpoint reads from.

import { betterAuth } from "better-auth";
import { Pool } from "pg";

// Neon requires SSL. rejectUnauthorized:false avoids local CA-chain issues;
// if you'd rather validate the cert, drop this and instead append
// `?sslmode=require` to DATABASE_URL (see .env.example).
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false },
});

export const auth = betterAuth({
  database: pool,

  baseURL: process.env.NEXT_PUBLIC_AUTH_URL,
  secret: process.env.BETTER_AUTH_SECRET, // openssl rand -base64 32

  emailAndPassword: {
    enabled: true,
  },

  // Lets signUp.email({ ..., firm_name }) actually reach the server.
  // Requires a matching `firm_name text` column on the "user" table —
  // see migrations.sql.
  user: {
    additionalFields: {
      firm_name: {
        type: "string",
        required: false,
        input: true,
      },
    },
  },

  trustedOrigins: [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "https://ledgerai-smoky.vercel.app",
  ],

  databaseHooks: {
    user: {
      create: {
        after: async (user) => {
          // Provision a firm + profile row for the brand-new user so that
          // api.py's /api/users/{user_id}/profile lookup (SELECT firm_id
          // FROM profiles WHERE id = $1) doesn't 404 on first login.
          const firmName =
            (user as any).firm_name?.trim() || `${user.name || "New"}'s Firm`;

          const client = await pool.connect();
          try {
            await client.query("BEGIN");

            const firmResult = await client.query(
              `INSERT INTO firm_settings (id, firm_name, next_invoice_number, updated_at)
               VALUES (gen_random_uuid(), $1, 1, NOW())
               RETURNING id`,
              [firmName]
            );
            const firmId = firmResult.rows[0].id;

            await client.query(
              `INSERT INTO profiles (id, firm_id)
               VALUES ($1::uuid, $2::uuid)
               ON CONFLICT (id) DO UPDATE SET firm_id = EXCLUDED.firm_id`,
              [user.id, firmId]
            );

            await client.query("COMMIT");
          } catch (err) {
            await client.query("ROLLBACK");
            console.error("🚨 Failed to provision firm for new user:", err);
            // We deliberately don't throw here — the user account was already
            // created; AuthProvider's retry loop will just keep polling
            // /profile until this is fixed, rather than breaking signup.
          } finally {
            client.release();
          }
        },
      },
    },
  },
});