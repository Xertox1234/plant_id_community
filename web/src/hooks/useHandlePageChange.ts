import { useCallback } from 'react';
import type { SetURLSearchParams } from 'react-router-dom';

/**
 * Shared forum pagination handler (todo 222 / M14): updates the `page` URL search
 * param and scrolls to the top. Was a byte-identical `useCallback` in
 * ThreadListPage and SearchPage.
 */
export function useHandlePageChange(
  setSearchParams: SetURLSearchParams
): (newPage: number) => void {
  return useCallback(
    (newPage: number) => {
      setSearchParams((prev) => {
        const newParams = new URLSearchParams(prev);
        newParams.set('page', newPage.toString());
        return newParams;
      });
      window.scrollTo({ top: 0, behavior: 'smooth' });
    },
    [setSearchParams]
  );
}
