import { useState } from 'react';
import type { DiagnosisBlock } from '@/types';
import { logger } from '@/utils/logger';

/**
 * Block type options
 */
const BLOCK_TYPES = [
  { value: 'heading', label: 'Heading', icon: 'H' },
  { value: 'paragraph', label: 'Paragraph', icon: 'P' },
  { value: 'treatment_step', label: 'Treatment Step', icon: '✓' },
  { value: 'symptom_check', label: 'Symptom Check', icon: '⚠' },
  { value: 'prevention_tip', label: 'Prevention Tip', icon: 'ℹ' },
  { value: 'list_block', label: 'List', icon: '•' },
]

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

function BlockEditor({ block, onChange, onDelete, onMoveUp, onMoveDown, isFirst, isLast }: BlockEditorProps) {
  const { type, value } = block

  const handleValueChange = (newValue) => {
    onChange({ ...block, value: newValue })
  }

  // Render editor based on block type
  switch (type) {
    case 'heading':
      return (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-gray-100 text-gray-700 font-bold">
                H
              </span>
              <span className="font-medium text-gray-900">Heading</span>
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
            value={(value as string) || ''}
            onChange={(e) => handleValueChange(e.target.value)}
            placeholder="Enter heading text..."
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-green-500 focus:border-green-500"
          />
        </div>
      )

    case 'paragraph':
      return (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-gray-100 text-gray-700 font-bold">
                P
              </span>
              <span className="font-medium text-gray-900">Paragraph</span>
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
            value={(value as string) || ''}
            onChange={(e) => handleValueChange(e.target.value)}
            placeholder="Enter paragraph text..."
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-green-500 focus:border-green-500"
          />
        </div>
      )

    case 'treatment_step': {
      const stepValue = value as { title?: string; description?: string; frequency?: string } | undefined;
      return (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-blue-100 text-blue-700 font-bold">
                ✓
              </span>
              <span className="font-medium text-blue-900">Treatment Step</span>
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
              <label className="block text-sm font-medium text-blue-900 mb-1">
                Step Title
              </label>
              <input
                type="text"
                value={stepValue?.title || ''}
                onChange={(e) => handleValueChange({ ...stepValue, title: e.target.value })}
                placeholder="e.g., Apply fungicide spray"
                className="w-full px-3 py-2 border border-blue-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-blue-900 mb-1">
                Description
              </label>
              <textarea
                value={stepValue?.description || ''}
                onChange={(e) => handleValueChange({ ...stepValue, description: e.target.value })}
                placeholder="Detailed instructions for this step..."
                rows={3}
                className="w-full px-3 py-2 border border-blue-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-blue-900 mb-1">
                Frequency (optional)
              </label>
              <input
                type="text"
                value={stepValue?.frequency || ''}
                onChange={(e) => handleValueChange({ ...stepValue, frequency: e.target.value })}
                placeholder="e.g., Every 7 days"
                className="w-full px-3 py-2 border border-blue-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>
        </div>
      )
    }

    case 'symptom_check': {
      const symptomValue = value as { symptom?: string; what_to_look_for?: string } | undefined;
      return (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-yellow-100 text-yellow-700 font-bold">
                ⚠
              </span>
              <span className="font-medium text-yellow-900">Symptom Check</span>
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
              <label className="block text-sm font-medium text-yellow-900 mb-1">
                Symptom Name
              </label>
              <input
                type="text"
                value={symptomValue?.symptom || ''}
                onChange={(e) => handleValueChange({ ...symptomValue, symptom: e.target.value })}
                placeholder="e.g., Leaf discoloration"
                className="w-full px-3 py-2 border border-yellow-300 rounded-md focus:ring-yellow-500 focus:border-yellow-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-yellow-900 mb-1">
                What to Look For
              </label>
              <textarea
                value={symptomValue?.what_to_look_for || ''}
                onChange={(e) => handleValueChange({ ...symptomValue, what_to_look_for: e.target.value })}
                placeholder="Description of what to monitor..."
                rows={3}
                className="w-full px-3 py-2 border border-yellow-300 rounded-md focus:ring-yellow-500 focus:border-yellow-500"
              />
            </div>
          </div>
        </div>
      )
    }

    case 'prevention_tip':
      return (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-green-100 text-green-700 font-bold">
                ℹ
              </span>
              <span className="font-medium text-green-900">Prevention Tip</span>
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
            value={(value as string) || ''}
            onChange={(e) => handleValueChange(e.target.value)}
            placeholder="Enter prevention tip..."
            rows={3}
            className="w-full px-3 py-2 border border-green-300 rounded-md focus:ring-green-500 focus:border-green-500"
          />
        </div>
      )

    case 'list_block': {
      const listValue = value as { items?: string[] } | undefined;
      return (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-gray-100 text-gray-700 font-bold">
                •
              </span>
              <span className="font-medium text-gray-900">List</span>
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
      )
    }

    default:
      return (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-700">Unknown block type: {type}</p>
        </div>
      )
  }
}

/**
 * List editor sub-component
 */
function ListEditor({ items, onChange }) {
  const addItem = () => {
    onChange([...items, ''])
  }

  const updateItem = (index, value) => {
    const newItems = [...items]
    newItems[index] = value
    onChange(newItems)
  }

  const deleteItem = (index) => {
    onChange(items.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-2">
      {items.map((item, index) => (
        <div key={index} className="flex items-start gap-2">
          <input
            type="text"
            value={item}
            onChange={(e) => updateItem(index, e.target.value)}
            placeholder={`Item ${index + 1}...`}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-green-500 focus:border-green-500"
          />
          <button
            onClick={() => deleteItem(index)}
            className="p-2 text-red-600 hover:bg-red-50 rounded-md transition-colors"
            aria-label="Delete item"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}
      <button
        onClick={addItem}
        className="text-sm text-green-600 hover:text-green-700 font-medium"
      >
        + Add Item
      </button>
    </div>
  )
}

/**
 * Block control buttons (move up/down, delete)
 */
function BlockControls({ onDelete, onMoveUp, onMoveDown, isFirst, isLast }) {
  return (
    <div className="flex items-center gap-1">
      <button
        onClick={onMoveUp}
        disabled={isFirst}
        className="p-1 text-gray-600 hover:bg-gray-100 rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        aria-label="Move up"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 15l7-7 7 7" />
        </svg>
      </button>
      <button
        onClick={onMoveDown}
        disabled={isLast}
        className="p-1 text-gray-600 hover:bg-gray-100 rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        aria-label="Move down"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      <button
        onClick={onDelete}
        className="p-1 text-red-600 hover:bg-red-50 rounded transition-colors ml-1"
        aria-label="Delete block"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
      </button>
    </div>
  )
}

/**
 * Main StreamFieldEditor Component
 */
export default function StreamFieldEditor({ value = [], onChange, readOnly = false }) {
  const [showBlockMenu, setShowBlockMenu] = useState(false)

  /**
   * Add new block
   */
  const addBlock = (blockType) => {
    let newBlock = { type: blockType, value: null }

    // Initialize value based on block type
    switch (blockType) {
      case 'heading':
      case 'paragraph':
      case 'prevention_tip':
        newBlock.value = ''
        break
      case 'treatment_step':
        newBlock.value = { title: '', description: '', frequency: '' }
        break
      case 'symptom_check':
        newBlock.value = { symptom: '', what_to_look_for: '' }
        break
      case 'list_block':
        newBlock.value = { items: [''] }
        break
      default:
        newBlock.value = ''
    }

    const newBlocks = [...value, newBlock]
    onChange(newBlocks)
    setShowBlockMenu(false)

    logger.info('[StreamFieldEditor] Added block', { type: blockType })
  }

  /**
   * Update block at index
   */
  const updateBlock = (index, updatedBlock) => {
    const newBlocks = [...value]
    newBlocks[index] = updatedBlock
    onChange(newBlocks)
  }

  /**
   * Delete block at index
   */
  const deleteBlock = (index) => {
    if (confirm('Are you sure you want to delete this block?')) {
      const newBlocks = value.filter((_, i) => i !== index)
      onChange(newBlocks)
      logger.info('[StreamFieldEditor] Deleted block', { index })
    }
  }

  /**
   * Move block up
   */
  const moveBlockUp = (index) => {
    if (index === 0) return
    const newBlocks = [...value]
    ;[newBlocks[index - 1], newBlocks[index]] = [newBlocks[index], newBlocks[index - 1]]
    onChange(newBlocks)
  }

  /**
   * Move block down
   */
  const moveBlockDown = (index) => {
    if (index === value.length - 1) return
    const newBlocks = [...value]
    ;[newBlocks[index], newBlocks[index + 1]] = [newBlocks[index + 1], newBlocks[index]]
    onChange(newBlocks)
  }

  if (readOnly) {
    return (
      <div className="space-y-4">
        {value.length === 0 ? (
          <p className="text-gray-500 italic">No care instructions</p>
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
    )
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
          className="w-full py-3 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-green-500 hover:text-green-600 transition-colors flex items-center justify-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
          </svg>
          Add Block
        </button>
      ) : (
        <div className="bg-white border border-gray-300 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-medium text-gray-900">Choose block type</h4>
            <button
              onClick={() => setShowBlockMenu(false)}
              className="text-gray-600 hover:text-gray-900"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {BLOCK_TYPES.map(blockType => (
              <button
                key={blockType.value}
                onClick={() => addBlock(blockType.value)}
                className="flex items-center gap-3 p-3 border border-gray-200 rounded-md hover:border-green-500 hover:bg-green-50 transition-colors text-left"
              >
                <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-gray-100 text-gray-700 font-bold">
                  {blockType.icon}
                </span>
                <span className="text-sm font-medium text-gray-900">{blockType.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Help text */}
      {value.length === 0 && (
        <p className="text-sm text-gray-500 text-center">
          Click "Add Block" to start creating care instructions
        </p>
      )}
    </div>
  )
}
