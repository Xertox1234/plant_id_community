/**
 * MyPlantsPage Component
 *
 * Authenticated page listing the plants the user saved to their collection
 * after an identification ("Save to My Collection" on the identify flow).
 * Read surface for GET /api/v1/plant-identification/plants/ (todo 243).
 */

import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Leaf } from 'lucide-react';
import { plantIdService } from '../services/plantIdService';
import { logger } from '../utils/logger';
import type { UserPlant } from '../types/plantId';

const PAGE_SIZE = 20; // Backend DRF PageNumberPagination page size

export default function MyPlantsPage() {
  const [plants, setPlants] = useState<UserPlant[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalCount, setTotalCount] = useState<number>(0);

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  const loadPlants = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await plantIdService.getMyPlants(currentPage);

      setPlants(response.results || []);
      setTotalCount(response.count || 0);
    } catch (err) {
      logger.error('[MyPlantsPage] Failed to load plants:', err);
      setError(err instanceof Error ? err.message : 'Failed to load your plants');
    } finally {
      setLoading(false);
    }
  }, [currentPage]);

  useEffect(() => {
    loadPlants();
  }, [loadPlants]);

  return (
    <div className="min-h-screen bg-surface py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-ink">My Plants</h1>
          <p className="mt-2 text-ink-2">
            Plants you saved to your collection after identifying them
          </p>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div>
            <p className="mt-4 text-ink-2">Loading your plants...</p>
          </div>
        )}

        {/* Error State */}
        {error && !loading && (
          <div className="bg-error/10 border border-error/30 rounded-lg p-6 text-center">
            <h3 className="text-lg font-semibold text-error mb-2">Failed to Load Your Plants</h3>
            <p className="text-error mb-4">{error}</p>
            <button
              onClick={loadPlants}
              className="inline-flex items-center px-4 py-2 bg-error text-white rounded-md hover:bg-error/90 transition-colors"
            >
              Try Again
            </button>
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && plants.length === 0 && (
          <div className="bg-surface-2 rounded-lg shadow-sm border border-line p-12 text-center">
            <Leaf className="w-16 h-16 text-ink-3 mx-auto mb-4" aria-hidden="true" />
            <h3 className="text-lg font-semibold text-ink mb-2">No Plants Yet</h3>
            <p className="text-ink-2 mb-6">
              Identify a plant and save it to your collection to see it here
            </p>
            <Link
              to="/identify"
              className="inline-flex items-center px-4 py-2 bg-clay text-on-clay rounded-md hover:bg-clay/90 transition-colors"
            >
              Identify a Plant
            </Link>
          </div>
        )}

        {/* Plants Grid */}
        {!loading && !error && plants.length > 0 && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
              {plants.map((plant) => {
                const commonNames = plant.care_instructions_json?.common_names;
                const watering = plant.care_instructions_json?.watering;
                const confidence = plant.care_instructions_json?.confidence;

                return (
                  <article
                    key={plant.id}
                    className="bg-surface-2 rounded-lg shadow-sm border border-line overflow-hidden"
                  >
                    {/* Image or placeholder */}
                    {plant.image_thumbnail ? (
                      <img
                        src={plant.image_thumbnail}
                        alt={plant.display_name || plant.nickname || 'Saved plant'}
                        className="w-full h-40 object-cover"
                      />
                    ) : (
                      <div className="w-full h-40 bg-primary/10 flex items-center justify-center">
                        <Leaf className="w-12 h-12 text-primary" aria-hidden="true" />
                      </div>
                    )}

                    <div className="p-4">
                      <div className="flex items-start justify-between gap-2">
                        <h2 className="text-lg font-semibold text-ink">
                          {plant.display_name || plant.nickname || 'Unnamed plant'}
                        </h2>
                        {typeof confidence === 'number' && (
                          <span className="shrink-0 px-2 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium">
                            {Math.round(confidence * 100)}% match
                          </span>
                        )}
                      </div>

                      {Array.isArray(commonNames) && commonNames.length > 0 && (
                        <p className="mt-1 text-sm text-ink-2">{commonNames.join(', ')}</p>
                      )}

                      {watering && (
                        <p className="mt-3 text-sm text-ink-2 line-clamp-2">
                          <span className="font-medium text-ink">Watering:</span> {watering}
                        </p>
                      )}

                      {plant.notes && (
                        <p className="mt-2 text-sm text-ink-3 line-clamp-2">{plant.notes}</p>
                      )}

                      {plant.created_at && (
                        <p className="mt-3 text-xs text-ink-3">
                          Saved {new Date(plant.created_at).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between bg-surface-2 rounded-lg shadow-sm border border-line px-6 py-4">
                <div className="text-sm text-ink-2">
                  Showing page {currentPage} of {totalPages} ({totalCount} total)
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setCurrentPage(currentPage - 1)}
                    disabled={currentPage === 1}
                    className="px-4 py-2 border border-line-2 rounded-md text-sm font-medium text-ink-2 bg-surface-2 hover:bg-surface-3 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setCurrentPage(currentPage + 1)}
                    disabled={currentPage === totalPages}
                    className="px-4 py-2 border border-line-2 rounded-md text-sm font-medium text-ink-2 bg-surface-2 hover:bg-surface-3 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
  );
}
