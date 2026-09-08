import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { isWebGLAvailable } from "@/lib/particles/webgl";
import { ParticleCanvas } from "@/components/welcome/ParticleCanvas";

/**
 * Static fallback shown when WebGL is unavailable — a pure-black splash with a
 * faint ice-blue glow where the particle glyph would be. Never a blank page:
 * the CTA below is always rendered.
 */
function StaticSplash() {
  return (
    <div
      data-testid="welcome-static-splash"
      className="absolute inset-0 bg-black"
      aria-hidden="true"
    >
      <div className="absolute left-1/2 top-1/2 h-[46vmin] w-[72vmin] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(closest-side,rgba(159,198,255,0.22),rgba(234,244,255,0.06),transparent)]" />
    </div>
  );
}

/**
 * WelcomePage — the public, pre-login splash. A luminous particle glyph
 * ("YKM" + cat head) fills the viewport on black; the only UI is a single
 * "进入平台" CTA leading to /login. No headline or tagline — the particle art
 * carries the brand. Lazy-loaded so Three.js stays out of the main bundle.
 */
export default function WelcomePage() {
  const navigate = useNavigate();
  const webgl = useMemo(() => isWebGLAvailable(), []);

  return (
    <div className="relative min-h-dvh w-full overflow-hidden bg-black">
      {webgl ? <ParticleCanvas /> : <StaticSplash />}

      <div className="absolute inset-x-0 bottom-14 z-10 flex justify-center px-6">
        <Button
          size="lg"
          onClick={() => navigate("/login")}
          className="h-11 gap-2 rounded-full border border-white/25 bg-white/10 px-7 text-base font-medium text-white shadow-[0_0_30px_rgba(159,198,255,0.25)] backdrop-blur-md transition-colors hover:border-white/45 hover:bg-white/20 hover:text-white focus-visible:ring-2 focus-visible:ring-white/60"
        >
          进入平台
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
