import Button from './Button';

interface PaginationProps {
  page: number;
  onPageChange: (page: number) => void;
  hasPrevious: boolean;
  hasNext: boolean;
  /** When provided, renders "Page X of Y"; otherwise "Page X". */
  totalPages?: number;
  variant?: 'outline' | 'secondary';
}

/**
 * Previous / page-indicator / Next pagination controls. Single-sourced
 * (todo 222 / M14) — ThreadListPage and SearchPage had copy-pasted blocks that
 * had drifted (button variant, "Page X" vs "Page X of Y", `<=1` vs `===1`).
 * The caller decides whether to render this (the per-page "has more" guard).
 */
export function Pagination({
  page,
  onPageChange,
  hasPrevious,
  hasNext,
  totalPages,
  variant = 'outline',
}: PaginationProps) {
  return (
    <div className="mt-8 flex justify-center items-center gap-2">
      <Button onClick={() => onPageChange(page - 1)} disabled={!hasPrevious} variant={variant}>
        Previous
      </Button>

      <span className="px-4 py-2 text-ink-2">
        Page {page}
        {totalPages !== undefined && ` of ${totalPages}`}
      </span>

      <Button onClick={() => onPageChange(page + 1)} disabled={!hasNext} variant={variant}>
        Next
      </Button>
    </div>
  );
}
