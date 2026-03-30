export default function CanvasLayout({ children }: { children: React.ReactNode }) {
 return (
 <main id="main-content" tabIndex={-1} className="min-h-dvh focus:outline-none">
 {children}
 </main>
 );
}
