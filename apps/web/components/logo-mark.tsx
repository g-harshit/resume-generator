/** The logo: a page with a folded corner and a check. Below ~40px the text lines are
 *  dropped and the check thickened, so it stays crisp (brand/logo-mark-small.svg). */
export function LogoMark({ size = 32, className = "" }: { size?: number; className?: string }) {
  const small = size < 40;
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" className={`shrink-0 ${className}`}>
      <path d="M18 6H40L50 16V54A4 4 0 0 1 46 58H18A4 4 0 0 1 14 54V10A4 4 0 0 1 18 6Z" fill="var(--color-accent)" />
      <path d="M40 6V12A4 4 0 0 0 44 16H50Z" fill="#9fc2b5" />
      {small ? (
        <path d="M22 41L29 48L43 34" stroke="var(--color-ground)" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      ) : (
        <>
          <path d="M21 24H37M21 31H43" stroke="var(--color-ground)" strokeWidth="3.2" strokeLinecap="round" fill="none" />
          <path d="M22 43L28.5 49.5L42 36" stroke="var(--color-ground)" strokeWidth="4.6" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        </>
      )}
    </svg>
  );
}
