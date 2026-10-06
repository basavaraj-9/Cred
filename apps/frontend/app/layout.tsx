import type { Metadata } from "next";
import "./styles.css";
import { RuntimeSession } from "@/components/runtime-session";
import { RuntimeAccess } from "@/components/runtime-access";

export const metadata: Metadata = {
  title: "Company Intelligence Platform",
  description: "Foundation for credit decisions and Indian stock intelligence",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><main><RuntimeSession /><RuntimeAccess>{children}</RuntimeAccess></main></body></html>;
}
