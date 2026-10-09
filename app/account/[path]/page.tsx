"use client";

import { AccountView } from "@/components/auth/AccountView";
import { useParams } from "next/navigation";

export default function AccountPage() {
  const params = useParams();
  const path = (params?.path as string) ?? "settings";

  return (
    <div className="container mx-auto max-w-2xl py-8">
      <AccountView pathname={`/account/${path}`} />
    </div>
  );
}
