import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service | Transcriber Pro",
  description: "Terms of service for Transcriber Pro - usage terms and conditions.",
};

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-[#0a0a0a] bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(120,119,198,0.3),rgba(255,255,255,0))] p-6">
      <article className="max-w-3xl mx-auto prose prose-invert prose-zinc">
        <h1 className="text-3xl font-bold text-white/90 mt-4">Terms of Service</h1>
        <p className="text-white/60 text-sm">Last updated: March 12, 2026</p>
        <p className="text-white/70">
          Welcome to Transcriber Pro. By using our service at your-domain.com (&quot;Service&quot;), you agree to these Terms of Service (&quot;Terms&quot;). If you do not agree, please do not use the Service.
        </p>

        <h2 className="text-xl font-semibold text-white/90 mt-8">1. Service Description</h2>
        <p className="text-white/70">
          Transcriber Pro is a transcription service that converts audio and video into text. The Service is provided by [Your Company].
        </p>

        <h2 className="text-xl font-semibold text-white/90 mt-8">2. Account Registration</h2>
        <p className="text-white/70">
          You must create an account (for example, via Google Sign-In) to use the Service. You are responsible for maintaining the security of your account and for all activity under it.
        </p>

        <h2 className="text-xl font-semibold text-white/90 mt-8">3. Acceptable Use</h2>
        <p className="text-white/70">
          You agree to use the Service only for lawful purposes. You may not:
        </p>
        <ul className="text-white/70 list-disc pl-6 space-y-1">
          <li>Transcribe content that infringes intellectual property rights, is defamatory, or otherwise illegal</li>
          <li>Attempt to circumvent usage limits, access controls, or security measures</li>
          <li>Use the Service to harm, harass, or defraud others</li>
          <li>Resell or redistribute the Service without authorization</li>
        </ul>
        <p className="text-white/70 mt-4">
          We reserve the right to suspend or terminate accounts that violate these terms.
        </p>

        <h2 className="text-xl font-semibold text-white/90 mt-8">4. Credits and Billing</h2>
        <p className="text-white/70">
          Transcription usage is measured in minutes. Free tiers and paid credits apply as described in the Service. Paid top-ups are non-refundable except where required by law.
        </p>

        <h2 className="text-xl font-semibold text-white/90 mt-8">5. Intellectual Property</h2>
        <p className="text-white/70">
          You retain ownership of content you submit. By submitting content for transcription, you grant us a limited license to process it for providing the Service. We do not claim ownership of your transcripts.
        </p>

        <h2 className="text-xl font-semibold text-white/90 mt-8">6. Limitation of Liability</h2>
        <p className="text-white/70">
          The Service is provided &quot;as is&quot; without warranties of any kind. To the maximum extent permitted by law, we are not liable for indirect, incidental, special, or consequential damages, or any loss of data or revenue arising from your use of the Service.
        </p>

        <h2 className="text-xl font-semibold text-white/90 mt-8">7. Changes</h2>
        <p className="text-white/70">
          We may update these Terms from time to time. Continued use of the Service after changes constitutes acceptance of the new Terms.
        </p>

        <h2 className="text-xl font-semibold text-white/90 mt-8">8. Contact</h2>
        <p className="text-white/70">
          For questions about these Terms, contact us at:{" "}
          <a
            href="mailto:support@example.com"
            className="text-blue-400 hover:text-blue-300"
          >
            support@example.com
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
