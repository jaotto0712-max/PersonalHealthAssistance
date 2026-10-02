export function DisclaimerBanner() {
  return (
    <div
      role="note"
      aria-label="Medical disclaimer"
      className="flex items-start gap-2 border-l-4 border-gator-orange bg-gator-orange-tint px-4 py-2 text-sm text-gator-blue-dark"
    >
      <span aria-hidden className="text-base leading-5">⚠</span>
      <p>
        <strong>General health information only — not medical advice.</strong> Always check with your clinician.
        In an emergency, call <strong>911</strong>. In a mental-health crisis, call or text <strong>988</strong>.
      </p>
    </div>
  )
}
