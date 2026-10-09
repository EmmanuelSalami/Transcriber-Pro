import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy | Transcriber Pro",
  description: "Privacy policy for Transcriber Pro - how we collect, use, and protect your data.",
};

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-[#0a0a0a] bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(120,119,198,0.3),rgba(255,255,255,0))] p-6">
      <article className="max-w-3xl mx-auto prose prose-invert prose-zinc">
        <h1 className="text-3xl font-bold text-white/90 mt-4">Privacy Policy</h1>
        <p className="text-white/60 text-sm">Last updated: March 12, 2026</p>
        <p className="text-white/70">
          Transcriber Pro (&quot;we&quot;, &quot;our&quot;, or &quot;us&quot;) is operated by [Your Company] at your-domain.com. This privacy policy explains how we collect, use, store, and protect your information when you use our transcription service.
        </p>

        <h2 className="text-xl font-semibold text-white/90 mt-8">Google User Data</h2>
        <p className="text-white/70">
          When you sign in with Google OAuth, we receive the following information from Google:
        </p>
        <ul className="text-white/70 list-disc pl-6 space-y-1">
          <li>Your name</li>
          <li>Your email address</li>
          <li>Your profile picture (if provided by Google)</li>
        </ul>
        <p className="text-white/70 mt-4">
          We collect this data to authenticate you and manage your account. We do not use it for any purpose other than providing and improving our transcription service.
        </p>

        <h2 className="text-xl font-semibold text-white/90 mt-8">How We Use Your Data</h2>
        <p className="text-white/70">
          We use your data solely to provide you with the services you requested, including:
        </p>
        <ul className="text-white/70 list-disc pl-6 space-y-1">
          <li>Account creation and authentication</li>
          <li>Managing your transcription credits and usage</li>
          <li>Displaying your profile in the app</li>
          <li>Communicating with you about your account when necessary</li>
        </ul>
        <p className="text-white/70 mt-4">
          We will not sell your data to third parties. We will not use your data for advertising, retargeting, interest-based ads, AI model training, or any purpose other than providing or improving our application&apos;s functionality.
        </p>

        <h2 className="text-xl font-semibold text-white/90 mt-8">Sharing and Disclosure</h2>
        <p className="text-white/70">
          We do not transfer or disclose your information to third parties for purposes other than providing our services. We may share data only with service providers who help us operate the app (for example, our hosting provider and authentication provider). These providers are bound by contractual obligations to protect your data.
        </p>

        <h2 className="text-xl font-semibold text-white/90 mt-8">Data Protection</h2>
        <p className="text-white/70">
          We use encryption and industry-standard security practices to protect the confidentiality of your data. Sensitive data is transmitted over HTTPS and stored securely.
        </p>

        <h2 className="text-xl font-semibold text-white/90 mt-8">Data Retention and Deletion</h2>
        <p className="text-white/70">
          We retain your personal information for as long as needed to fulfill the purposes outlined in this privacy policy, unless a longer retention period is required by law. When the data retention period expires, we will delete or destroy it.
        </p>
        <p className="text-white/70 mt-4">
          You may request that your data be deleted at any time by contacting us (see User Rights below).
        </p>

        <h2 className="text-xl font-semibold text-white/90 mt-8">User Rights</h2>
        <p className="text-white/70">
          You have the right to:
        </p>
        <ul className="text-white/70 list-disc pl-6 space-y-1">
          <li><strong>Access</strong> your personal data we hold</li>
          <li><strong>Correct</strong> inaccurate or incomplete data</li>
          <li><strong>Delete</strong> your data upon request</li>
        </ul>
        <p className="text-white/70 mt-4">
          To exercise these rights, please contact us at the email below. We will respond to requests within a reasonable time frame.
        </p>

        <h2 className="text-xl font-semibold text-white/90 mt-8">Contact</h2>
        <p className="text-white/70">
          For privacy-related requests or questions, contact us at:{" "}
          <a
            href="mailto:privacy@example.com"
            className="text-blue-400 hover:text-blue-300"
          >
            privacy@example.com
          </a>
        </p>

        <div className="mt-12 pt-6 border-t border-white/10">
          <Link href="/" className="text-blue-400 hover:text-blue-300">
            ← Back to Transcriber Pro
          </Link>
        </div>
      </article>
    </main>
  );
}
