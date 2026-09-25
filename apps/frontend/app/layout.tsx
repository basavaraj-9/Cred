import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "Company Intelligence Platform",
  description: "Foundation for credit decisions and Indian stock intelligence",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><main>{children}</main></body></html>;
}
