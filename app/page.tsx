import TranscriptionForm from "@/components/TranscriptionForm";

export default function Home() {
  return (
    <main className="min-h-screen bg-[#0a0a0a] bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(120,119,198,0.3),rgba(255,255,255,0))] flex flex-col items-center justify-center p-4">
      <TranscriptionForm />
    </main>
  );
}
