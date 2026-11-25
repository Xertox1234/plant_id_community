import { useEffect, useState, type ComponentProps, type ComponentType } from 'react';
import { logger } from '../../utils/logger';
import Button from '../ui/Button';
import type TipTapEditor from './TipTapEditor';

type EditorProps = ComponentProps<typeof TipTapEditor>;

// Kept once loaded, so a remount (a new `key`) renders the editor at once.
let loadedEditor: ComponentType<EditorProps> | null = null;

/**
 * The composer, downloaded when it is first rendered (audit F110): about
 * 147 KB that a member only reading a thread never needs. Not React.lazy,
 * which keeps a failed download for good; here Retry asks again.
 */
export default function LazyTipTapEditor(props: EditorProps) {
  const [Editor, setEditor] = useState<ComponentType<EditorProps> | null>(() => loadedEditor);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (Editor) return;
    let ignore = false;
    import('./TipTapEditor').then(
      (module) => {
        loadedEditor = module.default;
        if (!ignore) setEditor(() => module.default);
      },
      (error: unknown) => {
        logger.error('The editor could not be loaded', { component: 'LazyTipTapEditor', error });
        if (!ignore) setFailed(true);
      }
    );
    return () => {
      ignore = true;
    };
  }, [Editor, attempt]);

  if (Editor) return <Editor {...props} />;
  return (
    <EditorPlaceholder
      failed={failed}
      onRetry={() => {
        setFailed(false);
        setAttempt((n) => n + 1);
      }}
    />
  );
}

interface EditorPlaceholderProps {
  failed: boolean;
  onRetry: () => void;
}

/** Stands where the editor will be, at its empty height, so nothing jumps. */
export function EditorPlaceholder({ failed, onRetry }: EditorPlaceholderProps) {
  return (
    <div className="flex min-h-[15.25rem] flex-col items-center justify-center gap-3 sm:min-h-[21.5rem] rounded-sm border border-line-2 bg-surface p-4 text-center">
      <p role="status" className="text-sm text-ink-2">
        {failed ? 'The editor could not be loaded. Check your connection.' : 'Loading editor…'}
      </p>
      {failed && (
        <Button type="button" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
