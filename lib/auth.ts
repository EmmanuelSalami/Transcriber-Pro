import { betterAuth } from "better-auth";
import { emailOTP } from "better-auth/plugins";
import { Pool } from "pg";

function getBaseUrl(): string {
  // Local dev: no platform env vars → use localhost (ignore BETTER_AUTH_URL)
  if (!process.env.RENDER_EXTERNAL_URL && !process.env.VERCEL_URL) {
    return "http://localhost:3000";
  }
  // Deployed: BETTER_AUTH_URL for custom domain (e.g. your-domain.com), else platform URL
  if (process.env.BETTER_AUTH_URL) return process.env.BETTER_AUTH_URL;
  if (process.env.RENDER_EXTERNAL_URL) return process.env.RENDER_EXTERNAL_URL;
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`; // fallback if ever used
  return "http://localhost:3000";
}

async function sendEmailViaResend(opts: {
  to: string;
  subject: string;
  html: string;
  text?: string;
}) {
  const apiKey = process.env.RESEND_API_KEY;
  const from = process.env.SENDER_EMAIL ?? "noreply@example.com";
  const fromName = process.env.SENDER_NAME ?? "Transcriber Pro";

  if (!apiKey) {
    console.error("[auth] RESEND_API_KEY not set, cannot send email");
    return;
  }

  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: `${fromName} <${from}>`,
      to: [opts.to],
      subject: opts.subject,
      html: opts.html,
      text: opts.text,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    console.error("[auth] Resend API error:", res.status, err);
  }
}

export const auth = betterAuth({
  baseURL: getBaseUrl(),
  trustedOrigins: [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://your-domain.com",
    getBaseUrl(),
  ].filter((o, i, a) => o && a.indexOf(o) === i),
  secret: process.env.BETTER_AUTH_SECRET!,
  database: new Pool({
    connectionString: process.env.DATABASE_URL,
  }),
  emailAndPassword: {
    enabled: true,
    minPasswordLength: 8,
    requireEmailVerification: true,
    sendResetPassword: async ({ user, url }) => {
      void sendEmailViaResend({
        to: user.email,
        subject: "Reset your password - Transcriber Pro",
        html: `Click the link to reset your password: <a href="${url}">${url}</a>`,
        text: `Click the link to reset your password: ${url}`,
      });
    },
  },
  emailVerification: {
    autoSignInAfterVerification: true, // Create session after OTP verify so user lands on home
  },
  socialProviders: {
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    },
  },
  plugins: [
    emailOTP({
      overrideDefaultEmailVerification: true,
      sendVerificationOnSignUp: true, // Send 6-digit OTP on sign-up (no link)
      sendVerificationOTP: async ({ email, otp, type }) => {
        if (type === "email-verification") {
          void sendEmailViaResend({
            to: email,
            subject: "Verify your email - Transcriber Pro",
            html: `Your verification code is: <strong>${otp}</strong>. It expires in 10 minutes.`,
            text: `Your verification code is: ${otp}. It expires in 10 minutes.`,
          });
        }
      },
    }),
  ],
});
