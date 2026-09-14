import type { Metadata } from "next";
import "./globals.css";
import { RoleProvider } from "../context/RoleContext";

export const metadata: Metadata = { title: "Outreach Operations · Post-Discharge AI Platform" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <RoleProvider>
          {children}
        </RoleProvider>
      </body>
    </html>
  );
}

