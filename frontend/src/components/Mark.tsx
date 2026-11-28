/** The AetherAuth "A" mark. Inherits the surrounding text colour. */
export function Mark({ className = "h-6 w-auto" }: { className?: string }) {
  return (
    <svg viewBox="648 246 626 520" className={className} fill="currentColor" aria-hidden="true">
      <path d="M651 763 726 620C737 598 755 589 780 589H1001C1007 589 1010 584 1010 578S1007 567 1001 567H861C825 564 797 540 797 507 797 495 800 486 805 475L908 284C920 262 939 249 961 249S1003 262 1015 284L1271 763H1200L961 317 862 501C860 504 861 505 864 505H1003C1044 505 1073 538 1073 578S1044 651 1003 651H793C786 651 781 654 778 660L722 763Z" />
    </svg>
  );
}

/** Mark plus wordmark, used in headers. */
export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 text-fg ${className}`}>
      <Mark className="h-5 w-auto" />
      <span className="text-[17px] font-semibold tracking-tight">AetherAuth</span>
    </span>
  );
}
