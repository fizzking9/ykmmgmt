import { Outlet } from "react-router-dom";
import { Menu, ScanSearch } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useDeviceAnalysisContext } from "@/contexts/DeviceAnalysisContext";
import { Sidebar } from "./Sidebar";
import { useState } from "react";

export function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { openDeviceAnalysis } = useDeviceAnalysisContext();

  return (
    <div className="flex min-h-dvh">
      {/* Skip-to-content link — visible on first Tab press */}
      <a href="#main" className="skip-link">
        跳到主要内容
      </a>

      {/* Desktop sidebar — hidden on small screens and in print (PDF export) */}
      <aside className="hidden md:flex md:w-60 md:flex-col md:border-r md:bg-card print:hidden">
        <Sidebar />
      </aside>

      {/* Mobile sidebar — Sheet overlay */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetTrigger
          aria-label="打开导航菜单"
          className="touch-manipulation fixed left-3 top-3 z-40 inline-flex h-9 w-9 items-center justify-center rounded-md transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:hidden print:hidden"
        >
          <Menu className="h-5 w-5" />
        </SheetTrigger>
        <SheetContent side="left" className="w-60 p-0">
          <Sidebar onNavClick={() => setMobileOpen(false)} />
        </SheetContent>
      </Sheet>

      {/* Main content */}
      <main id="main" className="flex-1 overflow-auto">
        {/* Global top bar — hosts the 设备分析 entry tag */}
        <header className="sticky top-0 z-30 flex h-12 items-center justify-start gap-2 border-b bg-background/95 pr-4 pl-14 backdrop-blur print:hidden md:pl-4">
          <button
            type="button"
            onClick={() => openDeviceAnalysis()}
            className="touch-manipulation inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ScanSearch className="h-3.5 w-3.5" />
            设备分析
          </button>
        </header>
        <div className="container mx-auto p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
