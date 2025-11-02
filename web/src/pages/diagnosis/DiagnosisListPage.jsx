/**
 * DiagnosisListPage Component
 *
 * Main page for viewing and managing saved diagnosis cards.
 * Features: filtering, search, sorting, pagination, favorites.
 */

import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import DiagnosisCard from '../../components/diagnosis/DiagnosisCard'
import { fetchDiagnosisCards } from '../../services/diagnosisService'
import logger from '../../utils/logger'

export default function DiagnosisListPage() {
  const [cards, setCards] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [treatmentFilter, setTreatmentFilter] = useState('')
  const [diseaseTypeFilter, setDiseaseTypeFilter] = useState('')
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false)
  const [sortOrder, setSortOrder] = useState('-saved_at')

  // Pagination
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalCount, setTotalCount] = useState(0)

  /**
   * Fetch diagnosis cards with current filters
   */
  const loadCards = async () => {
    try {
      setLoading(true)
      setError(null)

      const options = {
        search: searchQuery || undefined,
        treatment_status: treatmentFilter || undefined,
        disease_type: diseaseTypeFilter || undefined,
        is_favorite: showFavoritesOnly ? true : undefined,
        ordering: sortOrder,
        page: currentPage,
      }

      logger.info('[DiagnosisListPage] Loading cards with filters', options)

      const response = await fetchDiagnosisCards(options)

      setCards(response.results || [])
      setTotalCount(response.count || 0)
      setTotalPages(Math.ceil((response.count || 0) / 20)) // Backend uses 20 per page

      logger.info('[DiagnosisListPage] Loaded cards', {
        count: response.results?.length || 0,
        total: response.count || 0,
      })
    } catch (err) {
      logger.error('[DiagnosisListPage] Failed to load cards:', err)
      setError(err.message || 'Failed to load diagnosis cards')
    } finally {
      setLoading(false)
    }
  }

  /**
   * Load cards when filters or page changes
   */
  useEffect(() => {
    loadCards()
  }, [searchQuery, treatmentFilter, diseaseTypeFilter, showFavoritesOnly, sortOrder, currentPage])

  /**
   * Handle card update (favorite toggle)
   */
  const handleCardUpdate = (updatedCard) => {
    setCards(cards.map(card =>
      card.uuid === updatedCard.uuid ? updatedCard : card
    ))
  }

  /**
   * Handle card deletion
   */
  const handleCardDelete = (uuid) => {
    setCards(cards.filter(card => card.uuid !== uuid))
    setTotalCount(totalCount - 1)
  }

  /**
   * Clear all filters
   */
  const clearFilters = () => {
    setSearchQuery('')
    setTreatmentFilter('')
    setDiseaseTypeFilter('')
    setShowFavoritesOnly(false)
    setSortOrder('-saved_at')
    setCurrentPage(1)
  }

  /**
   * Check if any filters are active
   */
  const hasActiveFilters = searchQuery || treatmentFilter || diseaseTypeFilter || showFavoritesOnly || sortOrder !== '-saved_at'

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">My Diagnosis Cards</h1>
          <p className="mt-2 text-gray-600">
            Manage your saved plant health diagnoses and track treatment progress
          </p>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Search */}
            <div>
              <label htmlFor="search" className="block text-sm font-medium text-gray-700 mb-1">
                Search
              </label>
              <input
                type="text"
                id="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Plant or disease name..."
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-green-500 focus:border-green-500"
              />
            </div>

            {/* Treatment Status */}
            <div>
              <label htmlFor="treatment-status" className="block text-sm font-medium text-gray-700 mb-1">
                Treatment Status
              </label>
              <select
                id="treatment-status"
                value={treatmentFilter}
                onChange={(e) => setTreatmentFilter(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-green-500 focus:border-green-500"
              >
                <option value="">All Statuses</option>
                <option value="not_started">Not Started</option>
                <option value="in_progress">In Progress</option>
                <option value="successful">Successful</option>
                <option value="failed">Failed</option>
                <option value="monitoring">Monitoring</option>
              </select>
            </div>

            {/* Disease Type */}
            <div>
              <label htmlFor="disease-type" className="block text-sm font-medium text-gray-700 mb-1">
                Disease Type
              </label>
              <select
                id="disease-type"
                value={diseaseTypeFilter}
                onChange={(e) => setDiseaseTypeFilter(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-green-500 focus:border-green-500"
              >
                <option value="">All Types</option>
                <option value="fungal">Fungal</option>
                <option value="bacterial">Bacterial</option>
                <option value="viral">Viral</option>
                <option value="pest">Pest</option>
                <option value="nutrient">Nutrient</option>
                <option value="environmental">Environmental</option>
              </select>
            </div>

            {/* Sort Order */}
            <div>
              <label htmlFor="sort-order" className="block text-sm font-medium text-gray-700 mb-1">
                Sort By
              </label>
              <select
                id="sort-order"
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-green-500 focus:border-green-500"
              >
                <option value="-saved_at">Newest First</option>
                <option value="saved_at">Oldest First</option>
                <option value="disease_name">Disease Name (A-Z)</option>
                <option value="-disease_name">Disease Name (Z-A)</option>
                <option value="treatment_status">Treatment Status</option>
              </select>
            </div>
          </div>

          {/* Additional Filters */}
          <div className="mt-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
              {/* Favorites Toggle */}
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showFavoritesOnly}
                  onChange={(e) => setShowFavoritesOnly(e.target.checked)}
                  className="w-4 h-4 text-green-600 border-gray-300 rounded focus:ring-green-500"
                />
                <span className="text-sm text-gray-700">Favorites Only</span>
              </label>

              {/* Active Filters Count */}
              {hasActiveFilters && (
                <span className="text-sm text-gray-600">
                  {totalCount} {totalCount === 1 ? 'result' : 'results'}
                </span>
              )}
            </div>

            {/* Clear Filters */}
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="text-sm text-green-600 hover:text-green-700 font-medium"
              >
                Clear Filters
              </button>
            )}
          </div>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-green-500 border-t-transparent"></div>
            <p className="mt-4 text-gray-600">Loading diagnosis cards...</p>
          </div>
        )}

        {/* Error State */}
        {error && !loading && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
            <svg className="w-12 h-12 text-red-500 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 className="text-lg font-semibold text-red-900 mb-2">Failed to Load Diagnosis Cards</h3>
            <p className="text-red-700 mb-4">{error}</p>
            <button
              onClick={loadCards}
              className="inline-flex items-center px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
            >
              Try Again
            </button>
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && cards.length === 0 && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
            <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              {hasActiveFilters ? 'No Matching Diagnosis Cards' : 'No Diagnosis Cards Yet'}
            </h3>
            <p className="text-gray-600 mb-6">
              {hasActiveFilters
                ? 'Try adjusting your filters to see more results'
                : 'Start diagnosing your plants to save care instructions and track treatment progress'
              }
            </p>
            {hasActiveFilters ? (
              <button
                onClick={clearFilters}
                className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
              >
                Clear Filters
              </button>
            ) : (
              <Link
                to="/identify"
                className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
              >
                Diagnose a Plant
              </Link>
            )}
          </div>
        )}

        {/* Cards Grid */}
        {!loading && !error && cards.length > 0 && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
              {cards.map(card => (
                <DiagnosisCard
                  key={card.uuid}
                  card={card}
                  onUpdate={handleCardUpdate}
                  onDelete={handleCardDelete}
                />
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between bg-white rounded-lg shadow-sm border border-gray-200 px-6 py-4">
                <div className="text-sm text-gray-600">
                  Showing page {currentPage} of {totalPages} ({totalCount} total)
                </div>

                <div className="flex items-center gap-2">
                  {/* Previous Button */}
                  <button
                    onClick={() => setCurrentPage(currentPage - 1)}
                    disabled={currentPage === 1}
                    className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    Previous
                  </button>

                  {/* Page Numbers */}
                  <div className="hidden sm:flex items-center gap-1">
                    {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                      let pageNum
                      if (totalPages <= 5) {
                        pageNum = i + 1
                      } else if (currentPage <= 3) {
                        pageNum = i + 1
                      } else if (currentPage >= totalPages - 2) {
                        pageNum = totalPages - 4 + i
                      } else {
                        pageNum = currentPage - 2 + i
                      }

                      return (
                        <button
                          key={pageNum}
                          onClick={() => setCurrentPage(pageNum)}
                          className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                            currentPage === pageNum
                              ? 'bg-green-600 text-white'
                              : 'text-gray-700 hover:bg-gray-100'
                          }`}
                        >
                          {pageNum}
                        </button>
                      )
                    })}
                  </div>

                  {/* Next Button */}
                  <button
                    onClick={() => setCurrentPage(currentPage + 1)}
                    disabled={currentPage === totalPages}
                    className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
