/**
 * Diagnosis StreamField block renderers
 *
 * Single source of truth for rendering the diagnosis `care_instructions`
 * StreamField. Each block type maps to one small renderer component in
 * `BLOCK_RENDERERS`; the exhaustive `Record<DiagnosisBlock['type'], …>` makes
 * adding a new block type a single edit (TypeScript fails the build until the
 * new type has a registered renderer). `care_instructions` are produced by the
 * backend (AI-generated) and rendered read-only — there is no editor.
 */

import type { FC } from 'react';
import type { DiagnosisBlock } from '@/types';
import { logger } from '../../utils/logger';

/** One renderer per block type, narrowed to that type's `value` shape. */
type BlockRendererMap = {
  [K in DiagnosisBlock['type']]: FC<{ block: Extract<DiagnosisBlock, { type: K }> }>;
};

const HeadingBlock: BlockRendererMap['heading'] = ({ block }) => (
  <h3 className="text-xl font-semibold text-ink mt-6 mb-3">{block.value}</h3>
);

const ParagraphBlock: BlockRendererMap['paragraph'] = ({ block }) => (
  <p className="text-ink-2 mb-4 leading-relaxed">{block.value}</p>
);

const TreatmentStepBlock: BlockRendererMap['treatment_step'] = ({ block }) => {
  const typedValue = block.value;
  return (
    <div className="bg-sky/10 border-l-4 border-sky p-4 mb-4">
      <div className="flex items-start">
        <svg
          className="w-5 h-5 text-sky mt-0.5 mr-3 flex-shrink-0"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
            clipRule="evenodd"
          />
        </svg>
        <div className="flex-1">
          <h4 className="font-semibold text-sky mb-1">{typedValue.title}</h4>
          <p className="text-sky">{typedValue.description}</p>
          {typedValue.frequency && (
            <p className="text-sm text-sky mt-2">Frequency: {typedValue.frequency}</p>
          )}
        </div>
      </div>
    </div>
  );
};

const SymptomCheckBlock: BlockRendererMap['symptom_check'] = ({ block }) => {
  const typedValue = block.value;
  return (
    <div className="bg-warn/10 border-l-4 border-warn p-4 mb-4">
      <div className="flex items-start">
        <svg
          className="w-5 h-5 text-warn mt-0.5 mr-3 flex-shrink-0"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            fillRule="evenodd"
            d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
            clipRule="evenodd"
          />
        </svg>
        <div className="flex-1">
          <h4 className="font-semibold text-warn mb-1">Symptom Check: {typedValue.symptom}</h4>
          <p className="text-warn">{typedValue.what_to_look_for}</p>
        </div>
      </div>
    </div>
  );
};

const PreventionTipBlock: BlockRendererMap['prevention_tip'] = ({ block }) => (
  <div className="bg-leaf/10 border-l-4 border-leaf p-4 mb-4">
    <div className="flex items-start">
      <svg
        className="w-5 h-5 text-leaf mt-0.5 mr-3 flex-shrink-0"
        fill="currentColor"
        viewBox="0 0 20 20"
      >
        <path
          fillRule="evenodd"
          d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
          clipRule="evenodd"
        />
      </svg>
      <div className="flex-1">
        <h4 className="font-semibold text-leaf mb-1">Prevention Tip</h4>
        <p className="text-leaf">{block.value}</p>
      </div>
    </div>
  </div>
);

const ListBlock: BlockRendererMap['list_block'] = ({ block }) => (
  <ul className="list-disc list-inside space-y-2 mb-4 text-ink-2">
    {block.value.items?.map((item, index) => (
      <li key={index} className="ml-4">
        {item}
      </li>
    ))}
  </ul>
);

const ImageBlock: BlockRendererMap['image'] = ({ block }) => {
  const typedValue = block.value;
  return (
    <div className="mb-6">
      <img
        src={typedValue.url}
        alt={typedValue.alt_text || 'Care instruction image'}
        className="rounded-lg w-full max-w-2xl mx-auto"
      />
      {typedValue.caption && (
        <p className="text-sm text-ink-2 text-center mt-2 italic">{typedValue.caption}</p>
      )}
    </div>
  );
};

/**
 * Block-type registry. Exhaustive over `DiagnosisBlock['type']` — adding a new
 * block type to the union makes this object fail to type-check until its
 * renderer is registered here.
 */
const BLOCK_RENDERERS: BlockRendererMap = {
  heading: HeadingBlock,
  paragraph: ParagraphBlock,
  treatment_step: TreatmentStepBlock,
  symptom_check: SymptomCheckBlock,
  prevention_tip: PreventionTipBlock,
  list_block: ListBlock,
  image: ImageBlock,
};

/**
 * Renders a single diagnosis StreamField block by dispatching to the registry.
 * Unknown block types (unexpected backend data) log a warning and render nothing.
 */
export function StreamFieldBlock({ block }: { block: DiagnosisBlock }) {
  // `Object.hasOwn` (not `BLOCK_RENDERERS[block.type]` truthiness) guards the
  // lookup: a plain object literal inherits `Object.prototype` members, so a
  // backend block type of 'constructor'/'toString'/etc. would otherwise resolve
  // a truthy inherited function and render garbage. This intentionally defends
  // against block types the backend may send that are not yet in the
  // DiagnosisBlock union — don't drop it because the registry is statically
  // exhaustive.
  if (!Object.hasOwn(BLOCK_RENDERERS, block.type)) {
    logger.warn('[StreamFieldBlock] Unknown block type', {
      component: 'StreamFieldBlock',
      context: { block },
    });
    return null;
  }

  // The cast widens the per-type renderer to the union; dispatch is keyed on
  // `block.type`, so the runtime block always matches its renderer's narrowed type.
  const Renderer = BLOCK_RENDERERS[block.type] as FC<{ block: DiagnosisBlock }>;
  return <Renderer block={block} />;
}
