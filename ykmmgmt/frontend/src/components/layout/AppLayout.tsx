import { Outlet } from "react-router-dom";
import { Menu } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Sidebar } from "./Sidebar";
import { useState } from "react";

export function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar — hidden on small screens and in print (PDF export) */}
      <aside className="hidden md:flex md:w-60 md:flex-col md:border-r md:bg-card print:hidden">
        <Sidebar />
      </aside>

      {/* Mobile sidebar — Sheet overlay */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetTrigger className="fixed left-3 top-3 z-40 inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-muted md:hidden print:hidden">
          <Menu className="h-5 w-5" />
        </SheetTrigger>
        <SheetContent side="left" className="w-60 p-0">
          <Sidebar onNavClick={() => setMobileOpen(false)} />
        </SheetContent>
      </Sheet>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="container mx-auto p-6 pt-14 md:pt-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
