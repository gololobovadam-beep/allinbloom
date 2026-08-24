import type { Metadata } from "next";
import AdminSidebar from "@/components/admin-sidebar";
import Header from "@/components/header";
import { requireAdmin } from "@/lib/auth-session";

export const metadata: Metadata = {
  title: "Admin",
  robots: {
    index: false,
    follow: false,
  },
};

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await requireAdmin();

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 pb-24 pt-6 sm:px-6 sm:pt-10 lg:flex-row lg:items-start lg:px-8">
        <AdminSidebar />
        <div className="flex-1">{children}</div>
      </main>
    </div>
  );
}
