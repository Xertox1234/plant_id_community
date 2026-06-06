import { useState } from 'react';
import type { DiagnosisBlock } from '@/types';
import { logger } from '@/utils/logger';

/**
 * Block types that can be created from the editor menu. The 'image' variant of
 * DiagnosisBlock is render-only (produced by the backend), so it is excluded.
 */
type EditableBlockType = Exclude<DiagnosisBlock['type'], 'image'>;

interface BlockTypeOption {
  value: EditableBlockType;
  label: string;
  icon: string;
}

/**
 * Block type options
 */
const BLOCK_TYPES: BlockTypeOption[] = [
  { value: 'heading', label: 'Heading', icon: 'H' },
  { value: 'paragraph', label: 'Paragraph', icon: 'P' },
  { value: 'treatment_step', label: 'Treatment Step', icon: '✓' },
  { value: 'symptom_check', label: 'Symptom Check', icon: '⚠' },
  { value: 'prevention_tip', label: 'Prevention Tip', icon: 'ℹ' },
  { value: 'list_block', label: 'List', icon: '•' },
];

/**
 * Individual block editor based on type
 */
interface BlockEditorProps {
  block: DiagnosisBlock;
  onChange: (block: DiagnosisBlock) => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  isFirst: boolean;
  isLast: boolean;
}

function BlockEditor({
  block,
  onChange,
  onDelete,
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
}: BlockEditorProps) {
  const { type } = block;

  const handleValueChange = (newValue: DiagnosisBlock['value']) => {
    onChange({ ...block, value: newValue } as DiagnosisBlock);
  };

  // Render editor based on block type
  switch (block.type) {
    case 'heading':
      return (
        <div className="bg-surface-2 border border-line rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-surface-3 text-ink-2 font-bold">
                H
              </span>
              <span className="font-medium text-ink">Heading</span>
            </div>
            <BlockControls
              onDelete={onDelete}
              onMoveUp={onMoveUp}
              onMoveDown={onMoveDown}
              isFirst={isFirst}
              isLast={isLast}
            />
          </div>
          <input
            type="text"
            value={block.value || ''}
            onChange={(e) => handleValueChange(e.target.value)}
            placeholder="Enter heading text..."
            className="w-full px-3 py-2 border border-line-2 rounded-md bg-surface-2 text-ink focus:ring-primary focus:border-primary"
          />
        </div>
      );

    case 'paragraph':
      return (
        <div className="bg-surface-2 border border-line rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-surface-3 text-ink-2 font-bold">
                P
              </span>
              <span className="font-medium text-ink">Paragraph</span>
            </div>
            <BlockControls
              onDelete={onDelete}
              onMoveUp={onMoveUp}
              onMoveDown={onMoveDown}
              isFirst={isFirst}
              isLast={isLast}
            />
          </div>
          <textarea
            value={block.value || ''}
            onChange={(e) => handleValueChange(e.target.value)}
            placeholder="Enter paragraph text..."
            rows={3}
            className="w-full px-3 py-2 border border-line-2 rounded-md bg-surface-2 text-ink focus:ring-primary focus:border-primary"
          />
        </div>
      );

    case 'treatment_step': {
      const stepValue = block.value;
      return (
        <div className="bg-sky/10 border border-sky/30 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-sky/20 text-ink font-bold">
                ✓
              </span>
              <span className="font-medium text-sky">Treatment Step</span>
            </div>
            <BlockControls
              onDelete={onDelete}
              onMoveUp={onMoveUp}
              onMoveDown={onMoveDown}
              isFirst={isFirst}
              isLast={isLast}
            />
          </div>
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-sky mb-1">Step Title</label>
              <input
                type="text"
                value={stepValue?.title || ''}
                onChange={(e) => handleValueChange({ ...stepValue, title: e.target.value })}
                placeholder="e.g., Apply fungicide spray"
                className="w-full px-3 py-2 border border-sky/30 rounded-md bg-surface-2 text-ink focus:ring-sky focus:border-sky"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-sky mb-1">Description</label>
              <textarea
                value={stepValue?.description || ''}
                onChange={(e) => handleValueChange({ ...stepValue, description: e.target.value })}
                placeholder="Detailed instructions for this step..."
                rows={3}
                className="w-full px-3 py-2 border border-sky/30 rounded-md bg-surface-2 text-ink focus:ring-sky focus:border-sky"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-sky mb-1">
                Frequency (optional)
              </label>
              <input
                type="text"
                value={stepValue?.frequency || ''}
                onChange={(e) => handleValueChange({ ...stepValue, frequency: e.target.value })}
                placeholder="e.g., Every 7 days"
                className="w-full px-3 py-2 border border-sky/30 rounded-md bg-surface-2 text-ink focus:ring-sky focus:border-sky"
              />
            </div>
          </div>
        </div>
      );
    }

    case 'symptom_check': {
      const symptomValue = block.value;
      return (
        <div className="bg-warn/10 border border-warn/30 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-warn/20 text-ink font-bold">
                ⚠
              </span>
              <span className="font-medium text-warn">Symptom Check</span>
            </div>
            <BlockControls
              onDelete={onDelete}
              onMoveUp={onMoveUp}
              onMoveDown={onMoveDown}
              isFirst={isFirst}
              isLast={isLast}
            />
          </div>
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-warn mb-1">Symptom Name</label>
              <input
                type="text"
                value={symptomValue?.symptom || ''}
                onChange={(e) => handleValueChange({ ...symptomValue, symptom: e.target.value })}
                placeholder="e.g., Leaf discoloration"
                className="w-full px-3 py-2 border border-warn/30 rounded-md bg-surface-2 text-ink focus:ring-warn focus:border-warn"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-warn mb-1">What to Look For</label>
              <textarea
                value={symptomValue?.what_to_look_for || ''}
                onChange={(e) =>
                  handleValueChange({ ...symptomValue, what_to_look_for: e.target.value })
                }
                placeholder="Description of what to monitor..."
                rows={3}
                className="w-full px-3 py-2 border border-warn/30 rounded-md bg-surface-2 text-ink focus:ring-warn focus:border-warn"
              />
            </div>
          </div>
        </div>
      );
    }

    case 'prevention_tip':
      return (
        <div className="bg-leaf/10 border border-leaf/30 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-leaf/20 text-ink font-bold">
                ℹ
              </span>
              <span className="font-medium text-leaf">Prevention Tip</span>
            </div>
            <BlockControls
              onDelete={onDelete}
              onMoveUp={onMoveUp}
              onMoveDown={onMoveDown}
              isFirst={isFirst}
              isLast={isLast}
            />
          </div>
          <textarea
            value={block.value || ''}
            onChange={(e) => handleValueChange(e.target.value)}
            placeholder="Enter prevention tip..."
            rows={3}
            className="w-full px-3 py-2 border border-leaf/30 rounded-md bg-surface-2 text-ink focus:ring-leaf focus:border-leaf"
          />
        </div>
      );

    case 'list_block': {
      const listValue = block.value;
      return (
        <div className="bg-surface-2 border border-line rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-surface-3 text-ink-2 font-bold">
                •
              </span>
              <span className="font-medium text-ink">List</span>
            </div>
            <BlockControls
              onDelete={onDelete}
              onMoveUp={onMoveUp}
              onMoveDown={onMoveDown}
              isFirst={isFirst}
              isLast={isLast}
            />
          </div>
          <ListEditor
            items={listValue?.items || []}
            onChange={(newItems) => handleValueChange({ items: newItems })}
          />
        </div>
      );
    }

    default:
      return (
        <div className="bg-error/10 border border-error/30 rounded-lg p-4">
          <p className="text-error">Unknown block type: {type}</p>
        </div>
      );
  }
}

/**
 * List editor sub-component
 */
interface ListEditorProps {
  items: string[];
  onChange: (items: string[]) => void;
}

function ListEditor({ items, onChange }: ListEditorProps) {
  const addItem = () => {
    onChange([...items, '']);
  };

  const updateItem = (index: number, value: string) => {
    const newItems = [...items];
    newItems[index] = value;
    onChange(newItems);
  };

  const deleteItem = (index: number) => {
    onChange(items.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-2">
      {items.map((item, index) => (
        <div key={index} className="flex items-start gap-2">
          <input
            type="text"
            value={item}
            onChange={(e) => updateItem(index, e.target.value)}
            placeholder={`Item ${index + 1}...`}
            className="flex-1 px-3 py-2 border border-line-2 rounded-md bg-surface-2 text-ink focus:ring-primary focus:border-primary"
          />
          <button
            onClick={() => deleteItem(index)}
            className="p-2 text-error hover:bg-error/10 rounded-md transition-colors"
            aria-label="Delete item"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      ))}
      <button onClick={addItem} className="text-sm text-primary hover:text-primary/80 font-medium">
        + Add Item
      </button>
    </div>
  );
}

/**
 * Block control buttons (move up/down, delete)
 */
interface BlockControlsProps {
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  isFirst: boolean;
  isLast: boolean;
}

function BlockControls({ onDelete, onMoveUp, onMoveDown, isFirst, isLast }: BlockControlsProps) {
  return (
    <div className="flex items-center gap-1">
      <button
        onClick={onMoveUp}
        disabled={isFirst}
        className="p-1 text-ink-2 hover:bg-surface-3 rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        aria-label="Move up"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 15l7-7 7 7" />
        </svg>
      </button>
      <button
        onClick={onMoveDown}
        disabled={isLast}
        className="p-1 text-ink-2 hover:bg-surface-3 rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        aria-label="Move down"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      <button
        onClick={onDelete}
        className="p-1 text-error hover:bg-error/10 rounded transition-colors ml-1"
        aria-label="Delete block"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
          />
        </svg>
      </button>
    </div>
  );
}

/**
 * Main StreamFieldEditor Component
 */
interface StreamFieldEditorProps {
  value?: DiagnosisBlock[];
  onChange: (blocks: DiagnosisBlock[]) => void;
  readOnly?: boolean;
}

export default function StreamFieldEditor({
  value = [],
  onChange,
  readOnly = false,
}: StreamFieldEditorProps) {
  const [showBlockMenu, setShowBlockMenu] = useState(false);

  /**
   * Add new block
   */
  const addBlock = (blockType: EditableBlockType) => {
    let newBlock: DiagnosisBlock;

    // Initialize value based on block type
    switch (blockType) {
      case 'heading':
      case 'paragraph':
      case 'prevention_tip':
        newBlock = { type: blockType, value: '' };
        break;
      case 'treatment_step':
        newBlock = { type: blockType, value: { title: '', description: '', frequency: '' } };
        break;
      case 'symptom_check':
        newBlock = { type: blockType, value: { symptom: '', what_to_look_for: '' } };
        break;
      case 'list_block':
        newBlock = { type: blockType, value: { items: [''] } };
        break;
    }

    const newBlocks = [...value, newBlock];
    onChange(newBlocks);
    setShowBlockMenu(false);

    logger.info('[StreamFieldEditor] Added block', { type: blockType });
  };

  /**
   * Update block at index
   */
  const updateBlock = (index: number, updatedBlock: DiagnosisBlock) => {
    const newBlocks = [...value];
    newBlocks[index] = updatedBlock;
    onChange(newBlocks);
  };

  /**
   * Delete block at index
   */
  const deleteBlock = (index: number) => {
    if (confirm('Are you sure you want to delete this block?')) {
      const newBlocks = value.filter((_, i) => i !== index);
      onChange(newBlocks);
      logger.info('[StreamFieldEditor] Deleted block', { index });
    }
  };

  /**
   * Move block up
   */
  const moveBlockUp = (index: number) => {
    if (index === 0) return;
    const newBlocks = [...value];
    [newBlocks[index - 1], newBlocks[index]] = [newBlocks[index], newBlocks[index - 1]];
    onChange(newBlocks);
  };

  /**
   * Move block down
   */
  const moveBlockDown = (index: number) => {
    if (index === value.length - 1) return;
    const newBlocks = [...value];
    [newBlocks[index], newBlocks[index + 1]] = [newBlocks[index + 1], newBlocks[index]];
    onChange(newBlocks);
  };

  if (readOnly) {
    return (
      <div className="space-y-4">
        {value.length === 0 ? (
          <p className="text-ink-3 italic">No care instructions</p>
        ) : (
          value.map((block, index) => (
            <BlockEditor
              key={index}
              block={block}
              onChange={() => {}}
              onDelete={() => {}}
              onMoveUp={() => {}}
              onMoveDown={() => {}}
              isFirst={true}
              isLast={true}
            />
          ))
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Existing blocks */}
      {value.map((block, index) => (
        <BlockEditor
          key={index}
          block={block}
          onChange={(updatedBlock) => updateBlock(index, updatedBlock)}
          onDelete={() => deleteBlock(index)}
          onMoveUp={() => moveBlockUp(index)}
          onMoveDown={() => moveBlockDown(index)}
          isFirst={index === 0}
          isLast={index === value.length - 1}
        />
      ))}

      {/* Add block button */}
      {!showBlockMenu ? (
        <button
          onClick={() => setShowBlockMenu(true)}
          className="w-full py-3 border-2 border-dashed border-line-2 rounded-lg text-ink-2 hover:border-primary hover:text-primary transition-colors flex items-center justify-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
          </svg>
          Add Block
        </button>
      ) : (
        <div className="bg-surface-2 border border-line-2 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-medium text-ink">Choose block type</h4>
            <button onClick={() => setShowBlockMenu(false)} className="text-ink-2 hover:text-ink">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {BLOCK_TYPES.map((blockType) => (
              <button
                key={blockType.value}
                onClick={() => addBlock(blockType.value)}
                className="flex items-center gap-3 p-3 border border-line rounded-md hover:border-primary hover:bg-primary/10 transition-colors text-left"
              >
                <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-surface-3 text-ink-2 font-bold">
                  {blockType.icon}
                </span>
                <span className="text-sm font-medium text-ink">{blockType.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Help text */}
      {value.length === 0 && (
        <p className="text-sm text-ink-3 text-center">
          Click "Add Block" to start creating care instructions
        </p>
      )}
    </div>
  );
}
